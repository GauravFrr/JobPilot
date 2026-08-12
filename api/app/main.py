from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.routes.applications import router as applications_router

app = FastAPI(
    title="JobPilot API",
    description="Backend API for JobPilot personal job application automation system",
    version="1.0.0"
)

# Mount routes under /api/v1 prefix
app.include_router(applications_router, prefix="/api/v1")

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
