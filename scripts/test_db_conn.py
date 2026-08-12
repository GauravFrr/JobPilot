import os
import sys
import asyncio
import logging
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_db_conn")

# Add the api directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal

async def main():
    logger.info("Connecting to database...")
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully.")
            
            # Check if resume_profile table is present
            result = await session.execute(text("SELECT COUNT(*) FROM resume_profile"))
            count = result.scalar()
            logger.info(f"resume_profile table checked. Currently contains {count} rows.")
            
        except Exception as e:
            logger.error(f"Database verification failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
