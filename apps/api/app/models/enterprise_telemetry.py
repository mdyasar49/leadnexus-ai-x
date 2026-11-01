"""
LeadNexus AI X - Phase 44: Enterprise Analytics, Observability, Cost & Platform Telemetry Models
Provides time-series metric persistence, distributed tracing spans, multi-dimensional cost allocation,
and automated SLA anomaly alerting rules and events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class TelemetryMetricRecord(Base):
    """Time-series metric data point (Counter, Gauge, Histogram)."""
    __tablename__ = "telemetry_metric_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=True, index=True)
    metric_name = Column(String(128), nullable=False, index=True)
    metric_type = Column(String(32), default="GAUGE", index=True)  # COUNTER, GAUGE, HISTOGRAM
    value = Column(Float, nullable=False)
    labels = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "metric_name": self.metric_name,
            "metric_type": self.metric_type,
            "value": self.value,
            "labels": self.labels or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class DistributedTraceSpan(Base):
    """OpenTelemetry-compatible distributed trace span."""
    __tablename__ = "distributed_trace_spans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(36), nullable=False, index=True)
    parent_span_id = Column(String(36), nullable=True, index=True)
    service_name = Column(String(64), default="leadnexus-api", index=True)
    operation_name = Column(String(128), nullable=False)
    duration_ms = Column(Float, default=0.0)
    status_code = Column(String(16), default="OK")  # OK, ERROR
    attributes = Column(JSON, default=dict)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "attributes": self.attributes or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class CostAllocationRecord(Base):
    """Tracks granular resource cost attribution across workspaces and components."""
    __tablename__ = "cost_allocation_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    billing_entity = Column(String(64), nullable=False, index=True)  # AI_INFERENCE, WORKER_COMPUTE, STORAGE, NETWORK
    subsystem = Column(String(64), default="core")  # model_router, agent_runtime, document_ocr, database
    cost_micros = Column(Integer, default=0)  # Micro-USD (1,000,000 = $1.00 USD)
    units_consumed = Column(Float, default=1.0)
    unit_type = Column(String(32), default="TOKENS")  # TOKENS, MILLISECONDS, BYTES, REQUESTS
    metadata_payload = Column(JSON, default=dict)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "billing_entity": self.billing_entity,
            "subsystem": self.subsystem,
            "cost_micros": self.cost_micros,
            "cost_usd": self.cost_micros / 1_000_000.0,
            "units_consumed": self.units_consumed,
            "unit_type": self.unit_type,
            "metadata_payload": self.metadata_payload or {},
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }


class TelemetryAlertRule(Base):
    """Dynamic alert threshold definition for platform metrics."""
    __tablename__ = "telemetry_alert_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    metric_name = Column(String(128), nullable=False, index=True)
    condition = Column(String(16), default="GT")  # GT, LT, EQ, GTE, LTE
    threshold = Column(Float, nullable=False)
    duration_seconds = Column(Integer, default=60)
    severity = Column(String(16), default="WARNING", index=True)  # INFO, WARNING, CRITICAL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    events = relationship("TelemetryAlertEvent", back_populates="rule", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "duration_seconds": self.duration_seconds,
            "severity": self.severity,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TelemetryAlertEvent(Base):
    """Emitted alert event when an alert rule condition is breached."""
    __tablename__ = "telemetry_alert_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("telemetry_alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(128), nullable=False)
    observed_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    status = Column(String(32), default="TRIGGERED", index=True)  # TRIGGERED, RESOLVED, ACKNOWLEDGED
    details = Column(JSON, default=dict)
    triggered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = Column(DateTime, nullable=True)

    rule = relationship("TelemetryAlertRule", back_populates="events")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "status": self.status,
            "details": self.details or {},
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

