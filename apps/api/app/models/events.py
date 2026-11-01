"""
Phase 34: Enterprise Event-Driven Architecture Models.
Defines OutboxEvent, EventSubscription, ConsumerOffset, and EventReplayJob.
Strict tenant isolation and transactional integrity.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
    Index,
    Text,
)
from app.db.base import Base


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class ReplayStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(128), nullable=False, index=True)
    event_version = Column(String(16), nullable=False, default="1.0.0")
    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(128), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    source_service = Column(String(64), nullable=False, default="leadnexus-api")
    correlation_id = Column(String(64), nullable=False, index=True)
    causation_id = Column(String(64), nullable=True)
    schema_version = Column(String(16), nullable=False, default="1.0.0")
    payload = Column(JSON, nullable=False, default=dict)
    checksum = Column(String(64), nullable=True)
    status = Column(SQLEnum(OutboxStatus), nullable=False, default=OutboxStatus.PENDING, index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_outbox_events_tenant_status", "tenant_id", "status"),
        Index("ix_outbox_events_aggregate", "tenant_id", "aggregate_type", "aggregate_id"),
    )


class EventSubscription(Base):
    __tablename__ = "event_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    consumer_name = Column(String(128), nullable=False, index=True)
    event_type_pattern = Column(String(128), nullable=False, index=True)  # e.g., "company.*", "lead.scored"
    destination_endpoint = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    max_retries = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ConsumerOffset(Base):
    __tablename__ = "consumer_offsets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consumer_name = Column(String(128), nullable=False, unique=True, index=True)
    stream_partition = Column(String(64), nullable=False, default="partition-0")
    last_processed_event_id = Column(String(36), nullable=True)
    processed_count = Column(Integer, nullable=False, default=0)
    last_processed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class EventReplayJob(Base):
    __tablename__ = "event_replay_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    initiated_by = Column(String(36), nullable=False)
    target_consumer = Column(String(128), nullable=False)
    filter_event_types = Column(JSON, nullable=False, default=list)
    from_timestamp = Column(DateTime(timezone=True), nullable=False)
    to_timestamp = Column(DateTime(timezone=True), nullable=False)
    dry_run = Column(Boolean, nullable=False, default=False)
    status = Column(SQLEnum(ReplayStatus), nullable=False, default=ReplayStatus.PENDING)
    replayed_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
