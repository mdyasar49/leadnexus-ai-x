from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.enrichment import FieldObservation, FieldValueHistory, FreshnessTier, EnrichmentStatus
from app.models.scoring import FieldConflict


SOURCE_RELIABILITY_WEIGHTS = {
    "OFFICIAL_COMPANY_SOURCE": 1.0,
    "OFFICIAL_PUBLIC_API": 0.95,
    "OFFICIAL_GITHUB": 0.90,
    "PUBLIC_PROFESSIONAL_SOURCE": 0.85,
    "PUBLIC_JOB_SOURCE": 0.80,
    "RELIABLE_DIRECTORY": 0.75,
    "SEARCH_DISCOVERY": 0.70,
    "OTHER_PUBLIC_SOURCE": 0.50,
}

# Freshness expiration thresholds in days
FIELD_FRESHNESS_THRESHOLDS = {
    "intent": {"current": 14, "recent": 30, "aging": 60, "stale": 90},
    "decision_maker": {"current": 30, "recent": 60, "aging": 120, "stale": 180},
    "technology": {"current": 30, "recent": 90, "aging": 180, "stale": 365},
    "location": {"current": 90, "recent": 180, "aging": 365, "stale": 730},
    "company_profile": {"current": 90, "recent": 180, "aging": 365, "stale": 730},
}


class FieldResolver:
    """Multi-source observation tracker, conflict detector, and current-state resolver."""

    @staticmethod
    def calculate_freshness(field_name: str, observed_at: datetime) -> str:
        """Determines the freshness tier based on elapsed time and field type."""
        if not observed_at:
            return FreshnessTier.UNKNOWN.value

        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        elapsed_days = (now - observed_at).days

        # Match category threshold
        cat = "company_profile"
        if "intent" in field_name or "signal" in field_name:
            cat = "intent"
        elif "role" in field_name or "person" in field_name or "decision_maker" in field_name:
            cat = "decision_maker"
        elif "tech" in field_name or "version" in field_name:
            cat = "technology"
        elif "country" in field_name or "city" in field_name or "state" in field_name or "location" in field_name:
            cat = "location"

        thresholds = FIELD_FRESHNESS_THRESHOLDS[cat]
        if elapsed_days <= thresholds["current"]:
            return FreshnessTier.CURRENT.value
        elif elapsed_days <= thresholds["recent"]:
            return FreshnessTier.RECENT.value
        elif elapsed_days <= thresholds["aging"]:
            return FreshnessTier.AGING.value
        elif elapsed_days <= thresholds["stale"]:
            return FreshnessTier.STALE.value
        else:
            return FreshnessTier.EXPIRED.value

    @staticmethod
    def record_observation(
        db: Session,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        value: Any,
        source_name: str,
        source_url: str,
        confidence: float = 1.0,
        raw_value: Optional[str] = None
    ) -> Tuple[FieldObservation, bool]:
        """
        Records an atomic field observation.
        If a conflicting observation exists from another source, flags FieldConflict rather than overwriting.
        Returns (FieldObservation, is_conflicted).
        """
        now = datetime.now(timezone.utc)
        clean_val = str(value).strip() if value is not None else ""
        source_weight = SOURCE_RELIABILITY_WEIGHTS.get(source_name.upper(), 0.70)
        adjusted_confidence = round(confidence * source_weight, 2)
        freshness = FieldResolver.calculate_freshness(field_name, now)

        # Check existing active observations for this entity field
        existing_obs = (
            db.query(FieldObservation)
            .filter(
                FieldObservation.workspace_id == workspace_id,
                FieldObservation.entity_id == entity_id,
                FieldObservation.field_name == field_name,
                FieldObservation.valid_to.is_(None)
            )
            .all()
        )

        is_conflicted = False
        corroborated = False

        for obs in existing_obs:
            if obs.value.lower() == clean_val.lower():
                # Corroboration from independent source: increase confidence
                if obs.source_name != source_name:
                    corroborated = True
                    obs.confidence = min(1.0, round(obs.confidence + 0.10, 2))
                    obs.last_seen = now
            else:
                # Disagreement between sources: create FieldConflict without overwriting
                is_conflicted = True
                conflict = FieldConflict(
                    workspace_id=workspace_id,
                    company_id=entity_id if entity_type == "COMPANY" else None,
                    field_name=field_name,
                    value_a=obs.value,
                    source_a=obs.source_name,
                    value_b=clean_val,
                    source_b=source_name,
                    resolution_status="CONFLICTED"
                )
                db.add(conflict)

        # Boost confidence if corroborated
        if corroborated:
            adjusted_confidence = min(1.0, adjusted_confidence + 0.15)

        new_obs = FieldObservation(
            workspace_id=workspace_id,
            entity_type=entity_type.upper(),
            entity_id=entity_id,
            field_name=field_name,
            value=clean_val,
            raw_value=raw_value or clean_val,
            source_name=source_name,
            source_url=source_url,
            confidence=adjusted_confidence,
            freshness=freshness,
            status=EnrichmentStatus.CONFLICTED.value if is_conflicted else EnrichmentStatus.FOUND.value,
            observed_at=now,
            valid_from=now,
            is_canonical=(len(existing_obs) == 0 and not is_conflicted)
        )
        db.add(new_obs)
        db.commit()
        db.refresh(new_obs)

        return new_obs, is_conflicted

    @staticmethod
    def resolve_canonical_field(
        db: Session,
        workspace_id: str,
        entity_id: str,
        field_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resolves the winning canonical value based on:
        1. Verification status
        2. Source reliability weight
        3. Recency / Freshness
        4. Independent corroboration
        """
        observations = (
            db.query(FieldObservation)
            .filter(
                FieldObservation.workspace_id == workspace_id,
                FieldObservation.entity_id == entity_id,
                FieldObservation.field_name == field_name
            )
            .order_by(desc(FieldObservation.confidence), desc(FieldObservation.observed_at))
            .all()
        )

        if not observations:
            return None

        # Pick highest confidence observation
        best = observations[0]

        return {
            "entity_id": entity_id,
            "field_name": field_name,
            "canonical_value": best.value,
            "confidence": best.confidence,
            "source_name": best.source_name,
            "source_url": best.source_url,
            "freshness": FieldResolver.calculate_freshness(field_name, best.observed_at),
            "status": best.status,
            "observed_at": best.observed_at.isoformat() if best.observed_at else None,
            "observation_count": len(observations)
        }
