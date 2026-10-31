from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.workflow_ops import (
    ReviewItem,
    ReviewComment,
    HumanFeedback,
    ReviewStatus,
    ReviewPriority,
    FeedbackCategory,
    ConflictWorkflow,
    ConflictSeverity
)
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore, FieldConflict
from app.models.technology import TechnologyObservation


SLA_HOURS_MAP = {
    ReviewPriority.CRITICAL.value: 4,
    ReviewPriority.HIGH.value: 12,
    ReviewPriority.NORMAL.value: 24,
    ReviewPriority.LOW.value: 72,
}


class ReviewService:
    """Human-in-the-Loop review manager, SLA calculator, and bounded research loop governor."""

    @staticmethod
    def create_review_item(
        db: Session,
        workspace_id: str,
        entity_id: str,
        entity_type: str = "COMPANY",
        priority: str = "NORMAL",
        ai_recommendation: Optional[Dict[str, Any]] = None,
        queue_id: Optional[str] = None
    ) -> ReviewItem:
        """Enqueues an entity for human-in-the-loop inspection."""
        now = datetime.now(timezone.utc)
        sla_hours = SLA_HOURS_MAP.get(priority, 24)
        due_at = now + timedelta(hours=sla_hours)

        item = ReviewItem(
            workspace_id=workspace_id,
            queue_id=queue_id,
            entity_type=entity_type,
            entity_id=entity_id,
            priority=priority,
            status=ReviewStatus.PENDING.value,
            ai_recommendation=ai_recommendation or {"action": "REVIEW", "confidence": 0.80, "reason": "Automated qualification check required."},
            due_at=due_at
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_review_dossier(db: Session, workspace_id: str, review_id: str) -> Optional[Dict[str, Any]]:
        """Compiles the complete review dossier (lead, people, tech, AI recommendation, conflicts, comments)."""
        item = db.query(ReviewItem).filter(ReviewItem.workspace_id == workspace_id, ReviewItem.id == review_id).first()
        if not item:
            return None

        comp = db.query(Company).filter(Company.workspace_id == workspace_id, Company.id == item.entity_id).first()
        score = db.query(LeadScore).filter(LeadScore.workspace_id == workspace_id, LeadScore.company_id == item.entity_id).first()
        contacts = db.query(Contact).filter(Contact.workspace_id == workspace_id, Contact.company_id == item.entity_id).all()
        techs = db.query(TechnologyObservation).filter(TechnologyObservation.company_id == item.entity_id).all()
        conflicts = db.query(FieldConflict).filter(FieldConflict.company_id == item.entity_id).all()
        comments = db.query(ReviewComment).filter(ReviewComment.review_item_id == review_id).order_by(ReviewComment.created_at.desc()).all()

        now = datetime.now(timezone.utc)
        is_sla_breached = item.due_at is not None and now > item.due_at.replace(tzinfo=timezone.utc if item.due_at.tzinfo is None else item.due_at.tzinfo)

        return {
            "review_id": item.id,
            "status": item.status,
            "priority": item.priority,
            "due_at": item.due_at.isoformat() if item.due_at else None,
            "is_sla_breached": is_sla_breached,
            "research_attempts": item.research_attempts,
            "max_research_attempts": item.max_research_attempts,
            "ai_recommendation": item.ai_recommendation,
            "company": {
                "id": comp.id if comp else item.entity_id,
                "name": comp.name if comp else "Unknown",
                "domain": comp.domain if comp else None,
                "country": comp.country if comp else None,
                "status": comp.status if comp else "UNKNOWN"
            },
            "scores": {
                "lead_priority_score": score.lead_priority_score if score else (comp.lead_score if comp else 0),
                "intent_score": score.intent_score if score else 0.0,
                "priority_tier": score.priority_tier if score else "P3_LOW"
            },
            "people": [
                {"id": c.id, "name": c.full_name, "title": c.job_title, "email": c.email, "is_decision_maker": c.is_decision_maker}
                for c in contacts
            ],
            "technologies": [{"name": t.technology, "version": t.version} for t in techs],
            "conflicts": [
                {"field": cf.field_name, "value_a": cf.value_a, "value_b": cf.value_b, "status": cf.resolution_status}
                for cf in conflicts
            ],
            "comments": [
                {"id": cm.id, "author": cm.user_name, "text": cm.comment_text, "created_at": cm.created_at.isoformat()}
                for cm in comments
            ]
        }

    @staticmethod
    def process_decision(
        db: Session,
        workspace_id: str,
        user_id: str,
        review_id: str,
        decision: str,
        reason: str,
        feedback_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a human review decision with bounded research loop governance.
        Supported decisions: CONFIRM, REJECT, REQUEST_MORE_RESEARCH, MERGE, SPLIT, SUPPRESS, ESCALATE.
        """
        item = db.query(ReviewItem).filter(ReviewItem.workspace_id == workspace_id, ReviewItem.id == review_id).first()
        if not item:
            raise ValueError(f"Review item '{review_id}' not found.")

        now = datetime.now(timezone.utc)
        decision_upper = decision.upper()

        if decision_upper == "CONFIRM":
            item.status = ReviewStatus.APPROVED.value
            item.decision = "CONFIRM"
            # Update entity state
            comp = db.query(Company).filter(Company.id == item.entity_id).first()
            if comp:
                comp.status = "QUALIFIED"

        elif decision_upper == "REJECT":
            item.status = ReviewStatus.REJECTED.value
            item.decision = "REJECT"
            comp = db.query(Company).filter(Company.id == item.entity_id).first()
            if comp:
                comp.status = "DISQUALIFIED"

        elif decision_upper == "SUPPRESS":
            item.status = ReviewStatus.APPROVED.value
            item.decision = "SUPPRESS"
            comp = db.query(Company).filter(Company.id == item.entity_id).first()
            if comp:
                comp.status = "DISQUALIFIED"

        elif decision_upper == "REQUEST_MORE_RESEARCH":
            # Bounded Research Loop Check
            if item.research_attempts >= item.max_research_attempts:
                item.status = ReviewStatus.ESCALATED.value
                item.decision = "HUMAN_RESEARCH_REQUIRED"
                item.decision_reason = f"Max research attempts ({item.max_research_attempts}) reached. Automatic loop halted."
                db.commit()
                return {
                    "review_id": item.id,
                    "decision": item.decision,
                    "status": item.status,
                    "loop_halted": True,
                    "message": "Maximum research loops reached. Item escalated for manual investigation."
                }
            else:
                item.research_attempts += 1
                item.status = ReviewStatus.IN_PROGRESS.value
                item.decision = "REQUEST_MORE_RESEARCH"

        elif decision_upper == "ESCALATE":
            item.status = ReviewStatus.ESCALATED.value
            item.decision = "ESCALATE"

        item.decision_by_user_id = user_id
        item.decision_reason = reason
        item.decided_at = now

        # Record Human Feedback for AI calibration
        if feedback_category:
            fb = HumanFeedback(
                workspace_id=workspace_id,
                review_item_id=review_id,
                entity_id=item.entity_id,
                category=feedback_category,
                reason=reason
            )
            db.add(fb)

        db.commit()
        db.refresh(item)

        return {
            "review_id": item.id,
            "decision": item.decision,
            "status": item.status,
            "loop_halted": False,
            "decided_at": item.decided_at.isoformat()
        }

    @staticmethod
    def resolve_field_conflict(
        db: Session,
        workspace_id: str,
        user_id: str,
        conflict_id: str,
        resolved_value: str
    ) -> Dict[str, Any]:
        """Resolves an outstanding field conflict with selected verified value."""
        conflict = db.query(FieldConflict).filter(FieldConflict.workspace_id == workspace_id, FieldConflict.id == conflict_id).first()
        if not conflict:
            raise ValueError(f"Field conflict '{conflict_id}' not found.")

        conflict.chosen_value = resolved_value
        conflict.resolution_status = "RESOLVED"
        db.commit()

        return {
            "conflict_id": conflict.id,
            "field_name": conflict.field_name,
            "chosen_value": conflict.chosen_value,
            "status": conflict.resolution_status
        }
