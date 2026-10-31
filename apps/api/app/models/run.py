from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ResearchRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_runs"

    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    status = Column(String(50), default="QUEUED", nullable=False, index=True)
    trigger_type = Column(String(50), default="manual", nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    total_companies_found = Column(Integer, default=0, nullable=False)
    qualified_leads_count = Column(Integer, default=0, nullable=False)
    budget_spent_usd = Column(Float, default=0.0, nullable=False)
    stats = Column(JSON, default=dict, nullable=False)
    error_summary = Column(Text, default="", nullable=False)
    created_by = Column(String(36), nullable=True)

    campaign = relationship("Campaign", back_populates="runs")
    jobs = relationship("ResearchJob", back_populates="run", cascade="all, delete-orphan")

class ResearchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_jobs"

    run_id = Column(String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("research_sources.id"), nullable=True)
    source_key = Column(String(50), default="", nullable=False)
    stage = Column(String(50), default="DISCOVERY", nullable=False)
    job_type = Column(String(50), default="DISCOVERY", nullable=False)
    status = Column(String(50), default="QUEUED", nullable=False, index=True)
    items_discovered = Column(Integer, default=0, nullable=False)
    items_processed = Column(Integer, default=0, nullable=False)
    progress_percentage = Column(Integer, default=0, nullable=False)
    records_processed = Column(Integer, default=0, nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    error_message = Column(Text, default="", nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    run = relationship("ResearchRun", back_populates="jobs")
    source = relationship("ResearchSource")
