import os
import sys
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

# Add parent path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.db import get_db
from app.config import settings

logger = logging.getLogger("api.routes.settings")

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)

@router.post("/telegram/pair")
async def generate_pairing_token():
    """
    Generates a one-time pairing token for Telegram Bot linking.
    Stored in Redis with a 10-minute (600s) TTL.
    """
    token = f"PAIR-{uuid.uuid4().hex[:8].upper()}"
    redis_client = aioredis.from_url(settings.redis_url)
    
    # Store token in Redis: key = jobpilot:telegram:pairing_token:<token> -> value = "pending"
    # Expires in 10 minutes (600s)
    redis_key = f"jobpilot:telegram:pairing_token:{token}"
    await redis_client.set(redis_key, "pending", ex=600)
    await redis_client.close()
    
    logger.info(f"Generated Telegram pairing token: {token} (expires in 600s)")
    return {
        "token": token,
        "expires_in": 600
    }
