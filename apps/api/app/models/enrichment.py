from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EnrichmentType(str, Enum):
    COMPANY_ENRICHMENT = "COMPANY_ENRICHMENT"
    PERSON_ENRICHMENT = "PERSON_ENRICHMENT"
    CONTACT_ENRICHMENT = "CONTACT_ENRICHMENT"
    TECHNOLOGY_ENRICHMENT = "TECHNOLOGY_ENRICHMENT"
    LOCATION_ENRICHMENT = "LOCATION_ENRICHMENT"
    INDUSTRY_ENRICHMENT = "INDUSTRY_ENRICHMENT"
    INTENT_ENRICHMENT = "INTENT_ENRICHMENT"
    DECISION_MAKER_ENRICHMENT = "DECISION_MAKER_ENRICHMENT"
    BUYING_COMMITTEE_ENRICHMENT = "BUYING_COMMITTEE_ENRICHMENT"
    EVIDENCE_ENRICHMENT = "EVIDENCE_ENRICHMENT"


class EnrichmentStatus(str, Enum):
    MISSING = "MISSING"
    DISCOVERING = "DISCOVERING"
    FOUND = "FOUND"
    NORMALIZED = "NORMALIZED"
    VERIFIED = "VERIFIED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class FreshnessTier(str, Enum):
    CURRENT = "CURRENT"
    RECENT = "RECENT"
    AGING = "AGING"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    PAUSED = "PAUSED"


class ContactOwnershipType(str, Enum):
    PERSON_CONTACT = "PERSON_CONTACT"
    COMPANY_CONTACT = "COMPANY_CONTACT"
    SHARED_COMPANY_CONTACT = "SHARED_COMPANY_CONTACT"
    DEPARTMENT_CONTACT = "DEPARTMENT_CONTACT"
    UNKNOWN_OWNER = "UNKNOWN_OWNER"


class EmailDeliverabilityStatus(str, Enum):
    PUBLICLY_LISTED = "PUBLICLY_LISTED"
    VERIFIED_DELIVERABLE = "VERIFIED_DELIVERABLE"
    LIKELY_DELIVERABLE = "LIKELY_DELIVERABLE"
    RISKY = "RISKY"
    CATCH_ALL = "CATCH_ALL"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"
    UNDELIVERABLE = "UNDELIVERABLE"
    PREDICTED = "PREDICTED"


class PhoneType(str, Enum):
    HEAD_OFFICE = "HEAD_OFFICE"
    BRANCH = "BRANCH"
    SALES = "SALES"
    SUPPORT = "SUPPORT"
    DEPARTMENT = "DEPARTMENT"
    PERSONAL_PROFESSIONAL = "PERSONAL_PROFESSIONAL"
    UNKNOWN = "UNKNOWN"


class PrivacyClassification(str, Enum):
    PUBLIC_BUSINESS = "PUBLIC_BUSINESS"
    PUBLIC_PROFESSIONAL = "PUBLIC_PROFESSIONAL"
    COMPANY_GENERIC = "COMPANY_GENERIC"
    PRIVATE = "PRIVATE"
    UNKNOWN = "UNKNOWN"


class RoleChangeType(str, Enum):
    PROMOTION = "PROMOTION"
    COMPANY_CHANGE = "COMPANY_CHANGE"
    DEPARTMENT_CHANGE = "DEPARTMENT_CHANGE"
    TITLE_CHANGE = "TITLE_CHANGE"
    ROLE_DISAPPEARANCE = "ROLE_DISAPPEARANCE"


class EnrichmentDepth(str, Enum):
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    FORENSIC = "FORENSIC"


# 1. Field-Level Provenance & History
class FieldObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "field_observations"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # COMPANY, PERSON, CONTACT
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    
    value = Column(Text, nullable=True)
    raw_value = Column(Text, nullable=True)
    source_name = Column(String(100), nullable=False, index=True)
    source_url = Column(String(1000), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)  # 0.0 - 1.0 or 0-100
    freshness = Column(String(50), default="CURRENT", nullable=False)
    status = Column(String(50), default="FOUND", nullable=False)
    
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_to = Column(DateTime, nullable=True)
    is_canonical = Column(Boolean, default=False, nullable=False)
    metadata_payload = Column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("idx_field_obs_entity_field", "workspace_id", "entity_id", "field_name"),
    )


class FieldValueHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "field_value_histories"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    replaced_by_source = Column(String(100), nullable=False)
    reason = Column(Text, nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# 2. Domain Intelligence
class DomainCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "domain_candidates"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    domain = Column(String(255), nullable=False, index=True)
    normalized_domain = Column(String(255), nullable=False, index=True)
    source_url = Column(String(1000), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default="FOUND", nullable=False)
    
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_dom_candidate_ws_domain", "workspace_id", "normalized_domain"),
    )


