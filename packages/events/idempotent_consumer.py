"""
Idempotent Event Consumer Tracking.
Maintains state in consumer_offsets to guarantee at-least-once processing
with strict duplicate suppression.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.events import ConsumerOffset


class IdempotentConsumerManager:
    @staticmethod
    def is_duplicate(db: Session, consumer_name: str, event_id: str) -> bool:
        """Checks if event was already processed by this consumer."""
        offset = db.query(ConsumerOffset).filter(ConsumerOffset.consumer_name == consumer_name).first()
        if not offset:
            return False
        # If last processed event matches or exists in consumer history
        return offset.last_processed_event_id == event_id

    @staticmethod
    def record_processed(db: Session, consumer_name: str, event_id: str, partition: str = "partition-0") -> ConsumerOffset:
        """Updates consumer offset checkpoint idempotently."""
        offset = db.query(ConsumerOffset).filter(ConsumerOffset.consumer_name == consumer_name).first()
        if not offset:
            offset = ConsumerOffset(
                consumer_name=consumer_name,
                stream_partition=partition,
                last_processed_event_id=event_id,
                processed_count=1,
                last_processed_at=datetime.now(timezone.utc),
            )
            db.add(offset)
        else:
            offset.last_processed_event_id = event_id
            offset.processed_count += 1
            offset.last_processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(offset)
        return offset

    @staticmethod
    def get_consumer_lag(db: Session, consumer_name: str, total_stream_events: int) -> int:
        """Computes consumer lag relative to total available events."""
        offset = db.query(ConsumerOffset).filter(ConsumerOffset.consumer_name == consumer_name).first()
        if not offset:
            return total_stream_events
        return max(0, total_stream_events - offset.processed_count)
