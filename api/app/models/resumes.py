import uuid
from sqlalchemy import Column, Integer, Boolean, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db import Base

class ResumeProfile(Base):
    __tablename__ = "resume_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(Integer, nullable=False)
    content_json = Column(JSONB, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    content_json = Column(JSONB, nullable=False)
    pdf_path = Column(String, nullable=False)
    model_used = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