# 3. Contact Intelligence & Verification
class ContactPoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contact_points"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(String(36), nullable=True, index=True)
    
    contact_type = Column(String(50), nullable=False, index=True)  # EMAIL, PHONE, URL
    raw_value = Column(String(500), nullable=False)
    normalized_value = Column(String(500), nullable=False, index=True)
    ownership_type = Column(String(50), default="UNKNOWN_OWNER", nullable=False)
    privacy_class = Column(String(50), default="PUBLIC_BUSINESS", nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default="UNVERIFIED", nullable=False)
    
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    source_url = Column(String(1000), nullable=False)

    __table_args__ = (
        Index("idx_cp_workspace_norm", "workspace_id", "contact_type", "normalized_value"),
    )


class ContactVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contact_verifications"

    workspace_id = Column(String(36), nullable=False, index=True)
    contact_point_id = Column(String(36), ForeignKey("contact_points.id", ondelete="CASCADE"), nullable=False, index=True)
    
    syntax_valid = Column(Boolean, default=False, nullable=False)
    domain_valid = Column(Boolean, default=False, nullable=False)
    mx_valid = Column(Boolean, default=False, nullable=False)
    provider_status = Column(String(100), default="UNTESTED", nullable=False)
    deliverability_status = Column(String(50), default="UNVERIFIED", nullable=False)
    verification_provider = Column(String(100), default="INTERNAL_SYNTAX", nullable=False)
    confidence = Column(Float, default=0.5, nullable=False)
    
    verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    raw_response = Column(JSON, default=dict, nullable=False)


class VerificationExpiration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_expirations"

    workspace_id = Column(String(36), nullable=False, index=True)
    contact_point_id = Column(String(36), ForeignKey("contact_points.id", ondelete="CASCADE"), nullable=False, index=True)
    
    verified_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_expired = Column(Boolean, default=False, nullable=False)
    recheck_queued = Column(Boolean, default=False, nullable=False)


# 4. Person & Decision-Maker Intelligence
class PersonRoleObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "person_role_observations"

    workspace_id = Column(String(36), nullable=False, index=True)
    person_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    
    title = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=True)
    seniority = Column(String(50), nullable=True)
    buying_committee_role = Column(String(50), default="End User", nullable=False)
    
    start_date_str = Column(String(50), nullable=True)
    end_date_str = Column(String(50), nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)
    source_url = Column(String(1000), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PersonRoleChangeEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "person_role_change_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    person_id = Column(String(36), nullable=False, index=True)
    
    change_type = Column(String(50), default="COMPANY_CHANGE", nullable=False)  # PROMOTION, COMPANY_CHANGE, etc.
    previous_role = Column(JSON, default=dict, nullable=False)
    new_role = Column(JSON, default=dict, nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    source_url = Column(String(1000), nullable=False)
    affects_buying_committee = Column(Boolean, default=True, nullable=False)


# 5. Company Location Intelligence
class CompanyLocationObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "company_location_observations"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    country = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address_line = Column(String(255), nullable=True)
    postal_code = Column(String(50), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    source_url = Column(String(1000), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# 6. Enrichment Jobs, Tasks & Priority
class EnrichmentJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrichment_jobs"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    
    job_type = Column(String(50), default="COMPANY_ENRICHMENT", nullable=False)
    depth = Column(String(50), default="STANDARD", nullable=False)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    
    total_entities = Column(Integer, default=0, nullable=False)
    completed_entities = Column(Integer, default=0, nullable=False)
    failed_entities = Column(Integer, default=0, nullable=False)
    
    cost_usd = Column(Float, default=0.0, nullable=False)
    budget_limit_usd = Column(Float, default=50.0, nullable=False)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class EnrichmentTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrichment_tasks"

    workspace_id = Column(String(36), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("enrichment_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    
    priority_score = Column(Float, default=0.0, nullable=False)
    expected_info_gain = Column(Float, default=1.0, nullable=False)
    estimated_cost = Column(Float, default=0.01, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    result_summary = Column(JSON, default=dict, nullable=False)


class EnrichmentRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrichment_recommendations"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    
    recommended_action = Column(String(255), nullable=False)
    target_field = Column(String(100), nullable=True)
    target_role = Column(String(100), nullable=True)
    priority = Column(String(50), default="HIGH", nullable=False)
    expected_gain = Column(Float, default=0.8, nullable=False)
    reason = Column(Text, nullable=False)


# 7. Quality & Coverage Metrics
class EnrichmentQuality(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrichment_qualities"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    quality_score = Column(Float, default=0.0, nullable=False)  # 0-100
    completeness_score = Column(Float, default=0.0, nullable=False)
    freshness_score = Column(Float, default=0.0, nullable=False)
    verification_score = Column(Float, default=0.0, nullable=False)
    conflict_rate = Column(Float, default=0.0, nullable=False)
    last_assessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class EnrichmentCoverage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrichment_coverages"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    
    pct_domain = Column(Float, default=0.0, nullable=False)
    pct_technology = Column(Float, default=0.0, nullable=False)
    pct_decision_maker = Column(Float, default=0.0, nullable=False)
    pct_business_email = Column(Float, default=0.0, nullable=False)
    pct_business_phone = Column(Float, default=0.0, nullable=False)
    pct_verified_contacts = Column(Float, default=0.0, nullable=False)
    pct_fresh_fields = Column(Float, default=0.0, nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
