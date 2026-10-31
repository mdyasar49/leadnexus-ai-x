from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.workflow_ops import (
    ReviewItem,
    ReviewComment,
    HumanFeedback,
    ReviewStatus,
    ReviewPriority,
    ConflictWorkflow,
    ConflictSeverity
)
from app.models.scoring import FieldConflict
from app.services.permission_service import get_active_workspace, get_current_user
from packages.workflows.review_service import ReviewService


reviews_router = APIRouter(prefix="/reviews", tags=["Human-in-the-Loop Review System"])
conflicts_router = APIRouter(prefix="/conflicts", tags=["Conflict Resolution Center"])


class AssignReviewRequest(BaseModel):
    user_id: str


class DecisionRequest(BaseModel):
    decision: str  # CONFIRM, REJECT, REQUEST_MORE_RESEARCH, MERGE, SPLIT, SUPPRESS, ESCALATE
    reason: str
    feedback_category: Optional[str] = None  # AI_CORRECT, AI_INCORRECT, EVIDENCE_INSUFFICIENT, etc.


class CommentCreateRequest(BaseModel):
    comment_text: str
    comment_type: str = "NOTE"


class ConflictResolveRequest(BaseModel):
    resolved_value: str


# --- Reviews Endpoints ---
@reviews_router.get("")
def list_review_items(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists review items in the human review queue."""
    q = db.query(ReviewItem).filter(ReviewItem.workspace_id == ws.id)
    if status_filter:
        q = q.filter(ReviewItem.status == status_filter.upper())
    if priority_filter:
        q = q.filter(ReviewItem.priority == priority_filter.upper())
    items = q.order_by(ReviewItem.created_at.desc()).limit(limit).all()

    now = datetime.now(timezone.utc)
    return [
        {
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "priority": r.priority,
            "status": r.status,
            "assigned_to_user_id": r.assigned_to_user_id,
            "ai_recommendation": r.ai_recommendation,
            "research_attempts": r.research_attempts,
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "is_overdue": bool(r.due_at and now > (r.due_at if r.due_at.tzinfo else r.due_at.replace(tzinfo=timezone.utc)))
        }
        for r in items
    ]


@reviews_router.get("/{review_id}")
def get_review_dossier(
    review_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns the dedicated Review Workspace Dossier."""
    dossier = ReviewService.get_review_dossier(db, ws.id, review_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Review item not found")
    return dossier


@reviews_router.post("/{review_id}/assign")
def assign_review(
    review_id: str,
    req: AssignReviewRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Assigns a review item to a specific analyst."""
    item = db.query(ReviewItem).filter(ReviewItem.workspace_id == ws.id, ReviewItem.id == review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    item.assigned_to_user_id = req.user_id
    item.status = ReviewStatus.ASSIGNED.value
    db.commit()
    return {"id": item.id, "assigned_to_user_id": item.assigned_to_user_id, "status": item.status}


@reviews_router.post("/{review_id}/decision")
def submit_review_decision(
    review_id: str,
    req: DecisionRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Processes final human review decision with bounded research loop governance."""
    try:
        return ReviewService.process_decision(
            db=db,
            workspace_id=ws.id,
            user_id=user.id,
            review_id=review_id,
            decision=req.decision,
            reason=req.reason,
            feedback_category=req.feedback_category
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@reviews_router.post("/{review_id}/comments", status_code=status.HTTP_201_CREATED)
def add_review_comment(
    review_id: str,
    req: CommentCreateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Adds a structured audit comment to the review dossier."""
    item = db.query(ReviewItem).filter(ReviewItem.workspace_id == ws.id, ReviewItem.id == review_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    author_name = getattr(user, "full_name", None) or getattr(user, "email", "Analyst")
    comment = ReviewComment(
        workspace_id=ws.id,
        review_item_id=review_id,
        user_id=user.id,
        user_name=author_name,
        comment_text=req.comment_text,
        comment_type=req.comment_type
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "review_item_id": review_id, "status": "CREATED"}


# --- Conflicts Endpoints ---
@conflicts_router.get("")
def list_conflicts(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists field conflicts across workspace with severity rating."""
    conflicts = (
        db.query(FieldConflict)
        .filter(FieldConflict.workspace_id == ws.id)
        .order_by(FieldConflict.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "company_id": c.company_id,
            "field_name": c.field_name,
            "value_a": c.value_a,
            "source_a": c.source_a,
            "value_b": c.value_b,
            "source_b": c.source_b,
            "resolution_status": c.resolution_status,
            "chosen_value": c.chosen_value,
            "severity": "HIGH" if "country" in c.field_name or "company" in c.field_name else "MEDIUM",
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in conflicts
    ]


@conflicts_router.post("/{conflict_id}/resolve")
def resolve_conflict_endpoint(
    conflict_id: str,
    req: ConflictResolveRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Resolves a field conflict with the chosen verified value."""
    try:
        return ReviewService.resolve_field_conflict(
            db=db,
            workspace_id=ws.id,
            user_id=user.id,
            conflict_id=conflict_id,
            resolved_value=req.resolved_value
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
