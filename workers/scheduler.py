import os
import sys
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add api folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw
from app.models.resumes import ResumeProfile, ResumeVersion
from app.config import settings

# Import discovery adapters
from workers.discovery.tier_a_apis import fetch_remoteok_jobs, fetch_wwr_jobs, fetch_remotive_jobs
from workers.discovery.dork_search import run_dork_search
from workers.discovery.dedup import is_duplicate

# Import matching components
from workers.matching.score import process_matching_for_job

# Import tailoring components
from workers.tailoring.extract_keywords import extract_keywords_from_jd
from workers.tailoring.rewrite_resume import generate_tailored_resume_json
from workers.tailoring.render_pdf import render_resume_to_pdf

# Import applying components
from workers.applying.tier_a_apply import pre_build_application_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("workers.scheduler")

# Create output folder for resumes if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "api", "resumes"), exist_ok=True)

async def run_tailoring_pipeline(session: AsyncSession, job: JobRaw, profile: ResumeProfile) -> bool:
    """Runs the resume tailoring pipeline for a matched job."""
    try:
        logger.info(f"--- Starting tailoring pipeline for Job ID {job.id} ({job.title} at {job.company}) ---")
        
        # 1. Extract keywords
        keywords = await extract_keywords_from_jd(job.title, job.description_text)
        
        # 2. Tailor bullets
        tailored_json = await generate_tailored_resume_json(
            job.title,
            job.description_text,
            keywords,
            profile.content_json
        )
        
        # 3. Render PDF
        pdf_filename = f"resume_tailored_{job.id}.pdf"
        # Store in the api/resumes directory
        pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", "resumes", pdf_filename))
        render_resume_to_pdf(tailored_json, pdf_path)
        
        # 4. Save to resume_versions
        resume_ver = ResumeVersion(
            job_id=job.id,
            content_json=tailored_json,
            pdf_path=pdf_path,
            model_used="claude-sonnet-5"
        )
        session.add(resume_ver)
        
        # Update job status
        job.status = "tailored"
        await session.commit()
        logger.info(f"Tailoring pipeline succeeded. Resume version saved & rendered.")
        return True
        
    except Exception as e:
        logger.error(f"Failed tailoring pipeline for job {job.id}: {str(e)}")
        return False

async def process_new_jobs_pipeline():
    """Main discovery and matching background pipeline loop."""
    logger.info("Starting background discovery & matching run...")
    
    # 1. Fetch from Tier A adapters
    discovered_jobs = []
    
    # Run public APIs (safe, no keys needed)
    discovered_jobs.extend(await fetch_remoteok_jobs())
    discovered_jobs.extend(await fetch_wwr_jobs())
    discovered_jobs.extend(await fetch_remotive_jobs())
    
    # Run Google Custom Search dork search if keys are present
    google_key = settings.gemini_api_key or os.environ.get("GOOGLE_SEARCH_API_KEY") # Check google search keys
    google_cx = os.environ.get("GOOGLE_SEARCH_CX")
    if google_key and google_cx:
        logger.info("Google Search API keys detected. Running dork search discovery...")
        discovered_jobs.extend(await run_dork_search(google_key, google_cx))
    else:
        logger.info("Google Custom Search API keys not set. Skipping dork search discovery.")
        
    # 2. Ingest and deduplicate jobs
    new_job_ids = []
    async with AsyncSessionLocal() as session:
        for job_data in discovered_jobs:
            try:
                # Deduplicate
                if await is_duplicate(session, job_data):
                    continue
                    
                # Create raw job
                db_job = JobRaw(**job_data)
                session.add(db_job)
                await session.flush() # populate db_job.id
                
                new_job_ids.append(db_job.id)
                logger.info(f"Ingested new job: '{db_job.title}' at '{db_job.company}' (ID: {db_job.id})")
            except Exception as e:
                logger.error(f"Error ingesting job: {str(e)}")
                
        await session.commit()
        
    logger.info(f"Ingested {len(new_job_ids)} new unique jobs. Proceeding to score...")
    
    # 3. Match / Score
    matched_job_ids = []
    for job_id in new_job_ids:
        score_rec = await process_matching_for_job(job_id)
        if score_rec:
            # Check if it was matched
            async with AsyncSessionLocal() as session:
                stmt = select(JobRaw).where(JobRaw.id == job_id)
                result = await session.execute(stmt)
                job = result.scalars().first()
                if job and job.status == "matched":
                    matched_job_ids.append(job_id)

    # 4. Tailor matched jobs
    tailored_job_ids = []
    async with AsyncSessionLocal() as session:
        stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
        result = await session.execute(stmt)
        profile = result.scalars().first()
        if not profile:
            logger.error("No active profile, skipping tailoring.")
            return
            
        for job_id in matched_job_ids:
            stmt = select(JobRaw).where(JobRaw.id == job_id)
            result = await session.execute(stmt)
            job = result.scalars().first()
            if job:
                success = await run_tailoring_pipeline(session, job, profile)
                if success:
                    tailored_job_ids.append(job_id)

    # 5. Pre-build application payloads
    for job_id in tailored_job_ids:
        await pre_build_application_payload(job_id)

    logger.info("Pipeline run complete.")

async def main():
    logger.info("Scheduler starting...")
    # For Phase 1 manual verification, we run the loop once on startup
    await process_new_jobs_pipeline()
    
    # Keep active
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
