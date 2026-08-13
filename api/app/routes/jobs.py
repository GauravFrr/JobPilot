import os
import sys
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any

# Add parent path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.jobs import JobRaw, JobScore
from app.models.resumes import ResumeVersion
from app.models.applications import Application
from app.models.contacts import Contact
from app.models.outreach import OutreachDraft

logger = logging.getLogger("api.routes.jobs")

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"]
)

def redact_credentials(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    redacted = dict(payload)
    for key in ["password", "token", "key", "credentials"]:
        if key in redacted:
            redacted[key] = "[REDACTED]"
    return redacted

@router.get("")
async def list_jobs(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    has_contact: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    per_page: Optional[int] = None,  # alias used by frontend
    db: AsyncSession = Depends(get_db)
):
    # Allow per_page as alias for page_size
    if per_page is not None:
        page_size = per_page
    stmt = select(JobRaw)
    
    # Filter by basic fields
    if status:
        stmt = stmt.where(JobRaw.status == status)
    if tier:
        stmt = stmt.where(JobRaw.source_tier == tier)
    if source:
        stmt = stmt.where(JobRaw.source.ilike(f"%{source}%"))
        
    # Join with JobScore for match score filters
    stmt = stmt.outerjoin(JobScore, JobScore.job_id == JobRaw.id)
    if min_score is not None:
        stmt = stmt.where(JobScore.final_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(JobScore.final_score <= max_score)
        
    # Filter by contact presence
    if has_contact is not None:
        if has_contact:
            stmt = stmt.join(Contact, Contact.job_id == JobRaw.id)
        else:
            stmt = stmt.outerjoin(Contact, Contact.job_id == JobRaw.id).where(Contact.id == None)
            
    # Count total matching records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Paginate and order by discovery time
    stmt = stmt.order_by(desc(JobRaw.discovered_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    results = []
    for job in jobs:
        # Load match score
        score_stmt = select(JobScore).where(JobScore.job_id == job.id)
        score_res = await db.execute(score_stmt)
        score_rec = score_res.scalars().first()
        match_score = score_rec.final_score if score_rec else 0.0
        
        # Check has_resume_version
        rv_stmt = select(ResumeVersion).where(ResumeVersion.job_id == job.id)
        rv_res = await db.execute(rv_stmt)
        has_rv = rv_res.scalars().first() is not None
        
        # Check has_contact and load contact list
        c_stmt = select(Contact).where(Contact.job_id == job.id)
        c_res = await db.execute(c_stmt)
        c_list = c_res.scalars().all()
        has_c = len(c_list) > 0
        
        # Load application_id if status matches applied/ready_to_apply
        app_stmt = select(Application).where(Application.job_id == job.id)
        app_res = await db.execute(app_stmt)
        app_rec = app_res.scalars().first()
        app_id = str(app_rec.id) if app_rec else None
        
        results.append({
            "id": str(job.id),
            "company": job.company,
            "title": job.title,
            "tier": job.source_tier,
            "status": job.status,
            "match_score": match_score,
            "source": job.source,
            "url": job.source_url,
            "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
            "created_at": job.discovered_at.isoformat() if job.discovered_at else None,
            "applied_at": app_rec.applied_at.isoformat() if (app_rec and app_rec.applied_at) else None,
            "is_test": getattr(job, 'is_test', False),
            "has_resume_version": has_rv,
            "has_contact": has_c,
            "application_id": app_id,
            # Stub arrays — full arrays only in GET /jobs/{id}
            "resume_versions": [],
            "applications": [{"id": app_id, "status": app_rec.status, "method": app_rec.method, "applied_at": app_rec.applied_at.isoformat() if app_rec and app_rec.applied_at else None}] if app_rec else [],
            "contacts": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "title": c.title,
                    "linkedin_url": c.linkedin_url,
                    "email": c.email,
                    "email_confidence": c.email_confidence
                } for c in c_list
            ],
            "outreach_drafts": [],
        })
        
    return {
        "items": results,
        "total": total,
        "page": page,
        "per_page": page_size
    }

@router.get("/{job_id}")
async def get_job_detail(job_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(JobRaw).where(JobRaw.id == job_id)
    result = await db.execute(stmt)
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        
    # Get score
    score_stmt = select(JobScore).where(JobScore.job_id == job.id)
    score_res = await db.execute(score_stmt)
    score_rec = score_res.scalars().first()
    
    # Get resume versions
    rv_stmt = select(ResumeVersion).where(ResumeVersion.job_id == job.id).order_by(desc(ResumeVersion.generated_at))
    rv_res = await db.execute(rv_stmt)
    rv_list = rv_res.scalars().all()
    
    # Get contacts
    c_stmt = select(Contact).where(Contact.job_id == job.id)
    c_res = await db.execute(c_stmt)
    c_list = c_res.scalars().all()
    
    # Get applications
    app_stmt = select(Application).where(Application.job_id == job.id).order_by(desc(Application.created_at))
    app_res = await db.execute(app_stmt)
    app_list = app_res.scalars().all()
    
    # Get outreach drafts
    od_stmt = select(OutreachDraft).where(OutreachDraft.job_id == job.id).order_by(desc(OutreachDraft.generated_at))
    od_res = await db.execute(od_stmt)
    od_list = od_res.scalars().all()
    
    return {
        "id": str(job.id),
        "source": job.source,
        "tier": job.source_tier,
        "source_tier": job.source_tier,
        "source_job_id": job.source_job_id,
        "url": job.source_url,
        "source_url": job.source_url,
        "company": job.company,
        "title": job.title,
        "description_text": job.description_text,
        "location": job.location,
        "is_remote": job.is_remote,
        "posted_date": job.posted_date.isoformat() if job.posted_date else None,
        "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "created_at": job.discovered_at.isoformat() if job.discovered_at else None,
        "applied_at": app_list[0].applied_at.isoformat() if (app_list and app_list[0].applied_at) else None,
        "status": job.status,
        "is_test": job.is_test,
        "match_score": score_rec.final_score if score_rec else None,
        "score": {
            "embedding_score": score_rec.embedding_score if score_rec else 0.0,
            "llm_rerank_score": score_rec.llm_rerank_score if score_rec else None,
            "final_score": score_rec.final_score if score_rec else 0.0,
            "rationale": score_rec.rationale if score_rec else "No scoring record found."
        } if score_rec else None,
        "resume_versions": [
            {
                "id": str(rv.id),
                "version": str(len(rv_list) - idx),
                "generated_at": rv.generated_at.isoformat() if rv.generated_at else None,
                "created_at": rv.generated_at.isoformat() if rv.generated_at else None,
                "model_used": rv.model_used
            } for idx, rv in enumerate(rv_list)
        ],
        "contacts": [
            {
                "id": str(c.id),
                "name": c.name,
                "title": c.title,
                "company": c.company,
                "linkedin_url": c.linkedin_url,
                "email": c.email,
                "email_confidence": c.email_confidence,
                "evidence": c.evidence
            } for c in c_list
        ],
        "applications": [
            {
                "id": str(app.id),
                "status": app.status,
                "tier": app.tier,
                "method": app.method,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "request_payload_snapshot": redact_credentials(app.request_payload_snapshot),
                "result": app.result
            } for app in app_list
        ],
        "outreach_drafts": [
            {
                "id": str(od.id),
                "draft_text": od.draft_text,
                "channel": od.channel,
                "sent": od.sent,
                "created_at": od.generated_at.isoformat() if od.generated_at else None
            } for od in od_list
        ]
    }

@router.get("/{job_id}/resume/{version_id}/pdf")
async def get_resume_pdf(job_id: str, version_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ResumeVersion).where(ResumeVersion.id == version_id, ResumeVersion.job_id == job_id)
    result = await db.execute(stmt)
    rv = result.scalars().first()
    if not rv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume version not found for this job")
        
    pdf_path = rv.pdf_path
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailored PDF file does not exist on disk")
        
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"Resume_{job_id[:8]}.pdf")
