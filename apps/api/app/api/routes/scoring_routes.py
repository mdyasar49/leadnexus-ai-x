from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.lead import Company
from app.models.scoring import LeadScore, ScoreCalculation
from app.services.permission_service import get_active_workspace, get_current_user

router = APIRouter(prefix="/scoring", tags=["Lead Scoring & Versioning"])


@router.get("/explanation/{lead_id}")
async def get_score_explanation(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns granular explainability for a lead score:
    All 8 components, weights, positive/negative drivers, and calculation version.
    """
    stmt = select(LeadScore).where(LeadScore.company_id == lead_id, LeadScore.workspace_id == ws.id)
    result = await db.execute(stmt)
    score = result.scalar_one_or_none()

    if not score:
        raise HTTPException(status_code=404, detail="Score calculation not found for this lead")

    return {
        "lead_id": lead_id,
        "lead_priority_score": score.lead_priority_score,
        "priority_tier": score.priority_tier,
        "components": [
            {"name": "ICP Fit", "score": score.icp_fit_score, "weight": 0.30},
            {"name": "Intent Strength", "score": score.intent_score, "weight": 0.30},
            {"name": "Buying Readiness", "score": score.buying_readiness_score, "weight": 0.15},
            {"name": "Evidence Confidence", "score": score.evidence_confidence_score, "weight": 0.10},
            {"name": "Data Quality", "score": score.data_quality_score, "weight": 0.05},
            {"name": "Contact Quality", "score": score.contact_quality_score, "weight": 0.05},
            {"name": "Research Completeness", "score": score.research_completeness_score, "weight": 0.025},
            {"name": "Freshness", "score": score.freshness_score, "weight": 0.025},
        ],
        "positive_factors": score.positive_factors,
        "negative_factors": score.negative_factors,
        "calculation_version": score.calculation_version,
        "calculated_at": score.calculated_at.isoformat() if score.calculated_at else None
    }


@router.get("/history/{lead_id}")
async def get_score_history(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = (
        select(ScoreCalculation)
        .where(ScoreCalculation.company_id == lead_id, ScoreCalculation.workspace_id == ws.id)
        .order_by(desc(ScoreCalculation.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()
