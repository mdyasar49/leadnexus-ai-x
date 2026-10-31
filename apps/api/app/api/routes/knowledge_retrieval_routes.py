from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.knowledge_retrieval import (
    AIQuery,
    AIQueryPlan,
    AIQueryExecution,
    AICitation,
    AIClaim,
    AIAnswerValidation,
    AIResearchSession,
    AIBudget,
    AIFeedback,
    AIEvaluation,
    QueryType,
    RetrievalMode,
    AnswerState,
)

from packages.knowledge_retrieval.query_router_planner import QueryRouterAndPlanner
from packages.knowledge_retrieval.hybrid_retriever import HybridRetriever
from packages.knowledge_retrieval.retrieval_ranking_engine import RetrievalRankingEngine
from packages.knowledge_retrieval.grounded_response_engine import GroundedResponseEngine
from packages.knowledge_retrieval.claim_validation_engine import ClaimValidationEngine
from packages.knowledge_retrieval.research_assistant_engine import ResearchAssistantEngine
from packages.knowledge_retrieval.ai_cost_and_model_router import AICostAndModelRouter
from packages.knowledge_retrieval.evaluation_and_feedback_service import EvaluationAndFeedbackService


knowledge_retrieval_router = APIRouter(
    prefix="/ai",
    tags=["Enterprise AI Knowledge Retrieval, Grounded RAG & Research Assistant"]
)


# --- Pydantic Request Models ---

class AIQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    target_entity_ids: List[str] = Field(default_factory=list)
    retrieval_modes: List[str] = Field(default_factory=list)


class CompareCompaniesRequest(BaseModel):
    company_id_a: str
    company_id_b: str


class StartResearchSessionRequest(BaseModel):
    target_entity_id: str
    objective: str
    max_steps: int = 5


class SubmitFeedbackRequest(BaseModel):
    execution_id: str
    rating: str  # HELPFUL, UNHELPFUL, INACCURATE, MISSING_EVIDENCE
    feedback_text: Optional[str] = None


# --- 1. Grounded AI Query & Chat Endpoints ---

