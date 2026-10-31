"""
LeadNexus AI X - Phase 33: Enterprise Data Migration, Schema Evolution & Zero-Downtime Upgrade Models
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


class MigrationPhase(str, enum.Enum):
    PLANNED = "PLANNED"
    EXPANDING = "EXPANDING"
    BACKFILLING = "BACKFILLING"
    RECONCILING = "RECONCILING"
    CONTRACTING = "CONTRACTING"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"


class BackfillStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReconciliationStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class SchemaMigrationPlan(Base):
    __tablename__ = "schema_migration_plans"

    id = Column(String(100), primary_key=True)  # e.g. "plan_v27_to_v28_company_enrichment"
    name = Column(String(255), nullable=False)
    source_version = Column(String(50), nullable=False)
    target_version = Column(String(50), nullable=False)
    phase = Column(String(50), default=MigrationPhase.PLANNED.value, nullable=False)
    plan_definition = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class BackfillJob(Base):
    __tablename__ = "backfill_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    migration_plan_id = Column(String(100), ForeignKey("schema_migration_plans.id"), nullable=False, index=True)
    table_name = Column(String(100), nullable=False)
    chunk_size = Column(Integer, default=500, nullable=False)
    current_cursor = Column(String(255), nullable=True)
    total_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default=BackfillStatus.PENDING.value, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class ReconciliationJob(Base):
    __tablename__ = "reconciliation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    migration_plan_id = Column(String(100), ForeignKey("schema_migration_plans.id"), nullable=False, index=True)
    table_name = Column(String(100), nullable=False)
    source_column = Column(String(100), nullable=False)
    target_column = Column(String(100), nullable=False)
    records_evaluated = Column(Integer, default=0, nullable=False)
    discrepancies_count = Column(Integer, default=0, nullable=False)
    parity_pct = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default=ReconciliationStatus.RUNNING.value, nullable=False)
    report = Column(JSON, default=dict)
    completed_at = Column(DateTime, nullable=True)


class APIVersionContract(Base):
    __tablename__ = "api_version_contracts"

    id = Column(String(50), primary_key=True)  # e.g. "v1", "v2"
    api_version = Column(String(50), nullable=False)
    is_deprecated = Column(Boolean, default=False, nullable=False)
    sunset_date = Column(DateTime, nullable=True)
    breaking_changes = Column(JSON, default=list)
    min_supported_client_version = Column(String(50), default="1.0.0", nullable=False)
