"""
Phase 34: Enterprise Event-Driven Architecture API Routes.
Exposes Transactional Outbox, Subscriptions, Consumer Offsets, and Replay.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.events import OutboxEvent, OutboxStatus, EventSubscription, ConsumerOffset, EventReplayJob
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from packages.events.event_envelope import EventEnvelope
from packages.events.outbox_publisher import TransactionalOutboxService
from packages.events.event_bus import global_event_bus
from packages.events.event_replay_engine import EventReplayService
from packages.events.idempotent_consumer import IdempotentConsumerManager

router = APIRouter(prefix="/events", tags=["Enterprise Event-Driven Architecture"])


class PublishEventRequest(BaseModel):
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    flush_immediately: bool = True


class CreateSubscriptionRequest(BaseModel):
    consumer_name: str
    event_type_pattern: str
    destination_endpoint: str
    max_retries: int = 3


class CreateReplayRequest(BaseModel):
    target_consumer: str
    from_timestamp: datetime
    to_timestamp: datetime
    filter_event_types: Optional[List[str]] = None
    dry_run: bool = False


@router.post("/publish", status_code=status.HTTP_201_CREATED)
def publish_event(
    req: PublishEventRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Stages an event into the transactional outbox."""
    correlation_id = req.correlation_id or f"corr_{datetime.now(timezone.utc).timestamp()}"
    event = TransactionalOutboxService.stage_event(
        db=db,
        tenant_id=workspace.id,
        event_type=req.event_type,
        aggregate_type=req.aggregate_type,
        aggregate_id=req.aggregate_id,
        payload=req.payload,
        correlation_id=correlation_id,
        causation_id=req.causation_id,
    )
    db.commit()
    db.refresh(event)

    flush_res = None
    if req.flush_immediately:
        flush_res = TransactionalOutboxService.publish_pending(db, batch_size=10)

    return {
        "event_id": event.event_id,
        "status": event.status.value,
        "occurred_at": event.occurred_at.isoformat(),
        "checksum": event.checksum,
        "flushed": flush_res,
    }


@router.get("/outbox")
def list_outbox_events(
    status_filter: Optional[OutboxStatus] = None,
    limit: int = Query(50, ge=1, le=200),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Lists outbox events for tenant."""
    query = db.query(OutboxEvent).filter(OutboxEvent.tenant_id == workspace.id)
    if status_filter:
        query = query.filter(OutboxEvent.status == status_filter)
    events = query.order_by(OutboxEvent.created_at.desc()).limit(limit).all()

    return [
        {
            "id": e.id,
            "event_id": e.event_id,
            "event_type": e.event_type,
            "aggregate_type": e.aggregate_type,
            "aggregate_id": e.aggregate_id,
            "status": e.status.value,
            "retry_count": e.retry_count,
            "occurred_at": e.occurred_at.isoformat(),
            "published_at": e.published_at.isoformat() if e.published_at else None,
        }
        for e in events
    ]


@router.get("/outbox/{event_id}")
def get_outbox_event(
    event_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Inspects detailed event envelope."""
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.event_id == event_id, OutboxEvent.tenant_id == workspace.id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Outbox event not found")

    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "occurred_at": event.occurred_at.isoformat(),
        "source_service": event.source_service,
        "correlation_id": event.correlation_id,
        "payload": event.payload,
        "checksum": event.checksum,
        "status": event.status.value,
        "retry_count": event.retry_count,
        "last_error": event.last_error,
    }


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def create_subscription(
    req: CreateSubscriptionRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Registers a consumer subscription for event streams."""
    sub = EventSubscription(
        tenant_id=workspace.id,
        consumer_name=req.consumer_name,
        event_type_pattern=req.event_type_pattern,
        destination_endpoint=req.destination_endpoint,
        max_retries=req.max_retries,
        is_active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {
        "subscription_id": sub.id,
        "consumer_name": sub.consumer_name,
        "pattern": sub.event_type_pattern,
        "status": "ACTIVE",
    }


@router.get("/subscriptions")
def list_subscriptions(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Lists registered subscriptions."""
    subs = db.query(EventSubscription).filter(EventSubscription.tenant_id == workspace.id).all()
    return [
        {
            "id": s.id,
            "consumer_name": s.consumer_name,
            "event_type_pattern": s.event_type_pattern,
            "destination_endpoint": s.destination_endpoint,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]


@router.get("/consumers/offsets")
def list_consumer_offsets(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Lists consumer checkpoint offsets and compute lag."""
    total_events = db.query(OutboxEvent).filter(OutboxEvent.tenant_id == workspace.id).count()
    offsets = db.query(ConsumerOffset).all()
    return [
        {
            "consumer_name": o.consumer_name,
            "partition": o.stream_partition,
            "last_processed_event_id": o.last_processed_event_id,
            "processed_count": o.processed_count,
            "lag": max(0, total_events - o.processed_count),
            "last_processed_at": o.last_processed_at.isoformat(),
        }
        for o in offsets
    ]


@router.post("/replay", status_code=status.HTTP_202_ACCEPTED)
def initiate_replay(
    req: CreateReplayRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Initiates an audited event replay job."""
    job = EventReplayService.create_replay_job(
        db=db,
        tenant_id=workspace.id,
        user_id=user.id,
        target_consumer=req.target_consumer,
        from_timestamp=req.from_timestamp,
        to_timestamp=req.to_timestamp,
        filter_event_types=req.filter_event_types,
        dry_run=req.dry_run,
    )
    result = EventReplayService.execute_replay_job(db, job.id)
    return result


@router.get("/replay/{job_id}")
def get_replay_status(
    job_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Checks the status of an event replay job."""
    job = (
        db.query(EventReplayJob)
        .filter(EventReplayJob.id == job_id, EventReplayJob.tenant_id == workspace.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Replay job not found")

    return {
        "job_id": job.id,
        "target_consumer": job.target_consumer,
        "status": job.status.value,
        "replayed_count": job.replayed_count,
        "dry_run": job.dry_run,
        "from_timestamp": job.from_timestamp.isoformat(),
        "to_timestamp": job.to_timestamp.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/dlq")
def get_dead_letter_queue(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Inspects dead letter events."""
    return global_event_bus.get_dlq_records()
