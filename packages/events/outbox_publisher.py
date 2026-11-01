"""
Transactional Outbox Service.
Stages events within the caller's active database transaction and provides
a reliable publishing worker that scans, formats envelopes, dispatches to event bus,
and marks events as PUBLISHED or routes to DEAD_LETTER.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models.events import OutboxEvent, OutboxStatus
from packages.events.event_envelope import EventEnvelope
from packages.events.event_bus import global_event_bus

logger = logging.getLogger("leadnexus.events.outbox")


class TransactionalOutboxService:
    @staticmethod
    def stage_event(
        db: Session,
        tenant_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
        correlation_id: str,
        causation_id: Optional[str] = None,
        event_version: str = "1.0.0",
        schema_version: str = "1.0.0",
    ) -> OutboxEvent:
        """
        Stages an outbox event in the same DB transaction as entity write.
        Caller handles db.commit().
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(payload_bytes).hexdigest()

        event = OutboxEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            occurred_at=datetime.now(timezone.utc),
            source_service="leadnexus-api",
            correlation_id=correlation_id,
            causation_id=causation_id,
            schema_version=schema_version,
            payload=payload,
            checksum=checksum,
            status=OutboxStatus.PENDING,
            retry_count=0,
        )
        db.add(event)
        return event

    @staticmethod
    def publish_pending(db: Session, batch_size: int = 50) -> Dict[str, Any]:
        """
        Fetches PENDING outbox events, creates standardized EventEnvelope,
        dispatches to global_event_bus, and updates status.
        """
        pending = (
            db.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
            .all()
        )

        published_count = 0
        failed_count = 0

        for record in pending:
            envelope = EventEnvelope(
                event_id=record.event_id,
                event_type=record.event_type,
                event_version=record.event_version,
                tenant_id=record.tenant_id,
                aggregate_type=record.aggregate_type,
                aggregate_id=record.aggregate_id,
                occurred_at=record.occurred_at.isoformat() if record.occurred_at else datetime.now(timezone.utc).isoformat(),
                source_service=record.source_service,
                correlation_id=record.correlation_id,
                causation_id=record.causation_id,
                schema_version=record.schema_version,
                payload=record.payload,
                checksum=record.checksum,
            )

            try:
                dispatch_res = global_event_bus.publish(envelope)
                record.status = OutboxStatus.PUBLISHED
                record.published_at = datetime.now(timezone.utc)
                published_count += 1
            except Exception as e:
                logger.error(f"Failed to publish event {record.event_id}: {e}")
                record.retry_count += 1
                record.last_error = str(e)
                if record.retry_count >= 5:
                    record.status = OutboxStatus.DEAD_LETTER
                else:
                    record.status = OutboxStatus.FAILED
                failed_count += 1

        db.commit()
        return {
            "scanned": len(pending),
            "published": published_count,
            "failed": failed_count,
        }

