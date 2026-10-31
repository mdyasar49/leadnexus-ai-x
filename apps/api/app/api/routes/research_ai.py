from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.lead import Company
from app.models.scoring import LeadScore, AIUsageEvent, PromptTemplate
from app.services.permission_service import get_active_workspace, get_current_user
from packages.scoring.recommendation_engine import RecommendationEngine
from packages.scoring.nl_query import NaturalLanguageQueryBuilder

research_router = APIRouter(prefix="/research", tags=["AI Research Recommendations"])
ai_tools_router = APIRouter(prefix="/ai", tags=["AI Tools & Natural Language Search"])


class NLSearchRequest(BaseModel):
    query: str


@research_router.get("/recommendations/{lead_id}")
async def get_lead_research_recommendations(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    score_stmt = select(LeadScore).where(LeadScore.company_id == comp.id)
    score_obj = (await db.execute(score_stmt)).scalar_one_or_none()

    score_data = {
        "components": {
            "icp_fit_score": score_obj.icp_fit_score if score_obj else 50.0,
            "intent_score": score_obj.intent_score if score_obj else 50.0,
            "contact_quality_score": score_obj.contact_quality_score if score_obj else 30.0,
            "freshness_score": score_obj.freshness_score if score_obj else 85.0
        }
    }

    company_payload = {"name": comp.name, "domain": comp.domain, "business_phone": None}
    recs = RecommendationEngine.determine_next_action(company_payload, score_data, gaps=[])
    return recs


@research_router.get("/next-action/{lead_id}")
async def get_next_action(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    company_payload = {"name": comp.name, "domain": comp.domain}
    recs = RecommendationEngine.determine_next_action(company_payload, {}, gaps=[])
    return {"next_best_action": recs["recommended_action"], "details": recs["action_details"]}


@ai_tools_router.post("/nl-search")
async def natural_language_search(
    req: NLSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user)
):
    """
    Translates natural language questions into safe, structured parameterized query filters.
    Security: NEVER outputs or executes raw dynamic SQL.
    """
    parsed = NaturalLanguageQueryBuilder.parse_query(req.query)
    return parsed


@ai_tools_router.get("/usage")
async def get_ai_usage(
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(AIUsageEvent).where(AIUsageEvent.workspace_id == ws.id)
    result = await db.execute(stmt)
    records = result.scalars().all()
    total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in records)
    total_cost = sum(r.total_cost_usd for r in records)

    return {
        "workspace_id": ws.id,
        "total_events": len(records),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "model_breakdown": {"gemini-2.0-flash": total_tokens}
    }


@ai_tools_router.get("/models")
async def list_ai_models(
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user)
):
    return {
        "available_models": [
            {"name": "gemini-2.0-flash", "family": "gemini", "tier": "FAST", "cost_per_1m_tokens": 0.10},
            {"name": "gemini-2.5-pro", "family": "gemini", "tier": "REASONING", "cost_per_1m_tokens": 1.25},
            {"name": "claude-3-5-sonnet", "family": "anthropic", "tier": "REASONING", "cost_per_1m_tokens": 3.00},
        ],
        "default_classification_model": "gemini-2.0-flash",
        "default_reasoning_model": "gemini-2.0-flash"
    }
