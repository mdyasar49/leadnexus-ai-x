from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.operations import ResearchCostEvent, UsageBudget
from app.services.permission_service import get_active_workspace, get_current_user

router = APIRouter(prefix="/costs", tags=["Cost & Financial Intelligence"])


class SetBudgetRequest(BaseModel):
    period: str = "MONTHLY"
    max_budget_usd: float = 500.0
    alert_threshold_pct: float = 80.0
    campaign_id: Optional[str] = None


@router.get("/summary")
async def get_cost_summary(
    campaign_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(
        ResearchCostEvent.source_key,
        func.sum(ResearchCostEvent.cost_usd).label("total_cost"),
        func.sum(ResearchCostEvent.units).label("total_units")
    ).where(ResearchCostEvent.workspace_id == ws.id)

    if campaign_id:
        stmt = stmt.where(ResearchCostEvent.campaign_id == campaign_id)

    stmt = stmt.group_by(ResearchCostEvent.source_key)
    result = await db.execute(stmt)
    breakdown = [{"source": r[0], "cost_usd": float(r[1] or 0.0), "units": float(r[2] or 0.0)} for r in result.all()]

    total_spend = sum(b["cost_usd"] for b in breakdown)

    return {
        "workspace_id": ws.id,
        "total_spend_usd": round(total_spend, 4),
        "breakdown": breakdown,
        "currency": "USD"
    }


@router.get("/budgets")
async def list_budgets(
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(UsageBudget).where(UsageBudget.workspace_id == ws.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/budgets", status_code=status.HTTP_201_CREATED)
async def create_or_update_budget(
    req: SetBudgetRequest,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    budget = UsageBudget(
        workspace_id=ws.id,
        campaign_id=req.campaign_id,
        period=req.period,
        max_budget_usd=req.max_budget_usd,
        alert_threshold_pct=req.alert_threshold_pct
    )
    db.add(budget)
    await db.commit()
    return budget

