import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models.monitoring import (
    Alert,
    AlertFingerprint,
    AlertFeedback,
    AlertStatus,
    EntityChangeEvent,
    Notification,
    SignificanceLevel
)


class AlertEngine:
    """Intelligent alert generation, fingerprint deduplication, and lifecycle management."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    @staticmethod
    def generate_fingerprint(workspace_id: str, entity_id: str, change_class: str, field_name: str) -> str:
        """Computes a day-bucketed fingerprint hash for alert deduplication."""
        day_bucket = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw = f"{workspace_id}:{entity_id}:{change_class}:{field_name}:{day_bucket}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_or_corroborate_alert(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        change_class: str,
        title: str,
        message: str,
        evidence: Optional[str] = None,
        severity: str = "MEDIUM",
        db: Optional[Session] = None
    ) -> Tuple[Alert, bool]:
        """
        Creates a new alert or deduplicates against existing fingerprint for the day,
        appending multi-source corroborating evidence.
        Returns (Alert, is_new).
        """
        target_db = db or self.db
        if target_db is None:
            raise ValueError("Database session required.")

        fp_hash = self.generate_fingerprint(
            workspace_id=workspace_id,
            entity_id=entity_id,
            change_class=change_class,
            field_name=field_name
        )

        now = datetime.now(timezone.utc)

        # 1. Deduplication Check
        existing_fp = (
            target_db.query(AlertFingerprint)
            .filter(
                and_(
                    AlertFingerprint.workspace_id == workspace_id,
                    AlertFingerprint.fingerprint_hash == fp_hash
                )
            )
            .first()
        )

        if existing_fp:
            existing_fp.occurrence_count += 1
            alert = target_db.query(Alert).filter(
                and_(Alert.workspace_id == workspace_id, Alert.id == existing_fp.alert_id)
            ).first()
            if alert:
                if evidence and evidence not in (alert.evidence_summary or ""):
                    alert.evidence_summary = (alert.evidence_summary or "") + f" | Corroborating: {evidence}"
                target_db.commit()
                target_db.refresh(alert)
                return alert, False

        # 2. Create new alert
        category = change_class.split("_")[0] if "_" in change_class else change_class
        new_alert = Alert(
            workspace_id=workspace_id,
            entity_type=entity_type.upper(),
            entity_id=entity_id,
            alert_category=category,
            severity=severity,
            title=title,
            message=message,
            evidence_summary=evidence or "",
            status=AlertStatus.OPEN.value,
            fingerprint=fp_hash
        )
        target_db.add(new_alert)
        target_db.commit()
        target_db.refresh(new_alert)

        # 3. Create fingerprint
        fp = AlertFingerprint(
            workspace_id=workspace_id,
            fingerprint_hash=fp_hash,
            alert_id=new_alert.id,
            first_seen=now,
            occurrence_count=1
        )
        target_db.add(fp)
        target_db.commit()

        return new_alert, True

    def process_change_for_alert(
        self,
        workspace_id: str,
        change_event: EntityChangeEvent,
        title: Optional[str] = None,
        message: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Tuple[Optional[Alert], bool]:
        """
        Evaluates a change event and generates or deduplicates an Alert.
        Returns (Alert, is_new_alert).
        """
        target_db = db or self.db
        if target_db is None:
            raise ValueError("Database session required.")

        # Only alert for meaningful, high, or critical changes
        if change_event.significance_level in {SignificanceLevel.INFO.value, SignificanceLevel.LOW.value}:
            return None, False

        alert_title = title or f"{change_event.change_class.replace('_', ' ').title()} Detected on {change_event.entity_type.title()}"
        alert_msg = message or f"Field '{change_event.field_name}' changed from '{change_event.old_value}' to '{change_event.new_value}'. Significance score: {change_event.significance_score}/100."
        evidence_str = f"Primary source: {change_event.source_name} ({change_event.source_url})"
        if change_event.evidence_snippet:
            evidence_str += f" - \"{change_event.evidence_snippet}\""

        return self.create_or_corroborate_alert(
            workspace_id=workspace_id,
            entity_type=change_event.entity_type,
            entity_id=change_event.entity_id,
            field_name=change_event.field_name,
            change_class=change_event.change_class,
            title=alert_title,
            message=alert_msg,
            evidence=evidence_str,
            severity=change_event.significance_level,
            db=target_db
        )

    def acknowledge_alert(self, workspace_id: str, alert_id: str, user_id: str, db: Optional[Session] = None) -> Optional[Alert]:
        target_db = db or self.db
        alert = target_db.query(Alert).filter(and_(Alert.workspace_id == workspace_id, Alert.id == alert_id)).first()
        if not alert:
            return None
        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = user_id
        target_db.commit()
        target_db.refresh(alert)
        return alert

    def snooze_alert(self, workspace_id: str, alert_id: str, duration_hours: int = 24, db: Optional[Session] = None) -> Optional[Alert]:
        target_db = db or self.db
        alert = target_db.query(Alert).filter(and_(Alert.workspace_id == workspace_id, Alert.id == alert_id)).first()
        if not alert:
            return None
        alert.status = AlertStatus.SNOOZED.value
        alert.snoozed_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        target_db.commit()
        target_db.refresh(alert)
        return alert

    def resolve_alert(self, workspace_id: str, alert_id: str, db: Optional[Session] = None) -> Optional[Alert]:
        target_db = db or self.db
        alert = target_db.query(Alert).filter(and_(Alert.workspace_id == workspace_id, Alert.id == alert_id)).first()
        if not alert:
            return None
        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = datetime.now(timezone.utc)
        target_db.commit()
        target_db.refresh(alert)
        return alert

    def dismiss_alert(self, workspace_id: str, alert_id: str, db: Optional[Session] = None) -> Optional[Alert]:
        target_db = db or self.db
        alert = target_db.query(Alert).filter(and_(Alert.workspace_id == workspace_id, Alert.id == alert_id)).first()
        if not alert:
            return None
        alert.status = AlertStatus.DISMISSED.value
        target_db.commit()
        target_db.refresh(alert)
        return alert

    def record_feedback(
        self,
        workspace_id: str,
        user_id: str,
        alert_id: str,
        feedback_type: str,
        notes: Optional[str] = None,
        db: Optional[Session] = None
    ) -> AlertFeedback:
        target_db = db or self.db
        fb = AlertFeedback(
            workspace_id=workspace_id,
            user_id=user_id,
            alert_id=alert_id,
            feedback_type=feedback_type.upper(),
            notes=notes
        )
        target_db.add(fb)
        target_db.commit()
        target_db.refresh(fb)
        return fb

    def list_alerts(
        self,
        workspace_id: str,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db: Optional[Session] = None
    ) -> List[Alert]:
        target_db = db or self.db
        query = target_db.query(Alert).filter(Alert.workspace_id == workspace_id)
        if status_filter:
            query = query.filter(Alert.status == status_filter.upper())
        if severity_filter:
            query = query.filter(Alert.severity == severity_filter.upper())
        return query.order_by(desc(Alert.created_at)).offset(offset).limit(limit).all()
