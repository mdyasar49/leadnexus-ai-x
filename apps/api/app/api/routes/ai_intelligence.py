from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import (
    IntentAssessment,
    IntentTimelineEvent,
    PainPoint,
    UseCase,
    AIReasoningResult,
    LeadScore
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.scoring.icp_engine import ICPEngine
from packages.scoring.intent_engine import IntentEngine
from packages.scoring.readiness_engine import BuyingReadinessEngine
from packages.scoring.evidence_reasoner import EvidenceReasoner
from packages.scoring.composite_scorer import CompositeScorer

router = APIRouter(prefix="/ai", tags=["AI Intelligence & Reasoning"])
intel_router = APIRouter(prefix="/intelligence", tags=["Intelligence Feeds"])


@router.post("/qualify/{lead_id}", status_code=status.HTTP_200_OK)
async def qualify_lead(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes full AI Evidence Reasoning pipeline over a company lead:
    Gathers evidence -> assesses intent -> evaluates ICP -> computes composite scores.
    """
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    result = await db.execute(stmt)
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Fetch signals and contacts
    sig_stmt = select(IntentSignal).where(IntentSignal.company_id == comp.id)
    signals_res = await db.execute(sig_stmt)
    signals = [s.raw_data for s in signals_res.scalars().all()]

    con_stmt = select(Contact).where(Contact.company_id == comp.id)
    contacts_res = await db.execute(con_stmt)
    contacts = [{"job_title": c.job_title, "full_name": c.full_name, "email_status": c.email_status, "business_phone": c.business_phone} for c in contacts_res.scalars().all()]

    company_payload = {
        "name": comp.name,
        "domain": comp.domain,
        "country": comp.country,
        "industry": comp.industry,
        "signals": signals,
        "contacts": contacts,
        "employee_count_range": comp.employee_count_range
    }

    # 1. Intent Assessment
    intent_data = IntentEngine.assess_company_intent(signals, company_text_corpus=comp.description or "")

    # 2. ICP Evaluation
    icp_data = ICPEngine.evaluate_fit(company_payload)

    # 3. Buying Readiness
    readiness_data = BuyingReadinessEngine.evaluate_readiness(company_payload, intent_data)

    # 4. Evidence Reasoning
    reasoning = EvidenceReasoner.reason_over_lead(company_payload, icp_data, intent_data, readiness_data)

    # 5. Composite Score Calculation
    score_res = CompositeScorer.calculate_lead_score(company_payload, icp_data, intent_data, readiness_data)

    # Persist or update LeadScore
    score_stmt = select(LeadScore).where(LeadScore.company_id == comp.id)
    existing_score = (await db.execute(score_stmt)).scalar_one_or_none()

    if not existing_score:
        existing_score = LeadScore(
            company_id=comp.id,
            workspace_id=ws.id,
            campaign_id=comp.campaign_id
        )
        db.add(existing_score)

    existing_score.lead_priority_score = score_res["lead_priority_score"]
    existing_score.priority_tier = score_res["priority_tier"]
    for k, v in score_res["components"].items():
        setattr(existing_score, k, v)
    existing_score.positive_factors = score_res["positive_factors"]
    existing_score.negative_factors = score_res["negative_factors"]

    # Update company lead_score & status
    comp.lead_score = int(score_res["lead_priority_score"])
    comp.status = "QUALIFIED" if score_res["lead_priority_score"] >= 65.0 else "NEEDS_REVIEW"

    await db.commit()

    return {
        "lead_id": comp.id,
        "lead_priority_score": score_res["lead_priority_score"],
        "priority_tier": score_res["priority_tier"],
        "icp_fit_score": icp_data["icp_fit_score"],
        "intent_score": intent_data["intent_score"],
        "buying_readiness_score": readiness_data["buying_readiness_score"],
        "primary_need": reasoning.primary_need,
        "reasoning_summary": reasoning.reasoning_summary,
        "positive_factors": score_res["positive_factors"],
        "negative_factors": score_res["negative_factors"]
    }


@router.get("/reason/{lead_id}")
async def get_ai_reasoning(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    sig_stmt = select(IntentSignal).where(IntentSignal.company_id == comp.id)
    signals = [s.raw_data for s in (await db.execute(sig_stmt)).scalars().all()]

    con_stmt = select(Contact).where(Contact.company_id == comp.id)
    contacts = [{"job_title": c.job_title, "full_name": c.full_name} for c in (await db.execute(con_stmt)).scalars().all()]

    company_payload = {"name": comp.name, "domain": comp.domain, "country": comp.country, "signals": signals, "contacts": contacts}
    intent_data = IntentEngine.assess_company_intent(signals, company_text_corpus=comp.description or "")
    icp_data = ICPEngine.evaluate_fit(company_payload)
    readiness_data = BuyingReadinessEngine.evaluate_readiness(company_payload, intent_data)

    reasoning = EvidenceReasoner.reason_over_lead(company_payload, icp_data, intent_data, readiness_data)
    return reasoning.model_dump()


@intel_router.get("/intent/{lead_id}")
async def get_lead_intent(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    sig_stmt = select(IntentSignal).where(IntentSignal.company_id == comp.id)
    signals = [s.raw_data for s in (await db.execute(sig_stmt)).scalars().all()]

    intent_data = IntentEngine.assess_company_intent(signals, company_text_corpus=comp.description or "")
    return intent_data


@intel_router.get("/intent-timeline/{lead_id}")
async def get_intent_timeline(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(IntentSignal).where(IntentSignal.company_id == lead_id, IntentSignal.workspace_id == ws.id).order_by(desc(IntentSignal.created_at))
    result = await db.execute(stmt)
    signals = result.scalars().all()

    timeline = []
    for s in signals:
        timeline.append({
            "date": s.created_at.isoformat() if s.created_at else None,
            "source_type": s.source_name,
            "source_url": s.source_url,
            "intent_type": s.signal_type,
            "detected_keyword": s.detected_keyword,
            "evidence_snippet": s.evidence_snippet,
            "confidence": 0.90
        })
    return timeline
