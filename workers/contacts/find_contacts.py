import os
import sys
import re
import json
import logging
import httpx
import socket
import smtplib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select

# Resolve parent paths for api imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api")))

from app.db import AsyncSessionLocal
from app.models.jobs import JobRaw
from app.models.contacts import Contact
from app.config import settings
from workers.llm.provider import generate
from workers.contacts.hunter_verify import verify_email_with_hunter

logger = logging.getLogger("workers.contacts.find_contacts")

# Regex pattern for email parsing from description
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")

# Verbatim snippet evidence helper
def verify_evidence_snippet(field_val: str, snippet: str) -> bool:
    """Verifies that the extracted field value is referenced in the evidence snippet."""
    if not field_val or not snippet:
        return False
    # Check if first name or last name or parts of the value are in the snippet
    parts = re.findall(r"\w+", field_val.lower())
    if not parts:
        return False
    return any(p in snippet.lower() for p in parts)

def email_matches_name(email: str, name: str) -> bool:
    """Verifies that the email either matches the contact's name, or is a generic company email."""
    if not email or not name:
        return False
    username = email.split("@")[0].lower()
    
    # Generic prefix lists
    generic_prefixes = ["jobs", "careers", "recruiting", "recruitment", "hr", "talent", "info", "hello", "contact", "support", "hiring"]
    if any(prefix == username for prefix in generic_prefixes):
        return True
        
    # Clean username for matching
    clean_username = username.replace(".", "").replace("_", "").replace("-", "")
    name_parts = re.findall(r"\w+", name.lower())
    
    # Require at least one name part (longer than 2 chars) to be present in the personal username
    return any(part in clean_username for part in name_parts if len(part) > 2)

def clean_contact_name(name: str) -> str:
    """Cleans trailing noise and common lowercase filler words from the extracted contact name."""
    if not name:
        return ""
    words = name.strip().split()
    noise_words = {"on", "at", "or", "to", "the", "from", "in", "with", "please", "our", "apply", "job", "is", "a", "an", "and"}
    while words and (words[-1].lower() in noise_words or not words[-1][0].isupper()):
        words.pop()
    return " ".join(words)

def get_role_keyword(title: str) -> str:
    """Gets a matching keyword category based on the job title to narrow down LinkedIn searches."""
    title_lower = title.lower()
    if any(k in title_lower for k in ["software", "engineer", "developer", "tech", "data", "infrastructure", "devops"]):
        return "Engineering"
    elif "product" in title_lower:
        return "Product"
    elif any(k in title_lower for k in ["sales", "account", "business", "growth", "marketing"]):
        return "Sales"
    elif any(k in title_lower for k in ["design", "ux", "ui", "creative"]):
        return "Design"
    return "Talent"

def extract_domain_from_url(url: str, company: str) -> str:
    """Extracts company domain from source URL or generates a fallback based on company name."""
    if not url:
        return company.lower().replace(" ", "").replace("inc", "").replace("corp", "") + ".com"
    
    # Try to parse domain from URLs like https://jobs.lever.co/acme or boards.greenhouse.io/acme
    url_lower = url.lower()
    for ats in ["lever.co/", "greenhouse.io/", "ashbyhq.com/"]:
        if ats in url_lower:
            parts = url_lower.split(ats)[1].split("/")[0].split("?")[0]
            if parts:
                return f"{parts}.com"
                
    # Direct domains
    match = re.search(r"https?://(?:www\.)?([^/]+)", url_lower)
    if match:
        domain = match.group(1)
        # Avoid returning common board domains
        if not any(board in domain for board in ["lever.co", "greenhouse.io", "ashbyhq.com", "remoteok", "weworkremotely", "remotive"]):
            return domain
            
    # Fallback to normalized company name
    clean_company = re.sub(r"[^\w]", "", company.lower())
    return f"{clean_company}.com"

