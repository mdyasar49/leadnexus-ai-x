from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiscoveryMethod(str, Enum):
    SEARCH_QUERY = "SEARCH_QUERY"
    DOMAIN_CRAWL = "DOMAIN_CRAWL"
    GITHUB_RESEARCH = "GITHUB_RESEARCH"
    JOB_BOARD = "JOB_BOARD"
    FORUM_SCAN = "FORUM_SCAN"
    RSS_INGEST = "RSS_INGEST"
    PUBLIC_DIRECTORY = "PUBLIC_DIRECTORY"


class DiscoveryRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_runs"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True)
    
    query = Column(String(500), nullable=False)
    source_type = Column(String(50), default="SEARCH_ENGINE", nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)
    candidates_count = Column(Integer, default=0, nullable=False)
    filters = Column(JSON, default=dict, nullable=False)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    candidates = relationship("DiscoveryCandidate", back_populates="discovery_run", cascade="all, delete-orphan")


class DiscoveryCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_candidates"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    discovery_run_id = Column(String(36), ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    
    url = Column(String(1000), nullable=False, index=True)
    normalized_url = Column(String(1000), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    snippet = Column(Text, nullable=True)
    query = Column(String(500), nullable=True)
    source_rank = Column(Integer, default=1, nullable=False)
    content_type = Column(String(100), default="text/html", nullable=False)
    discovery_method = Column(String(50), default="SEARCH_QUERY", nullable=False)
    
    preliminary_relevance = Column(Float, default=0.5, nullable=False)
    confidence = Column(Float, default=0.5, nullable=False)
    evidence_pointer = Column(String(500), nullable=True)
    
    is_processed = Column(Boolean, default=False, nullable=False)
    raw_payload = Column(JSON, default=dict, nullable=False)

    discovery_run = relationship("DiscoveryRun", back_populates="candidates")

    __table_args__ = (
        Index("idx_disc_cand_ws_norm_url", "workspace_id", "normalized_url"),
        Index("idx_disc_cand_ws_relevance", "workspace_id", "preliminary_relevance"),
    )

