import uuid
from sqlalchemy import Column, String, Boolean, Date, DateTime, Float, ForeignKey, UniqueConstraint, CHAR, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

class JobRaw(Base):
    __tablename__ = "jobs_raw"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False)
    source_tier = Column(CHAR(1), nullable=False)
    source_job_id = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description_text = Column(String, nullable=False)
    location = Column(String, nullable=True)
    is_remote = Column(Boolean, nullable=True)
    posted_date = Column(Date, nullable=True)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_payload = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, default="discovered")

    __table_args__ = (
        UniqueConstraint("source", "source_job_id", name="uq_source_source_job_id"),
    )

class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    resume_profile_version = Column(Integer, nullable=False)  # Wait, version is INT in doc 11, let's use Integer
    final_score = Column(Float, nullable=False)
    embedding_score = Column(Float, nullable=True)
    llm_rerank_score = Column(Float, nullable=True)
    rationale = Column(String, nullable=True)
    scored_at = Column(DateTime(timezone=True), server_default=func.now())
