import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_tier_c")

# Add the api directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.settings import TargetCompany
from app.models.jobs import JobRaw
from workers.discovery.tier_c_crawlers import resolve_careers_url, crawl_target_company, run_tier_c_crawl
from sqlalchemy import select

from app.models.applications import Application
from app.models.jobs import JobScore
from app.models.resumes import ResumeVersion
from app.models.contacts import Contact
from app.models.outreach import OutreachDraft
from sqlalchemy import delete

async def cleanup_test_jobs(session):
    """Clean up test jobs and all referencing child records."""
    stmt = select(JobRaw.id).where(JobRaw.is_test == True)
    res = await session.execute(stmt)
    test_ids = res.scalars().all()
    if test_ids:
        await session.execute(delete(Application).where(Application.job_id.in_(test_ids)))
        await session.execute(delete(JobScore).where(JobScore.job_id.in_(test_ids)))
        await session.execute(delete(ResumeVersion).where(ResumeVersion.job_id.in_(test_ids)))
        await session.execute(delete(Contact).where(Contact.job_id.in_(test_ids)))
        await session.execute(delete(OutreachDraft).where(OutreachDraft.job_id.in_(test_ids)))
        await session.execute(delete(JobRaw).where(JobRaw.id.in_(test_ids)))
        await session.commit()

async def test_resolver():
    logger.info("--- Testing Careers URL Resolver ---")
    url = await resolve_careers_url("Spektr", "spektr.com")
    logger.info(f"Spektr careers URL resolved to: {url}")
    assert "spektr" in url.lower()
    logger.info("Resolver test passed!")

async def test_crawler_greenhouse():
    logger.info("--- Testing Greenhouse Board Crawler (Spektr) ---")
    async with AsyncSessionLocal() as session:
        # Create a mock target company for Spektr
        company = TargetCompany(
            name="Spektr",
            domain="spektr.com",
            careers_url="https://www.spektr.com/careers",
            is_active=True
        )
        # We run it with is_test = True
        await crawl_target_company(company, is_test=True)
        
        # Verify in DB
        stmt = select(JobRaw).where(JobRaw.company == "Spektr", JobRaw.is_test == True)
        res = await session.execute(stmt)
        jobs = res.scalars().all()
        logger.info(f"Greenhouse crawl successful! Discovered {len(jobs)} test jobs in DB.")
        
        # Clean up test data
        await cleanup_test_jobs(session)
        logger.info("Cleaned up Greenhouse crawl test data.")

async def test_crawl_full_pipeline():
    logger.info("--- Testing Full Tier C pipeline run ---")
    # Run the daily crawler with is_test = True
    await run_tier_c_crawl(is_test=True)
    
    async with AsyncSessionLocal() as session:
        stmt = select(JobRaw).where(JobRaw.is_test == True)
        res = await session.execute(stmt)
        jobs = res.scalars().all()
        logger.info(f"Pipeline crawl successful! Discovered {len(jobs)} total test jobs in DB.")
        
        # Clean up test data
        await cleanup_test_jobs(session)
        logger.info("Cleaned up pipeline test data.")

async def main():
    await test_resolver()
    await test_crawler_greenhouse()
    await test_crawl_full_pipeline()

if __name__ == "__main__":
    asyncio.run(main())

