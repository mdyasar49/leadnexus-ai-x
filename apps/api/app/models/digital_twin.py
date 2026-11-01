"""
LeadNexus AI X — Enterprise Digital Twin & Operational Simulation Models
Phase 34 (ChatGPT Master Blueprint): What-If Scenarios, Capacity Testing & Production Non-Mutation
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


class SimulationScenario(Base):
    """
    User or system defined simulation scenario.
    Types: WHAT_IF, SCENARIO, CAPACITY_TEST, FAILURE_SIMULATION, COST_SIMULATION.
    """
    __tablename__ = "simulation_scenarios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    scenario_type = Column(String(64), default="WHAT_IF", nullable=False)
    description = Column(Text, nullable=True)
    
    # Simulation Parameters
    # e.g. {"lead_volume_multiplier": 5.0, "ai_cost_multiplier": 2.0, "source_unavailable": "github", "region_failed": "ap-southeast-2"}
    parameters = Column(JSON, nullable=False, default=dict)
    
    status = Column(String(32), default="DRAFT", nullable=False)  # DRAFT, RUNNING, COMPLETED, FAILED
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_sim_scenarios_tenant", "tenant_id", "scenario_type"),
    )


class SimulationRun(Base):
    """
    Audited execution output of a digital twin simulation.
    Strict Invariant: Production data is NEVER mutated.
    """
    __tablename__ = "simulation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    scenario_id = Column(String(36), ForeignKey("simulation_scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    scenario_type = Column(String(64), nullable=False)
    
    # Baseline vs Projected State
    baseline_snapshot = Column(JSON, nullable=False)
    simulated_projections = Column(JSON, nullable=False)
    bottlenecks_detected = Column(JSON, nullable=False, default=list)
    recommendations = Column(JSON, nullable=False, default=list)
    
    duration_ms = Column(Float, nullable=False, default=0.0)
    executed_by = Column(String(64), nullable=False)
    status = Column(String(32), default="COMPLETED", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_sim_runs_tenant_type", "tenant_id", "scenario_type"),
    )


class OperationalCapacityModel(Base):
    """
    Resource capacity bounds used by the digital twin to calculate bottlenecks.
    """
    __tablename__ = "operational_capacities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    resource_name = Column(String(64), nullable=False)  # BROWSER_WORKERS, AI_TOKENS, SCRAPER_CONCURRENCY, DB_CONNECTIONS
    current_capacity = Column(Float, nullable=False, default=100.0)
    max_capacity = Column(Float, nullable=False, default=500.0)
    unit_cost_usd = Column(Float, nullable=False, default=0.01)
    utilization_pct = Column(Float, nullable=False, default=30.0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_op_capacities_tenant_res", "tenant_id", "resource_name", unique=True),
    )

