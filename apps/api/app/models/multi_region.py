"""
LeadNexus AI X — Multi-Region Global Architecture Models
Phase 35 (ChatGPT Master Roadmap): Tenant Region Affinity, PostgreSQL Replication, Failover & Split-Brain Prevention
DEFAULT: ONE AUTHORIZED WRITE REGION. No uncontrolled multi-primary.
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


class RegionNode(Base):
    """
    Physical cloud region node with health status and write authorization state.
    """
    __tablename__ = "region_nodes"

    id = Column(String(64), primary_key=True)  # e.g. ap-southeast-2, ap-southeast-1, us-west-2
    name = Column(String(255), nullable=False)  # e.g. "Asia Pacific (Sydney)"
    cloud_provider = Column(String(32), default="AWS", nullable=False)  # AWS, GCP, Cloudflare
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, DRAINING, DEGRADED, OFFLINE
    
    # Write Authorization (Exactly ONE node is primary write)
    is_primary_write = Column(Boolean, default=False, nullable=False)
    
    latency_ms = Column(Float, default=12.5, nullable=False)
    replication_lag_seconds = Column(Float, default=0.05, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class TenantRegionAffinity(Base):
    """
    Tenant data residency policy and geographic region binding.
    """
    __tablename__ = "tenant_region_affinities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, unique=True, index=True)
    primary_region_id = Column(String(64), ForeignKey("region_nodes.id"), nullable=False)
    failover_region_id = Column(String(64), ForeignKey("region_nodes.id"), nullable=False)
    
    # Data Residency & Sovereignty
    data_residency_requirement = Column(String(32), default="AU_ONLY", nullable=False)  # AU_ONLY, APAC, GLOBAL
    strict_sovereignty_enforced = Column(Boolean, default=True, nullable=False)
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class FailoverExecutionJob(Base):
    """
    Audited failover or failback execution log with split-brain fencing token.
    """
    __tablename__ = "failover_execution_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String(64), default="PLANNED_FAILOVER", nullable=False)  # PLANNED_FAILOVER, EMERGENCY_FAILOVER, CONTROLLED_FAILBACK
    source_region_id = Column(String(64), nullable=False)
    target_region_id = Column(String(64), nullable=False)
    
    status = Column(String(64), default="INITIATED", nullable=False)  # INITIATED, DRAINING_SOURCE, WAITING_FOR_SYNC, PROMOTING_TARGET, COMPLETED, FAILED, ABORTED
    initiated_by = Column(String(64), nullable=False)
    split_brain_fence_token = Column(String(128), nullable=False)  # e.g. epoch-1700000000-ap-southeast-1
    replication_lag_at_switchover_s = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class RegionalHealthHeartbeat(Base):
    """
    High-frequency health and replication telemetry recorded per region.
    """
    __tablename__ = "regional_health_heartbeats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    region_id = Column(String(64), ForeignKey("region_nodes.id"), nullable=False, index=True)
    database_replica_status = Column(String(32), default="HEALTHY", nullable=False)  # HEALTHY, CATCHING_UP, DISCONNECTED
    replication_lag_bytes = Column(Integer, default=0, nullable=False)
    replication_lag_seconds = Column(Float, default=0.01, nullable=False)
    queue_depth = Column(Integer, default=0, nullable=False)
    p99_latency_ms = Column(Float, default=24.0, nullable=False)
    error_rate_pct = Column(Float, default=0.0, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