async def parse_ats_metadata(job: JobRaw) -> List[Dict[str, Any]]:
    """Parses raw payload or JD description for recruiter/hiring manager metadata."""
    contacts = []
    
    # 1. Search in raw payload dictionary if present
    payload = job.raw_payload or {}
    for key in ["recruiter", "hiring_manager", "contact", "author", "creator"]:
        val = payload.get(key)
        if isinstance(val, dict) and val.get("name"):
            contacts.append({
                "name": val.get("name"),
                "title": val.get("title") or f"{key.replace('_', ' ').title()} at {job.company}",
                "email": val.get("email"),
                "linkedin_url": val.get("linkedin") or val.get("linkedin_url"),
                "source": "ATS Payload"
            })
        elif isinstance(val, str) and len(val) > 2 and "@" not in val:
            contacts.append({
                "name": val,
                "title": f"{key.replace('_', ' ').title()} at {job.company}",
                "email": None,
                "linkedin_url": None,
                "source": "ATS Payload"
            })
            
    # 2. Extract using regex from JD text description
    jd = job.description_text or ""
    patterns = [
        (r"(?i)hiring manager:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", "Hiring Manager"),
        (r"(?i)recruiter:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", "Recruiter"),
        (r"(?i)reach out to:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", "Point of Contact"),
        (r"(?i)contact:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", "Point of Contact")
    ]
    for pattern, title in patterns:
        match = re.search(pattern, jd)
        if match:
            name = match.group(1).strip()
            name = clean_contact_name(name)
            # Verify name doesn't contain noise
            if name and len(name) < 40 and not any(noise in name.lower() for noise in ["the", "our", "apply", "job", "please"]):
                # Look for email nearby
                email_match = EMAIL_RE.search(jd, max(0, match.start() - 100), min(len(jd), match.end() + 100))
                email = email_match.group(0) if email_match else None
                if email and not email_matches_name(email, name):
                    email = None
                contacts.append({
                    "name": name,
                    "title": f"{title} at {job.company}",
                    "email": email,
                    "linkedin_url": None,
                    "source": "JD Text Parse"
                })
                
    return contacts

