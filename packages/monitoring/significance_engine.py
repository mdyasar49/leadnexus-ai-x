import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.monitoring import (
    EntityChangeEvent,
    ChangeClass,
    SignificanceLevel
)
from app.models.scoring import LeadScore


NOISE_PATTERNS = [
    r'copyright\s*\d{4}',
    r'all\s*rights\s*reserved',
    r'privacy\s*policy\s*updated',
    r'terms\s*of\s*service',
    r'cookie\s*settings',
    r'page\s*rendered\s*in',
    r'session_id',
    r'csrf_token',
]


class ChangeSignificanceEngine:
    """Classifies entity diffs, eliminates noise, and calculates ChangeSignificanceScore (0-100)."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def classify_change(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
        entity_id: Optional[str] = None,
        lead_priority_score: Optional[float] = None
    ) -> Tuple[str, float, str]:
        """Instance method to classify changes, dynamically looking up entity score if db is available."""
        score = lead_priority_score
        if score is None and self.db and entity_id:
            lead_score_rec = self.db.query(LeadScore).filter(LeadScore.company_id == entity_id).first()
            if lead_score_rec:
                score = lead_score_rec.lead_priority_score

        if score is None:
            score = 50.0

        return self.classify_and_score(
            field_name=field_name,
            old_val=old_value,
            new_val=new_value,
            lead_priority_score=score
        )

    @staticmethod
    def classify_and_score(
        field_name: str,
        old_val: Any,
        new_val: Any,
        lead_priority_score: float = 50.0
    ) -> Tuple[str, float, str]:
        """
        Classifies change into ChangeClass and computes significance score (0-100) and SignificanceLevel.
        Factors: field importance, magnitude of diff, lead priority, noise filtering.
        """
        s_old = str(old_val).strip() if old_val is not None else ""
        s_new = str(new_val).strip() if new_val is not None else ""

        # 1. Noise Check
        for pat in NOISE_PATTERNS:
            if re.search(pat, s_old.lower()) or re.search(pat, s_new.lower()):
                return ChangeClass.NOISE.value, 10.0, SignificanceLevel.INFO.value

        f = field_name.lower()
        base_score = 50.0
        change_class = ChangeClass.CONTENT_CHANGE.value

        # 2. Technology & Version Changes
        if "tech" in f or "version" in f or "odoo" in f or "erp" in f:
            change_class = ChangeClass.TECHNOLOGY_CHANGE.value
            base_score = 75.0
            if "odoo" in s_new.lower() and ("17" in s_new or "18" in s_new or "19" in s_new):
                base_score = 85.0

        # 3. Contact Changes (email, phone, contact details)
        elif "email" in f or "phone" in f or "mobile" in f:
            change_class = ChangeClass.CONTACT_CHANGE.value
            base_score = 65.0

        # 4. Leadership & Decision-Maker Changes
        elif "role" in f or "title" in f or "decision_maker" in f or "cto" in f or "ceo" in f or "executive" in f:
            change_class = ChangeClass.LEADERSHIP_CHANGE.value
            base_score = 85.0
            if any(k in s_new.lower() for k in ["ceo", "cto", "managing director", "erp manager"]):
                base_score = 90.0

        # 5. Intent Signals
        elif "intent" in f or "signal" in f or "rfp" in f:
            change_class = ChangeClass.INTENT_CHANGE.value
            base_score = 88.0

        # 6. Lead Score Changes
        elif "lead_score" in f or "lead_priority_score" in f:
            change_class = ChangeClass.SCORE_CHANGE.value
            try:
                delta = abs(float(s_new) - float(s_old))
                base_score = min(95.0, 50.0 + delta * 2.5)
            except (ValueError, TypeError):
                base_score = 70.0

        # 7. Business & Location Changes
        elif "country" in f or "city" in f or "industry" in f or "domain" in f or "funding" in f:
            change_class = ChangeClass.BUSINESS_CHANGE.value
            base_score = 70.0

        # Weight by lead importance (higher priority lead raises significance)
        lead_factor = max(0.8, min(1.3, lead_priority_score / 75.0))
        final_score = max(5.0, min(100.0, round(base_score * lead_factor, 1)))

        # Map to SignificanceLevel
        if final_score >= 85.0:
            level = SignificanceLevel.CRITICAL.value
        elif final_score >= 70.0:
            level = SignificanceLevel.HIGH.value
        elif final_score >= 50.0:
            level = SignificanceLevel.MEDIUM.value
        elif final_score >= 30.0:
            level = SignificanceLevel.LOW.value
        else:
            level = SignificanceLevel.INFO.value

        return change_class, final_score, level

    def record_change_event(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        source_name: str,
        source_url: str,
        evidence_snippet: Optional[str] = None,
        lead_priority_score: Optional[float] = None,
        db: Optional[Session] = None
    ) -> EntityChangeEvent:
        """Evaluates diff significance and logs an immutable EntityChangeEvent."""
        target_db = db or self.db
        if target_db is None:
            raise ValueError("Database session required to record change event.")

        score = lead_priority_score
        if score is None:
            lead_score_rec = target_db.query(LeadScore).filter(LeadScore.company_id == entity_id).first()
            if lead_score_rec:
                score = lead_score_rec.lead_priority_score
            else:
                score = 50.0

        change_class, final_score, level = self.classify_and_score(
            field_name=field_name,
            old_val=old_value,
            new_val=new_value,
            lead_priority_score=score
        )

        now = datetime.now(timezone.utc)
        event = EntityChangeEvent(
            workspace_id=workspace_id,
            entity_type=entity_type.upper(),
            entity_id=entity_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            change_class=change_class,
            significance_score=final_score,
            significance_level=level,
            source_name=source_name,
            source_url=source_url,
            evidence_snippet=evidence_snippet,
            observed_at=now,
            detected_at=now
        )
        target_db.add(event)
        target_db.commit()
        target_db.refresh(event)

        return event
