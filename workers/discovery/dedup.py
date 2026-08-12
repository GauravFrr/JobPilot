import logging
from difflib import SequenceMatcher
from datetime import timedelta
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.jobs import JobRaw

logger = logging.getLogger("workers.discovery.dedup")

import re

def clean_title(title: str) -> str:
    """Cleans a job title by removing common non-content keywords and characters."""
    t = title.lower()
    # Remove common suffixes/adjectives
    t = re.sub(r'\(remote\)|remote|contract|full-time|part-time|hybrid|on-site', '', t)
    # Remove non-alphanumeric characters
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    # Normalize spacing
    return " ".join(t.split())

def get_title_similarity(title1: str, title2: str) -> float:
    """Computes similarity ratio between two job titles using SequenceMatcher."""
    t1 = clean_title(title1)
    t2 = clean_title(title2)
    return SequenceMatcher(None, t1, t2).ratio()

async def is_duplicate(session: AsyncSession, new_job: dict) -> bool:
    """
    Checks if a job is a duplicate in the database.
    1. Uniqueness check: (source, source_job_id) - Database has UNIQUE constraint, but we check first.
    2. Fuzzy check: Same company, similar title (>=85%), and posted within +/- 3 days of existing job.
    """
    # 1. Uniqueness check
    if new_job.get("source_job_id"):
        stmt = select(JobRaw).where(
            and_(
                JobRaw.source == new_job["source"],
                JobRaw.source_job_id == str(new_job["source_job_id"])
            )
        )
        result = await session.execute(stmt)
        if result.scalars().first():
            logger.debug(f"Duplicate found by unique source/id: {new_job['source']}/{new_job['source_job_id']}")
            return True

    # 2. Fuzzy secondary check (Same company, close dates)
    # If no posted date is available, we use discovered_at date
    posted_date = new_job.get("posted_date")
    if not posted_date:
        posted_date = new_job.get("discovered_at")
        if posted_date and hasattr(posted_date, "date"):
            posted_date = posted_date.date()
        else:
            from datetime import date
            posted_date = date.today()

    # Query for jobs from the same company posted within 3 days
    start_date = posted_date - timedelta(days=3)
    end_date = posted_date + timedelta(days=3)
    
    # We strip company name for search
    company_name = new_job["company"].strip().lower()
    
    stmt = select(JobRaw).where(
        and_(
            func_lower_company(JobRaw.company) == company_name,
            or_(
                JobRaw.posted_date.between(start_date, end_date),
                # If existing job has no posted date, match close to discovered_at
                and_(JobRaw.posted_date == None, JobRaw.discovered_at.between(
                    # timezone aware or naive depending on database setup - Alembic defines timezone=True
                    # We compare dates to be safe
                    start_date, end_date
                ))
            )
        )
    )
    
    result = await session.execute(stmt)
    existing_jobs = result.scalars().all()
    
    for ext_job in existing_jobs:
        similarity = get_title_similarity(new_job["title"], ext_job.title)
        if similarity >= 0.85:
            logger.info(
                f"Fuzzy duplicate detected: '{new_job['title']}' at '{new_job['company']}' "
                f"matches existing '{ext_job.title}' (similarity: {similarity:.2f})"
            )
            return True
            
    return False

def func_lower_company(col):
    """Helper to lower company name since sqlalchemy func.lower is standard."""
    from sqlalchemy import func
    return func.lower(col)
