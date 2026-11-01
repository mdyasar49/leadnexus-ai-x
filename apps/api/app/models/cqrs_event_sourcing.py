"""
LeadNexus AI X — Phase 36: CQRS, Event Sourcing & Schema Registry Models
Supports selective Event Sourced Aggregates, Snapshots, Command Idempotency,
Event Schema Registry, and Dead Letter Queue (DLQ) management.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    Enum as SQLEnum,
    JSON,
    Index,
    Text,
)
from app.db.base import Base


class SchemaCompatibility(str, enum.Enum):
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"
    FORWARD_COMPATIBLE = "FORWARD_COMPATIBLE"
    FULLY_COMPATIBLE = "FULLY_COMPATIBLE"
    BREAKING = "BREAKING"


class CommandStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class DLQReason(str, enum.Enum):
    SCHEMA_ERROR = "SCHEMA_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    MISSING_ENTITY = "MISSING_ENTITY"
    TEMPORARY_PROVIDER_FAILURE = "TEMPORARY_PROVIDER_FAILURE"
    TIMEOUT = "TIMEOUT"
    LOOP_DETECTED = "LOOP_DETECTED"
    UNKNOWN = "UNKNOWN"


class DLQStatus(str, enum.Enum):
    UNRESOLVED = "UNRESOLVED"
    RETRIED = "RETRIED"
    DISCARDED = "DISCARDED"
    REPAIRED = "REPAIRED"


class EventSchemaRecord(Base):
    """Event Schema Registry storing schema versions, definitions, and compatibility metadata."""
    __tablename__ = "event_schema_registry"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(128), nullable=False, index=True)
    version = Column(String(16), nullable=False, default="1.0.0")  # SemVer
    schema_definition = Column(JSON, nullable=False)  # JSON Schema definition
    fingerprint = Column(String(64), nullable=False, index=True)  # SHA-256 fingerprint
    compatibility = Column(SQLEnum(SchemaCompatibility), nullable=False, default=SchemaCompatibility.BACKWARD_COMPATIBLE)
    is_deprecated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_schema_type_version", "event_type", "version", unique=True),
    )


class AggregateEvent(Base):
    """Selective Event Sourced record for historical state reconstruction."""
    __tablename__ = "aggregate_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    aggregate_type = Column(String(64), nullable=False, index=True)  # e.g., "Lead", "ResearchRun", "Review"
    aggregate_id = Column(String(128), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)  # Strictly monotonic 1, 2, 3...
    event_type = Column(String(128), nullable=False, index=True)
    event_version = Column(String(16), nullable=False, default="1.0.0")
    payload = Column(JSON, nullable=False, default=dict)
    causation_id = Column(String(64), nullable=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agg_events_seq", "tenant_id", "aggregate_type", "aggregate_id", "sequence_number", unique=True),
    )


class AggregateSnapshot(Base):
    """Optimized state checkpoint preventing full-stream replay overhead."""
    __tablename__ = "aggregate_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(128), nullable=False, index=True)
    last_sequence_number = Column(Integer, nullable=False)
    snapshot_version = Column(Integer, nullable=False, default=1)
    state = Column(JSON, nullable=False)  # Materialized aggregate state
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agg_snapshot_latest", "tenant_id", "aggregate_type", "aggregate_id"),
    )


class CommandIdempotencyRecord(Base):
    """Enforces strict idempotency on incoming state mutation commands."""
    __tablename__ = "command_idempotency_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    command_name = Column(String(128), nullable=False)
    actor_id = Column(String(64), nullable=False)
    status = Column(SQLEnum(CommandStatus), nullable=False, default=CommandStatus.EXECUTED)
    result_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class DeadLetterEvent(Base):
    """Quarantine for failed event processing, with audit trails and redrive capability."""
    __tablename__ = "dead_letter_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    original_event_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    consumer_name = Column(String(128), nullable=False, index=True)
    reason = Column(SQLEnum(DLQReason), nullable=False, default=DLQReason.UNKNOWN)
    error_details = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False)
    propagation_depth = Column(Integer, nullable=False, default=1)
    status = Column(SQLEnum(DLQStatus), nullable=False, default=DLQStatus.UNRESOLVED, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

