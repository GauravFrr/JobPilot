import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs_raw.id"), nullable=False)
    name = Column(String, nullable=True)
    title = Column(String, nullable=True)
    company = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    email_confidence = Column(String, nullable=True)
    website = Column(String, nullable=True)
    social_profiles = Column(JSONB, nullable=True)
    evidence = Column(JSONB, nullable=True)
    found_at = Column(DateTime(timezone=True), server_default=func.now())