@knowledge_retrieval_router.post("/query")
def execute_grounded_ai_query(
    req: AIQueryRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """
    Executes an end-to-end grounded query:
    Understand -> Plan -> Retrieve -> Rank -> Synthesize -> Validate Claims -> Return Citations
    """
    planner = QueryRouterAndPlanner(db)
    retriever = HybridRetriever(db)
    ranker = RetrievalRankingEngine()
    responder = GroundedResponseEngine(db)
    validator = ClaimValidationEngine(db)
    cost_router = AICostAndModelRouter(db)

    # 1. Budget check
    allowed = cost_router.check_and_update_budget(ws.id, tokens_used=150)
    if not allowed:
        raise HTTPException(status_code=429, detail="Workspace monthly AI token budget has been exhausted.")

    # 2. Plan Query
    ai_query, plan = planner.plan_query(
        workspace_id=ws.id,
        user_id=user.id,
        raw_query=req.query,
        conversation_id=req.conversation_id
    )

    # 3. Retrieve Candidate Items
    entity_ids = req.target_entity_ids or [e["entity_id"] for e in plan.target_entities if "entity_id" in e]
    raw_candidates = retriever.retrieve(
        workspace_id=ws.id,
        raw_query=req.query,
        retrieval_modes=req.retrieval_modes or plan.retrieval_modes,
        target_entity_ids=entity_ids
    )

    # 4. Multi-Signal Ranking & Deduplication
    ranked = ranker.rank_and_deduplicate(raw_candidates, max_items=plan.max_evidence_items)

    # 5. Synthesize Grounded Response
    target_name = plan.target_entities[0].get("name") if plan.target_entities else None
    execution = responder.synthesize_response(
        query_id=ai_query.id,
        user_query=req.query,
        ranked_context=ranked,
        detected_entity_name=target_name
    )

    # 6. Extract Claims & Validate Groundedness
    validation = validator.extract_and_validate_claims(
        execution_id=execution.id,
        response_text=execution.response_text,
        retrieved_evidence=ranked
    )

    # 7. Fetch Citations for response
    citations = db.query(AICitation).filter(AICitation.execution_id == execution.id).all()

    return {
        "query_id": ai_query.id,
        "execution_id": execution.id,
        "query_type": ai_query.query_type,
        "answer_state": execution.answer_state,
        "response": execution.response_text,
        "confidence_score": execution.confidence_score,
        "has_conflicts": execution.has_conflicts,
        "conflict_notes": execution.conflict_notes,
        "validation": {
            "is_grounded": validation.is_grounded,
            "groundedness_score": validation.groundedness_score,
            "supported_claims": validation.supported_claims,
            "unsupported_claims": validation.unsupported_claims_count
        },
        "citations": [
            {
                "citation_number": c.citation_number,
                "source_title": c.source_title,
                "source_url": c.source_url,
                "snippet": c.evidence_snippet,
                "confidence": c.confidence,
                "observed_at": c.observed_at.isoformat() if c.observed_at else None
            }
            for c in citations
        ]
    }


@knowledge_retrieval_router.post("/query/plan")
def preview_query_plan(
    req: AIQueryRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Generates and previews the query routing classification and retrieval plan without execution."""
    planner = QueryRouterAndPlanner(db)
    ai_query, plan = planner.plan_query(
        workspace_id=ws.id,
        user_id=user.id,
        raw_query=req.query
    )
    return {
        "query_id": ai_query.id,
        "query_type": plan.query_type,
        "target_entities": plan.target_entities,
        "target_concepts": plan.target_concepts,
        "retrieval_modes": plan.retrieval_modes,
        "temporal_constraints": plan.temporal_constraints,
        "plan_steps": plan.plan_steps
    }


# --- 2. Lead 360, Company & Person AI Summaries ---

@knowledge_retrieval_router.get("/lead/{company_id}/summary")
def get_lead_360_ai_summary(
    company_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Synthesizes comprehensive Lead 360 AI intelligence summary."""
    assistant = ResearchAssistantEngine(db)
    try:
        return assistant.generate_lead_360_summary(ws.id, company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@knowledge_retrieval_router.post("/compare")
def compare_companies_ai(
    req: CompareCompaniesRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Performs side-by-side comparative analysis between two companies."""
    assistant = ResearchAssistantEngine(db)
    try:
        return assistant.compare_companies(ws.id, req.company_id_a, req.company_id_b)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 3. Interactive Research Assistant ---

@knowledge_retrieval_router.post("/research/start")
def start_research_session(
    req: StartResearchSessionRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Starts a bounded multi-step research session."""
    assistant = ResearchAssistantEngine(db)
    session = assistant.start_research_session(
        workspace_id=ws.id,
        user_id=user.id,
        target_entity_id=req.target_entity_id,
        objective=req.objective,
        max_steps=req.max_steps
    )
    return {
        "session_id": session.id,
        "target_entity_id": session.target_entity_id,
        "status": session.current_status,
        "max_steps": session.max_steps
    }


# --- 4. Quality Evaluation & Feedback ---

@knowledge_retrieval_router.post("/feedback")
def submit_ai_feedback(
    req: SubmitFeedbackRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Submits operator feedback on answer accuracy, groundedness, and evidence."""
    service = EvaluationAndFeedbackService(db)
    fb = service.submit_feedback(
        workspace_id=ws.id,
        execution_id=req.execution_id,
        user_id=user.id,
        rating=req.rating,
        feedback_text=req.feedback_text
    )
    return {"status": "SUCCESS", "feedback_id": fb.id, "rating": fb.rating}


@knowledge_retrieval_router.get("/evaluations")
def get_rag_evaluations(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Retrieves workspace-level groundedness and retrieval quality metrics."""
    service = EvaluationAndFeedbackService(db)
    evaluation = service.run_workspace_evaluation(ws.id)
    return {
        "evaluation_name": evaluation.evaluation_name,
        "dataset_size": evaluation.dataset_size,
        "average_groundedness": evaluation.average_groundedness,
        "average_citation_coverage": evaluation.average_citation_coverage,
        "unsupported_claim_rate": evaluation.unsupported_claim_rate
    }

