"""
LeadNexus AI X - Phase 29: Enterprise Governance, Policy Engine, Data Contracts & Platform Administration Models
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


# --- Enums ---

class PolicyType(str, enum.Enum):
    ACCESS = "ACCESS"
    EXPORT = "EXPORT"
    DATA_MUTATION = "DATA_MUTATION"
    AUTONOMY = "AUTONOMY"
    PRIVACY = "PRIVACY"


class PolicyEffect(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    MASK = "MASK"


class ContractEnforcementMode(str, enum.Enum):
    STRICT_REJECT = "STRICT_REJECT"
    WARN_AND_LOG = "WARN_AND_LOG"


class SuppressionType(str, enum.Enum):
    DOMAIN = "DOMAIN"
    EMAIL = "EMAIL"
    COMPANY_NAME = "COMPANY_NAME"


# --- Models ---

class GovernancePolicy(Base):
    __tablename__ = "governance_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    policy_type = Column(String(50), default=PolicyType.ACCESS.value, nullable=False)
    effect = Column(String(50), default=PolicyEffect.DENY.value, nullable=False)
    rules_dsl = Column(JSON, default=dict)
    priority = Column(Integer, default=100, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PolicyEvaluationEvent(Base):
    __tablename__ = "policy_evaluation_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    policy_id = Column(String(36), ForeignKey("governance_policies.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    actor_id = Column(String(255), nullable=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=True)
    decision = Column(String(50), nullable=False)  # ALLOW, DENY, REQUIRE_APPROVAL, MASK
    matched_rule = Column(String(255), nullable=True)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataContract(Base):
    __tablename__ = "data_contracts"

    id = Column(String(100), primary_key=True)  # e.g. "contract_company_profile_v1"
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)  # "COMPANY", "CONTACT", "SIGNAL"
    version = Column(String(50), default="1.0.0", nullable=False)
    schema_definition = Column(JSON, default=dict)
    sla_freshness_hours = Column(Integer, default=72, nullable=False)
    min_completeness_score = Column(Float, default=0.70, nullable=False)
    enforcement_mode = Column(String(50), default=ContractEnforcementMode.STRICT_REJECT.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataContractViolation(Base):
    __tablename__ = "data_contract_violations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String(100), ForeignKey("data_contracts.id"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    producer_id = Column(String(255), nullable=False)
    violation_type = Column(String(100), nullable=False)  # "SCHEMA_MISMATCH", "MISSING_REQUIRED_FIELD", "SLA_BREACH"
    details = Column(JSON, default=dict)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SuppressionRecord(Base):
    __tablename__ = "suppression_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    suppression_type = Column(String(50), default=SuppressionType.DOMAIN.value, nullable=False)
    pattern = Column(String(255), nullable=False, index=True)  # e.g. "competitor.com", "ceo@target.com"
    reason = Column(String(255), nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class LegalHold(Base):
    __tablename__ = "legal_holds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    target_entity_type = Column(String(50), nullable=False)  # "COMPANY", "CONTACT", "ALL"
    target_entity_id = Column(String(255), nullable=True, index=True)
    case_reference = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    placed_by = Column(String(255), nullable=True)
    placed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    released_at = Column(DateTime, nullable=True)


class TenantQuota(Base):
    __tablename__ = "tenant_quotas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, unique=True, index=True)
    max_daily_research_budget_usd = Column(Float, default=100.0, nullable=False)
    max_concurrent_runs = Column(Integer, default=5, nullable=False)
    max_monthly_exports = Column(Integer, default=10000, nullable=False)
    current_daily_spend_usd = Column(Float, default=0.0, nullable=False)
    is_enforced = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
