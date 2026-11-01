"""
LeadNexus AI X — Phase 36: Event Sourcing & Snapshot Engine
Selective event-sourcing for historical domain auditability and state reconstruction.
Enforces monotonic sequence numbers and fast reconstruction via checkpoints.
"""

from typing import Dict, Any, List, Optional, Callable, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.cqrs_event_sourcing import AggregateEvent, AggregateSnapshot


class ConcurrencyConflictError(Exception):
    """Raised when an aggregate event sequence conflict occurs."""
    pass


class EventSourcingEngine:
    """Manages append-only aggregate event streams and snapshotting."""

    @classmethod
    def append_event(
        cls,
        db: Session,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: str,
        causation_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_version: str = "1.0.0",
        expected_version: Optional[int] = None
    ) -> AggregateEvent:
        """Appends an event to the aggregate's sequence stream with optimistic concurrency check."""
        # Query highest sequence number for this aggregate
        latest = (
            db.query(AggregateEvent)
            .filter(
                AggregateEvent.tenant_id == tenant_id,
                AggregateEvent.aggregate_type == aggregate_type,
                AggregateEvent.aggregate_id == aggregate_id
            )
            .order_by(AggregateEvent.sequence_number.desc())
            .first()
        )

        current_version = latest.sequence_number if latest else 0

        if expected_version is not None and expected_version != current_version:
            raise ConcurrencyConflictError(
                f"Optimistic concurrency violation on {aggregate_type}:{aggregate_id}. "
                f"Expected version {expected_version}, but current version is {current_version}."
            )

        new_sequence = current_version + 1

        event = AggregateEvent(
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            sequence_number=new_sequence,
            event_type=event_type,
            event_version=event_version,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
            actor_id=actor_id,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @classmethod
    def create_snapshot(
        cls,
        db: Session,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        state: Dict[str, Any],
        last_sequence_number: int,
    ) -> AggregateSnapshot:
        """Stores a state checkpoint to accelerate future state reconstruction."""
        # Find latest snapshot version
        latest_snapshot = (
            db.query(AggregateSnapshot)
            .filter(
                AggregateSnapshot.tenant_id == tenant_id,
                AggregateSnapshot.aggregate_type == aggregate_type,
                AggregateSnapshot.aggregate_id == aggregate_id
            )
            .order_by(AggregateSnapshot.snapshot_version.desc())
            .first()
        )

        next_version = (latest_snapshot.snapshot_version + 1) if latest_snapshot else 1

        snapshot = AggregateSnapshot(
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            last_sequence_number=last_sequence_number,
            snapshot_version=next_version,
            state=state,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @classmethod
    def rebuild_aggregate_state(
        cls,
        db: Session,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        apply_fn: Optional[Callable[[Dict[str, Any], AggregateEvent], Dict[str, Any]]] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Reconstructs the canonical state by reading the latest snapshot (if any)
        and applying all subsequent events sequentially.
        """
        snapshot = (
            db.query(AggregateSnapshot)
            .filter(
                AggregateSnapshot.tenant_id == tenant_id,
                AggregateSnapshot.aggregate_type == aggregate_type,
                AggregateSnapshot.aggregate_id == aggregate_id
            )
            .order_by(AggregateSnapshot.snapshot_version.desc())
            .first()
        )

        current_state = dict(snapshot.state) if snapshot else {}
        from_sequence = (snapshot.last_sequence_number + 1) if snapshot else 1

        # Fetch subsequent events
        events = (
            db.query(AggregateEvent)
            .filter(
                AggregateEvent.tenant_id == tenant_id,
                AggregateEvent.aggregate_type == aggregate_type,
                AggregateEvent.aggregate_id == aggregate_id,
                AggregateEvent.sequence_number >= from_sequence
            )
            .order_by(AggregateEvent.sequence_number.asc())
            .all()
        )

        current_version = snapshot.last_sequence_number if snapshot else 0

        # Default fold function if none provided: shallow merge payload
        default_apply = lambda state, ev: {**state, **ev.payload, "_last_event_type": ev.event_type}
        folder = apply_fn or default_apply

        for event in events:
            current_state = folder(current_state, event)
            current_version = event.sequence_number

        return current_state, current_version

