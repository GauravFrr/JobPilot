import os
import sys
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from google import genai

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.config import settings
from app.models.settings import Setting, TargetCompany
from app.models.resumes import ResumeProfile

logger = logging.getLogger("api.routes.settings")

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)

# ─── Aggregated settings for the web dashboard ───────────────────────────────

@router.get("")
async def get_settings_summary(db: AsyncSession = Depends(get_db)):
    """Return all settings the dashboard cares about in one call."""
    chat_id = await get_setting_value(db, "telegram_chat_id", None)
    min_match_score = await get_setting_value(db, "min_match_score", 70)
    auto_apply_tier = await get_setting_value(db, "auto_apply_tier", "A")
    preferred_sources = await get_setting_value(db, "preferred_sources", [])
    pause_automation = await get_setting_value(db, "pause_automation", False)
    return {
        "chat_id": chat_id,
        "min_match_score": min_match_score,
        "auto_apply_tier": auto_apply_tier,
        "preferred_sources": preferred_sources,
        "pause_automation": pause_automation,
    }

@router.put("")
async def update_settings_summary(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """Update any subset of aggregated settings."""
    if "min_match_score" in payload:
        await set_setting_value(db, "min_match_score", float(payload["min_match_score"]))
    if "auto_apply_tier" in payload:
        await set_setting_value(db, "auto_apply_tier", str(payload["auto_apply_tier"]))
    if "preferred_sources" in payload:
        await set_setting_value(db, "preferred_sources", list(payload["preferred_sources"]))
    if "pause_automation" in payload:
        await set_setting_value(db, "pause_automation", bool(payload["pause_automation"]))
    await db.commit()
    return await get_settings_summary(db)

# Helper functions for key-value settings
async def get_setting_value(db: AsyncSession, key: str, default: Any) -> Any:
    stmt = select(Setting).where(Setting.key == key)
    res = await db.execute(stmt)
    setting = res.scalars().first()
    if setting:
        return setting.value
    return default

async def set_setting_value(db: AsyncSession, key: str, value: Any):
    stmt = select(Setting).where(Setting.key == key)
    res = await db.execute(stmt)
    setting = res.scalars().first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)

# --- Resume Profile ---

def get_resume_text_representation(profile: dict) -> str:
    parts = []
    parts.append(f"Name: {profile.get('name', '')}")
    parts.append(f"Target Roles: {', '.join(profile.get('target_roles', []))}")
    
    skills = profile.get('skills', {})
    if isinstance(skills, dict):
        skills_str = "\n".join(f"- {category}: {', '.join(items) if isinstance(items, list) else items}" for category, items in skills.items())
        parts.append(f"Skills:\n{skills_str}")
        
    experience = profile.get('experience', [])
    if isinstance(experience, list):
        exp_str = "\n\n".join(
            f"Role: {e.get('role')}\nCompany: {e.get('company')}\nBullets:\n" + 
            "\n".join(f"- {b}" for b in e.get('bullets', []))
            for e in experience if isinstance(e, dict)
        )
        parts.append(f"Experience:\n{exp_str}")
        
    projects = profile.get('projects', [])
    if isinstance(projects, list):
        projects_str = "\n\n".join(
            f"Project: {p.get('name')}\nBullets:\n" + 
            "\n".join(f"- {b}" for b in p.get('bullets', []))
            for p in projects if isinstance(p, dict)
        )
        parts.append(f"Projects:\n{projects_str}")
        
    return "\n\n".join(parts)

async def generate_embedding(text: str) -> list[float]:
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    client = genai.Client(api_key=api_key)
    response = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config={"output_dimensionality": 768}
    )
    if not response.embeddings or not response.embeddings[0].values:
        raise ValueError("Could not extract embedding from Gemini response.")
    return response.embeddings[0].values

@router.get("/resume-profile")
async def get_resume_profile(db: AsyncSession = Depends(get_db)):
    stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="No active resume profile found.")
    return {
        "id": str(profile.id),
        "version": profile.version,
        "content_json": profile.content_json,
        "has_embedding": profile.embedding is not None,
        "created_at": profile.created_at.isoformat() if profile.created_at else None
    }

