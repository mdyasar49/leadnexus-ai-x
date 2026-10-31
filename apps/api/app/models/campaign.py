from enum import Enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"

class CampaignType(str, Enum):
    ODOO = "ODOO"
    ZOHO = "ZOHO"
    ERP = "ERP"
    ECOMMERCE = "ECOMMERCE"
    DIGITAL_MARKETING = "DIGITAL_MARKETING"
    AI_AUTOMATION = "AI_AUTOMATION"
    CUSTOM = "CUSTOM"

class CampaignPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), default="", nullable=False)
    status = Column(String(50), default="DRAFT", nullable=False, index=True) # DRAFT, ACTIVE, PAUSED, ARCHIVED
    campaign_type = Column(String(50), default="CUSTOM", nullable=False)     # ODOO, ZOHO, ERP, ECOMMERCE, DIGITAL_MARKETING, AI_AUTOMATION, CUSTOM
    priority = Column(String(50), default="NORMAL", nullable=False)          # LOW, NORMAL, HIGH, CRITICAL
    created_by = Column(String(36), nullable=True)
    created_by_user_id = Column(String(36), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

    workspace = relationship("Workspace", back_populates="campaigns")
    config = relationship("CampaignConfig", back_populates="campaign", uselist=False, cascade="all, delete-orphan")
    sources = relationship("CampaignSource", back_populates="campaign", cascade="all, delete-orphan")
    runs = relationship("ResearchRun", back_populates="campaign", cascade="all, delete-orphan")

class CampaignConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_configs"

    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Target Geography
    country = Column(String(100), default="Global", nullable=True)
    state = Column(String(100), default="", nullable=True)
    city = Column(String(100), default="", nullable=True)
    countries = Column(JSON, default=list, nullable=False)
    regions = Column(JSON, default=list, nullable=False)
    cities = Column(JSON, default=list, nullable=False)

    # Target Market & Firmographics
    industry = Column(String(150), default="", nullable=True)
    industries = Column(JSON, default=list, nullable=False)
    company_sizes = Column(JSON, default=list, nullable=False)
    company_keywords = Column(JSON, default=list, nullable=False)
    intent_keywords = Column(JSON, default=list, nullable=False)
    target_job_titles = Column(JSON, default=list, nullable=False)

    # Technologies & Intent
    technologies = Column(JSON, default=list, nullable=False)
    intent_types = Column(JSON, default=list, nullable=False)
    intent_min_score = Column(Integer, default=60, nullable=False)

    # Decision-Maker Targeting
    decision_maker_roles = Column(JSON, default=list, nullable=False)
    
    # Contact & Verification Requirements
    require_email = Column(Boolean, default=True, nullable=False)
    require_phone = Column(Boolean, default=False, nullable=False)
    email_verification_policy = Column(String(50), default="PROVIDER_DELIVERABLE_OR_LISTED", nullable=False)
    phone_verification_policy = Column(String(50), default="VALID_NUMBER", nullable=False)
    minimum_data_quality = Column(Integer, default=70, nullable=False)

    # Research Sources & Limits
    sources = Column(JSON, default=list, nullable=False)
    maximum_results = Column(Integer, default=100, nullable=False)
    maximum_leads = Column(Integer, default=100, nullable=False)
    max_requests_per_source = Column(Integer, default=50, nullable=False)
    budget_limit_usd = Column(Float, default=25.0, nullable=False)
    configuration_version = Column(Integer, default=1, nullable=False)

    # ICP & Exclusion Rules
    icp_rules = Column(JSON, default=dict, nullable=False)
    exclusion_criteria = Column(JSON, default=dict, nullable=False)
    rate_limits = Column(JSON, default=dict, nullable=False)

    campaign = relationship("Campaign", back_populates="config")

class CampaignTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_templates"

    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), default="General", nullable=False)
    description = Column(String(1000), default="", nullable=False)
    campaign_type = Column(String(50), nullable=False)
    default_config = Column(JSON, default=dict, nullable=False)
    config_defaults = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=True, nullable=False)
