import asyncio
import logging
from aiogram import Router, F, types
from sqlalchemy import select
import httpx

from db import AsyncSessionLocal, DBApplication, DBJobRaw, DBJobScore
from handlers.commands import check_auth

logger = logging.getLogger("bot.handlers.callbacks")
router = Router()

@router.callback_query(F.data.startswith("apply:"))
async def handle_apply_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if not await check_auth(chat_id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
        
    app_id = callback.data.split(":")[1]
    await callback.answer("Initiating submission...")
    
    # 1. Fetch current status to check idempotency
    async with AsyncSessionLocal() as session:
        stmt = (
            select(DBApplication, DBJobRaw, DBJobScore)
            .join(DBJobRaw, DBApplication.job_id == DBJobRaw.id)
            .outerjoin(DBJobScore, DBApplication.job_id == DBJobScore.job_id)
            .where(DBApplication.id == app_id)
        )
        result = await session.execute(stmt)
        row = result.first()
        
    if not row:
        await callback.message.edit_text("❌ Application not found in database.")
        return
        
    app, job, score = row
    score_val = score.final_score if score else 0.0
    
    if app.status != "ready_to_apply":
        await callback.message.edit_text(
            f"🏢 **{job.company}**\n"
            f"💼 **{job.title}**\n\n"
            f"⚠️ **Stale Action:** This application is already in `{app.status}` status."
        )
        return
        
    # 2. Update message to Applying state and remove buttons
    base_text = (
        f"🏢 **{job.company}**\n"
        f"💼 **{job.title}**\n"
        f"🎯 Match Score: `{score_val:.1f}%` ({job.source})\n\n"
    )
    await callback.message.edit_text(base_text + "⏳ **Applying...**")
    
    # 3. Call API apply endpoint
    api_url = f"http://api:8000/api/v1/applications/{app_id}/apply"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, timeout=10)
            
        if response.status_code not in (200, 201):
            raise Exception(f"API returned status code {response.status_code}")
            
        # 4. Poll database for applied status change
        success = False
        error_msg = "Timeout waiting for worker"
        
        for _ in range(10):
            await asyncio.sleep(1.5)
            async with AsyncSessionLocal() as session:
                stmt = select(DBApplication).where(DBApplication.id == app_id)
                res = await session.execute(stmt)
                refreshed_app = res.scalars().first()
                if refreshed_app:
                    if refreshed_app.status == "applied":
                        success = True
                        break
                    elif refreshed_app.status == "failed":
                        # Fetch fail reason
                        error_msg = "Submission failed (check logs)"
                        break
                        
        if success:
            await callback.message.edit_text(base_text + "✅ **Applied successfully!**")
        else:
            await callback.message.edit_text(base_text + f"❌ **Application failed:** `{error_msg}`")
            
    except Exception as e:
        logger.error(f"Error calling apply endpoint for app {app_id}: {str(e)}")
        await callback.message.edit_text(base_text + f"❌ **Error calling API apply endpoint:** `{str(e)}`")

@router.callback_query(F.data.startswith("pass:"))
async def handle_pass_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if not await check_auth(chat_id):
        await callback.answer("Unauthorized.", show_alert=True)
        return
        
    app_id = callback.data.split(":")[1]
    await callback.answer("Passing job...")
    
    async with AsyncSessionLocal() as session:
        stmt = (
            select(DBApplication, DBJobRaw)
            .join(DBJobRaw, DBApplication.job_id == DBJobRaw.id)
            .where(DBApplication.id == app_id)
        )
        result = await session.execute(stmt)
        row = result.first()
        
    if not row:
        await callback.message.edit_text("❌ Application not found.")
        return
        
    app, job = row
    
    if app.status != "ready_to_apply":
        await callback.message.edit_text(f"🏢 **{job.company}**\n💼 **{job.title}**\n\n⚠️ Already in `{app.status}` status.")
        return
        
    # Call pass endpoint
    api_url = f"http://api:8000/api/v1/applications/{app_id}/pass"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, timeout=10)
            
        if response.status_code == 200:
            await callback.message.edit_text(
                f"🏢 **{job.company}**\n"
                f"💼 **{job.title}**\n\n"
                f"🚫 **Skipped**"
            )
        else:
            await callback.message.edit_text(f"❌ Failed to skip application (HTTP {response.status_code}).")
    except Exception as e:
        logger.error(f"Error calling pass endpoint: {str(e)}")
        await callback.message.edit_text(f"❌ Error: `{str(e)}`")


@router.callback_query(F.data.startswith("draft:"))
async def handle_draft_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    if not await check_auth(chat_id):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    job_id = callback.data.split(":")[1]
    await callback.answer("Generating outreach draft…")

    api_url = f"http://api:8000/api/v1/outreach/{job_id}/draft"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json={"channel": "linkedin", "tone": "confident"},
                timeout=30
            )

        if response.status_code in (200, 201):
            data = response.json()
            draft_text = data.get("draft_text", "")
            reply_text = (
                f"✉️ **LinkedIn Outreach Draft**\n\n"
                f"`{draft_text}`\n\n"
                f"_Copy the draft above and send it manually via LinkedIn._"
            )
            await callback.message.answer(reply_text, parse_mode="Markdown")
        else:
            await callback.message.answer(
                f"❌ Failed to generate outreach draft (HTTP {response.status_code})."
            )
    except Exception as e:
        logger.error(f"Error calling outreach draft endpoint for job {job_id}: {str(e)}")
        await callback.message.answer(f"❌ Error generating draft: `{str(e)}`")

