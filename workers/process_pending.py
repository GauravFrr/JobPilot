import os
import sys
import asyncio
import logging
from sqlalchemy import select

# Setup paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw
from app.models.resumes import ResumeProfile
from workers.matching.score import process_matching_for_job
from workers.scheduler import run_tailoring_pipeline
from workers.applying.tier_a_apply import pre_build_application_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("workers.process_pending")

async def process_pending():
    logger.info("Starting processing pipeline for pending jobs in DB...")
    
    # 1. Score all "discovered" jobs
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.status == "discovered")
        res = await session.execute(stmt)
        discovered_jobs = res.scalars().all()
        
    logger.info(f"Found {len(discovered_jobs)} discovered jobs to score.")
    for job in discovered_jobs:
        logger.info(f"Scoring: {job.title} at {job.company} (ID: {job.id})")
        try:
            await process_matching_for_job(str(job.id))
        except Exception as e:
            logger.error(f"Error scoring job {job.id}: {str(e)}")
            
    # 2. Tailor all "matched" jobs
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.status == "matched")
        res = await session.execute(stmt)
        matched_jobs = res.scalars().all()
        
        stmt_profile = select(ResumeProfile).where(ResumeProfile.is_active == True)
        res_profile = await session.execute(stmt_profile)
        profile = res_profile.scalars().first()
        
        if not profile:
            logger.error("No active profile, skipping tailoring.")
            return
            
        logger.info(f"Found {len(matched_jobs)} matched jobs to tailor.")
        tailored_job_ids = []
        for job in matched_jobs:
            # We must fetch and pass job to run_tailoring_pipeline
            # run_tailoring_pipeline commits inside
            success = await run_tailoring_pipeline(session, job, profile)
            if success:
                tailored_job_ids.append(job.id)
                
    # 3. Pre-build application payloads or pre-fill form screenshots for tailored jobs
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.status == "tailored")
        res = await session.execute(stmt)
        tailored_jobs = res.scalars().all()
        
    logger.info(f"Found {len(tailored_jobs)} tailored jobs to pre-fill/pre-build.")
    for job in tailored_jobs:
        if job.source_tier == "B":
            try:
                from workers.applying.tier_b_apply import pre_build_tier_b_application
                await pre_build_tier_b_application(str(job.id))
            except Exception as e:
                logger.error(f"Failed promoting manual app for job {job.id}: {str(e)}")
        else:
            try:
                await pre_build_application_payload(str(job.id))
            except Exception as e:
                logger.error(f"Failed pre-building application payload for job {job.id}: {str(e)}")

    logger.info("Pipeline run complete.")

if __name__ == "__main__":
    asyncio.run(process_pending())
