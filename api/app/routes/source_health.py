import os
import sys
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.models.settings import SourceHealth

router = APIRouter(
    prefix="/source-health",
    tags=["source-health"]
)

@router.get("")
async def get_source_health(db: AsyncSession = Depends(get_db)):
    stmt = select(SourceHealth).order_by(SourceHealth.source)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "consecutive_failures": r.consecutive_failures,
            "last_error": r.last_error
        } for r in records
    ]
