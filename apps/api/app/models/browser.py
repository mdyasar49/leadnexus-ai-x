from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PageAccessStatus(str, Enum):
    PUBLIC = "PUBLIC"
    PUBLIC_DYNAMIC = "PUBLIC_DYNAMIC"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PAYWALL = "PAYWALL"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN = "UNKNOWN"


class BrowserJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_jobs"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    url = Column(String(1000), nullable=False, index=True)
    
    status = Column(String(50), default="QUEUED", nullable=False, index=True)
    access_status = Column(String(50), default="UNKNOWN", nullable=False, index=True)
    http_status_code = Column(Integer, nullable=True)
    
    navigation_time_ms = Column(Integer, default=0, nullable=False)
    page_load_time_ms = Column(Integer, default=0, nullable=False)
    error = Column(Text, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    snapshot = relationship("BrowserSnapshot", uselist=False, back_populates="job", cascade="all, delete-orphan")


class BrowserSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_snapshots"

    job_id = Column(String(36), ForeignKey("browser_jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    url = Column(String(1000), nullable=False)
    canonical_url = Column(String(1000), nullable=True)
    title = Column(String(500), nullable=True)
    language = Column(String(20), nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    
    dom_summary = Column(Text, nullable=True)
    rendered_text = Column(Text, nullable=True)
    
    json_ld = Column(JSON, default=list, nullable=False)
    opengraph = Column(JSON, default=dict, nullable=False)
    twitter_meta = Column(JSON, default=dict, nullable=False)
    headings = Column(JSON, default=dict, nullable=False)
    links = Column(JSON, default=list, nullable=False)
    
    metadata_extracted = Column(JSON, default=dict, nullable=False)
    screenshot_path = Column(String(500), nullable=True)

    job = relationship("BrowserJob", back_populates="snapshot")


class RawArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "raw_artifacts"

    workspace_id = Column(String(36), nullable=False, index=True)
    url = Column(String(1000), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), default="text/html", nullable=False)
    status_code = Column(Integer, default=200, nullable=False)
    
    headers_metadata = Column(JSON, default=dict, nullable=False)
    raw_payload_text = Column(Text, nullable=True)
    source_name = Column(String(100), default="web", nullable=False)
    parser_version = Column(String(20), default="1.0.0", nullable=False)
    retention_policy = Column(String(50), default="90_DAYS", nullable=False)
    
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_raw_art_ws_hash", "workspace_id", "content_hash"),
    )

