import os
import sys
import json
import random
import logging
import asyncio
import tempfile
from typing import Dict, Any, Tuple
from sqlalchemy import select, func, and_, text

# Setup pythonpath imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw
from app.models.resumes import ResumeProfile, ResumeVersion
from app.models.applications import Application
from app.models.settings import Setting
from app.utils.security import decrypt_session_data

from playwright.async_api import async_playwright

logger = logging.getLogger("workers.applying.tier_b_apply")

class CaptchaDetectedException(Exception):
    pass

async def get_daily_cap(platform: str, session) -> int:
    """Gets the daily cap configuration for the given platform from the database settings table."""
    try:
        stmt = select(Setting).where(Setting.key == "daily_caps_by_platform")
        res = await session.execute(stmt)
        setting = res.scalars().first()
        if setting and setting.value:
            return int(setting.value.get(platform.lower(), 3))
    except Exception as e:
        logger.error(f"Error fetching cap from settings: {str(e)}")
    return 3

async def get_daily_application_count(platform: str, session) -> int:
    """Counts applications created or submitted for the given platform in the last 24 hours."""
    stmt = (
        select(func.count(Application.id))
        .join(JobRaw, Application.job_id == JobRaw.id)
        .where(
            and_(
                JobRaw.source.ilike(f"{platform}%"),
                Application.created_at >= func.now() - text("INTERVAL '24 hours'"),
                Application.status.in_(["ready_to_apply", "applied"])
            )
        )
    )
    res = await session.execute(stmt)
    return res.scalar() or 0

async def get_session_state() -> dict:
    """Decrypts and retrieves the LinkedIn session state from storage."""
    enc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage_state", "linkedin.enc"))
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Encrypted session state not found at {enc_path}. Run scripts/login_helper.py first.")
        
    with open(enc_path, "rb") as f:
        encrypted_bytes = f.read()
        
    return decrypt_session_data(encrypted_bytes)

