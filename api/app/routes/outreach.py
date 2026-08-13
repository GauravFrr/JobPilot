import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.jobs import JobRaw
from app.models.contacts import Contact
from app.models.resumes import ResumeProfile
from app.models.outreach import OutreachDraft
from workers.llm.provider import generate

logger = logging.getLogger("api.routes.outreach")

router = APIRouter(
    prefix="/outreach",
    tags=["outreach"]
)

@router.post("/{job_id}/draft")
async def generate_outreach_draft(
    job_id: str,
    payload: Dict[str, str],
    db: AsyncSession = Depends(get_db)
):
    channel = payload.get("channel", "linkedin").lower()
    if channel not in ["linkedin", "email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid channel. Must be 'linkedin' or 'email'."
        )
        
    # Check contact exists
    stmt_contact = select(Contact).where(Contact.job_id == job_id)
    contact_res = await db.execute(stmt_contact)
    contact = contact_res.scalars().first()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contact found for this job. Cannot generate draft."
        )
        
    # Fetch job info
    stmt_job = select(JobRaw).where(JobRaw.id == job_id)
    job_res = await db.execute(stmt_job)
    job = job_res.scalars().first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
        
    # Fetch active resume profile info to reference Gaurav's background
    stmt_profile = select(ResumeProfile).where(ResumeProfile.is_active == True)
    profile_res = await db.execute(stmt_profile)
    profile = profile_res.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active resume profile found."
        )
        
    # Construct generation prompt
    prompt = f"""
You are an outreach assistant helping Gaurav draft a personalized cold outreach message to a hiring contact.
The message must be professional, brief, and highly customized to both the job and the contact's background.

Master Profile of Gaurav:
{profile.content_json}

Job Listing details:
Company: {job.company}
Role Title: {job.title}
Job Description: {job.description_text[:1200]}

Contact details:
Name: {contact.name}
Title: {contact.title}

Channel: {channel.upper()} (LinkedIn or Email)

Instructions:
1. Write a cold outreach message targeting this contact.
2. If the channel is Email, include a Subject line at the beginning. If it is LinkedIn, make it fit within 300 characters (or a short note format).
3. Do NOT make up any details or credentials that are not present in Gaurav's Master Profile (TRD REQ-GEN-1). Keep it strictly factual.
4. Use standard past-tense verbs for accomplishments (e.g., Developed, Built, Led).
5. Output ONLY the raw drafted message content, without conversational preamble or formatting indicators.
"""
    logger.info(f"Generating outreach draft for job {job_id} using model provider...")
    try:
        draft_text = await generate(prompt, "outreach_draft", "premium")
        
        # Save to DB
        od = OutreachDraft(
            job_id=job.id,
            contact_id=contact.id,
            channel=channel,
            draft_text=draft_text.strip(),
            sent=False
        )
        db.add(od)
        await db.commit()
        
        return {
            "draft_id": str(od.id),
            "draft_text": od.draft_text,
            "channel": od.channel
        }
    except Exception as e:
        logger.error(f"Error generating draft for {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Outreach generation failed: {str(e)}"
        )

@router.patch("/{draft_id}")
async def update_outreach_sent(
    draft_id: str,
    payload: Dict[str, bool],
    db: AsyncSession = Depends(get_db)
):
    sent = payload.get("sent", False)
    stmt = select(OutreachDraft).where(OutreachDraft.id == draft_id)
    res = await db.execute(stmt)
    od = res.scalars().first()
    if not od:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found"
        )
        
    od.sent = sent
    await db.commit()
    return {"status": "success", "sent": od.sent}
