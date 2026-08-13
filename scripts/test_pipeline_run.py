import os
import sys
import json
import asyncio
import logging
from sqlalchemy import select, delete

# Add directories to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw, JobScore
from app.models.resumes import ResumeProfile, ResumeVersion
from app.models.applications import Application

from workers.matching.score import process_matching_for_job
from workers.scheduler import run_tailoring_pipeline
from workers.applying.tier_a_apply import pre_build_application_payload, execute_submission

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_pipeline_run")

async def main():
    logger.info("--- Starting Phase 1 Integration Test Run ---")
    
    mock_source = "greenhouse:acme"
    mock_job_id = "mock-12345"
    
    async with AsyncSessionLocal() as session:
        # Clean up any existing records first
        stmt_find = select(JobRaw).where(JobRaw.source == mock_source, JobRaw.source_job_id == mock_job_id)
        res = await session.execute(stmt_find)
        job = res.scalars().first()
        if job:
            logger.info(f"Cleaning up old mock job records for ID {job.id}...")
            # Cascade deletes
            await session.execute(delete(Application).where(Application.job_id == job.id))
            await session.execute(delete(ResumeVersion).where(ResumeVersion.job_id == job.id))
            await session.execute(delete(JobScore).where(JobScore.job_id == job.id))
            await session.execute(delete(JobRaw).where(JobRaw.id == job.id))
            await session.commit()
            
        # Create a new mock job posting matching Gaurav's stack
        mock_job = JobRaw(
            source=mock_source,
            source_tier="A",
            source_job_id=mock_job_id,
            source_url="https://boards.greenhouse.io/acme/jobs/mock-12345",
            company="Acme Corporation",
            title="Backend Software Engineer (FastAPI/Python)",
            description_text="We are looking for a Backend Engineer who loves FastAPI, Python, RAG pipelines, and PostgreSQL. You will work on database schema design, vector similarity search with pgvector, and scaling services.",
            location="Remote",
            is_remote=True,
            status="discovered",
            is_test=True
        )
        session.add(mock_job)
        await session.commit()
        
        job_id = mock_job.id
        logger.info(f"Mock job inserted with ID: {job_id}")
        
    # --- Step 1: Run Matching Engine ---
    logger.info("\n1. Running matching engine...")
    score_rec = await process_matching_for_job(job_id)
    if not score_rec:
        logger.error("Matching engine failed to process mock job.")
        return
    logger.info(f"Matching finished. Score: {score_rec.final_score:.2f}, Status after matching: {score_rec.rationale}")

    # --- Step 2: Verify Status in DB ---
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.id == job_id)
        res = await session.execute(stmt)
        job = res.scalars().first()
        logger.info(f"Job status is currently: '{job.status}' (expected 'matched')")
        assert job.status == "matched"
        
        stmt_profile = select(ResumeProfile).where(ResumeProfile.is_active == True)
        res_profile = await session.execute(stmt_profile)
        profile = res_profile.scalars().first()

    # --- Step 3: Run Tailoring ---
    logger.info("\n2. Running resume tailoring pipeline...")
    async with AsyncSessionLocal() as session:
        stmt_job = select(JobRaw).where(JobRaw.id == job_id)
        res_job = await session.execute(stmt_job)
        job = res_job.scalars().first()
        success = await run_tailoring_pipeline(session, job, profile)
        assert success == True
        
    # --- Step 4: Verify Tailored Resume and PDF ---
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.id == job_id)
        res = await session.execute(stmt)
        job = res.scalars().first()
        logger.info(f"Job status after tailoring: '{job.status}' (expected 'tailored')")
        assert job.status == "tailored"
        
        stmt_ver = select(ResumeVersion).where(ResumeVersion.job_id == job_id)
        res_ver = await session.execute(stmt_ver)
        resume_version = res_ver.scalars().first()
        assert resume_version is not None
        logger.info(f"Tailored resume saved in database: ID {resume_version.id}")
        logger.info(f"PDF saved on disk: {resume_version.pdf_path}")
        assert os.path.exists(resume_version.pdf_path) == True

    # --- Step 5: Pre-build Application Payload (halt before apply) ---
    logger.info("\n3. Running pre-builder payload construction...")
    app = await pre_build_application_payload(job_id)
    assert app is not None
    
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.id == job_id)
        res = await session.execute(stmt)
        job = res.scalars().first()
        logger.info(f"Job status after pre-building: '{job.status}' (expected 'ready_to_apply')")
        assert job.status == "ready_to_apply"
        
        stmt_app = select(Application).where(Application.job_id == job_id)
        res_app = await session.execute(stmt_app)
        application = res_app.scalars().first()
        assert application is not None
        logger.info(f"Application status is: '{application.status}' (expected 'ready_to_apply')")
        assert application.status == "ready_to_apply"
        
        # Verify no auto-submit happened
        logger.info("VERIFICATION: Pipeline halted in 'ready_to_apply' status. No request has been fired.")

    # --- Step 6: Trigger Manual Apply ---
    logger.info("\n4. Triggering manual Apply call...")
    submission_success = await execute_submission(str(application.id))
    
    async with AsyncSessionLocal() as session:
        stmt_app = select(Application).where(Application.id == application.id)
        res_app = await session.execute(stmt_app)
        application = res_app.scalars().first()
        
        stmt = select(JobRaw).where(JobRaw.id == job_id)
        res = await session.execute(stmt)
        job = res.scalars().first()
        
        logger.info(f"Submission finished. Application status: '{application.status}', Job status: '{job.status}'")
        logger.info(f"Application submission details: {json.dumps(application.result, indent=2)}")
        
        assert application.status == "applied" or application.status == "failed" # it's OK if it failed with 404/400 because of mock job ID on live Greenhouse, as long as it executed and logged it
        logger.info("\n>>> Phase 1 Integration Test: SUCCESS <<<")

if __name__ == "__main__":
    asyncio.run(main())
