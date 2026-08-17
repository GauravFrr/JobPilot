import os
import sys
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

# Add parent path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.applications import Application
from app.models.jobs import JobRaw
from workers.applying.tier_a_apply import execute_submission as execute_tier_a_submission
from workers.applying.tier_b_apply import execute_linkedin_submission as execute_tier_b_submission

router = APIRouter(
    prefix="/applications",
    tags=["applications"]
)

@router.post("/{application_id}/apply")
async def apply_job(application_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Tapping 'Apply': triggers submission process for the job.
    Must be in 'ready_to_apply' status.
    """
    # Fetch application
    stmt = select(Application).where(Application.id == application_id)
    result = await db.execute(stmt)
    app = result.scalars().first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
        
    # Idempotency guard: only ready_to_apply can be processed
    if app.status != "ready_to_apply":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "not_ready", "message": "Application is not in ready_to_apply state."}
        )
        
    # Mark status as 'applying' immediately to prevent double-tap race conditions
    app.status = "applying"
    await db.commit()
    
    # Run submission asynchronously in background
    if app.tier == "B":
        background_tasks.add_task(execute_tier_b_submission, str(app.id))
    else:
        background_tasks.add_task(execute_tier_a_submission, str(app.id))
    
    return {
        "application_id": str(app.id),
        "status": "applying"
    }

@router.post("/{application_id}/pass")
async def pass_job(application_id: str, db: AsyncSession = Depends(get_db)):
    """
    Tapping 'Pass': skips application and does not submit.
    """
    stmt = select(Application).where(Application.id == application_id)
    result = await db.execute(stmt)
    app = result.scalars().first()
    
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
        
    if app.status != "ready_to_apply":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "not_ready", "message": "Application is not in ready_to_apply state."}
        )
        
    # Update application and job status to skipped/skipped
    app.status = "skipped"
    
    # Update related job
    stmt = select(JobRaw).where(JobRaw.id == app.job_id)
    result = await db.execute(stmt)
    job = result.scalars().first()
    if job:
        job.status = "skipped"
        
    await db.commit()
    
    return {
        "application_id": str(app.id),
        "status": "skipped"
    }

@router.post("/{application_id}/mark-applied")
async def mark_applied(application_id: str, db: AsyncSession = Depends(get_db)):
    """
    For Tier D / manual leads only — self-tracking, no automation triggered.
    """
    stmt = select(Application).where(Application.id == application_id)
    result = await db.execute(stmt)
    app = result.scalars().first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    from datetime import datetime
    app.status = "applied"
    app.method = "manual"
    app.applied_at = datetime.utcnow()

    stmt = select(JobRaw).where(JobRaw.id == app.job_id)
    result = await db.execute(stmt)
    job = result.scalars().first()
    if job:
        job.status = "applied"

    await db.commit()
    return {"application_id": str(app.id), "status": "applied", "method": "manual"}

@router.get("/{application_id}")
async def get_application(application_id: str, db: AsyncSession = Depends(get_db)):
    """
    Full audit record for a single application.
    """
    stmt = select(Application).where(Application.id == application_id)
    result = await db.execute(stmt)
    app = result.scalars().first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Redact sensitive fields per TRD REQ-SEC-3
    payload = app.request_payload_snapshot
    if isinstance(payload, dict):
        for key in ["password", "token", "key", "credentials"]:
            if key in payload:
                payload[key] = "[REDACTED]"

    return {
        "id": str(app.id),
        "job_id": str(app.job_id),
        "tier": app.tier,
        "method": app.method,
        "status": app.status,
        "applied_at": app.applied_at.isoformat() if app.applied_at else None,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "request_payload_snapshot": payload,
        "result": app.result
    }
