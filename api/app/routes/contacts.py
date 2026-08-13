import os
import sys
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.contacts import Contact

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"]
)

@router.get("/{job_id}")
async def get_contacts_by_job(job_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Contact).where(Contact.job_id == job_id)
    result = await db.execute(stmt)
    contacts = result.scalars().all()
    
    if not contacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contact found for this job"
        )
        
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "title": c.title,
            "company": c.company,
            "linkedin_url": c.linkedin_url,
            "email": c.email,
            "email_confidence": c.email_confidence,
            "evidence": c.evidence
        } for c in contacts
    ]
