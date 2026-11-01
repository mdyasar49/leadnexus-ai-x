"""
Enterprise Access Review & Certification Manager (Phase 38)
Manages quarterly/periodic access certification campaigns, reviewer workflows, and automated entitlement revocation.
"""

from datetime import datetime, timezone, timedelta
import uuid
from typing import Any, Dict, List, Optional
from app.models.enterprise_identity import AccessReviewStatus, ReviewDecision


class AccessReviewError(Exception):
    pass


class AccessReviewManager:
    """Orchestrates periodic access certification campaigns."""

    @classmethod
    def create_campaign(
        cls,
        workspace_id: str,
        campaign_name: str,
        due_days: int = 14,
    ) -> Dict[str, Any]:
        """Creates a new access review campaign."""
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=due_days)

        return {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "campaign_name": campaign_name,
            "status": AccessReviewStatus.ACTIVE,
            "due_date": due_date,
            "created_at": now,
        }

    @classmethod
    def populate_review_items(
        cls,
        campaign_id: str,
        workspace_users: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Populates review queue from active workspace user entitlements."""
        items = []
        for u in workspace_users:
            items.append({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign_id,
                "user_id": u["id"],
                "user_email": u.get("email", ""),
                "assigned_role": u.get("role", "member"),
                "decision": ReviewDecision.PENDING,
                "reviewer_id": None,
                "reviewed_at": None,
                "notes": None,
            })
        return items

    @classmethod
    def record_decision(
        cls,
        item: Any,
        reviewer_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records reviewer certification decision (APPROVED or REVOKED)."""
        if decision not in (ReviewDecision.APPROVED, ReviewDecision.REVOKED):
            raise AccessReviewError(f"Invalid review decision: {decision}. Must be APPROVED or REVOKED.")

        now = datetime.now(timezone.utc)
        item.decision = decision
        item.reviewer_id = reviewer_id
        item.reviewed_at = now
        item.notes = notes

        return {
            "item_id": str(item.id),
            "decision": decision,
            "reviewer_id": reviewer_id,
            "reviewed_at": now.isoformat(),
        }

    @classmethod
    def calculate_campaign_progress(cls, items: List[Any]) -> Dict[str, Any]:
        """Calculates completion rate and breakdown of review items."""
        total = len(items)
        if total == 0:
            return {"total": 0, "completed": 0, "percentage": 100.0, "approved": 0, "revoked": 0, "pending": 0}

        approved = sum(1 for i in items if getattr(i, "decision", "") == ReviewDecision.APPROVED)
        revoked = sum(1 for i in items if getattr(i, "decision", "") == ReviewDecision.REVOKED)
        pending = sum(1 for i in items if getattr(i, "decision", "") == ReviewDecision.PENDING)
        completed = approved + revoked

        percentage = round((completed / total) * 100, 1)

        return {
            "total": total,
            "completed": completed,
            "percentage": percentage,
            "approved": approved,
            "revoked": revoked,
            "pending": pending,
        }
