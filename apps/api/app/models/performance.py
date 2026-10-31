"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering, Scalability & Cost Optimization Models
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


class PriorityTier(str, enum.Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_BACKGROUND = "P2_BACKGROUND"


class ModelTier(str, enum.Enum):
    CHEAP_FAST = "CHEAP_FAST"
    BALANCED = "BALANCED"
    PREMIUM = "PREMIUM"


class LatencyMetricSnapshot(Base):
    __tablename__ = "latency_metric_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operation_name = Column(String(100), nullable=False, index=True)
    sample_count = Column(Integer, default=0, nullable=False)
    p50_ms = Column(Float, default=0.0, nullable=False)
    p90_ms = Column(Float, default=0.0, nullable=False)
    p95_ms = Column(Float, default=0.0, nullable=False)
    p99_ms = Column(Float, default=0.0, nullable=False)
    max_ms = Column(Float, default=0.0, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)


class AdmissionControlPolicy(Base):
    __tablename__ = "admission_control_policies"

    id = Column(String(50), primary_key=True)  # PriorityTier value, e.g. "P0_CRITICAL"
    priority_tier = Column(String(50), nullable=False)
    max_concurrency = Column(Integer, default=100, nullable=False)
    current_active = Column(Integer, default=0, nullable=False)
    shedding_active = Column(Boolean, default=False, nullable=False)
    rejected_requests_count = Column(Integer, default=0, nullable=False)


class AIModelCostRecord(Base):
    __tablename__ = "ai_model_cost_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_tier = Column(String(50), default=ModelTier.BALANCED.value, nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class InfrastructureCapacityForecast(Base):
    __tablename__ = "infrastructure_capacity_forecasts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False, index=True)
    current_value = Column(Float, default=0.0, nullable=False)
    projected_30d = Column(Float, default=0.0, nullable=False)
    projected_90d = Column(Float, default=0.0, nullable=False)
    growth_rate_pct = Column(Float, default=0.0, nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
