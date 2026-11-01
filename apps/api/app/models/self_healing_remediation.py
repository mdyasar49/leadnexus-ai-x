"""
LeadNexus AI X - Phase 45: Self-Healing, Automated Remediation & Reliability Engineering Models
Provides persistence for remediation playbooks, incidents, execution audit logs,
safety rate limits, and post-remediation metric verifications.
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


class RemediationPlaybook(Base):
    """Catalog entry for an approved automated self-healing action."""
    __tablename__ = "remediation_playbooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    action_type = Column(String(64), nullable=False, index=True)  # RESTART_WORKER, FLUSH_CACHE, FAILOVER_PROVIDER, THROTTLE_INGRESS, RESET_CIRCUIT
    target_subsystem = Column(String(64), nullable=False, index=True)  # worker_pool, model_router, cache_redis, api_gateway
    description = Column(Text, nullable=True)
    parameters = Column(JSON, default=dict)
    cooldown_seconds = Column(Integer, default=300)
    max_executions_per_hour = Column(Integer, default=5)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incidents = relationship("RemediationIncident", back_populates="playbook")
    executions = relationship("RemediationActionExecution", back_populates="playbook")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "action_type": self.action_type,
            "target_subsystem": self.target_subsystem,
            "description": self.description,
            "parameters": self.parameters or {},
            "cooldown_seconds": self.cooldown_seconds,
            "max_executions_per_hour": self.max_executions_per_hour,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RemediationIncident(Base):
    """Reliability incident tracking detection, auto-remediation, verification, and resolution."""
    __tablename__ = "remediation_incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), nullable=True, index=True)
    metric_name = Column(String(128), nullable=False, index=True)
    trigger_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    status = Column(String(32), default="DETECTED", index=True)  # DETECTED, REMEDIATING, VERIFYING, RESOLVED, ESCALATED, FAILED
    severity = Column(String(16), default="WARNING")  # INFO, WARNING, CRITICAL
    assigned_playbook_id = Column(String(36), ForeignKey("remediation_playbooks.id"), nullable=True)
    details = Column(JSON, default=dict)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = Column(DateTime, nullable=True)

    playbook = relationship("RemediationPlaybook", back_populates="incidents")
    executions = relationship("RemediationActionExecution", back_populates="incident", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "metric_name": self.metric_name,
            "trigger_value": self.trigger_value,
            "threshold": self.threshold,
            "status": self.status,
            "severity": self.severity,
            "assigned_playbook_id": self.assigned_playbook_id,
            "details": self.details or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class RemediationActionExecution(Base):
    """Audit log of an executed automated self-healing action with pre/post verification."""
    __tablename__ = "remediation_action_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = Column(String(36), ForeignKey("remediation_incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    playbook_id = Column(String(36), ForeignKey("remediation_playbooks.id"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False)
    target_subsystem = Column(String(64), nullable=False)
    execution_payload = Column(JSON, default=dict)
    pre_metric_value = Column(Float, nullable=False)
    post_metric_value = Column(Float, nullable=True)
    outcome = Column(String(32), default="SUCCESS")  # SUCCESS, NO_IMPROVEMENT, FAILED, ROLLED_BACK
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incident = relationship("RemediationIncident", back_populates="executions")
    playbook = relationship("RemediationPlaybook", back_populates="executions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "playbook_id": self.playbook_id,
            "action_type": self.action_type,
            "target_subsystem": self.target_subsystem,
            "execution_payload": self.execution_payload or {},
            "pre_metric_value": self.pre_metric_value,
            "post_metric_value": self.post_metric_value,
            "outcome": self.outcome,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class RemediationRateLimitLog(Base):
    """Tracks safety bounds and cooldowns to prevent remediation cascading loops."""
    __tablename__ = "remediation_rate_limit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subsystem = Column(String(64), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    count_last_hour = Column(Integer, default=1)
    max_per_hour = Column(Integer, default=5)
    last_executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subsystem": self.subsystem,
            "action_type": self.action_type,
            "count_last_hour": self.count_last_hour,
            "max_per_hour": self.max_per_hour,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
        }
