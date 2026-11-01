"""
Enterprise Data Fabric Models (Phase 39)
Provides unified data contracts, data catalog, lineage, cross-domain entity graphs,
data quality scoring, and policy enforcement across all 13 enterprise domains.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class DataDomainEnum:
    COMPANIES = "COMPANIES"
    PEOPLE = "PEOPLE"
    CONTACTS = "CONTACTS"
    LEADS = "LEADS"
    EVIDENCE = "EVIDENCE"
    SIGNALS = "SIGNALS"
    INTENT = "INTENT"
    RESEARCH = "RESEARCH"
    GRAPH = "GRAPH"
    ANALYTICS = "ANALYTICS"
    WORKFLOWS = "WORKFLOWS"
    MONITORING = "MONITORING"
    INTEGRATIONS = "INTEGRATIONS"

    ALL_DOMAINS = [
        COMPANIES,
        PEOPLE,
        CONTACTS,
        LEADS,
        EVIDENCE,
        SIGNALS,
        INTENT,
        RESEARCH,
        GRAPH,
        ANALYTICS,
        WORKFLOWS,
        MONITORING,
        INTEGRATIONS,
    ]


class DataClassification:
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ContractStatus:
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class PolicyEnforcementAction:
    ALLOW = "ALLOW"
    MASK = "MASK"
    RESTRICT = "RESTRICT"
    BLOCK = "BLOCK"


class DataContractRecord(Base):
    """Formal schema and SLA specification for an enterprise data domain asset."""

    __tablename__ = "data_contract_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(32), nullable=False, index=True)
    contract_version = Column(String(16), default="1.0.0", nullable=False)
    asset_name = Column(String(128), nullable=False)
    schema_definition = Column(JSON, default=dict, nullable=False)  # JSON Schema specification
    sla_freshness_seconds = Column(Integer, default=3600, nullable=False)  # Max allowed data age
    quality_rules = Column(JSON, default=list, nullable=False)  # Completeness, regex, range constraints
    owner_team = Column(String(64), default="Data Engineering", nullable=False)
    status = Column(String(16), default=ContractStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class DataCatalogEntry(Base):
    """Metadata catalog entry for cross-domain asset discovery."""

    __tablename__ = "data_catalog_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(32), nullable=False, index=True)
    asset_name = Column(String(128), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
    fields = Column(JSON, default=list, nullable=False)  # [{name, type, description, is_pii}]
    tags = Column(JSON, default=list, nullable=False)  # ["b2b", "search", "canonical"]
    classification = Column(String(16), default=DataClassification.INTERNAL, nullable=False)
    freshness_updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    owner_email = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataLineageEdge(Base):
    """Directed dependency edge between source and target domain assets."""

    __tablename__ = "data_lineage_edges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    source_domain = Column(String(32), nullable=False, index=True)
    source_asset = Column(String(128), nullable=False)
    target_domain = Column(String(32), nullable=False, index=True)
    target_asset = Column(String(128), nullable=False)
    transformation_type = Column(String(32), default="ETL", nullable=False)  # ETL, CDC, AGGREGATION, ENRICHMENT, INFERENCE
    lineage_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CrossDomainRelation(Base):
    """High-order semantic relationship connecting disparate domain entities."""

    __tablename__ = "cross_domain_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    primary_domain = Column(String(32), nullable=False, index=True)
    primary_entity_id = Column(String(64), nullable=False, index=True)
    related_domain = Column(String(32), nullable=False, index=True)
    related_entity_id = Column(String(64), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False)  # EMPLOYED_AT, SIGNAL_FROM, INTENT_SURFACED_BY, etc.
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataQualityAssessment(Base):
    """Automated multi-dimensional data quality score for a domain asset."""

    __tablename__ = "data_quality_assessments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    domain = Column(String(32), nullable=False, index=True)
    asset_name = Column(String(128), nullable=False, index=True)
    completeness_score = Column(Float, nullable=False)  # 0.0 - 100.0
    validity_score = Column(Float, nullable=False)      # 0.0 - 100.0
    timeliness_score = Column(Float, nullable=False)    # 0.0 - 100.0
    uniqueness_score = Column(Float, nullable=False)    # 0.0 - 100.0
    overall_quality_score = Column(Float, nullable=False)
    violations = Column(JSON, default=list, nullable=False)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataPolicyEnforcement(Base):
    """Enforceable security and governance policy across data fabric domains."""

    __tablename__ = "data_policy_enforcements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    policy_name = Column(String(128), nullable=False)
    target_domain = Column(String(32), nullable=False, index=True)
    enforcement_action = Column(String(16), default=PolicyEnforcementAction.MASK, nullable=False)
    field_name = Column(String(64), nullable=True)  # Field to mask or check
    condition_expression = Column(String(255), nullable=True)  # Optional SQL/Expr condition
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
