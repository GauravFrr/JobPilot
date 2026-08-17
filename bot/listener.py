import asyncio
import json
import logging
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from db import AsyncSessionLocal, DBSetting, DBJobRaw, DBJobScore, DBApplication, DBContact
from config import settings

logger = logging.getLogger("bot.listener")

async def get_paired_chat_id() -> int:
    """Queries Postgres settings table for paired telegram_chat_id."""
    async with AsyncSessionLocal() as session:
        stmt = select(DBSetting).where(DBSetting.key == "telegram_chat_id")
        result = await session.execute(stmt)
        db_setting = result.scalars().first()
        if db_setting and db_setting.value:
            return db_setting.value.get("chat_id")
    return None

async def start_event_listener(bot: Bot):
    """
    Listens to 'jobpilot:events' on Redis pub/sub and sends push notifications
    to the paired Telegram Chat ID dynamically.
    """
    import redis.asyncio as aioredis
    
    logger.info("Initializing Redis Pub/Sub listener...")
    redis_client = aioredis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("jobpilot:events")
    
    logger.info("Redis Pub/Sub listener started. Monitoring channel 'jobpilot:events'...")
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
                
            try:
                data = json.loads(message["data"])
                event_type = data.get("event_type")
                job_id = data.get("job_id")
                payload = data.get("payload", {})
                
                logger.info(f"Received Redis event: {event_type} for job {job_id}")
                
                # Fetch paired Telegram chat ID
                chat_id = await get_paired_chat_id()
                if not chat_id:
                    logger.warning("No paired Telegram chat ID found in settings database. Skipping notification.")
                    continue
                
                # Format and dispatch notification
                if event_type == "job.ready_to_apply":
                    app_id = payload.get("application_id")
                    
                    # Fetch job details and contacts
                    async with AsyncSessionLocal() as session:
                        stmt = (
                            select(DBJobRaw, DBJobScore)
                            .outerjoin(DBJobScore, DBJobRaw.id == DBJobScore.job_id)
                            .where(DBJobRaw.id == job_id)
                        )
                        res = await session.execute(stmt)
                        row = res.first()
                        
                        # Fetch contacts
                        c_stmt = select(DBContact).where(DBContact.job_id == job_id)
                        c_res = await session.execute(c_stmt)
                        contacts = c_res.scalars().all()
                        
                    if not row:
                        logger.error(f"Job {job_id} not found in DB. Skipping notification.")
                        continue
                        
                    job, score = row
                    score_val = score.final_score if score else 0.0
                    
                    text = (
                        f"🆕 **New Job Ready to Apply!**\n\n"
                        f"🏢 **{job.company}**\n"
                        f"💼 **{job.title}**\n"
                        f"🎯 Match Score: `{score_val:.1f}%` ({job.source})\n"
                    )
                    
                    # Include contact info if found
                    if contacts:
                        c = contacts[0]
                        text += (
                            f"\n👤 **Contact:** {c.name} ({c.title})\n"
                            f"📧 Email: `{c.email}`\n"
                            f"🔗 [LinkedIn Profile]({c.linkedin_url})\n"
                        )
                    
                    # Keyboard
                    builder = InlineKeyboardBuilder()
                    builder.button(text="✅ Apply", callback_data=f"apply:{app_id}")
                    builder.button(text="🚫 Pass", callback_data=f"pass:{app_id}")
                    builder.button(text="🌐 View", url=f"http://127.0.0.1:3000/applications/{app_id}")
                    if contacts:
                        builder.button(text="✉️ Draft Message", callback_data=f"draft:{job_id}")
                    builder.adjust(2)
                    
                    await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")
                    
                elif event_type == "contact.found":
                    contact_id = payload.get("contact_id")
                    name = payload.get("name")
                    title = payload.get("title")
                    email = payload.get("email")
                    linkedin_url = payload.get("linkedin_url")
                    
                    async with AsyncSessionLocal() as session:
                        stmt = select(DBJobRaw).where(DBJobRaw.id == job_id)
                        res = await session.execute(stmt)
                        job = res.scalars().first()
                        
                        c_stmt = select(DBContact).where(DBContact.id == contact_id)
                        c_res = await session.execute(c_stmt)
                        db_contact = c_res.scalars().first()
                        
                    if job and db_contact:
                        evidence_list = db_contact.evidence or []
                        evidence_str = ""
                        for ev in evidence_list[:2]:
                            field = ev.get("field", "info")
                            snippet = ev.get("snippet", "")
                            evidence_str += f"• *{field.title()}*: \"{snippet[:85]}...\"\n"
                            
                        text = (
                            f"👤 **Recruiter Contact Found! (Post-hoc)**\n\n"
                            f"🏢 Company: **{job.company}**\n"
                            f"💼 Role: **{job.title}**\n\n"
                            f"🗣️ **{name}**\n"
                            f"📌 {title}\n"
                            f"📧 Email: `{email}`\n"
                            f"🔗 [LinkedIn Profile]({linkedin_url})\n\n"
                            f"🔍 **Evidence Trace:**\n{evidence_str}"
                        )
                        
                        builder = InlineKeyboardBuilder()
                        builder.button(text="✉️ Draft Message", callback_data=f"draft:{job_id}")
                        builder.adjust(1)
                        
                        await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")
                        
                elif event_type == "job.applied":
                    app_id = payload.get("application_id")
                    async with AsyncSessionLocal() as session:
                        stmt = select(DBJobRaw).where(DBJobRaw.id == job_id)
                        res = await session.execute(stmt)
                        job = res.scalars().first()
                    
                    if job:
                        text = (
                            f"✅ **Application Submitted!**\n\n"
                            f"🏢 Company: **{job.company}**\n"
                            f"💼 Role: **{job.title}**\n"
                        )
                        await bot.send_message(chat_id, text)
                        
                elif event_type == "job.application_failed":
                    app_id = payload.get("application_id")
                    error_reason = payload.get("error", "Unknown error")
                    
                    async with AsyncSessionLocal() as session:
                        stmt = select(DBJobRaw).where(DBJobRaw.id == job_id)
                        res = await session.execute(stmt)
                        job = res.scalars().first()
                        
                    if job:
                        text = (
                            f"❌ **Application Submission Failed!**\n\n"
                            f"🏢 Company: **{job.company}**\n"
                            f"💼 Role: **{job.title}**\n"
                            f"⚠️ Error: `{error_reason}`"
                        )
                        # Add Retry / Mark Manual buttons
                        builder = InlineKeyboardBuilder()
                        builder.button(text="🔄 Retry", callback_data=f"apply:{app_id}")
                        builder.button(text="🌐 View in Dashboard", url=f"http://127.0.0.1:3000/applications/{app_id}")
                        builder.adjust(1)
                        await bot.send_message(chat_id, text, reply_markup=builder.as_markup())
                        
                elif event_type == "job.captcha_detected":
                    app_id = payload.get("application_id")
                    
                    async with AsyncSessionLocal() as session:
                        stmt = select(DBJobRaw).where(DBJobRaw.id == job_id)
                        res = await session.execute(stmt)
                        job = res.scalars().first()
                        
                    if job:
                        text = (
                            f"⚠️ **CAPTCHA Block Encountered!**\n\n"
                            f"LinkedIn has prompted for verification/CAPTCHA during Easy Apply pre-fill or submission for:\n"
                            f"🏢 **{job.company}**\n"
                            f"💼 **{job.title}**\n\n"
                            f"Please open headed Chromium or view in your dashboard to manually verify and complete the application."
                        )
                        builder = InlineKeyboardBuilder()
                        builder.button(text="🌐 View Dashboard", url=f"http://127.0.0.1:3000/applications/{app_id}")
                        builder.adjust(1)
                        await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")
                        
                elif event_type == "weekly_summary":
                    discovered = payload.get("discovered", 0)
                    matched = payload.get("matched", 0)
                    ready = payload.get("ready", 0)
                    applied = payload.get("applied", 0)
                    contacts = payload.get("contacts", 0)
                    
                    text = (
                        f"📊 **Weekly Activity Summary**\n\n"
                        f"🔍 Jobs Discovered: `{discovered}`\n"
                        f"🎯 Jobs Matched: `{matched}`\n"
                        f"⏳ Ready to Apply: `{ready}`\n"
                        f"✅ Applications Submitted: `{applied}`\n"
                        f"👤 Recruiter Contacts Found: `{contacts}`\n\n"
                        f"🔗 View details on the [Dashboard](http://127.0.0.1:3000/)"
                    )
                    await bot.send_message(chat_id, text, parse_mode="Markdown")
                    
                elif event_type == "general.notification":
                    msg_text = payload.get("text", "")
                    if msg_text:
                        await bot.send_message(chat_id, msg_text, parse_mode="Markdown")
                        
                        
            except Exception as ex:
                logger.error(f"Error handling pubsub message payload: {str(ex)}")
                
    except asyncio.CancelledError:
        logger.info("Redis Pub/Sub listener task cancelled.")
    finally:
        await pubsub.unsubscribe("jobpilot:events")
        await redis_client.close()
