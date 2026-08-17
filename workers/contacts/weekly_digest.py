import os
import sys
import json
import logging
import asyncio
import redis.asyncio as aioredis
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func

# Add the api directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.config import settings
from app.models.jobs import JobRaw, JobScore
from app.models.applications import Application
from app.models.contacts import Contact
from app.models.settings import Setting

logger = logging.getLogger("workers.contacts.weekly_digest")

async def get_setting_value(session, key: str, default):
    stmt = select(Setting).where(Setting.key == key)
    res = await session.execute(stmt)
    s = res.scalars().first()
    return s.value if s else default

async def calculate_weekly_metrics() -> dict:
    """Calculates application and discovery metrics for the last 7 days."""
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)
    
    async with AsyncSessionLocal() as session:
        # Get match threshold
        min_score = await get_setting_value(session, "min_match_score", 70.0)
        
        # 1. Discovered Jobs Count (non-test only)
        stmt_discovered = select(func.count(JobRaw.id)).where(
            JobRaw.discovered_at >= one_week_ago,
            JobRaw.is_test == False
        )
        res = await session.execute(stmt_discovered)
        discovered_count = res.scalar() or 0
        
        # 2. Matched Jobs Count
        stmt_matched = select(func.count(JobScore.id)).where(
            JobScore.scored_at >= one_week_ago,
            JobScore.final_score >= min_score
        )
        res = await session.execute(stmt_matched)
        matched_count = res.scalar() or 0
        
        # 3. Ready to Apply Count
        stmt_ready = select(func.count(Application.id)).where(
            Application.created_at >= one_week_ago,
            Application.status == "ready_to_apply"
        )
        res = await session.execute(stmt_ready)
        ready_count = res.scalar() or 0
        
        # 4. Applied Count
        stmt_applied = select(func.count(Application.id)).where(
            Application.created_at >= one_week_ago,
            Application.status == "applied"
        )
        res = await session.execute(stmt_applied)
        applied_count = res.scalar() or 0
        
        # 5. Contacts Found
        stmt_contacts = select(func.count(Contact.id)).where(
            Contact.found_at >= one_week_ago
        )
        res = await session.execute(stmt_contacts)
        contacts_count = res.scalar() or 0
        
        logger.info(
            f"Calculated weekly metrics: discovered={discovered_count}, matched={matched_count}, "
            f"ready={ready_count}, applied={applied_count}, contacts={contacts_count}"
        )
        
        return {
            "discovered": discovered_count,
            "matched": matched_count,
            "ready": ready_count,
            "applied": applied_count,
            "contacts": contacts_count
        }

async def send_weekly_digest():
    """Calculates weekly metrics and publishes a notification event to Redis."""
    try:
        metrics = await calculate_weekly_metrics()
        
        redis_client = aioredis.from_url(settings.redis_url)
        event = {
            "event_type": "weekly_summary",
            "job_id": None,
            "payload": metrics
        }
        
        await redis_client.publish("jobpilot:events", json.dumps(event))
        await redis_client.close()
        logger.info("Successfully published weekly digest event to Redis.")
    except Exception as e:
        logger.error(f"Failed to generate and send weekly digest: {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(send_weekly_digest())
