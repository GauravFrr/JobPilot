import re
import httpx
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models.resumes import ResumeProfile
from app.models.settings import DorkQuery
from workers.discovery.tier_a_apis import fetch_greenhouse_job, fetch_lever_job

logger = logging.getLogger("workers.discovery.dork_search")

# Regex to extract Greenhouse / Lever info
GREENHOUSE_RE = re.compile(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)")
LEVER_RE = re.compile(r"jobs\.lever\.co/([^/]+)/([a-zA-Z0-9\-]+)")

async def get_target_roles() -> List[str]:
    """Retrieves target roles from the active resume profile."""
    async with AsyncSessionLocal() as session:
        stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
        result = await session.execute(stmt)
        profile = result.scalars().first()
        if profile and profile.content_json:
            return profile.content_json.get("target_roles", [])
    return []

async def get_active_dork_templates() -> List[str]:
    """Retrieves active dork query templates from database."""
    async with AsyncSessionLocal() as session:
        stmt = select(DorkQuery).where(DorkQuery.is_active == True)
        result = await session.execute(stmt)
        queries = result.scalars().all()
        if queries:
            return [q.query_template for q in queries]
    # Return defaults if database is empty
    return [
        'site:boards.greenhouse.io "{role}" remote',
        'site:jobs.lever.co "{role}" remote'
    ]

async def execute_google_search(query: str, api_key: str, cx: str) -> List[Dict[str, Any]]:
    """Runs a search query on Google Custom Search API."""
    url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 10 # get top 10 results
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Running Google Custom Search for: {query}")
            response = await client.get(url, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(f"Google Search API returned {response.status_code}: {response.text}")
                return []
                
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Google Search API error: {str(e)}")
            return []

async def execute_serper_search(query: str, api_key: str) -> List[Dict[str, Any]]:
    """Runs a search query on Serper.dev API (Google Search scraper)."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Running Serper.dev Google Search for: {query}")
            response = await client.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Serper API returned {response.status_code}: {response.text}")
                return []
            data = response.json()
            return data.get("organic", [])
        except Exception as e:
            logger.error(f"Serper API error: {str(e)}")
            return []


async def parse_dork_result(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parses a single Google Custom Search item and normalizes or routes it."""
    link = item.get("link", "")
    title = item.get("title", "Unknown")
    snippet = item.get("snippet", "")
    
    # 1. Check for Greenhouse
    gh_match = GREENHOUSE_RE.search(link)
    if gh_match:
        company_token = gh_match.group(1)
        job_id = gh_match.group(2)
        try:
            job_details = await fetch_greenhouse_job(company_token, job_id)
            if job_details:
                job_details["source"] = f"dork:greenhouse:{company_token}"
                return job_details
        except Exception as e:
            logger.error(f"Error fetching greenhouse dork job details: {str(e)}")
            
    # 2. Check for Lever
    lever_match = LEVER_RE.search(link)
    if lever_match:
        company_token = lever_match.group(1)
        job_id = lever_match.group(2)
        try:
            job_details = await fetch_lever_job(company_token, job_id)
            if job_details:
                job_details["source"] = f"dork:lever:{company_token}"
                return job_details
        except Exception as e:
            logger.error(f"Error fetching lever dork job details: {str(e)}")
            
    # 3. Check for Tier B platforms (LinkedIn, Naukri, Wellfound, Instahyre) -> Save as Tier D leads
    is_tier_b_link = any(domain in link for domain in ["linkedin.com/jobs", "naukri.com", "wellfound.com/jobs", "instahyre.com"])
    if is_tier_b_link:
        # Parse title and company from title if possible (e.g. "Software Engineer at Acme")
        company = "Unknown"
        job_title = title
        if " at " in title:
            job_title, company_part = title.split(" at ", 1)
            company = company_part.split("|")[0].split("-")[0].strip()
            job_title = job_title.strip()
            
        logger.info(f"Discovered Tier B link via dork, logging as Tier D lead: {link}")
        return {
            "source": f"dork:lead:{link.split('/')[2]}", # e.g. dork:lead:linkedin.com
            "source_tier": "D",
            "source_job_id": link, # use link as id since no separate ID is scraped
            "source_url": link,
            "company": company,
            "title": job_title,
            "description_text": f"Discovered via search dork.\nSnippet: {snippet}",
            "location": "Remote",
            "is_remote": True,
            "posted_date": None,
            "raw_payload": item,
            "status": "discovered"
        }
        
    return None

async def run_dork_search(api_key: str, cx: str = None) -> List[Dict[str, Any]]:
    """Runs dork search queries for all target roles and template dorks, returning normalized jobs."""
    roles = await get_target_roles()
    templates = await get_active_dork_templates()
    
    if not roles:
        logger.warning("No target roles found in active resume profile. Skipping dork search.")
        return []
        
    discovered_jobs = []
    
    for role in roles:
        for template in templates:
            query = template.format(role=role)
            # Route search query depending on whether CX is present
            if cx:
                items = await execute_google_search(query, api_key, cx)
            else:
                items = await execute_serper_search(query, api_key)
            
            for item in items:
                try:
                    job = await parse_dork_result(item)
                    if job:
                        discovered_jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing dork item {item.get('link')}: {str(e)}")
                    
    return discovered_jobs