@router.put("/resume-profile")
async def update_resume_profile(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    content_json = payload.get("content_json")
    if not content_json:
        raise HTTPException(status_code=400, detail="content_json is required")
        
    # Get active profile
    stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
    res = await db.execute(stmt)
    active = res.scalars().first()
    
    new_version = 1
    if active:
        active.is_active = False
        new_version = active.version + 1
        
    new_profile = ResumeProfile(
        version=new_version,
        content_json=content_json,
        embedding=None, # Marked stale until recompute
        is_active=True
    )
    db.add(new_profile)
    await db.commit()
    
    return {
        "status": "success",
        "version": new_profile.version,
        "embedding_stale": True
    }

@router.post("/resume-profile/recompute-embedding")
async def recompute_resume_embedding(db: AsyncSession = Depends(get_db)):
    stmt = select(ResumeProfile).where(ResumeProfile.is_active == True)
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="No active profile to embed")
        
    resume_text = get_resume_text_representation(profile.content_json)
    try:
        embedding = await generate_embedding(resume_text)
        profile.embedding = embedding
        await db.commit()
        return {"status": "success", "message": "Embeddings recomputed successfully."}
    except Exception as e:
        logger.error(f"Embedding recompute failed: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to generate embedding: {str(e)}")

# --- Target Companies ---

@router.get("/target-companies")
async def get_target_companies(db: AsyncSession = Depends(get_db)):
    stmt = select(TargetCompany).where(TargetCompany.is_active == True).order_by(TargetCompany.name)
    res = await db.execute(stmt)
    companies = res.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "domain": c.domain,
            "careers_url": c.careers_url,
            "detected_ats": c.detected_ats
        } for c in companies
    ]

@router.put("/target-companies")
async def update_target_companies(payload: List[Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    # Deactivate existing
    await db.execute(update(TargetCompany).where(TargetCompany.is_active == True).values(is_active=False))
    
    # Add new ones
    for c_data in payload:
        name = c_data.get("name")
        if not name:
            continue
        c = TargetCompany(
            name=name,
            domain=c_data.get("domain"),
            careers_url=c_data.get("careers_url"),
            detected_ats=c_data.get("detected_ats"),
            is_active=True
        )
        db.add(c)
        
    await db.commit()
    return {"status": "success"}

# --- Thresholds ---

@router.get("/thresholds")
async def get_thresholds(db: AsyncSession = Depends(get_db)):
    min_score = await get_setting_value(db, "min_match_score", 70.0)
    daily_caps = await get_setting_value(db, "daily_caps_by_platform", {})
    return {"min_match_score": min_score, "daily_caps_by_platform": daily_caps}

@router.put("/thresholds")
async def update_thresholds(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    min_score = payload.get("min_match_score")
    daily_caps = payload.get("daily_caps_by_platform")
    
    if min_score is not None:
        await set_setting_value(db, "min_match_score", float(min_score))
    if daily_caps is not None:
        await set_setting_value(db, "daily_caps_by_platform", daily_caps)
        
    await db.commit()
    return {"status": "success"}

# --- Platform Toggles ---

@router.get("/platform-toggles")
async def get_platform_toggles(db: AsyncSession = Depends(get_db)):
    toggles = await get_setting_value(db, "platform_toggles", {})
    return toggles

@router.put("/platform-toggles")
async def update_platform_toggles(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    await set_setting_value(db, "platform_toggles", payload)
    await db.commit()
    return {"status": "success"}

# --- Default Answers ---

@router.get("/default-answers")
async def get_default_answers(db: AsyncSession = Depends(get_db)):
    answers = await get_setting_value(db, "default_answers", {})
    return answers

@router.put("/default-answers")
async def update_default_answers(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    await set_setting_value(db, "default_answers", payload)
    await db.commit()
    return {"status": "success"}

# --- Telegram Bot Pairing ---

import redis.asyncio as aioredis
@router.post("/telegram/pair")
async def generate_pairing_token():
    token = f"PAIR-{uuid.uuid4().hex[:8].upper()}"
    redis_client = aioredis.from_url(settings.redis_url)
    redis_key = f"jobpilot:telegram:pairing_token:{token}"
    await redis_client.set(redis_key, "pending", ex=600)
    await redis_client.close()
    
    logger.info(f"Generated Telegram pairing token: {token} (expires in 600s)")
    return {
        "token": token,
        "expires_in": 600
    }
