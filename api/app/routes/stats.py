import os
import sys
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.jobs import JobRaw, JobScore
from app.models.applications import Application
from app.models.contacts import Contact
from app.models.outreach import OutreachDraft

router = APIRouter(
    prefix="/stats",
    tags=["stats"]
)

@router.get("/weekly-summary")
async def get_weekly_summary(db: AsyncSession = Depends(get_db)):
    # Week starts 7 days ago
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    # 1. Discovered: count of JobRaw discovered in last 7 days
    stmt = select(func.count(JobRaw.id)).where(JobRaw.discovered_at >= seven_days_ago)
    res = await db.execute(stmt)
    discovered = res.scalar() or 0
    
    # 2. Matched: count of JobScore with score >= min_score in last 7 days
    # Let's count non-zero scores
    stmt = select(func.count(JobScore.id)).where(
        and_(
            JobScore.scored_at >= seven_days_ago,
            JobScore.final_score >= 70.0  # standard threshold
        )
    )
    res = await db.execute(stmt)
    matched = res.scalar() or 0
    
    # 3. Ready to apply count currently
    stmt = select(func.count(Application.id)).where(Application.status == "ready_to_apply")
    res = await db.execute(stmt)
    ready = res.scalar() or 0
    
    # 4. Applied in last 7 days
    stmt = select(func.count(Application.id)).where(
        and_(
            Application.status == "applied",
            Application.applied_at >= seven_days_ago
        )
    )
    res = await db.execute(stmt)
    applied = res.scalar() or 0
    
    # 5. Skipped/passed in last 7 days
    stmt = select(func.count(Application.id)).where(
        and_(
            Application.status == "skipped",
            Application.created_at >= seven_days_ago
        )
    )
    res = await db.execute(stmt)
    skipped = res.scalar() or 0
    
    # 6. Manual leads: jobs with tier D in last 7 days
    stmt = select(func.count(JobRaw.id)).where(
        and_(
            JobRaw.source_tier == "D",
            JobRaw.discovered_at >= seven_days_ago
        )
    )
    res = await db.execute(stmt)
    manual_leads = res.scalar() or 0
    
    # 7. Contacts found in last 7 days
    # Wait, Contact model does not have a created_at column in DB schema (doc 11),
    # but we can count total contacts or count by jobs discovered in last 7 days.
    # Let's join Contact with JobRaw to check discovered_at!
    stmt = select(func.count(Contact.id)).join(JobRaw, Contact.job_id == JobRaw.id).where(JobRaw.discovered_at >= seven_days_ago)
    res = await db.execute(stmt)
    contacts_found = res.scalar() or 0
    
    # 8. Outreach drafts in last 7 days
    stmt = select(func.count(OutreachDraft.id)).where(OutreachDraft.generated_at >= seven_days_ago)
    res = await db.execute(stmt)
    drafts = res.scalar() or 0
    
    return {
        "week_start": seven_days_ago.isoformat() + "Z",
        "discovered": discovered,
        "matched": matched,
        "ready_to_apply": ready,
        "applied": applied,
        "skipped": skipped,
        "manual_leads": manual_leads,
        "contacts_found": contacts_found,
        "outreach_drafts": drafts
    }


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    """All-time dashboard summary stats."""
    from sqlalchemy import distinct

    # total applied
    stmt = select(func.count(Application.id)).where(Application.status == "applied")
    total_applied = (await db.execute(stmt)).scalar() or 0

    # total discarded
    stmt = select(func.count(JobRaw.id)).where(JobRaw.status == "discarded")
    total_discarded = (await db.execute(stmt)).scalar() or 0

    # total matched (ever scored above 0 and not discarded)
    stmt = select(func.count(distinct(JobScore.job_id))).where(JobScore.final_score >= 70)
    total_matched = (await db.execute(stmt)).scalar() or 0

    # interviews: placeholder — count applications with result containing 'interview'
    interviews = 0

    # apply rate: applied / matched
    apply_rate = (total_applied / total_matched) if total_matched > 0 else 0.0

    # avg match score
    stmt = select(func.avg(JobScore.final_score)).where(JobScore.final_score > 0)
    avg_score = (await db.execute(stmt)).scalar()
    if avg_score:
        avg_score = round(float(avg_score), 1)

    # sources breakdown
    stmt = (
        select(JobRaw.source, func.count(Application.id))
        .join(Application, Application.job_id == JobRaw.id)
        .where(Application.status == "applied")
        .group_by(JobRaw.source)
    )
    rows = (await db.execute(stmt)).all()
    sources = {row[0]: row[1] for row in rows}

    # 30-day timeline
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    stmt = (
        select(
            func.date(Application.applied_at).label("date"),
            func.count(Application.id).label("count")
        )
        .where(
            and_(
                Application.status == "applied",
                Application.applied_at >= thirty_days_ago
            )
        )
        .group_by(func.date(Application.applied_at))
        .order_by(func.date(Application.applied_at))
    )
    timeline_rows = (await db.execute(stmt)).all()
    timeline = [{"date": str(r[0]), "count": r[1]} for r in timeline_rows]

    return {
        "total_applied": total_applied,
        "total_discarded": total_discarded,
        "total_matched": total_matched,
        "interviews": interviews,
        "apply_rate": round(apply_rate, 3),
        "avg_match_score": avg_score,
        "sources": sources,
        "timeline": timeline
    }
