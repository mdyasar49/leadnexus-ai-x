"""
LeadNexus AI X — Phase 37: Enterprise API Gateway & Edge Intelligence Models
Stores tenant quotas, rate limit allocations, edge cache states, circuit breaker telemetry,
and gateway route access metrics.
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
    Float,
    Enum as SQLEnum,
    JSON,
    Index,
    Text,
)
from app.db.base import Base


class QuotaTier(str, enum.Enum):
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"
    MISSION_CRITICAL = "MISSION_CRITICAL"


class GatewayCircuitStatus(str, enum.Enum):
    CLOSED = "CLOSED"      # Healthy, passing all requests
    OPEN = "OPEN"          # Tripped, rejecting or serving fallback
    HALF_OPEN = "HALF_OPEN"  # Probing upstream health


class TenantAPIQuota(Base):
    """Configures rate limits, burst thresholds, and daily budgets per tenant."""
    __tablename__ = "tenant_api_quotas"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, unique=True, index=True)
    tier = Column(SQLEnum(QuotaTier), nullable=False, default=QuotaTier.PROFESSIONAL)
    requests_per_second = Column(Integer, nullable=False, default=50)
    burst_capacity = Column(Integer, nullable=False, default=100)
    daily_quota = Column(Integer, nullable=False, default=100000)
    used_today = Column(Integer, nullable=False, default=0)
    is_throttled = Column(Boolean, nullable=False, default=False)
    last_reset_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class GatewayRouteMetric(Base):
    """Tracks latency, status codes, and edge cache hit ratio per API route."""
    __tablename__ = "gateway_route_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    route_pattern = Column(String(128), nullable=False, index=True)
    status_code = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=False)
    cache_hit = Column(Boolean, nullable=False, default=False)
    client_ip = Column(String(45), nullable=True)
    trace_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_route_metrics_tenant_time", "tenant_id", "timestamp"),
    )


class GatewayCircuitState(Base):
    """Maintains health state and tripped timestamp for protected upstream services."""
    __tablename__ = "gateway_circuit_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_name = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(SQLEnum(GatewayCircuitStatus), nullable=False, default=GatewayCircuitStatus.CLOSED)
    failure_count = Column(Integer, nullable=False, default=0)
    consecutive_successes = Column(Integer, nullable=False, default=0)
    tripped_at = Column(DateTime(timezone=True), nullable=True)
    last_probe_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
