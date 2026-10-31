from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailStatus(str, Enum):
    PUBLICLY_LISTED = "PUBLICLY_LISTED"
    PREDICTED = "PREDICTED"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


class PhoneStatus(str, Enum):
    PUBLICLY_LISTED = "PUBLICLY_LISTED"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


class CompanyStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    DISQUALIFIED = "DISQUALIFIED"
    DUPLICATE = "DUPLICATE"


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)
    website = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    industry = Column(String(150), nullable=True, index=True)
    description = Column(Text, nullable=True)
    
    employee_count_range = Column(String(50), nullable=True)
    confidence_score = Column(Float, default=0.0, nullable=False)
    lead_score = Column(Integer, default=0, nullable=False)
    lead_score_reasons = Column(JSON, default=list, nullable=False)
    status = Column(String(50), default="NEW", nullable=False, index=True)
    
    metadata_payload = Column(JSON, default=dict, nullable=False)

    # Relationships
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    signals = relationship("IntentSignal", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_comp_workspace_domain", "workspace_id", "domain"),
        Index("idx_comp_workspace_norm_name", "workspace_id", "normalized_name"),
    )


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contacts"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    full_name = Column(String(255), nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    job_title = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=True)
    seniority = Column(String(50), nullable=True)
    
    email = Column(String(255), nullable=True, index=True)
    email_status = Column(String(50), default="UNVERIFIED", nullable=False)
    business_phone = Column(String(100), nullable=True)
    phone_status = Column(String(50), default="UNVERIFIED", nullable=False)
    
    profile_url = Column(String(500), nullable=True)
    source_url = Column(String(1000), nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    is_decision_maker = Column(Boolean, default=False, nullable=False)
    
    metadata_payload = Column(JSON, default=dict, nullable=False)

    company = relationship("Company", back_populates="contacts")

    __table_args__ = (
        Index("idx_contact_workspace_email", "workspace_id", "email"),
        Index("idx_contact_comp_name", "company_id", "full_name"),
    )


class IntentSignal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intent_signals"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id = Column(String(36), ForeignKey("research_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("research_sources.id", ondelete="SET NULL"), nullable=True)
    
    source_name = Column(String(100), nullable=False, index=True)
    source_url = Column(String(1000), nullable=False)
    signal_type = Column(String(100), nullable=False, index=True)
    detected_keyword = Column(String(150), nullable=False)
    raw_content = Column(Text, nullable=True)
    evidence_snippet = Column(Text, nullable=False)
    signal_strength = Column(Float, default=1.0, nullable=False)
    
    raw_data = Column(JSON, default=dict, nullable=False)

    company = relationship("Company", back_populates="signals")

