import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.routes.applications import router as applications_router
from app.routes.settings import router as settings_router
from app.routes.jobs import router as jobs_router
from app.routes.contacts import router as contacts_router
from app.routes.outreach import router as outreach_router
from app.routes.stats import router as stats_router
from app.routes.source_health import router as source_health_router

app = FastAPI(
    title="JobPilot API",
    description="Backend API for JobPilot personal job application automation system",
    version="1.0.0"
)

# Configure CORS — restrict to dashboard origins only, never wildcard
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes under /api/v1 prefix
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(contacts_router, prefix="/api/v1")
app.include_router(outreach_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(source_health_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Check DB connection
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": f"error: {str(e)}"
        }

@app.get("/")
async def root():
    return {"message": "Welcome to JobPilot API"}
