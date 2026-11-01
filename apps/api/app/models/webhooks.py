"""
LeadNexus AI X — Enterprise Webhook Delivery & Replay Defense Models
Phase 35: Cryptographic HMAC-SHA256 Signing, Replay Attack Defense, Circuit Breakers & Dead-Letter Redrive
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from app.db.base import Base


class EnterpriseWebhookEndpoint(Base):
    """
    Enterprise registered webhook destination with tenant isolation,
    HMAC secret key, subscribed event patterns, and circuit breaker state.
    """
    __tablename__ = "enterprise_webhook_endpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    secret_token = Column(String(128), nullable=False)  # e.g. whsec_...
    event_patterns = Column(JSON, nullable=False, default=list)  # e.g. ["company.*", "lead.scored"]
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Circuit Breaker state
    circuit_status = Column(String(32), default="CLOSED", nullable=False)  # CLOSED, OPEN, HALF_OPEN
    consecutive_failures = Column(Integer, default=0, nullable=False)
    circuit_opened_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ent_webhook_endpoints_tenant_active", "tenant_id", "is_active"),
    )


class EnterpriseWebhookDelivery(Base):
    """
    Audited record of an individual webhook dispatch attempt with
    tamper-evident signed headers, execution latency, and retry tracking.
    """
    __tablename__ = "enterprise_webhook_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    endpoint_id = Column(String(36), ForeignKey("enterprise_webhook_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    
    payload = Column(JSON, nullable=False)
    headers = Column(JSON, nullable=False)  # X-LeadNexus-Signature-256, X-LeadNexus-Timestamp, X-LeadNexus-Nonce
    
    status_code = Column(Integer, nullable=True)
    execution_duration_ms = Column(Float, nullable=True)
    status = Column(String(32), default="PENDING", nullable=False, index=True)  # PENDING, SUCCESS, RETRYING, FAILED, DEAD_LETTER
    attempt_number = Column(Integer, default=1, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ent_webhook_deliveries_tenant_status", "tenant_id", "status"),
        Index("ix_ent_webhook_deliveries_endpoint_status", "endpoint_id", "status"),
    )


class WebhookReplayGuard(Base):
    """
    Nonce and timestamp cache to detect and reject replay attacks.
    """
    __tablename__ = "webhook_replay_guards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    endpoint_id = Column(String(36), nullable=False, index=True)
    nonce = Column(String(64), nullable=False)
    timestamp = Column(Integer, nullable=False)  # Unix epoch seconds
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_webhook_replay_tenant_nonce", "tenant_id", "nonce", unique=True),
    )


class WebhookRedriveJob(Base):
    """
    Audited batch redrive of failed or dead-lettered webhook deliveries.
    """
    __tablename__ = "webhook_redrive_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    endpoint_id = Column(String(36), nullable=True)
    initiated_by = Column(String(64), nullable=False)
    filter_status = Column(String(32), default="DEAD_LETTER", nullable=False)
    max_attempts = Column(Integer, default=50, nullable=False)
    total_eligible = Column(Integer, default=0, nullable=False)
    redriven_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
