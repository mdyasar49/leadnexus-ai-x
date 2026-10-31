"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle & Retention
Retention Policy Engine: Entity expiration evaluation, legal hold compliance, and tier transitions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.data_lifecycle import DataRetentionPolicy, LifecycleTransitionEvent, StorageTier
from packages.governance.suppression_and_legal_hold_service import SuppressionAndLegalHoldService


class RetentionPolicyEngine:
    """Evaluates data retention SLAs and initiates tier migrations while honoring legal holds."""

    DEFAULT_RETENTIONS = {
        "AUDIT_LOG": 365,
        "BROWSER_SNAPSHOT": 30,
        "RAW_SIGNAL": 90,
        "UNVERIFIED_CONTACT": 60,
        "EPHEMERAL_AI_CACHE": 7,
    }

    def __init__(self, db_session: Any):
        self.db = db_session
        self.legal_hold_svc = SuppressionAndLegalHoldService(db_session)

    def is_eligible_for_transition(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        created_at: datetime,
        retention_days: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determines if an entity has passed its retention window.
        Returns: (eligible, reason)
        """
        # 1. Check Legal Hold Exemption
        if self.legal_hold_svc.is_under_legal_hold(workspace_id, entity_type, entity_id):
            return False, "EXEMPT: Entity is subject to an active Legal Hold"

        # 2. Check Age against retention policy
        days = retention_days or self.DEFAULT_RETENTIONS.get(entity_type, 90)
        now = datetime.now(timezone.utc)
        created_utc = created_at.replace(tzinfo=timezone.utc if created_at.tzinfo is None else created_at.tzinfo)

        age_days = (now - created_utc).total_seconds() / 86400.0
        if age_days >= days:
            return True, f"Retention window expired ({age_days:.1f} days >= {days} days policy)"

        return False, f"Within retention window ({age_days:.1f} days < {days} days policy)"

    def record_transition(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        from_tier: StorageTier,
        to_tier: StorageTier,
        reason: str,
    ) -> LifecycleTransitionEvent:
        event = LifecycleTransitionEvent(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            from_tier=from_tier.value if isinstance(from_tier, StorageTier) else from_tier,
            to_tier=to_tier.value if isinstance(to_tier, StorageTier) else to_tier,
            reason=reason,
            transitioned_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
