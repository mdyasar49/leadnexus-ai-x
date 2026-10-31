from enum import Enum

class SourceType(str, Enum):
    API = 'API'
    WEB = 'WEB'
    RSS = 'RSS'
    DIRECTORY = 'DIRECTORY'
    FORUM = 'FORUM'
    JOB_BOARD = 'JOB_BOARD'

class SourceHealthStatus(str, Enum):
    HEALTHY = 'HEALTHY'
    DEGRADED = 'DEGRADED'
    RATE_LIMITED = 'RATE_LIMITED'
    OFFLINE = 'OFFLINE'

from sqlalchemy import Column, String, Boolean, Float, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ResearchSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_sources"

    code = Column(String(50), unique=True, nullable=False, index=True)
    key = Column(String(50), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    requires_auth = Column(Boolean, default=False, nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    concurrency_limit = Column(Integer, default=5, nullable=False) # github, company_website, public_directory, rss_forum, job_posting
    name = Column(String(150), nullable=False)
    description = Column(String(500), default="", nullable=False)
    source_type = Column(String(50), default="WEB", nullable=False) # API, WEB, RSS, DIRECTORY
    enabled = Column(Boolean, default=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    requires_credentials = Column(Boolean, default=False, nullable=False)
    cost_type = Column(String(50), default="FREE", nullable=False) # FREE, PAID_PER_REQUEST, SUBSCRIPTION
    health_status = Column(String(50), default="HEALTHY", nullable=False) # HEALTHY, DEGRADED, RATE_LIMITED, OFFLINE
    configuration_schema = Column(JSON, default=dict, nullable=False)

    campaign_mappings = relationship("CampaignSource", back_populates="source", cascade="all, delete-orphan")

class CampaignSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_sources"

    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    custom_rate_limit = Column(Float, default=1.5, nullable=False) # delay seconds between requests
    priority = Column(String(50), default="NORMAL", nullable=False)

    campaign = relationship("Campaign", back_populates="sources")
    source = relationship("ResearchSource", back_populates="campaign_mappings")

    __table_args__ = (
        UniqueConstraint("campaign_id", "source_id", name="uq_campaign_source"),
    )

