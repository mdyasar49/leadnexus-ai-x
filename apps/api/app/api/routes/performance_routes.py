"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering, Scalability & Cost Optimization Routes
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.lead import Company
from app.models.performance import (
    AdmissionControlPolicy,
    AIModelCostRecord,
    InfrastructureCapacityForecast,
    LatencyMetricSnapshot,
    ModelTier,
    PriorityTier,
)
from packages.performance.admission_control_service import (
    AdmissionControlService,
)
from packages.performance.ai_model_router_and_cost import (
    AIModelRouterAndCostEngine,
)
from packages.performance.infrastructure_capacity_forecaster import (
    InfrastructureCapacityForecaster,
)
from packages.performance.keyset_pagination import (
    KeysetPaginationEngine,
)
from packages.performance.latency_profiler import LatencyProfiler

router = APIRouter(prefix="/api/v1/performance", tags=["Enterprise Performance & Scalability"])


# --- Schemas ---

class LoadSheddingRequest(BaseModel):
    tier: str = "P2_BACKGROUND"
    active: bool = True


class RecordLatencyRequest(BaseModel):
    operation_name: str
    samples_ms: List[float]


class RouteAIRequest(BaseModel):
    task_type: str
    estimated_prompt_tokens: int = 500
    estimated_completion_tokens: int = 200


class CreateForecastRequest(BaseModel):
    metric_name: str
    current_value: float
    monthly_growth_rate_pct: float = 15.0


# --- Keyset Pagination Demo ---

@router.get("/pagination/demo")
def demo_keyset_pagination(
    cursor: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    query = db.query(Company).filter(Company.workspace_id == workspace.id)
    page = KeysetPaginationEngine.paginate(
        query=query,
        model_cls=Company,
        cursor=cursor,
        limit=limit,
        sort_field_name="id",
        ascending=True,
    )
    return {
        "items_count": page.page_size,
        "next_cursor": page.next_cursor,
        "has_next_page": page.has_next_page,
        "items": [{"id": c.id, "name": c.name, "domain": c.domain} for c in page.items],
    }


# --- Admission Control ---

@router.get("/admission-control")
def get_admission_control_status(db: Session = Depends(get_sync_db)):
    service = AdmissionControlService(db)
    policies = [service.get_or_create_policy(tier) for tier in PriorityTier]
    return {"admission_policies": policies}


@router.post("/admission-control/load-shedding")
def set_load_shedding(
    req: LoadSheddingRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    service = AdmissionControlService(db)
    tier = PriorityTier(req.tier) if req.tier in [t.value for t in PriorityTier] else PriorityTier.P2_BACKGROUND
    policy = service.set_load_shedding(tier, req.active)
    return {"status": "UPDATED", "policy": policy}


# --- Latency Telemetry ---

@router.get("/latency/snapshots")
def list_latency_snapshots(db: Session = Depends(get_sync_db)):
    snapshots = db.query(LatencyMetricSnapshot).order_by(LatencyMetricSnapshot.window_end.desc()).limit(20).all()
    return {"snapshots": snapshots}


@router.post("/latency/record", status_code=status.HTTP_201_CREATED)
def record_latency_snapshot(req: RecordLatencyRequest, db: Session = Depends(get_sync_db)):
    profiler = LatencyProfiler(db)
    now = datetime.now(timezone.utc)
    snapshot = profiler.create_snapshot(
        operation_name=req.operation_name,
        samples=req.samples_ms,
        window_start=now - timedelta(minutes=5),
        window_end=now,
    )
    return {"snapshot": snapshot}


# --- AI Routing & Costs ---

@router.post("/ai-costs/route")
def route_ai_task(req: RouteAIRequest):
    tier, model_name = AIModelRouterAndCostEngine.route_task(req.task_type)
    cost = AIModelRouterAndCostEngine.calculate_cost(
        tier, req.estimated_prompt_tokens, req.estimated_completion_tokens
    )
    return {
        "task_type": req.task_type,
        "selected_model_tier": tier.value,
        "selected_model": model_name,
        "estimated_cost_usd": cost,
    }


@router.get("/ai-costs")
def list_ai_costs(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    records = db.query(AIModelCostRecord).filter(
        AIModelCostRecord.workspace_id == workspace.id
    ).order_by(AIModelCostRecord.recorded_at.desc()).limit(50).all()

    total_cost = sum(r.cost_usd for r in records)
    return {"total_cost_usd": round(total_cost, 4), "records": records}


# --- Capacity Forecasts ---

@router.get("/capacity-forecasts")
def list_capacity_forecasts(db: Session = Depends(get_sync_db)):
    forecasts = db.query(InfrastructureCapacityForecast).order_by(InfrastructureCapacityForecast.calculated_at.desc()).limit(20).all()
    return {"forecasts": forecasts}


@router.post("/capacity-forecasts", status_code=status.HTTP_201_CREATED)
def create_capacity_forecast(req: CreateForecastRequest, db: Session = Depends(get_sync_db)):
    forecaster = InfrastructureCapacityForecaster(db)
    forecast = forecaster.generate_forecast(
        metric_name=req.metric_name,
        current_value=req.current_value,
        monthly_growth_rate_pct=req.monthly_growth_rate_pct,
    )
    return {"forecast": forecast}
