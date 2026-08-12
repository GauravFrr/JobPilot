import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db import Base

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(JSONB, nullable=False)

class TargetCompany(Base):
    __tablename__ = "target_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    careers_url = Column(String, nullable=True)
    detected_ats = Column(String, nullable=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

class DorkQuery(Base):
    __tablename__ = "dork_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_template = Column(String, nullable=False)
    target_group = Column(String, nullable=True)
    role_keyword_source = Column(String, server_default="resume_profile.target_roles")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SourceHealth(Base):
    __tablename__ = "source_health"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    last_error = Column(String, nullable=True)
