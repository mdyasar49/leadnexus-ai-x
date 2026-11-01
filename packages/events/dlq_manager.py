"""
LeadNexus AI X — Phase 36: Dead Letter Queue (DLQ) & Loop Defense Engine
Quarantines poison-pill events, detects cascading recursion loops (max_depth=5),
and provides audited Redrive, Discard, and Repair capabilities.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session

from app.models.cqrs_event_sourcing import DeadLetterEvent, DLQReason, DLQStatus


class EventLoopDetectedError(Exception):
    """Raised when an event propagation depth exceeds safe limits or creates a cycle."""
    pass


class DeadLetterManager:
    """Manages poisoned event triage, audited redrive, and circuit protection."""

    MAX_PROPAGATION_DEPTH = 5

    @classmethod
    def verify_propagation_depth(cls, current_depth: int, causation_ids: Optional[List[str]] = None) -> None:
        """Enforces loop prevention limits (Rule 42)."""
        if current_depth > cls.MAX_PROPAGATION_DEPTH:
            raise EventLoopDetectedError(
                f"Event propagation depth {current_depth} exceeds maximum limit of {cls.MAX_PROPAGATION_DEPTH}. "
                "Possible infinite event cascade detected. Quarantining event to DLQ."
            )

        if causation_ids and len(causation_ids) != len(set(causation_ids)):
            raise EventLoopDetectedError(
                "Cycle detected in event causation chain. Terminating recursive event cascade."
            )

    @classmethod
    def quarantine(
        cls,
        db: Session,
        tenant_id: str,
        original_event_id: str,
        event_type: str,
        consumer_name: str,
        reason: DLQReason,
        error_details: str,
        payload: Dict[str, Any],
        propagation_depth: int = 1
    ) -> DeadLetterEvent:
        """Quarantines a failed event into the dead-letter repository."""
        dlq_event = DeadLetterEvent(
            tenant_id=tenant_id,
            original_event_id=original_event_id,
            event_type=event_type,
            consumer_name=consumer_name,
            reason=reason,
            error_details=error_details,
            payload=payload,
            propagation_depth=propagation_depth,
            status=DLQStatus.UNRESOLVED,
        )
        db.add(dlq_event)
        db.commit()
        db.refresh(dlq_event)
        return dlq_event

    @classmethod
    def redrive_event(
        cls,
        db: Session,
        dlq_id: str,
        consumer_fn: Callable[[Dict[str, Any]], Any]
    ) -> bool:
        """Retries a quarantined event. Updates status to RETRIED if successful."""
        record = db.query(DeadLetterEvent).filter(DeadLetterEvent.id == dlq_id).first()
        if not record:
            raise ValueError(f"DLQ record {dlq_id} not found.")

        record.retry_count += 1
        try:
            consumer_fn(record.payload)
            record.status = DLQStatus.RETRIED
            record.resolved_at = datetime.now(timezone.utc)
            db.commit()
            return True
        except Exception as err:
            record.error_details = f"Redrive retry {record.retry_count} failed: {err}"
            db.commit()
            return False

    @classmethod
    def repair_and_redrive(
        cls,
        db: Session,
        dlq_id: str,
        repaired_payload: Dict[str, Any],
        consumer_fn: Callable[[Dict[str, Any]], Any]
    ) -> bool:
        """Applies schema corrections or repaired data before reprocessing."""
        record = db.query(DeadLetterEvent).filter(DeadLetterEvent.id == dlq_id).first()
        if not record:
            raise ValueError(f"DLQ record {dlq_id} not found.")

        record.payload = repaired_payload
        record.retry_count += 1
        try:
            consumer_fn(repaired_payload)
            record.status = DLQStatus.REPAIRED
            record.resolved_at = datetime.now(timezone.utc)
            db.commit()
            return True
        except Exception as err:
            record.error_details = f"Repaired redrive failed: {err}"
            db.commit()
            return False

    @classmethod
    def discard(cls, db: Session, dlq_id: str, reason_note: str) -> DeadLetterEvent:
        """Discards an irrecoverable or poison-pill message."""
        record = db.query(DeadLetterEvent).filter(DeadLetterEvent.id == dlq_id).first()
        if not record:
            raise ValueError(f"DLQ record {dlq_id} not found.")

        record.status = DLQStatus.DISCARDED
        record.error_details = f"{record.error_details}\n[Discarded Note]: {reason_note}"
        record.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record

