"""
LeadNexus AI X - Phase 29: Enterprise Governance & Compliance
Suppression & Legal Hold Service: Global suppression lists and legal hold lifecycle management.
"""

import fnmatch
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.governance import (
    LegalHold,
    SuppressionRecord,
    SuppressionType,
)


class SuppressionAndLegalHoldService:
    """Enforces global privacy suppressions and immutable legal hold protections."""

    def __init__(self, db_session: Any):
        self.db = db_session

    # --- Suppression Management ---

    def add_suppression(
        self,
        workspace_id: str,
        suppression_type: SuppressionType,
        pattern: str,
        reason: str,
        created_by: Optional[str] = None,
    ) -> SuppressionRecord:
        record = SuppressionRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            suppression_type=suppression_type.value if isinstance(suppression_type, SuppressionType) else suppression_type,
            pattern=pattern.strip().lower(),
            reason=reason,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def is_suppressed(
        self,
        workspace_id: str,
        suppression_type: str,
        value: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if value matches any active suppression patterns (exact or wildcard).
        Returns: (is_suppressed, reason)
        """
        records = self.db.query(SuppressionRecord).filter(
            SuppressionRecord.workspace_id == workspace_id,
            SuppressionRecord.suppression_type == suppression_type,
        ).all()

        val_lower = value.strip().lower()
        for rec in records:
            pat = rec.pattern.lower()
            if pat == val_lower or fnmatch.fnmatch(val_lower, pat):
                return True, f"Suppressed by rule '{rec.pattern}': {rec.reason}"

        return False, None

    # --- Legal Hold Management ---

    def place_legal_hold(
        self,
        workspace_id: str,
        name: str,
        target_entity_type: str,
        case_reference: str,
        target_entity_id: Optional[str] = None,
        notes: Optional[str] = None,
        placed_by: Optional[str] = None,
    ) -> LegalHold:
        hold = LegalHold(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name=name,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            case_reference=case_reference,
            notes=notes,
            is_active=True,
            placed_by=placed_by,
            placed_at=datetime.now(timezone.utc),
        )
        self.db.add(hold)
        self.db.commit()
        self.db.refresh(hold)
        return hold

    def release_legal_hold(self, hold_id: str) -> Optional[LegalHold]:
        hold = self.db.query(LegalHold).filter(LegalHold.id == hold_id).first()
        if not hold:
            return None

        hold.is_active = False
        hold.released_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(hold)
        return hold

    def is_under_legal_hold(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """Checks if a specific entity is subject to an active legal hold."""
        hold = self.db.query(LegalHold).filter(
            LegalHold.workspace_id == workspace_id,
            LegalHold.is_active == True,
            LegalHold.target_entity_type.in_([entity_type, "ALL"]),
            (LegalHold.target_entity_id == entity_id) | (LegalHold.target_entity_id == None),
        ).first()

        return hold is not None
