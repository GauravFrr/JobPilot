from sqlalchemy import Column, String, ForeignKey, CHAR, Float, Boolean, Date, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from config import settings

engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

class DBSetting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(JSONB, nullable=False)

class DBJobRaw(Base):
    __tablename__ = "jobs_raw"
    id = Column(UUID(as_uuid=True), primary_key=True)
    source = Column(String, nullable=False)
    source_tier = Column(CHAR(1), nullable=False)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False)

class DBJobScore(Base):
    __tablename__ = "job_scores"
    id = Column(UUID(as_uuid=True), primary_key=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    final_score = Column(Float, nullable=False)

class DBApplication(Base):
    __tablename__ = "applications"
    id = Column(UUID(as_uuid=True), primary_key=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    resume_version_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id"), nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=True)
