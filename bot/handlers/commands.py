import datetime
import logging
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, text
import redis.asyncio as aioredis

from config import settings
from db import AsyncSessionLocal, DBSetting, DBApplication, DBJobRaw, DBJobScore

logger = logging.getLogger("bot.handlers.commands")
router = Router()

async def check_auth(chat_id: int) -> bool:
    """
    Checks if the given Telegram Chat ID is paired in the settings database table.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(DBSetting).where(DBSetting.key == "telegram_chat_id")
        result = await session.execute(stmt)
        db_setting = result.scalars().first()
        return db_setting is not None and db_setting.value.get("chat_id") == chat_id

@router.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    token = command.args
    chat_id = message.chat.id
    
    if token:
        redis_client = aioredis.from_url(settings.redis_url)
        redis_key = f"jobpilot:telegram:pairing_token:{token}"
        exists = await redis_client.get(redis_key)
        
        if exists:
            # Pair successful! Write chat ID to settings table in Postgres
            async with AsyncSessionLocal() as session:
                stmt = select(DBSetting).where(DBSetting.key == "telegram_chat_id")
                result = await session.execute(stmt)
                db_setting = result.scalars().first()
                
                if db_setting:
                    db_setting.value = {"chat_id": chat_id}
                else:
                    db_setting = DBSetting(key="telegram_chat_id", value={"chat_id": chat_id})
                    session.add(db_setting)
                await session.commit()
            
            # Delete one-time token from Redis
            await redis_client.delete(redis_key)
            await redis_client.close()
            
            await message.reply(
                "✅ **JobPilot Paired Successfully!**\n\n"
                f"Your Telegram Chat ID (`{chat_id}`) has been linked. You will now receive real-time notifications for jobs that are ready to apply."
            )
            logger.info(f"Successfully paired chat ID {chat_id}")
        else:
            await redis_client.close()
            await message.reply(
                "❌ **Invalid or Expired Pairing Token**\n\n"
                "Please generate a new token from your settings dashboard and try again."
            )
    else:
        # Check if already paired
        if await check_auth(chat_id):
            await message.reply(
                "🤖 **JobPilot Bot is Active**\n\n"
                "Your chat is already paired. Use `/pending` to view jobs in the queue or `/settings` to access settings."
            )
        else:
            await message.reply(
                "👋 **Welcome to JobPilot**\n\n"
                "To link this Telegram account with your system, please generate a pairing token from the settings dashboard and use:\n"
                "`/start <token>`"
            )

@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    if not await check_auth(message.chat.id):
        return
    await message.reply(
        "⚙️ **JobPilot Settings**\n\n"
        "Click the link below to access your JobPilot Settings dashboard:\n"
        "http://localhost:3000/settings#telegram"
    )

@router.message(Command("pending"))
async def cmd_pending(message: types.Message):
    if not await check_auth(message.chat.id):
        return
        
    async with AsyncSessionLocal() as session:
        stmt = (
            select(DBApplication, DBJobRaw, DBJobScore)
            .join(DBJobRaw, DBApplication.job_id == DBJobRaw.id)
            .outerjoin(DBJobScore, DBApplication.job_id == DBJobScore.job_id)
            .where(DBApplication.status == "ready_to_apply")
            .order_by(DBApplication.created_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()
        
    if not rows:
        await message.reply("📭 **Your pending queue is empty!**\n\nNo jobs are currently waiting for your decision.")
        return
        
    await message.reply(f"📋 **Pending Applications Queue ({len(rows)} jobs):**")
    
    for app, job, score in rows:
        score_val = score.final_score if score else 0.0
        text_content = (
            f"🏢 **{job.company}**\n"
            f"💼 **{job.title}**\n"
            f"🎯 Match Score: `{score_val:.1f}%` ({job.source})\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Apply", callback_data=f"apply:{app.id}")
        builder.button(text="🚫 Pass", callback_data=f"pass:{app.id}")
        builder.button(text="🌐 View", url=f"http://localhost:3000/applications/{app.id}")
        builder.adjust(2)
        
        await message.answer(text_content, reply_markup=builder.as_markup())

@router.message(Command("today"))
async def cmd_today(message: types.Message):
    if not await check_auth(message.chat.id):
        return
        
    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    
    async with AsyncSessionLocal() as session:
        # Total discovered today
        stmt_disc = await session.execute(
            text("SELECT COUNT(*) FROM jobs_raw WHERE discovered_at >= :t"), {"t": today_start}
        )
        disc_count = stmt_disc.scalar() or 0
        
        # Total matched today
        stmt_matched = await session.execute(
            text("SELECT COUNT(*) FROM job_scores WHERE scored_at >= :t"), {"t": today_start}
        )
        matched_count = stmt_matched.scalar() or 0
        
        # Queue count
        stmt_pending = await session.execute(
            text("SELECT COUNT(*) FROM applications WHERE status = 'ready_to_apply'")
        )
        pending_count = stmt_pending.scalar() or 0
        
        # Applied today
        stmt_applied = await session.execute(
            text("SELECT COUNT(*) FROM applications WHERE status = 'applied' AND applied_at >= :t"), {"t": today_start}
        )
        applied_count = stmt_applied.scalar() or 0
        
    text_msg = (
        f"📊 **Activity for Today ({datetime.date.today().strftime('%Y-%b-%d')}):**\n\n"
        f"🔍 Discovered: `{disc_count}` jobs\n"
        f"🎯 Matched: `{matched_count}` jobs\n"
        f"📋 Pending Queue: `{pending_count}` jobs\n"
        f"✅ Applied: `{applied_count}` jobs"
    )
    await message.reply(text_msg)

@router.message(Command("pause"))
async def cmd_pause(message: types.Message):
    if not await check_auth(message.chat.id):
        return
        
    async with AsyncSessionLocal() as session:
        stmt = select(DBSetting).where(DBSetting.key == "pause_crawler")
        result = await session.execute(stmt)
        db_setting = result.scalars().first()
        if db_setting:
            db_setting.value = {"paused": True}
        else:
            session.add(DBSetting(key="pause_crawler", value={"paused": True}))
        await session.commit()
        
    await message.reply("⏸️ **JobPilot Ingestion Paused**\n\nDiscovery crawlers and automated scoring have been suspended.")

@router.message(Command("resume"))
async def cmd_resume(message: types.Message):
    if not await check_auth(message.chat.id):
        return
        
    async with AsyncSessionLocal() as session:
        stmt = select(DBSetting).where(DBSetting.key == "pause_crawler")
        result = await session.execute(stmt)
        db_setting = result.scalars().first()
        if db_setting:
            db_setting.value = {"paused": False}
        else:
            session.add(DBSetting(key="pause_crawler", value={"paused": False}))
        await session.commit()
        
    await message.reply("▶️ **JobPilot Ingestion Resumed**\n\nDiscovery crawlers and automated scoring are now active.")
