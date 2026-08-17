import os
import re
import time
import random
import logging
import asyncio
from typing import List, Dict, Any
from sqlalchemy import select, and_
from playwright.async_api import async_playwright

# Setup pythonpath imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw
from app.models.resumes import ResumeProfile
from workers.discovery.dedup import is_duplicate

logger = logging.getLogger("workers.discovery.tier_b_discovery")

async def get_target_roles() -> List[str]:
    """Retrieves target roles from the active resume profile."""
    async with AsyncSessionLocal() as session:
        stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
        result = await session.execute(stmt)
        profile = result.scalars().first()
        if profile and profile.content_json:
            return profile.content_json.get("target_roles", [])
    return ["Python Developer", "FastAPI Engineer", "AI Architect"]

async def fetch_linkedin_job_details(page, job_id: str) -> str:
    """Navigates to the public job view page and extracts the description_text in a logged-out state."""
    url = f"https://www.linkedin.com/jobs/view/{job_id}"
    logger.info(f"Fetching description for LinkedIn Job ID {job_id} from {url}...")
    try:
        await page.goto(url, timeout=20000)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        # Check for description container
        desc_selector = ".show-more-less-html__markup"
        desc_el = await page.query_selector(desc_selector)
        if not desc_el:
            # Fallback selectors
            for sel in [".description__text", ".jobs-box__html-content", ".job-description"]:
                desc_el = await page.query_selector(sel)
                if desc_el:
                    break
                    
        if desc_el:
            description_html = await desc_el.inner_html()
            return description_html.strip()
        else:
            logger.warning(f"Could not find description container for Job ID {job_id}.")
            return ""
    except Exception as e:
        logger.error(f"Error fetching job details for {job_id}: {str(e)}")
        return ""

async def discover_linkedin_jobs(is_test: bool = False):
    """Scrapes LinkedIn job listings in a logged-out state and fetches matching details."""
    logger.info("Starting logged-out LinkedIn discovery...")
    target_roles = await get_target_roles()
    if not target_roles:
        logger.info("No active target roles found. Skipping discovery.")
        return
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        discovered_jobs = []
        
        for role in target_roles:
            role_encoded = role.replace(" ", "%20")
            url = f"https://www.linkedin.com/jobs/search?keywords={role_encoded}&location=Remote&f_TPR=r86400"
            logger.info(f"Scraping listings from: {url}")
            
            try:
                await page.goto(url, timeout=30000)
                await asyncio.sleep(random.uniform(3.0, 5.0))
                
                # Extract job cards
                cards = await page.query_selector_all("li")
                for card in cards:
                    card_el = await card.query_selector("div[data-entity-urn]")
                    job_id = None
                    if card_el:
                        urn = await card_el.get_attribute("data-entity-urn")
                        if urn and "jobPosting" in urn:
                            job_id = urn.split(":")[-1]
                            
                    title_el = await card.query_selector(".base-search-card__title")
                    company_el = await card.query_selector(".base-search-card__subtitle")
                    link_el = await card.query_selector(".base-card__full-link")
                    
                    title = (await title_el.inner_text()).strip() if title_el else "Unknown Title"
                    company = (await company_el.inner_text()).strip() if company_el else "Unknown Company"
                    link = await link_el.get_attribute("href") if link_el else None
                    
                    if link and not link.startswith("http"):
                        link = "https://www.linkedin.com" + link
                        
                    if not job_id and link:
                        match = re.search(r"/view/.*-(\d+)", link)
                        if match:
                            job_id = match.group(1)
                            
                    if not job_id:
                        continue
                        
                    if not link:
                        link = f"https://www.linkedin.com/jobs/view/{job_id}"
                    
                    # Coarse relevance filter on title (Fix #1)
                    title_lower = title.lower()
                    if not any(kw in title_lower for kw in ["software", "engineer", "developer", "architect", "data", "ai", "ml", "fastapi", "python"]):
                        continue
                        
                    discovered_jobs.append({
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "url": link
                    })
            except Exception as e:
                logger.error(f"Error searching for role '{role}': {str(e)}")
                
        # Deduplicate job listings in search results
        unique_jobs = {j["job_id"]: j for j in discovered_jobs}.values()
        
        async with AsyncSessionLocal() as session:
            for job_info in unique_jobs:
                job_id = job_info["job_id"]
                
                # Check DB duplicate first before loading detail page
                stmt = select(JobRaw).where(
                    and_(
                        JobRaw.source == "linkedin",
                        JobRaw.source_job_id == job_id
                    )
                )
                res = await session.execute(stmt)
                existing = res.scalars().first()
                if existing:
                    if existing.is_test and not is_test:
                        # Convert test job to real job
                        existing.is_test = False
                        existing.title = job_info["title"]
                        existing.company = job_info["company"]
                        existing.source_url = job_info["url"]
                        await session.commit()
                        logger.info(f"Promoted test job {job_id} to real job.")
                    continue
                    
                # Fetch description (gated load)
                description = await fetch_linkedin_job_details(page, job_id)
                if not description:
                    continue
                    
                # Secondary duplicate check
                new_job_dict = {
                    "source": "linkedin",
                    "source_job_id": job_id,
                    "title": job_info["title"],
                    "company": job_info["company"],
                    "description_text": description,
                    "is_test": is_test
                }
                if await is_duplicate(session, new_job_dict):
                    continue
                    
                # Save to database
                new_job = JobRaw(
                    source=f"linkedin",
                    source_tier="B",
                    source_job_id=job_id,
                    source_url=job_info["url"],
                    company=job_info["company"],
                    title=job_info["title"],
                    description_text=description,
                    location="Remote",
                    is_remote=True,
                    raw_payload={
                        "job_id": job_id,
                        "title": job_info["title"],
                        "company": job_info["company"],
                        "url": job_info["url"]
                    },
                    status="discovered",
                    is_test=is_test
                )
                session.add(new_job)
                logger.info(f"✅ Discovered and saved job: {job_info['title']} at {job_info['company']} (Source ID: {job_id})")
                await session.commit()
                
        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode (mark jobs as is_test=True)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(discover_linkedin_jobs(is_test=args.test))
