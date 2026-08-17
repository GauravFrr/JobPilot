import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_weekly_digest")

# Add paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import AsyncSessionLocal
from workers.contacts.weekly_digest import calculate_weekly_metrics, send_weekly_digest

async def test_digest():
    logger.info("--- Testing Weekly Digest metrics calculation ---")
    metrics = await calculate_weekly_metrics()
    logger.info(f"Calculated weekly metrics: {metrics}")
    assert "discovered" in metrics
    assert "matched" in metrics
    assert "ready" in metrics
    assert "applied" in metrics
    assert "contacts" in metrics
    
    logger.info("--- Testing Redis message dispatching ---")
    await send_weekly_digest()
    logger.info("Weekly digest test run complete successfully!")

if __name__ == "__main__":
    asyncio.run(test_digest())
