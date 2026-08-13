import os
import sys
import asyncio
import logging
from sqlalchemy import select, delete

# Add directories to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw, JobScore
from app.models.resumes import ResumeProfile
from workers.discovery.tier_a_apis import fetch_remoteok_jobs
from workers.matching.score import process_matching_for_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_matching")

async def main():
    logger.info("=== Starting Live Matching Engine Verification Run ===")
    
    # 1. Fetch live jobs from RemoteOK
    logger.info("Fetching jobs from RemoteOK...")
    jobs = await fetch_remoteok_jobs()
    if not jobs:
        logger.error("No jobs discovered. Exiting.")
        return
        
    logger.info(f"Discovered {len(jobs)} jobs. Selecting 5 diverse jobs to score...")
    
    # Let's pick 5 jobs with different titles (some senior/lead, some developer roles)
    selected_jobs = []
    # Make sure we have a mix of roles
    for job in jobs:
        title_lower = job["title"].lower()
        # Add to list
        selected_jobs.append(job)
        if len(selected_jobs) >= 5:
            break
            
    # 2. Ingest and run matching on each
    results = []
    async with AsyncSessionLocal() as session:
        # Get active resume profile first
        profile = (await session.execute(
            select(ResumeProfile).where(ResumeProfile.is_active == True)
        )).scalars().first()
        if not profile:
            logger.error("No active profile in database. Please run seed_resume.py first.")
            return
            
        logger.info(f"Active Resume Profile: {profile.content_json.get('name')} (Version {profile.version})")
        
        for job_data in selected_jobs:
            # Clean up existing to prevent unique constraint failures
            existing = (await session.execute(
                select(JobRaw).where(
                    JobRaw.source == job_data["source"],
                    JobRaw.source_job_id == str(job_data["source_job_id"])
                )
            )).scalars().first()
            if existing:
                await session.execute(delete(JobScore).where(JobScore.job_id == existing.id))
                await session.execute(delete(JobRaw).where(JobRaw.id == existing.id))
                await session.commit()
                
            db_job = JobRaw(
                source=job_data["source"],
                source_tier=job_data.get("source_tier", "A"),
                source_job_id=str(job_data["source_job_id"]),
                source_url=job_data.get("source_url"),
                company=job_data.get("company"),
                title=job_data.get("title"),
                description_text=job_data.get("description_text", ""),
                location=job_data.get("location"),
                is_remote=job_data.get("is_remote", True),
                status="discovered",
                is_test=True,
            )
            session.add(db_job)
            await session.commit()
            
            job_id = db_job.id
            logger.info(f"\nProcessing matching for: '{db_job.title}' at '{db_job.company}' (ID: {job_id})")
            
            # Run Stage 1/2/3 matching
            score_rec = await process_matching_for_job(job_id)
            
            # Fetch final status
            db_job_refreshed = (await session.execute(
                select(JobRaw).where(JobRaw.id == job_id)
            )).scalars().first()
            
            score_val = score_rec.final_score if score_rec else 0.0
            rationale = score_rec.rationale if score_rec else "n/a"
            
            results.append({
                "title": db_job_refreshed.title,
                "company": db_job_refreshed.company,
                "status": db_job_refreshed.status,
                "score": score_val,
                "rationale": rationale
            })
            
    # 3. Print verification table
    logger.info("\n==========================================================================================")
    logger.info("                                 VERIFICATION RESULTS TABLE                               ")
    logger.info("==========================================================================================")
    for res in results:
        logger.info(f"🏢 Company  : {res['company']}")
        logger.info(f"💼 Role     : {res['title']}")
        logger.info(f"📊 Status   : {res['status'].upper()}")
        logger.info(f"🎯 Score    : {res['score']:.2f}%")
        logger.info(f"📝 Rationale: {res['rationale']}")
        logger.info("------------------------------------------------------------------------------------------")
    logger.info("==========================================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
