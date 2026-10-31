"""
LeadNexus AI X - Phase 30: Enterprise Reliability, Resilience, Disaster Recovery & Self-Healing Models
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


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class IncidentStatus(str, enum.Enum):
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"


class DLQStatus(str, enum.Enum):
    QUARANTINED = "QUARANTINED"
    REDRIVEN = "REDRIVEN"
    DISCARDED = "DISCARDED"


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class BackupStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    CORRUPTED = "CORRUPTED"


class TaskLease(Base):
    __tablename__ = "task_leases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(255), nullable=False, unique=True, index=True)
    worker_id = Column(String(255), nullable=False)
    fencing_token = Column(Integer, default=1, nullable=False)
    lease_acquired_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    lease_expires_at = Column(DateTime, nullable=False, index=True)
    heartbeat_count = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class DeadLetterMessage(Base):
    __tablename__ = "dead_letter_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    queue_name = Column(String(100), nullable=False, index=True)
    task_id = Column(String(255), nullable=False)
    payload = Column(JSON, default=dict)
    error_category = Column(String(100), default="UNCLASSIFIED", nullable=False)
    error_message = Column(Text, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    quarantined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(50), default=DLQStatus.QUARANTINED.value, nullable=False)


class CircuitBreakerState(Base):
    __tablename__ = "circuit_breaker_states"

    id = Column(String(100), primary_key=True)  # service_name, e.g. "github_api", "google_sheets"
    state = Column(String(50), default=CircuitState.CLOSED.value, nullable=False)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_failure_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    half_opened_at = Column(DateTime, nullable=True)
    cooldown_seconds = Column(Integer, default=30, nullable=False)


class BackupSnapshot(Base):
    __tablename__ = "backup_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)
    records_count = Column(Integer, default=0, nullable=False)
    size_bytes = Column(Integer, default=0, nullable=False)
    verification_status = Column(String(50), default=BackupStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    verified_at = Column(DateTime, nullable=True)


class SelfHealingAction(Base):
    __tablename__ = "self_healing_actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_name = Column(String(255), nullable=False)
    trigger_event = Column(String(255), nullable=False)
    target_resource = Column(String(255), nullable=False)
    action_taken = Column(String(255), nullable=False)
    remediation_status = Column(String(50), default="SUCCESS", nullable=False)
    details = Column(JSON, default=dict)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PlatformIncident(Base):
    __tablename__ = "platform_incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    severity = Column(String(50), default=IncidentSeverity.MAJOR.value, nullable=False)
    status = Column(String(50), default=IncidentStatus.INVESTIGATING.value, nullable=False)
    affected_components = Column(JSON, default=list)
    root_cause = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
