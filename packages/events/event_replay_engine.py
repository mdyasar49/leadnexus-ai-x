"""
Bounded, Audited Event Replay Engine.
Supports bounded event re-drive for specified target consumers, timestamp windows,
event type filters, and dry-run execution.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.events import OutboxEvent, EventReplayJob, ReplayStatus, OutboxStatus
from packages.events.event_envelope import EventEnvelope
from packages.events.event_bus import global_event_bus


class EventReplayService:
    @staticmethod
    def create_replay_job(
        db: Session,
        tenant_id: str,
        user_id: str,
        target_consumer: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        filter_event_types: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> EventReplayJob:
        """Initializes an audited EventReplayJob."""
        job = EventReplayJob(
            tenant_id=tenant_id,
            initiated_by=user_id,
            target_consumer=target_consumer,
            filter_event_types=filter_event_types or [],
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            dry_run=dry_run,
            status=ReplayStatus.PENDING,
            replayed_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def execute_replay_job(db: Session, job_id: str) -> Dict[str, Any]:
        """Executes a replay job over the target window."""
        job = db.query(EventReplayJob).filter(EventReplayJob.id == job_id).first()
        if not job:
            raise ValueError(f"Replay job {job_id} not found")

        job.status = ReplayStatus.RUNNING
        db.commit()

        query = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.tenant_id == job.tenant_id,
                OutboxEvent.occurred_at >= job.from_timestamp,
                OutboxEvent.occurred_at <= job.to_timestamp,
            )
            .order_by(OutboxEvent.occurred_at.asc())
        )

        if job.filter_event_types:
            query = query.filter(OutboxEvent.event_type.in_(job.filter_event_types))

        events = query.all()
        replayed = 0

        for record in events:
            if not job.dry_run:
                envelope = EventEnvelope(
                    event_id=record.event_id,
                    event_type=record.event_type,
                    event_version=record.event_version,
                    tenant_id=record.tenant_id,
                    aggregate_type=record.aggregate_type,
                    aggregate_id=record.aggregate_id,
                    occurred_at=record.occurred_at.isoformat() if record.occurred_at else datetime.now(timezone.utc).isoformat(),
                    source_service="event-replay-engine",
                    correlation_id=record.correlation_id,
                    causation_id=job.id,
                    schema_version=record.schema_version,
                    payload=record.payload,
                    checksum=record.checksum,
                )
                global_event_bus.publish(envelope)
            replayed += 1

        job.status = ReplayStatus.COMPLETED
        job.replayed_count = replayed
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        return {
            "job_id": job.id,
            "status": job.status.value,
            "replayed_count": replayed,
            "dry_run": job.dry_run,
        }

