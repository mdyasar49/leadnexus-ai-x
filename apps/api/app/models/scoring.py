from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LeadPriorityTier(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"
    P4_IGNORE = "P4_IGNORE"


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    STALE = "STALE"
    REJECTED = "REJECTED"


class ICPProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "icp_profiles"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    target_industries = Column(JSON, default=list, nullable=False)
    target_countries = Column(JSON, default=list, nullable=False)
    target_technologies = Column(JSON, default=list, nullable=False)
    target_job_titles = Column(JSON, default=list, nullable=False)
    
    min_employees = Column(Integer, default=1, nullable=False)
    max_employees = Column(Integer, default=50000, nullable=False)
    weights = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class IntentAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intent_assessments"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    intent_score = Column(Float, default=0.0, nullable=False)  # 0-100
    primary_intent = Column(String(100), nullable=True)
    secondary_intents = Column(JSON, default=list, nullable=False)
    
    positive_signals_count = Column(Integer, default=0, nullable=False)
    negative_signals_count = Column(Integer, default=0, nullable=False)
    corroboration_count = Column(Integer, default=0, nullable=False)
    temporal_decay_factor = Column(Float, default=1.0, nullable=False)
    is_service_provider = Column(Boolean, default=False, nullable=False)
    assessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntentTimelineEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intent_timeline_events"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    event_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    source_type = Column(String(100), nullable=False)
    source_url = Column(String(1000), nullable=False)
    intent_type = Column(String(100), nullable=False)
    signal_strength = Column(Float, default=1.0, nullable=False)
    evidence_snippet = Column(Text, nullable=False)
    confidence = Column(Float, default=0.8, nullable=False)


class PainPoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pain_points"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    category = Column(String(100), nullable=False)  # e.g., "ERP_MIGRATION", "INTEGRATION_FAILURE"
    description = Column(Text, nullable=False)
    evidence_ids = Column(JSON, default=list, nullable=False)
    severity = Column(String(50), default="HIGH", nullable=False)
    confidence = Column(Float, default=0.85, nullable=False)


class UseCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "use_cases"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    use_case_type = Column(String(100), nullable=False)  # "ERP_IMPLEMENTATION", "ECOMMERCE_INTEGRATION"
    description = Column(Text, nullable=False)
    evidence_ids = Column(JSON, default=list, nullable=False)
    confidence = Column(Float, default=0.9, nullable=False)


class BuyingReadinessAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "buying_readiness_assessments"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    readiness_score = Column(Float, default=0.0, nullable=False)  # 0-100
    timeline_indicator = Column(String(50), default="IMMEDIATE", nullable=False)  # IMMEDIATE, 1-3_MONTHS, EXPLORATORY
    has_active_hiring = Column(Boolean, default=False, nullable=False)
    has_decision_maker_identified = Column(Boolean, default=False, nullable=False)
    readiness_factors = Column(JSON, default=list, nullable=False)


class EvidenceClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_claims"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    claim_type = Column(String(100), nullable=False)  # "USES_ODOO", "NEEDS_MIGRATION", "RETAIL_SECTOR"
    claim_text = Column(Text, nullable=False)
    supporting_evidence_ids = Column(JSON, default=list, nullable=False)
    contradicting_evidence_ids = Column(JSON, default=list, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(50), default="SUPPORTED", nullable=False)


class LeadScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_scores"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    
    lead_priority_score = Column(Float, default=0.0, nullable=False, index=True)  # Overall 0-100
    priority_tier = Column(String(50), default="P3_LOW", nullable=False, index=True)
    
    # 8 Separate Component Scores
    icp_fit_score = Column(Float, default=0.0, nullable=False)
    intent_score = Column(Float, default=0.0, nullable=False)
    buying_readiness_score = Column(Float, default=0.0, nullable=False)
    evidence_confidence_score = Column(Float, default=0.0, nullable=False)
    data_quality_score = Column(Float, default=0.0, nullable=False)
    contact_quality_score = Column(Float, default=0.0, nullable=False)
    research_completeness_score = Column(Float, default=0.0, nullable=False)
    freshness_score = Column(Float, default=0.0, nullable=False)
    
    positive_factors = Column(JSON, default=list, nullable=False)
    negative_factors = Column(JSON, default=list, nullable=False)
    calculation_version = Column(String(20), default="v1.0", nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ScoreCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "score_calculations"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    score_before = Column(Float, default=0.0, nullable=False)
    score_after = Column(Float, default=0.0, nullable=False)
    delta = Column(Float, default=0.0, nullable=False)
    reason = Column(Text, nullable=False)
    inputs_hash = Column(String(64), nullable=False)
    calculation_metadata = Column(JSON, default=dict, nullable=False)


class AIReasoningResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_reasoning_results"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    primary_need = Column(String(255), nullable=True)
    reasoning_summary = Column(Text, nullable=False)
    positive_evidence_ids = Column(JSON, default=list, nullable=False)
    negative_evidence_ids = Column(JSON, default=list, nullable=False)
    contradictions = Column(JSON, default=list, nullable=False)
    missing_information = Column(JSON, default=list, nullable=False)
    recommended_actions = Column(JSON, default=list, nullable=False)
    ai_confidence = Column(Float, default=0.9, nullable=False)


class FieldConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "field_conflicts"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    field_name = Column(String(100), nullable=False)  # e.g., "odoo_version"
    value_a = Column(String(255), nullable=False)
    source_a = Column(String(500), nullable=False)
    value_b = Column(String(255), nullable=False)
    source_b = Column(String(500), nullable=False)
    resolution_status = Column(String(50), default="CONFLICTED", nullable=False)  # CURRENTLY_BELIEVED, CONFLICTED, UNKNOWN
    chosen_value = Column(String(255), nullable=True)


class PromptTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_templates"

    name = Column(String(100), nullable=False, unique=True)
    version = Column(String(20), default="1.0.0", nullable=False)
    template_text = Column(Text, nullable=False)
    model_family = Column(String(50), default="gemini-2.0-flash", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class AIUsageEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_usage_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True)
    company_id = Column(String(36), nullable=True)
    
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
    task_name = Column(String(100), default="evidence_reasoning", nullable=False)


class HumanAIReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "human_ai_reviews"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    
    escalation_reason = Column(String(100), nullable=False)  # AI_LOW_CONFIDENCE, ENTITY_CONFLICT, etc.
    ai_recommendation = Column(Text, nullable=False)
    human_decision = Column(String(50), nullable=True)  # APPROVED, REJECTED, MODIFIED
    correction_notes = Column(Text, nullable=True)
    reviewer_user_id = Column(String(36), nullable=True)
    is_reviewed = Column(Boolean, default=False, nullable=False, index=True)