async def pre_fill_linkedin_form(job_id: str) -> bool:
    """Asynchronously launches Playwright, pre-fills the application form, and captures a screenshot."""
    logger.info(f"Starting form pre-fill for Job ID {job_id}...")
    
    async with AsyncSessionLocal() as session:
        # 1. Cap checks
        cap = await get_daily_cap("linkedin", session)
        count = await get_daily_application_count("linkedin", session)
        if count >= cap:
            logger.warning(f"LinkedIn daily limit reached ({count}/{cap}). Aborting pre-fill.")
            return False
            
        # Fetch Job & Resume Version info
        stmt_job = select(JobRaw).where(JobRaw.id == job_id)
        res_job = await session.execute(stmt_job)
        job = res_job.scalars().first()
        if not job:
            logger.error(f"Job {job_id} not found in database.")
            return False
            
        stmt_rv = select(ResumeVersion).where(ResumeVersion.job_id == job_id).order_by(ResumeVersion.generated_at.desc())
        res_rv = await session.execute(stmt_rv)
        rv = res_rv.scalars().first()
        if not rv:
            logger.error(f"Tailored ResumeVersion not found for Job ID {job_id}.")
            return False
            
        # Fetch Resume Profile (default answers)
        stmt_prof = select(ResumeProfile).where(ResumeProfile.is_active == True)
        res_prof = await session.execute(stmt_prof)
        profile = res_prof.scalars().first()
        if not profile or not profile.content_json:
            logger.error("Active ResumeProfile not found.")
            return False
            
        default_answers = profile.content_json.get("default_answers", {})
        contact_info = profile.content_json.get("contact_info", {})
        
        # Determine paths
        # Determine paths (translate /app container prefix to host workspace path if not in docker)
        resume_pdf_path = rv.pdf_path
        if not os.path.exists("/.dockerenv"):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if resume_pdf_path.startswith("/app/"):
                resume_pdf_path = resume_pdf_path.replace("/app/", project_root + "/")
        resume_pdf_path = os.path.abspath(resume_pdf_path)
        screenshot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api", "resumes", f"form_preview_{job_id}.png"))
        
        # Check files exist
        if not os.path.exists(resume_pdf_path):
            logger.error(f"Tailored resume PDF not found at {resume_pdf_path}")
            return False
            
        # 2. Decrypt storage state to temp file
        session_state = await get_session_state()
        
        # 3. Launch Playwright (headed on host to bypass anti-bot, headless in docker)
        is_docker = os.path.exists("/.dockerenv")
        headless_mode = True if is_docker else False
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless_mode,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as temp_file:
                json.dump(session_state, temp_file)
                temp_state_path = temp_file.name
                
            try:
                context = await browser.new_context(
                    storage_state=temp_state_path,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                # Delete temp credentials file immediately to keep storage safe
                try:
                    os.unlink(temp_state_path)
                except Exception:
                    pass
                    
                page = await context.new_page()
                
                # Navigate to feed first to establish session and prevent redirect loops
                logger.info("Navigating to LinkedIn home feed first to establish session...")
                await page.goto("https://www.linkedin.com/feed/", timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 3.0))
                
                # Navigate to the job page (normalize country subdomain to www.linkedin.com to match cookies)
                import re
                job_url = re.sub(r"https?://[a-z]{2}\.linkedin\.com/", "https://www.linkedin.com/", job.source_url)
                logger.info(f"Navigating to LinkedIn Job page: {job_url}")
                await page.goto(job_url, timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                # Check if we were redirected to search or another non-job page
                if "/jobs/view/" not in page.url:
                    logger.warning(f"Redirected away from job details page to: {page.url}. Marking as manual lead.")
                    await save_application_record(session, job_id, rv.id, "manual_lead", {"error": f"Redirected to non-job page: {page.url}"})
                    return False
                    
                # Check for Captcha / verification panel
                if await page.query_selector("iframe[src*='captcha']"):
                    raise CaptchaDetectedException("LinkedIn Captcha / bot challenge detected.")
                    
                # Check if already applied
                page_content_html = await page.content()
                already_applied_el = await page.query_selector("text=Application submitted, text=Applied")
                if already_applied_el or "Application submitted" in page_content_html or "Application status" in page_content_html:
                    logger.info("Already applied to this job. Marking as applied in DB.")
                    await save_application_record(session, job_id, rv.id, "applied", {"note": "Already applied detected on page"})
                    return True
                    
                # Click Easy Apply button
                try:
                    easy_apply_btn = await page.wait_for_selector(
                        "button.jobs-apply-button, a.jobs-apply-button, .jobs-apply-button, button:has-text('Easy Apply'), a:has-text('Easy Apply'), span:has-text('Easy Apply'), [aria-label*='Easy Apply']",
                        timeout=15000
                    )
                except Exception:
                    easy_apply_btn = None
                    
                if not easy_apply_btn:
                    logger.warning("LinkedIn Easy Apply button not found. Marking as manual lead.")
                    # Create application row in manual_lead status
                    await save_application_record(session, job_id, rv.id, "manual_lead", {"error": "Easy Apply button not found"})
                    return False
                    
                await easy_apply_btn.click()
                await asyncio.sleep(random.uniform(2.0, 3.0))
                
                # Multi-step form filling loop
                max_steps = 10
                for step in range(max_steps):
                    # Check for Captcha/Challenge during filling
                    if await page.query_selector("iframe[src*='captcha']") or await page.query_selector(".challenge-dialog"):
                        raise CaptchaDetectedException("LinkedIn Captcha / bot challenge detected during form fill.")
                        
                    # 1. Fill basic input texts (tel, email, text)
                    inputs = await page.query_selector_all("input")
                    for inp in inputs:
                        inp_type = await inp.get_attribute("type") or ""
                        inp_id = await inp.get_attribute("id") or ""
                        inp_name = await inp.get_attribute("name") or ""
                        
                        # Match name/phone fields
                        if "phone" in inp_id.lower() or "phone" in inp_name.lower():
                            await inp.fill(contact_info.get("phone", ""))
                        elif "email" in inp_id.lower() or "email" in inp_name.lower():
                            await inp.fill(contact_info.get("email", ""))
                            
                    # 2. Upload resume
                    file_input = await page.query_selector("input[type='file']")
                    if file_input:
                        filename = os.path.basename(resume_pdf_path)
                        logger.info(f"Uploading tailored resume: {filename}")
                        await file_input.set_input_files(resume_pdf_path)
                        # Wait for upload to progress and settle (up to 6 seconds)
                        logger.info("Waiting for resume upload to complete...")
                        await page.wait_for_timeout(6000)
                        
                        # Explicitly search for the newly uploaded resume option and select it
                        try:
                            # Search for any label or element containing the filename of our uploaded resume
                            resume_option = await page.query_selector(f"label:has-text('{filename}'), :has-text('{filename}')")
                            if resume_option:
                                logger.info(f"Explicitly selecting uploaded resume: {filename}")
                                await resume_option.click()
                                await page.wait_for_timeout(1000)
                        except Exception as ex:
                            logger.warning(f"Could not explicitly select resume option: {str(ex)}")
                        
                    # 3. Check for screen questions select dropdowns and radio buttons
                    # Match answers from default_answers
                    radio_groups = await page.query_selector_all("fieldset")
                    for group in radio_groups:
                        legend_el = await group.query_selector("legend")
                        if legend_el:
                            legend_text = (await legend_el.inner_text()).lower()
                            # Match question with default answers keys
                            for key, val in default_answers.items():
                                if key.lower() in legend_text:
                                    # Select radio button matching value
                                    label_el = await group.query_selector(f"label:has-text('{val}')")
                                    if label_el:
                                        await label_el.click()
                                        
                    # Click Next / Review / Submit
                    next_btn = await page.query_selector("button:has-text('Next'), button:has-text('Review')")
                    if next_btn:
                        await next_btn.click()
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    else:
                        # No Next/Review button - we have reached the final step (usually has a Submit button)
                        break
                        
                # Take screenshot of the pre-filled state before clicking final submit
                logger.info(f"Saving form pre-fill preview screenshot to {screenshot_path}")
                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                await page.screenshot(path=screenshot_path)
                
                # Save application record as ready_to_apply
                await save_application_record(session, job_id, rv.id, "ready_to_apply", {
                    "message": "Form successfully pre-filled, waiting for manual confirmation."
                })
                
                await context.close()
                await browser.close()
                return True
                
            except CaptchaDetectedException as e:
                logger.error(str(e))
                # Fetch app record
                app_stmt = select(Application).where(Application.job_id == job_id)
                app_res = await session.execute(app_stmt)
                app = app_res.scalars().first()
                app_id_str = str(app.id) if app else None

                await save_application_record(session, job_id, rv.id, "manual_lead", {
                    "error": "CAPTCHA / Verification panel encountered. Automated execution halted."
                })
                await browser.close()
                
                # Publish Redis event
                try:
                    import redis
                    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
                    event = {
                        "event_type": "job.captcha_detected",
                        "job_id": job_id,
                        "payload": {
                            "application_id": app_id_str,
                        }
                    }
                    r.publish("jobpilot:events", json.dumps(event))
                    logger.info("Published CAPTCHA event to Redis pub/sub channel.")
                except Exception as ex:
                    logger.error(f"Failed to publish CAPTCHA event: {str(ex)}")
                return False
            except Exception as e:
                logger.error(f"Execution error during form pre-fill: {str(e)}")
                await save_application_record(session, job_id, rv.id, "failed", {"error": str(e)})
                await browser.close()
                return False

async def save_application_record(session, job_id: str, rv_id: str, status: str, result_meta: dict):
    """Inserts or updates an application entry in the database."""
    stmt = select(Application).where(Application.job_id == job_id)
    res = await session.execute(stmt)
    app = res.scalars().first()
    
    if app:
        app.status = status
        app.result = result_meta
    else:
        app = Application(
            job_id=job_id,
            resume_version_id=rv_id,
            tier="B",
            status=status,
            result=result_meta
        )
        session.add(app)
        
    await session.commit()
    logger.info(f"Saved application status '{status}' for job {job_id}.")

async def execute_linkedin_submission(application_id: str) -> bool:
    """Asynchronously logs back in, loads the draft, clicks final submit, and marks as applied."""
    logger.info(f"Executing final submission for Application ID {application_id}...")
    
    async with AsyncSessionLocal() as session:
        stmt = select(Application).where(Application.id == application_id)
        res = await session.execute(stmt)
        app = res.scalars().first()
        if not app:
            logger.error(f"Application {application_id} not found.")
            return False
            
        # Per-platform cap enforcement
        cap = await get_daily_cap("linkedin", session)
        count = await get_daily_application_count("linkedin", session)
        if count >= cap:
            logger.warning(f"LinkedIn daily limit reached ({count}/{cap}) during submit. Aborting.")
            app.status = "ready_to_apply"
            app.result = {"error": "Submission aborted: daily cap exceeded."}
            await session.commit()
            return False
            
        stmt_job = select(JobRaw).where(JobRaw.id == app.job_id)
        res_job = await session.execute(stmt_job)
        job = res_job.scalars().first()
        if not job:
            logger.error(f"Job not found for application {application_id}.")
            return False
            
        session_state = await get_session_state()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as temp_file:
                json.dump(session_state, temp_file)
                temp_state_path = temp_file.name
                
            try:
                context = await browser.new_context(
                    storage_state=temp_state_path,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                
                try:
                    os.unlink(temp_state_path)
                except Exception:
                    pass
                    
                page = await context.new_page()
                
                # Navigate back to page and trigger Easy Apply modal
                await page.goto(job.source_url, timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 4.0))
                
                easy_apply_btn = await page.query_selector("button.jobs-apply-button")
                if not easy_apply_btn:
                    raise Exception("Easy Apply button not found during submission click.")
                    
                await easy_apply_btn.click()
                await asyncio.sleep(random.uniform(2.0, 3.0))
                
                # Fast forward to final step by clicking "Next" / "Review"
                for _ in range(10):
                    if await page.query_selector("iframe[src*='captcha']"):
                        raise CaptchaDetectedException("Captcha detected during submission.")
                        
                    next_btn = await page.query_selector("button:has-text('Next'), button:has-text('Review')")
                    if next_btn:
                        await next_btn.click()
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                    else:
                        break
                        
                # Locate final Submit application button
                submit_btn = await page.query_selector("button:has-text('Submit application')")
                if not submit_btn:
                    raise Exception("Submit application button not found on final step.")
                    
                logger.info("Clicking final Submit application button...")
                await submit_btn.click()
                await asyncio.sleep(random.uniform(3.0, 5.0))
                
                # Verify application submission completed successfully
                app.status = "applied"
                from sqlalchemy.sql import func
                app.applied_at = func.now()
                app.result = {"message": "LinkedIn Easy Apply application submitted successfully."}
                
                # Update job status
                job.status = "applied"
                await session.commit()
                
                await context.close()
                await browser.close()
                return True
                
            except CaptchaDetectedException as e:
                logger.error(str(e))
                app.status = "manual_lead"
                app.result = {"error": "CAPTCHA challenge detected on submit page. Halted."}
                await session.commit()
                await browser.close()
                
                # Publish Redis event
                try:
                    import redis
                    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
                    event = {
                        "event_type": "job.captcha_detected",
                        "job_id": str(app.job_id),
                        "payload": {
                            "application_id": application_id,
                        }
                    }
                    r.publish("jobpilot:events", json.dumps(event))
                    logger.info("Published CAPTCHA event to Redis pub/sub channel from submit handler.")
                except Exception as ex:
                    logger.error(f"Failed to publish CAPTCHA event: {str(ex)}")
                return False
            except Exception as e:
                logger.error(f"Error during final submission execution: {str(e)}")
                app.status = "failed"
                app.result = {"error": str(e)}
                await session.commit()
                await browser.close()
                return False

async def pre_build_tier_b_application(job_id: str) -> bool:
    """
    Instantly creates an Application record in 'ready_to_apply' status for Tier B jobs,
    avoiding Playwright execution entirely.
    """
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(JobRaw).where(JobRaw.id == job_id)
            result = await session.execute(stmt)
            job = result.scalars().first()
            if not job or job.status not in ("matched", "tailored"):
                return False
                
            stmt = select(ResumeVersion).where(ResumeVersion.job_id == job_id).order_by(ResumeVersion.generated_at.desc())
            result = await session.execute(stmt)
            resume_version = result.scalars().first()
            if not resume_version:
                logger.error(f"No tailored resume found for job {job_id}.")
                return False
                
            # Create Application record
            app = Application(
                job_id=job.id,
                resume_version_id=resume_version.id,
                tier=job.source_tier,
                method="manual",
                status="ready_to_apply",
                request_payload_snapshot={"note": "Manual Apply redirect to original source link"}
            )
            session.add(app)
            job.status = "ready_to_apply"
            await session.commit()
            logger.info(f"Promoted Tier B job '{job.title}' to ready_to_apply state.")
            return True
        except Exception as e:
            logger.error(f"Error promoting Tier B job {job_id}: {str(e)}")
            return False
