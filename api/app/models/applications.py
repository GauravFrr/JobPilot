import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    resume_version_id = Column(UUID(as_uuid=True), ForeignKey("resume_versions.id"), nullable=True)
    tier = Column(CHAR(1), nullable=False)
    method = Column(String, nullable=True)
    status = Column(String, nullable=False)
    request_payload_snapshot = Column(JSONB, nullable=True)
    result = Column(JSONB, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
