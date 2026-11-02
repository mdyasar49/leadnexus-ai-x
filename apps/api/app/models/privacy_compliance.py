"""
LeadNexus AI X - Phase 48: Privacy Engineering, Consent Vault & Data Subject Rights Models
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer, Text
from app.db.base import Base


class OptOutType(str, Enum):
    GDPR_RTBF = "GDPR_RTBF"  # Right to be Forgotten
    CCPA_DO_NOT_SELL = "CCPA_DO_NOT_SELL"
    MARKETING_SUPPRESSION = "MARKETING_SUPPRESSION"
    GLOBAL_EXCLUSION = "GLOBAL_EXCLUSION"


class DSARType(str, Enum):
    ACCESS_EXPORT = "ACCESS_EXPORT"
    ERASURE = "ERASURE"
    RECTIFICATION = "RECTIFICATION"


class DSARStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ConsentOptOutRecord(Base):
    __tablename__ = "consent_opt_outs"

    id = Column(String(64), primary_key=True, default=lambda: f"opt_{uuid.uuid4().hex[:12]}")
    subject_email = Column(String(255), nullable=True, index=True)
    subject_domain = Column(String(255), nullable=True, index=True)
    opt_out_type = Column(String(32), default=OptOutType.GDPR_RTBF.value, index=True)
    reason = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DSARRequestRecord(Base):
    __tablename__ = "dsar_requests"

    id = Column(String(64), primary_key=True, default=lambda: f"dsar_{uuid.uuid4().hex[:12]}")
    request_type = Column(String(32), default=DSARType.ACCESS_EXPORT.value, index=True)
    subject_email = Column(String(255), nullable=False, index=True)
    status = Column(String(32), default=DSARStatus.SUBMITTED.value, index=True)
    evidence_digest = Column(String(64), nullable=True)
    report_data = Column(JSON, default=dict)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class PrivacyAuditRecord(Base):
    __tablename__ = "privacy_audit_logs"

    id = Column(String(64), primary_key=True, default=lambda: f"paudit_{uuid.uuid4().hex[:12]}")
    action = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=True)
    target_subject = Column(String(255), nullable=False)
    policy_applied = Column(String(64), nullable=False)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# --- Pydantic Schemas ---

class CreateOptOutRequest(BaseModel):
    subject_email: Optional[str] = None
    subject_domain: Optional[str] = None
    opt_out_type: OptOutType = OptOutType.GDPR_RTBF
    reason: Optional[str] = "User requested exclusion"


class OptOutResponse(BaseModel):
    id: str
    subject_email: Optional[str]
    subject_domain: Optional[str]
    opt_out_type: str
    reason: Optional[str]
    is_active: bool
    requested_at: datetime


class CreateDSARRequest(BaseModel):
    request_type: DSARType
    subject_email: str


class DSARResponse(BaseModel):
    id: str
    request_type: str
    subject_email: str
    status: str
    evidence_digest: Optional[str]
    submitted_at: datetime
    completed_at: Optional[datetime]
    report_data: Dict[str, Any] = Field(default_factory=dict)


class PIIScrubRequest(BaseModel):
    text: str
    preserve_business_contacts: bool = True


class PIIScrubResponse(BaseModel):
    scrubbed_text: str
    redactions_count: int
    redacted_categories: List[str]


class PseudonymizeRequest(BaseModel):
    values: List[str]
    salt: Optional[str] = "leadnexus_privacy_salt_v1"


class PseudonymizeResponse(BaseModel):
    pseudonymized_values: List[str]
    key_fingerprint: str


class KAnonymityRequest(BaseModel):
    records: List[Dict[str, Any]]
    quasi_identifiers: List[str]
    k_threshold: int = 5


class KAnonymityResponse(BaseModel):
    is_k_anonymous: bool
    min_k: int
    violating_cohorts_count: int
    total_cohorts: int
    recommendations: List[str]


class PrivacyStatsResponse(BaseModel):
    total_opt_outs: int
    active_dsar_requests: int
    completed_dsar_requests: int
    total_audit_events: int
    active_suppression_domains: int
    compliance_score_percent: float
