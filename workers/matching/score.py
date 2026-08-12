import os
import sys
import logging
import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

# Add api folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw, JobScore
from app.models.resumes import ResumeProfile
from app.models.settings import Setting

from workers.matching.embed import get_job_description_embedding
from workers.matching.rerank import get_llm_rerank_score

logger = logging.getLogger("workers.matching.score")

# Simple title blocklist to avoid obvious mismatches for 2-3 years experience
TITLE_BLOCKLIST = [
    "director", "vice president", "vp", "head of", "principal", 
    "staff", "senior staff", "lead", "manager", "architect"
]

def check_title_blocklist(title: str) -> bool:
    """Returns True if the title contains blocklisted keywords, indicating a mismatch."""
    t = title.lower()
    for word in TITLE_BLOCKLIST:
        # Check for word boundaries where possible or exact substrings
        if word in t:
            logger.info(f"Title '{title}' blocked by keyword '{word}'")
            return True
    return False

def check_location_preference(job: JobRaw) -> bool:
    """Returns True if the job matches remote preference."""
    # Since JobPilot is remote-first, if it's explicitly marked not remote, we reject
    if job.is_remote is False:
        logger.info(f"Job rejected: not remote.")
        return False
    return True

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

async def get_min_match_score(session: AsyncSession) -> float:
    """Retrieves min_match_score from settings, defaulting to 70."""
    stmt = select(Setting).where(Setting.key == "min_match_score")
    result = await session.execute(stmt)
    setting = result.scalars().first()
    if setting and setting.value:
        # value is stored as JSONB, e.g. {"value": 70} or raw integer
        if isinstance(setting.value, dict):
            return float(setting.value.get("value", 70.0))
        return float(setting.value)
    return 70.0

async def process_matching_for_job(job_id: str) -> Optional[JobScore]:
    """Runs the 3-stage matching pipeline for a job by ID."""
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch job and active profile
            stmt = select(JobRaw).where(JobRaw.id == job_id)
            result = await session.execute(stmt)
            job = result.scalars().first()
            if not job or job.status != "discovered":
                return None
                
            stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
            result = await session.execute(stmt)
            profile = result.scalars().first()
            if not profile:
                logger.error("No active resume profile found. Cannot score job.")
                return None
                
            # Stage 1: Cheap filters
            if not check_location_preference(job):
                # Mark discarded immediately
                job.status = "discarded"
                await session.commit()
                return None
                
            if check_title_blocklist(job.title):
                job.status = "discarded"
                # Save a 0-score record to database to log the discard rationale
                score_rec = JobScore(
                    job_id=job.id,
                    resume_profile_version=profile.version,
                    embedding_score=0.0,
                    final_score=0.0,
                    rationale=f"Rejected in Stage 1: Title contains blocked keyword."
                )
                session.add(score_rec)
                await session.commit()
                return score_rec

            # Stage 2: Embedding Similarity
            job_emb = await get_job_description_embedding(job.title, job.description_text)
            similarity = cosine_similarity(job_emb, profile.embedding)
            
            # Map similarity (-1 to 1) or (0 to 1) to 0-100 score
            # Cosine similarity is usually positive for embeddings, map 0-1 to 0-100 directly
            emb_score = max(0.0, min(100.0, similarity * 100.0))
            
            final_score = emb_score
            llm_rerank_score = None
            rationale = "Scored via vector embedding similarity."
            
            # Stage 3: LLM Rerank (for middle-band scores, e.g. 60 to 80)
            # Below 60 is definitely low match, above 80 is high match
            if 60.0 <= emb_score <= 80.0:
                logger.info(f"Embedding score {emb_score:.2f} is in middle-band. Triggering LLM rerank...")
                llm_score, llm_rationale = await get_llm_rerank_score(
                    job.title, 
                    job.description_text, 
                    profile.content_json
                )
                llm_rerank_score = llm_score
                final_score = llm_score
                rationale = f"LLM Reranked. Rationale: {llm_rationale}"
            
            # 4. Save score record
            score_rec = JobScore(
                job_id=job.id,
                resume_profile_version=profile.version,
                embedding_score=emb_score,
                llm_rerank_score=llm_rerank_score,
                final_score=final_score,
                rationale=rationale
            )
            session.add(score_rec)
            
            # 5. Update job status
            min_score = await get_min_match_score(session)
            if final_score >= min_score:
                job.status = "matched"
                logger.info(f"Job {job.title} matched with score {final_score:.2f} (threshold: {min_score})")
            else:
                job.status = "discarded"
                logger.info(f"Job {job.title} discarded with score {final_score:.2f} (threshold: {min_score})")
                
            await session.commit()
            return score_rec
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error matching job {job_id}: {str(e)}")
            return None