async def search_linkedin_contacts(company: str, role_title: str) -> List[Dict[str, Any]]:
    """Runs a Google Custom Search query targetting LinkedIn profiles."""
    google_key = settings.gemini_api_key or os.environ.get("GOOGLE_SEARCH_API_KEY")
    google_cx = os.environ.get("GOOGLE_SEARCH_CX")
    if not google_key or not google_cx:
        logger.warning("Google search keys not set. Skipping LinkedIn search.")
        return []
        
    role_keyword = get_role_keyword(role_title)
    query = f'site:linkedin.com/in "{company}" ("Talent Acquisition" OR "Recruiter" OR "Technical Recruiter" OR "Hiring Manager") "{role_keyword}"'
    
    url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {
        "key": google_key,
        "cx": google_cx,
        "q": query,
        "num": 5
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Searching LinkedIn profiles via Google CSE: {query}")
            response = await client.get(url, params=params, timeout=12)
            if response.status_code != 200:
                logger.error(f"Google CSE returned status {response.status_code} in contact search")
                return []
                
            data = response.json()
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Google search execution failed: {str(e)}")
            return []

async def extract_and_verify_contacts(search_items: List[Dict[str, Any]], company: str) -> List[Dict[str, Any]]:
    """Calls Gemini to parse Google search items and extract verified contacts with evidence snippets."""
    if not search_items:
        return []
        
    prompt = (
        f"You are an expert contact extraction system. Analyze these Google Custom Search results for employees at the company '{company}'.\n"
        "Extract only people who are recruiters, talent acquisition partners, or hiring managers at this company.\n\n"
        "Search Results:\n"
    )
    
    for idx, item in enumerate(search_items):
        prompt += (
            f"Result {idx+1}:\n"
            f"Link: {item.get('link')}\n"
            f"Title: {item.get('title')}\n"
            f"Snippet: {item.get('snippet')}\n\n"
        )
        
    prompt += (
        "Return a JSON list of contacts. Every contact MUST include:\n"
        "- 'name': The person's full name\n"
        "- 'title': Their professional title (e.g. Recruiter, Talent Acquisition Manager)\n"
        "- 'linkedin_url': Their LinkedIn profile URL\n"
        "- 'evidence': A list of evidence items. Each item must be a dictionary with:\n"
        "   - 'field': The name of the field verified (e.g. 'name', 'title')\n"
        "   - 'snippet': The EXACT verbatim text snippet from the title or snippet above that contains this information\n"
        "   - 'source_url': The link of the result it came from\n\n"
        "CRITICAL RULES:\n"
        "1. Do NOT hallucinate. The 'snippet' in the evidence array must match verbatim text in the search results.\n"
        "2. If name or title cannot be verified with a verbatim snippet, do NOT extract that contact.\n"
        "3. Respond ONLY with valid JSON. Do not include markdown wraps."
    )
    
    try:
        response_text = await generate(prompt, task_type="contact_extraction", model_tier="cheap")
        # Clean JSON codeblock wrapper if generated
        clean_text = re.sub(r"^```json\s*", "", response_text.strip())
        clean_text = re.sub(r"\s*```$", "", clean_text)
        
        extracted = json.loads(clean_text)
        verified_contacts = []
        
        # Enforce evidence check at model-write boundary
        for c in extracted:
            name = c.get("name")
            title = c.get("title")
            linkedin_url = c.get("linkedin_url")
            evidence = c.get("evidence", [])
            
            if not name or not title or not linkedin_url or not evidence:
                continue
                
            # Verify evidence entries match field values
            has_name_evidence = False
            has_title_evidence = False
            for ev in evidence:
                f = ev.get("field")
                snip = ev.get("snippet", "")
                if f == "name" and verify_evidence_snippet(name, snip):
                    has_name_evidence = True
                elif f == "title" and verify_evidence_snippet(title, snip):
                    has_title_evidence = True
                    
            if has_name_evidence and has_title_evidence:
                verified_contacts.append({
                    "name": name,
                    "title": title,
                    "linkedin_url": linkedin_url,
                    "evidence": evidence,
                    "source": "LinkedIn Search"
                })
            else:
                logger.warning(f"Contact {name} failed evidence verification checks. Dropped.")
                
        return verified_contacts
        
    except Exception as e:
        logger.error(f"Failed LLM contact extraction/verification: {str(e)}")
        return []

async def verify_smtp_mailbox(email: str, domain: str) -> bool:
    """Performs a lightweight SMTP handshake mailbox check to verify email deliverability."""
    try:
        # Find MX records using socket lookup
        logger.info(f"Looking up MX records for domain: {domain}")
        # Try to use dns resolver if available, otherwise fallback to socket getaddrinfo
        mx_host = None
        try:
            import dns.resolver
            records = dns.resolver.resolve(domain, 'MX')
            mx_record = sorted(records, key=lambda r: r.preference)[0]
            mx_host = str(mx_record.exchange).rstrip(".")
        except Exception:
            # Fallback: resolve domain direct mail exchanger host or use the domain directly
            mx_host = f"mail.{domain}"
            
        logger.info(f"Connecting to MX server: {mx_host}")
        
        # Establish SMTP connection
        # Running in executor to prevent blocking the async loop
        import asyncio
        loop = asyncio.get_event_loop()
        
        def run_smtp():
            try:
                server = smtplib.SMTP(timeout=7)
                server.connect(mx_host)
                server.helo(socket.gethostname())
                server.mail("test@example.com")
                code, message = server.rcpt(email)
                server.quit()
                logger.info(f"SMTP rcpt code for {email}: {code} ({message})")
                return code == 250
            except Exception as se:
                logger.warning(f"SMTP verify connection failed for {email}: {str(se)}")
                return False
                
        return await loop.run_in_executor(None, run_smtp)
        
    except Exception as e:
        logger.warning(f"SMTP deliverability check failed for {email}: {str(e)}")
        return False

async def infer_and_verify_email(name: str, company: str, source_url: str) -> Tuple[Optional[str], str]:
    """Generates likely email address patterns for a contact and verifies it using Hunter.io or SMTP."""
    domain = extract_domain_from_url(source_url, company)
    parts = re.findall(r"\w+", name.lower())
    if len(parts) < 2:
        return None, "unverified"
        
    first, last = parts[0], parts[1]
    
    # Generate common patterns
    patterns = [
        f"{first}.{last}@{domain}",
        f"{first}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{first[0]}{last}@{domain}"
    ]
    
    # Select default first candidate
    primary_email = patterns[0]
    
    # 1. Try Hunter.io verification if key is set
    hunter_key = settings.hunter_api_key or os.environ.get("HUNTER_API_KEY")
    if hunter_key:
        for email in patterns[:2]: # verify top 2 patterns
            conf = await verify_email_with_hunter(email, hunter_key)
            if conf == "verified":
                return email, "verified"
            elif conf == "inferred":
                return email, "inferred"
                
    # 2. Try SMTP verify fallback
    logger.info(f"Trying SMTP verification fallback for: {primary_email}")
    smtp_success = await verify_smtp_mailbox(primary_email, domain)
    if smtp_success:
        return primary_email, "verified"
        
    # Default fallback to inferred, unverified
    return primary_email, "inferred"

def publish_event(event_type: str, job_id: str, payload_data: dict):
    """Publishes an event to the Redis pub/sub channel 'jobpilot:events'."""
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        event = {
            "event_type": event_type,
            "job_id": job_id,
            "payload": payload_data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        r.publish("jobpilot:events", json.dumps(event))
        r.close()
        logger.info(f"Published event '{event_type}' to Redis for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to publish event to Redis: {str(e)}")

async def run_contact_finder_for_job(job_id: str) -> bool:
    """Main worker entry point: locates, extracts, verifies, and saves contacts for a job."""
    try:
        logger.info(f"=== Starting Contact-Finder for Job ID {job_id} ===")
        
        async with AsyncSessionLocal() as session:
            stmt = select(JobRaw).where(JobRaw.id == job_id)
            result = await session.execute(stmt)
            job = result.scalars().first()
            if not job:
                logger.error(f"Job {job_id} not found in DB.")
                return False
                
            # 1. Try ATS metadata extraction
            contacts_data = await parse_ats_metadata(job)
            
            # 2. Try LinkedIn search if ATS yielded nothing or for extra coverage
            if not contacts_data:
                search_items = await search_linkedin_contacts(job.company, job.title)
                contacts_data = await extract_and_verify_contacts(search_items, job.company)
                
            if not contacts_data:
                logger.info(f"No contacts discovered for Job ID {job_id}.")
                return False
                
            # Save extracted contacts
            saved_any = False
            for c_data in contacts_data:
                name = c_data.get("name")
                title = c_data.get("title")
                linkedin_url = c_data.get("linkedin_url")
                source = c_data.get("source", "Unknown")
                
                # Verify / Infer email
                email = c_data.get("email")
                confidence = "unverified"
                
                if email:
                    confidence = "verified"
                else:
                    email, confidence = await infer_and_verify_email(name, job.company, job.source_url)
                    
                # Create evidence array if missing (e.g. for ATS parsing)
                evidence = c_data.get("evidence")
                if not evidence:
                    evidence = [
                        {
                            "field": "name",
                            "snippet": f"Found direct contact mapping from source: {source}",
                            "source_url": job.source_url
                        },
                        {
                            "field": "title",
                            "snippet": f"Title extracted from source: {title}",
                            "source_url": job.source_url
                        }
                    ]
                else:
                    evidence = list(evidence)
                    
                # Add email evidence entry if email was found or inferred
                if email:
                    if confidence == "verified" and c_data.get("email"):
                        email_snippet = f"Email found directly in source text: {email}"
                    elif confidence == "verified":
                        email_snippet = f"Email verified via SMTP/Hunter handshake pattern: {email}"
                    else:
                        email_snippet = f"Inferred candidate email pattern: {email}"
                        
                    if not any(ev.get("field") == "email" for ev in evidence):
                        evidence.append({
                            "field": "email",
                            "snippet": email_snippet,
                            "source_url": job.source_url
                        })
                    
                # Insert contact
                contact_rec = Contact(
                    job_id=job.id,
                    name=name,
                    title=title,
                    company=job.company,
                    linkedin_url=linkedin_url,
                    email=email,
                    email_confidence=confidence,
                    website=extract_domain_from_url(job.source_url, job.company),
                    social_profiles={},
                    evidence=evidence
                )
                session.add(contact_rec)
                saved_any = True
                
            if saved_any:
                await session.commit()
                logger.info(f"Contacts successfully saved to DB for job {job_id}")
                
                # Fetch saved records to publish event
                stmt = select(Contact).where(Contact.job_id == job_id)
                res = await session.execute(stmt)
                saved_contacts = res.scalars().all()
                for c in saved_contacts:
                    publish_event("contact.found", str(job_id), {
                        "contact_id": str(c.id),
                        "name": c.name,
                        "title": c.title,
                        "email": c.email,
                        "linkedin_url": c.linkedin_url
                    })
                    
            return True
            
    except Exception as e:
        logger.error(f"Contact finder run failed for job {job_id}: {str(e)}")
        return False

if __name__ == "__main__":
    import asyncio
    if len(sys.argv) > 1:
        job_uuid = sys.argv[1]
        asyncio.run(run_contact_finder_for_job(job_uuid))
    else:
        print("Usage: python find_contacts.py <job_uuid>")
