import os
import sys
import json
import asyncio
import logging
from sqlalchemy import select

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_target_companies")

# Add the api directory to the Python path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db import AsyncSessionLocal
from app.models.settings import TargetCompany

async def main():
    json_path = os.path.join(os.path.dirname(__file__), "target_companies.json")
    if not os.path.exists(json_path):
        logger.error(f"Could not find target companies JSON at {json_path}")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        companies_data = json.load(f)
        
    async with AsyncSessionLocal() as session:
        for c_data in companies_data:
            name = c_data.get("name")
            domain = c_data.get("domain")
            
            # Check if company already exists
            stmt = select(TargetCompany).where(TargetCompany.name == name)
            res = await session.execute(stmt)
            existing = res.scalars().first()
            
            if existing:
                logger.info(f"Company '{name}' already exists in DB. Skipping.")
                continue
                
            # Create new target company
            company = TargetCompany(
                name=name,
                domain=domain,
                is_active=True
            )
            session.add(company)
            logger.info(f"Adding company '{name}' (domain: {domain}) to seed.")
            
        await session.commit()
        logger.info("Target companies seeding complete!")

if __name__ == "__main__":
    asyncio.run(main())
