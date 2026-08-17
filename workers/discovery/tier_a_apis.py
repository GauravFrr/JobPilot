import httpx
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import List, Dict, Any, Optional

logger = logging.getLogger("workers.discovery.tier_a_apis")

# HTTP headers to prevent getting blocked
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_date(date_str: Any) -> Optional[date]:
    """Tries to parse date from string, numeric timestamp or returns None."""
    if not date_str:
        return None
        
    if isinstance(date_str, (int, float)):
        if date_str > 1e11:
            date_str = date_str / 1000.0
        try:
            return datetime.fromtimestamp(date_str).date()
        except Exception:
            return None
            
    if isinstance(date_str, str):
        if date_str.isdigit():
            try:
                val = float(date_str)
                if val > 1e11:
                    val = val / 1000.0
                return datetime.fromtimestamp(val).date()
            except Exception:
                pass
                
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
    return None

async def fetch_remoteok_jobs() -> List[Dict[str, Any]]:
    """Polls the RemoteOK API and returns a list of normalized job postings."""
    url = "https://remoteok.com/api"
    logger.info("Polling RemoteOK API...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"RemoteOK API returned status code {response.status_code}")
                return []
            
            data = response.json()
            # RemoteOK returns a legal notice as the first item, skip it
            if isinstance(data, list) and len(data) > 1:
                raw_jobs = data[1:]
            else:
                raw_jobs = []
                
            normalized = []
            for job in raw_jobs:
                job_id = str(job.get("id"))
                normalized.append({
                    "source": "remoteok",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": job.get("url"),
                    "company": job.get("company", "Unknown"),
                    "title": job.get("position", "Unknown"),
                    "description_text": job.get("description", ""),
                    "location": job.get("location"),
                    "is_remote": True, # inherently remote
                    "posted_date": parse_date(job.get("date")),
                    "raw_payload": job,
                    "status": "discovered"
                })
            logger.info(f"Discovered {len(normalized)} jobs from RemoteOK.")
            return normalized
        except Exception as e:
            logger.error(f"Error fetching jobs from RemoteOK: {str(e)}")
            return []

async def fetch_wwr_jobs() -> List[Dict[str, Any]]:
    """Parses We Work Remotely RSS feed and returns normalized job postings."""
    url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    logger.info("Fetching We Work Remotely RSS feed...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"WWR RSS returned status code {response.status_code}")
                return []
            
            root = ET.fromstring(response.content)
            channel = root.find("channel")
            if channel is None:
                return []
                
            items = channel.findall("item")
            normalized = []
            for item in items:
                # WWR URL format: https://weworkremotely.com/remote-jobs/company-title-id
                source_url = item.find("link").text if item.find("link") is not None else ""
                job_id = source_url.split("/")[-1].split("-")[-1] if source_url else ""
                
                title_text = item.find("title").text if item.find("title") is not None else "Unknown"
                # Title format in RSS is usually: "Company: Position"
                if ":" in title_text:
                    company, title = title_text.split(":", 1)
                    company = company.strip()
                    title = title.strip()
                else:
                    company = "Unknown"
                    title = title_text.strip()
                    
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else None
                desc = item.find("description").text if item.find("description") is not None else ""
                
                normalized.append({
                    "source": "weworkremotely",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": source_url,
                    "company": company,
                    "title": title,
                    "description_text": desc,
                    "location": "Remote",
                    "is_remote": True,
                    "posted_date": parse_date(pub_date),
                    "raw_payload": {"title": title_text, "pubDate": pub_date, "description": desc},
                    "status": "discovered"
                })
            logger.info(f"Discovered {len(normalized)} jobs from We Work Remotely.")
            return normalized
        except Exception as e:
            logger.error(f"Error fetching jobs from WWR: {str(e)}")
            return []

async def fetch_remotive_jobs() -> List[Dict[str, Any]]:
    """Polls the Remotive API and returns normalized job postings."""
    url = "https://remotive.com/api/remote-jobs?category=software-development"
    logger.info("Polling Remotive API...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Remotive API returned status code {response.status_code}")
                return []
                
            data = response.json()
            raw_jobs = data.get("jobs", [])
            normalized = []
            for job in raw_jobs:
                job_id = str(job.get("id"))
                normalized.append({
                    "source": "remotive",
                    "source_tier": "A",
                    "source_job_id": job_id,
                    "source_url": job.get("url"),
                    "company": job.get("company_name", "Unknown"),
                    "title": job.get("title", "Unknown"),
                    "description_text": job.get("description", ""),
                    "location": job.get("candidate_required_location"),
                    "is_remote": True,
                    "posted_date": parse_date(job.get("publication_date")),
                    "raw_payload": job,
                    "status": "discovered"
                })
            logger.info(f"Discovered {len(normalized)} jobs from Remotive.")
            return normalized
        except Exception as e:
            logger.error(f"Error fetching jobs from Remotive: {str(e)}")
            return []

async def fetch_greenhouse_job(company_token: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Fetches details for a specific Greenhouse job and returns it in normalized schema."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs/{job_id}"
    logger.info(f"Fetching Greenhouse job details: {company_token}/{job_id}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Greenhouse job fetch failed with status {response.status_code}")
                return None
                
            job = response.json()
            title = job.get("title", "Unknown")
            desc = job.get("content", "") # Greenhouse API returns html in content
            
            # Extract remote from location/title/metadata
            location = job.get("location", {}).get("name", "")
            is_remote = "remote" in location.lower() or "remote" in title.lower()
            
            return {
                "source": f"greenhouse:{company_token}",
                "source_tier": "A",
                "source_job_id": str(job_id),
                "source_url": job.get("absolute_url"),
                "company": company_token.capitalize(), # API does not return company name, only board token
                "title": title,
                "description_text": desc,
                "location": location,
                "is_remote": is_remote,
                "posted_date": date.today(), # API doesn't return publish date directly, default to today
                "raw_payload": job,
                "status": "discovered"
            }
        except Exception as e:
            logger.error(f"Error fetching Greenhouse job: {str(e)}")
            return None

async def fetch_lever_job(company_token: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Fetches details for a specific Lever job and returns it in normalized schema."""
    url = f"https://api.lever.co/v0/postings/{company_token}/{job_id}"
    logger.info(f"Fetching Lever job details: {company_token}/{job_id}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Lever job fetch failed with status {response.status_code}")
                return None
                
            job = response.json()
            title = job.get("text", "Unknown")
            desc = job.get("descriptionHtml", "") + "\n" + "\n".join(
                [list(item.values())[0] if isinstance(item, dict) else str(item) for item in job.get("lists", [])]
            )
            
            # Lever remote flag
            categories = job.get("categories", {})
            location = categories.get("location", "")
            is_remote = categories.get("commitment") == "Remote" or "remote" in location.lower() or "remote" in title.lower()
            
            return {
                "source": f"lever:{company_token}",
                "source_tier": "A",
                "source_job_id": str(job_id),
                "source_url": job.get("hostedUrl"),
                "company": company_token.capitalize(),
                "title": title,
                "description_text": desc,
                "location": location,
                "is_remote": is_remote,
                "posted_date": parse_date(job.get("createdAt")),
                "raw_payload": job,
                "status": "discovered"
            }
        except Exception as e:
            logger.error(f"Error fetching Lever job: {str(e)}")
            return None

async def fetch_greenhouse_board(company_token: str) -> List[Dict[str, Any]]:
    """Fetches all jobs from a company's Greenhouse board and returns them normalized."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs?content=true"
    logger.info(f"Fetching all Greenhouse board jobs for: {company_token}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Greenhouse board fetch failed with status {response.status_code}")
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
                    "posted_date": parse_date(job.get("updated_at")) or date.today(),
                    "raw_payload": job,
                    "status": "discovered"
                })
            logger.info(f"Discovered {len(normalized)} jobs from Greenhouse board '{company_token}'.")
            return normalized
        except Exception as e:
            logger.error(f"Error fetching Greenhouse board {company_token}: {str(e)}")
            return []

async def fetch_lever_board(company_token: str) -> List[Dict[str, Any]]:
    """Fetches all postings from a company's Lever board and returns them normalized."""
    url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"
    logger.info(f"Fetching all Lever board jobs for: {company_token}...")
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url, timeout=15)
            if response.status_code != 200:
                logger.error(f"Lever board fetch failed with status {response.status_code}")
                return []
                
            jobs = response.json()
            if not isinstance(jobs, list):
                logger.error(f"Expected list from Lever board API, got {type(jobs)}")
                return []
                
            normalized = []
            for job in jobs:
                job_id = str(job.get("id"))
                title = job.get("text", "Unknown")
                
                # Build description from plain text representation
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
                    "posted_date": parse_date(job.get("createdAt")),
                    "raw_payload": job,
                    "status": "discovered"
                })
            logger.info(f"Discovered {len(normalized)} jobs from Lever board '{company_token}'.")
            return normalized
        except Exception as e:
            logger.error(f"Error fetching Lever board {company_token}: {str(e)}")
            return []

