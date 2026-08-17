import os
import sys
import re
import json
import logging
import asyncio
import random
import httpx
from datetime import datetime, date
from typing import Any
from sqlalchemy import select, update
from playwright.async_api import async_playwright

# Add the api directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.settings import TargetCompany
from app.models.jobs import JobRaw
from workers.discovery.dedup import is_duplicate
from workers.discovery.dork_search import execute_serper_search
from workers.llm import provider

logger = logging.getLogger("workers.discovery.tier_c_crawlers")

# Standard headers to bypass basic blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_date(date_str: Any) -> date:
    """Safely parse ISO date strings, timestamps or returns date.today() on failure."""
    if not date_str:
        return date.today()
        
    if isinstance(date_str, (int, float)):
        if date_str > 1e11:
            date_str = date_str / 1000.0
        try:
            return datetime.fromtimestamp(date_str).date()
        except Exception:
            return date.today()
            
    if isinstance(date_str, str):
        if date_str.isdigit():
            try:
                val = float(date_str)
                if val > 1e11:
                    val = val / 1000.0
                return datetime.fromtimestamp(val).date()
            except Exception:
                pass
                
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
    return date.today()

# Programmatic ATS board fetchers
async def fetch_greenhouse_board(company_token: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs?content=true"
    logger.info(f"Fetching Greenhouse board jobs for: {company_token}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Greenhouse board fetch failed ({response.status_code}) for token: {company_token}")
                return []
            data = response.json()
            jobs = data.get("jobs", [])
            normalized = []
            for job in jobs:
                job_id = str(job.get("id"))
                title = job.get("title", "Unknown")
                desc = job.get("content", "")
                location = job.get("location", {}).get("name", "")
                is_remote = "remote" in location.lower() or "remote" in title.lower()
                normalized.append({
                    "source": f"greenhouse:{company_token}",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": job.get("absolute_url"),
                    "company": company_token.capitalize(),
                    "title": title,
                    "description_text": desc,
                    "location": location,
                    "is_remote": is_remote,
                    "posted_date": date.today(),
                    "raw_payload": job
                })
            return normalized
        except Exception as e:
            logger.error(f"Greenhouse board fetch error for {company_token}: {str(e)}")
            return []

async def fetch_lever_board(company_token: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"
    logger.info(f"Fetching Lever board postings for: {company_token}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Lever board fetch failed ({response.status_code}) for token: {company_token}")
                return []
            jobs = response.json()
            if not isinstance(jobs, list):
                return []
            normalized = []
            for job in jobs:
                job_id = str(job.get("id"))
                title = job.get("text", "Unknown")
                desc = job.get("descriptionPlain", "") + "\n" + "\n".join(
                    [list(item.values())[0] if isinstance(item, dict) else str(item) for item in job.get("lists", [])]
                )
                categories = job.get("categories", {})
                location = categories.get("location", "")
                is_remote = categories.get("commitment") == "Remote" or "remote" in location.lower() or "remote" in title.lower()
                normalized.append({
                    "source": f"lever:{company_token}",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": job.get("hostedUrl"),
                    "company": company_token.capitalize(),
                    "title": title,
                    "description_text": desc,
                    "location": location,
                    "is_remote": is_remote,
                    "posted_date": date.today(),
                    "raw_payload": job
                })
            return normalized
        except Exception as e:
            logger.error(f"Lever board fetch error for {company_token}: {str(e)}")
            return []

async def fetch_ashby_board(company_token: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/v1/iframe/{company_token}/listings"
    logger.info(f"Fetching Ashby board listings for: {company_token}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Ashby board fetch failed ({response.status_code}) for token: {company_token}")
                return []
            data = response.json()
            jobs = data.get("jobs", [])
            normalized = []
            for job in jobs:
                job_id = str(job.get("id"))
                title = job.get("title", "Unknown")
                desc = job.get("descriptionHtml", job.get("description", ""))
                location = job.get("location", "")
                is_remote = job.get("isRemote", False) or "remote" in location.lower() or "remote" in title.lower()
                normalized.append({
                    "source": f"ashby:{company_token}",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": job.get("jobUrl"),
                    "company": company_token.capitalize(),
                    "title": title,
                    "description_text": desc,
                    "location": location,
                    "is_remote": is_remote,
                    "posted_date": date.today(),
                    "raw_payload": job
                })
            return normalized
        except Exception as e:
            logger.error(f"Ashby board fetch error for {company_token}: {str(e)}")
            return []


# Task 2: Careers URL Resolver
async def resolve_careers_url(company_name: str, domain: str) -> str:
    """Attempts to guess the careers page URL or falls back to Google dork search."""
    logger.info(f"Resolving careers URL for {company_name} (domain: {domain})...")
    
    # Guess subpaths first
    subpaths = ["/careers", "/jobs", "/join-us", "/join", "/careers-portal", "/about/careers"]
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for path in subpaths:
            candidate_url = f"https://{domain}{path}"
            try:
                # Use a fast HEAD request first
                r = await client.head(candidate_url, timeout=5)
                if r.status_code == 200:
                    logger.info(f"Resolved careers URL by guessing: {candidate_url}")
                    return candidate_url
            except Exception:
                continue

    # Fallback to Serper.dev Google search dork
    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    if api_key:
        query = f"site:{domain} careers OR jobs"
        logger.info(f"Guessing failed. Querying Serper fallback for {domain}...")
        results = await execute_serper_search(query, api_key)
        
        # Look for the first link matching the target domain
        for item in results:
            link = item.get("link", "")
            if domain.lower() in link.lower() and not link.endswith(domain):
                logger.info(f"Resolved careers URL via Serper fallback search: {link}")
                return link
                
    # Ultimate fallback is the main domain homepage
    fallback = f"https://{domain}"
    logger.warning(f"Could not resolve careers page for {company_name}. Using homepage fallback: {fallback}")
    return fallback


# Main crawling logic per company
async def crawl_target_company(company: TargetCompany, is_test: bool = False):
    """Executes crawler logic for a single target company with concurrency limits."""
    logger.info(f"Starting crawl for target company: {company.name}")
    
    async with AsyncSessionLocal() as session:
        # Step 1: Resolve careers URL if missing
        if not company.careers_url:
            resolved_url = await resolve_careers_url(company.name, company.domain)
            # Re-fetch company object within this session to update it
            stmt = select(TargetCompany).where(TargetCompany.id == company.id)
            res = await session.execute(stmt)
            db_company = res.scalars().first()
            if db_company:
                db_company.careers_url = resolved_url
                await session.commit()
                company.careers_url = resolved_url

        # Fetch the resolved career page text to look for ATS tokens
        page_html = ""
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=10) as client:
                r = await client.get(company.careers_url)
                if r.status_code == 200:
                    page_html = r.text
        except Exception as e:
            logger.warning(f"Basic HTTP fetch failed for {company.careers_url}: {str(e)}")

        # Step 2 & 3: ATS Fingerprint detection
        detected_ats = None
        ats_token = None
        
        # Greenhouse
        gh_match = re.search(r"boards\.greenhouse\.io/([^/\"\'\?\s]+)", page_html)
        if gh_match:
            detected_ats = "greenhouse"
            ats_token = gh_match.group(1)
        else:
            gh_embed_match = re.search(r"board=([^/\"\'\&\s]+)", page_html)
            if gh_embed_match and ("greenhouse" in page_html.lower() or "grnh" in page_html.lower()):
                detected_ats = "greenhouse"
                ats_token = gh_embed_match.group(1)
                
        # Lever
        if not detected_ats:
            lever_match = re.search(r"jobs\.lever\.co/([^/\"\'\?\s]+)", page_html)
            if lever_match:
                detected_ats = "lever"
                ats_token = lever_match.group(1)
                
        # Ashby
        if not detected_ats:
            ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/\"\'\?\s]+)", page_html)
            if ashby_match:
                detected_ats = "ashby"
                ats_token = ashby_match.group(1)

        # Update detected ATS on target company
        if detected_ats:
            logger.info(f"ATS fingerprint '{detected_ats}' detected for {company.name} with token '{ats_token}'")
            stmt = select(TargetCompany).where(TargetCompany.id == company.id)
            res = await session.execute(stmt)
            db_company = res.scalars().first()
            if db_company:
                db_company.detected_ats = detected_ats
                db_company.last_crawled_at = datetime.now()
                await session.commit()
            
            # Fetch postings programmatically from the ATS API (Tier A)
            jobs = []
            if detected_ats == "greenhouse":
                jobs = await fetch_greenhouse_board(ats_token)
            elif detected_ats == "lever":
                jobs = await fetch_lever_board(ats_token)
            elif detected_ats == "ashby":
                jobs = await fetch_ashby_board(ats_token)
                
            # Ingest to DB
            if jobs:
                for job in jobs:
                    job["is_test"] = is_test
                    if await is_duplicate(session, job):
                        continue
                    db_job = JobRaw(
                        source=job["source"],
                        source_tier=job["source_tier"],
                        source_job_id=job["source_job_id"],
                        source_url=job["source_url"],
                        company=company.name, # Use standard target company name
                        title=job["title"],
                        description_text=job["description_text"],
                        location=job["location"],
                        is_remote=job["is_remote"],
                        posted_date=job["posted_date"],
                        raw_payload=job["raw_payload"],
                        status="discovered",
                        is_test=is_test
                    )
                    session.add(db_job)
                    logger.info(f"✅ Programmatic ATS crawler matching Tier A: {job['title']} at {company.name}")
                await session.commit()
                return
            else:
                logger.warning(f"Programmatic ATS board API fetch failed or returned 0 results for {company.name}. Falling back to custom page Playwright/LLM scraper.")

        # Step 4 & 5: LLM Custom Page listings extraction
        logger.info(f"No ATS detected for {company.name}. Fetching page DOM text via Playwright...")
        
        page_text = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(user_agent=HEADERS["User-Agent"])
            page = await context.new_page()
            try:
                await page.goto(company.careers_url, timeout=30000, wait_until="networkidle")
                await asyncio.sleep(3)
                page_text = await page.evaluate("() => document.body.innerText")
            except Exception as e:
                logger.error(f"Playwright rendering failed for {company.careers_url}: {str(e)}")
            finally:
                await browser.close()
                
        if not page_text or len(page_text.strip()) < 50:
            logger.warning(f"Could not extract meaningful text from {company.name} careers page. Skipping custom scrape.")
            return
            
        # Call Gemini cheap model to parse listings
        prompt = f"""
You are an expert job board scraper. You will extract open job listings from the raw text content of a company's career page.
Below is the text content of the career page:
---
{page_text}
---

Extract all active job postings from the text.
For each job, extract:
1. title: The job title (e.g. "Software Engineer").
2. description: A brief description or overview of the job.
3. location: The location (e.g. "Remote", "New York, NY").
4. job_url: The direct link to apply to this job if present in the text (otherwise construct one if it's based on an ID, or use the careers page URL as a fallback).
5. apply_method: Classify the application method as "simple_form" (direct simple form on page asking for name/email/resume) or "complex" (redirects to lever/greenhouse/another site, or requires registration/login, or has extensive multi-step forms, or asks to apply via email).

Return the results ONLY as a valid JSON list of objects. Do not wrap in markdown or block codes.
Example output format:
[
  {{
    "title": "AI Engineer",
    "description": "Building RAG systems...",
    "location": "Remote",
    "job_url": "https://company.com/jobs/123",
    "apply_method": "simple_form"
  }}
]
"""
        logger.info(f"Querying Gemini flash-lite to extract custom listings for {company.name}...")
        try:
            resp = await provider.generate(prompt, "tier_c_custom_parse", "cheap")
            clean_resp = resp.strip()
            # Clean markdown code blocks if any
            if clean_resp.startswith("```"):
                lines = clean_resp.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_resp = "\n".join(lines).strip()
                
            jobs = json.loads(clean_resp)
            if not isinstance(jobs, list):
                logger.error(f"Parsed JSON from Gemini is not a list: {type(jobs)}")
                return
                
            for j in jobs:
                title = j.get("title", "Unknown")
                desc = j.get("description", "")
                loc = j.get("location", "Remote")
                j_url = j.get("job_url") or company.careers_url
                apply_method = j.get("apply_method", "complex")
                
                # Classify source tier based on apply method
                source_tier = "B" if apply_method == "simple_form" else "D"
                is_remote = "remote" in loc.lower() or "remote" in title.lower()
                
                job_dict = {
                    "source": f"careers:{company.name.lower()}",
                    "source_job_id": j_url,
                    "title": title,
                    "company": company.name,
                    "posted_date": date.today(),
                    "is_test": is_test
                }
                
                if await is_duplicate(session, job_dict):
                    continue
                    
                db_job = JobRaw(
                    source=job_dict["source"],
                    source_tier=source_tier,
                    source_job_id=j_url,
                    source_url=j_url,
                    company=company.name,
                    title=title,
                    description_text=desc,
                    location=loc,
                    is_remote=is_remote,
                    posted_date=date.today(),
                    raw_payload=j,
                    status="discovered",
                    is_test=is_test
                )
                session.add(db_job)
                logger.info(f"✅ Custom Playwright/LLM crawler matching Tier {source_tier}: {title} at {company.name}")
            
            # Update last_crawled_at
            stmt = select(TargetCompany).where(TargetCompany.id == company.id)
            res = await session.execute(stmt)
            db_company = res.scalars().first()
            if db_company:
                db_company.last_crawled_at = datetime.now()
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Failed to scrape custom career page for {company.name}: {str(e)}")


async def run_tier_c_crawl(is_test: bool = False):
    """Executes the daily crawl loop for all active target companies, limiting concurrency to 2."""
    logger.info("Starting Tier C Career Page Crawl pipeline...")
    
    async with AsyncSessionLocal() as session:
        stmt = select(TargetCompany).where(TargetCompany.is_active == True)
        res = await session.execute(stmt)
        companies = res.scalars().all()
        
    if not companies:
        logger.info("No active target companies to crawl.")
        return
        
    logger.info(f"Found {len(companies)} active target companies to crawl. Limiting concurrency to 2.")
    
    # Use a Semaphore to enforce maximum concurrency of 2 Playwright sessions
    sem = asyncio.Semaphore(2)
    
    async def worker(company):
        async with sem:
            # Stagger startup randomly to prevent hitting platforms simultaneously
            await asyncio.sleep(random.uniform(1.0, 5.0))
            try:
                await crawl_target_company(company, is_test)
            except Exception as e:
                logger.error(f"Error crawling company {company.name}: {str(e)}")
                
    tasks = [worker(c) for c in companies]
    await asyncio.gather(*tasks)
    logger.info("Tier C Career Page Crawl pipeline completed successfully!")
