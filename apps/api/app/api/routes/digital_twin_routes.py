"""
LeadNexus AI X — Enterprise Digital Twin & Operational Simulation Routes
Phase 34 (ChatGPT Master Roadmap): What-If Scenarios & Production Non-Mutation
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.user import User
from app.models.tenant import Workspace
from app.models.digital_twin import (
    SimulationScenario,
    SimulationRun,
    OperationalCapacityModel,
)
from packages.simulation.digital_twin_engine import DigitalTwinEngine

router = APIRouter(prefix="/simulation", tags=["Enterprise Digital Twin"])


# --- Schemas ---

class CreateScenarioRequest(BaseModel):
    name: str = Field(..., example="5x Lead Surge & GitHub Outage")
    scenario_type: str = Field(default="WHAT_IF", example="WHAT_IF")
    description: Optional[str] = Field(None, example="Simulates lead volume 5x and primary web discovery source down.")
    parameters: Dict[str, Any] = Field(
        default={
            "lead_volume_multiplier": 5.0,
            "source_unavailable": "github",
            "ai_cost_multiplier": 1.5,
            "region_failed": None,
        }
    )


class QuickWhatIfRequest(BaseModel):
    lead_volume_multiplier: float = Field(default=1.0, ge=0.1, le=50.0)
    ai_cost_multiplier: float = Field(default=1.0, ge=0.1, le=20.0)
    source_unavailable: Optional[str] = None
    region_failed: Optional[str] = None
    verification_backlog_multiplier: float = Field(default=1.0, ge=1.0, le=10.0)


# --- Route Handlers ---

@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(
    req: CreateScenarioRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Registers a new simulation scenario for digital twin modeling.
    """
    scenario = SimulationScenario(
        id=str(uuid.uuid4()),
        tenant_id=workspace.id,
        name=req.name,
        scenario_type=req.scenario_type,
        description=req.description,
        parameters=req.parameters,
        status="DRAFT",
        created_by=str(user.id),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return {
        "id": scenario.id,
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "parameters": scenario.parameters,
        "status": scenario.status,
        "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
    }


@router.get("/scenarios")
def list_scenarios(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Lists all simulation scenarios configured for this workspace.
    """
    scenarios = db.query(SimulationScenario).filter(
        SimulationScenario.tenant_id == workspace.id
    ).order_by(SimulationScenario.created_at.desc()).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "scenario_type": s.scenario_type,
            "description": s.description,
            "parameters": s.parameters,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in scenarios
    ]


@router.post("/scenarios/{scenario_id}/run")
def execute_scenario_run(
    scenario_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Executes a simulation on the digital twin. Non-mutating to production data.
    """
    scenario = db.query(SimulationScenario).filter(
        SimulationScenario.id == scenario_id,
        SimulationScenario.tenant_id == workspace.id,
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    run = DigitalTwinEngine.execute_run(
        db=db,
        tenant_id=workspace.id,
        executed_by=str(user.id),
        scenario=scenario,
    )
    return {
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "scenario_type": run.scenario_type,
        "baseline_snapshot": run.baseline_snapshot,
        "simulated_projections": run.simulated_projections,
        "bottlenecks_detected": run.bottlenecks_detected,
        "recommendations": run.recommendations,
        "duration_ms": run.duration_ms,
        "status": run.status,
    }


@router.post("/quick-what-if")
def quick_what_if_query(
    req: QuickWhatIfRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Instant What-If query without persisting a scenario entity first.
    Strictly non-mutating.
    """
    params = {
        "lead_volume_multiplier": req.lead_volume_multiplier,
        "ai_cost_multiplier": req.ai_cost_multiplier,
        "source_unavailable": req.source_unavailable,
        "region_failed": req.region_failed,
        "verification_backlog_multiplier": req.verification_backlog_multiplier,
    }
    run = DigitalTwinEngine.execute_run(
        db=db,
        tenant_id=workspace.id,
        executed_by=str(user.id),
        scenario=None,
        custom_params=params,
    )
    return {
        "run_id": run.id,
        "baseline_snapshot": run.baseline_snapshot,
        "simulated_projections": run.simulated_projections,
        "bottlenecks_detected": run.bottlenecks_detected,
        "recommendations": run.recommendations,
        "duration_ms": run.duration_ms,
    }


@router.get("/runs")
def list_simulation_runs(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Lists historical digital twin simulation runs and detected bottlenecks.
    """
    runs = db.query(SimulationRun).filter(
        SimulationRun.tenant_id == workspace.id
    ).order_by(SimulationRun.created_at.desc()).limit(50).all()

    return [
        {
            "id": r.id,
            "scenario_id": r.scenario_id,
            "scenario_type": r.scenario_type,
            "bottlenecks_count": len(r.bottlenecks_detected or []),
            "recommendations_count": len(r.recommendations or []),
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
def get_simulation_run_detail(
    run_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Retrieves full metrics of a simulation run.
    """
    r = db.query(SimulationRun).filter(
        SimulationRun.id == run_id,
        SimulationRun.tenant_id == workspace.id,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Simulation run not found")

    return {
        "id": r.id,
        "scenario_id": r.scenario_id,
        "scenario_type": r.scenario_type,
        "baseline_snapshot": r.baseline_snapshot,
        "simulated_projections": r.simulated_projections,
        "bottlenecks_detected": r.bottlenecks_detected,
        "recommendations": r.recommendations,
        "duration_ms": r.duration_ms,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/capacity")
def get_operational_capacity(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Returns current operational capacity allocations.
    """
    caps = db.query(OperationalCapacityModel).filter(
        OperationalCapacityModel.tenant_id == workspace.id
    ).all()
    if not caps:
        # Provide default enterprise limits
        return [
            {"resource_name": "BROWSER_WORKERS", "current_capacity": 4, "max_capacity": 32, "utilization_pct": 32.5},
            {"resource_name": "AI_TOKENS", "current_capacity": 1000000, "max_capacity": 10000000, "utilization_pct": 45.0},
            {"resource_name": "SCRAPER_CONCURRENCY", "current_capacity": 25, "max_capacity": 100, "utilization_pct": 20.0},
            {"resource_name": "DB_CONNECTIONS", "current_capacity": 20, "max_capacity": 100, "utilization_pct": 18.0},
        ]
    return [
        {
            "resource_name": c.resource_name,
            "current_capacity": c.current_capacity,
            "max_capacity": c.max_capacity,
            "utilization_pct": c.utilization_pct,
        }
        for c in caps
    ]

