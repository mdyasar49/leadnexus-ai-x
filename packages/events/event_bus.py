"""
Enterprise In-Memory / Distributed Event Bus.
Supports pattern-based subscriptions (e.g., 'company.*', 'lead.scored', '*'),
handler dispatching, delivery retry, and Dead-Letter Queue (DLQ) routing.
"""

import fnmatch
import logging
from typing import Callable, Dict, List, Any, Optional
from packages.events.event_envelope import EventEnvelope

logger = logging.getLogger("leadnexus.events.bus")


class SubscriptionHandler:
    def __init__(self, consumer_name: str, pattern: str, callback: Callable[[EventEnvelope], Any], max_retries: int = 3):
        self.consumer_name = consumer_name
        self.pattern = pattern
        self.callback = callback
        self.max_retries = max_retries


class EnterpriseEventBus:
    def __init__(self):
        self._handlers: List[SubscriptionHandler] = []
        self._dlq: List[Dict[str, Any]] = []
        self._published_history: List[EventEnvelope] = []

    def subscribe(self, consumer_name: str, pattern: str, callback: Callable[[EventEnvelope], Any], max_retries: int = 3) -> None:
        """Register a consumer callback for matching event patterns."""
        handler = SubscriptionHandler(consumer_name, pattern, callback, max_retries)
        self._handlers.append(handler)
        logger.info(f"Subscribed consumer '{consumer_name}' to pattern '{pattern}'")

    def unsubscribe(self, consumer_name: str) -> None:
        """Remove subscriptions for a consumer."""
        self._handlers = [h for h in self._handlers if h.consumer_name != consumer_name]

    def publish(self, envelope: EventEnvelope) -> Dict[str, Any]:
        """Dispatches event envelope to all matching consumer handlers."""
        if not envelope.verify_checksum():
            raise ValueError(f"Checksum mismatch for event {envelope.event_id}")

        self._published_history.append(envelope)
        delivered_count = 0
        failed_count = 0

        for handler in self._handlers:
            if fnmatch.fnmatch(envelope.event_type, handler.pattern):
                success = False
                last_error = None
                for attempt in range(handler.max_retries):
                    try:
                        handler.callback(envelope)
                        success = True
                        delivered_count += 1
                        break
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"Handler '{handler.consumer_name}' attempt {attempt + 1} failed: {e}")

                if not success:
                    failed_count += 1
                    dlq_record = {
                        "event_id": envelope.event_id,
                        "event_type": envelope.event_type,
                        "consumer_name": handler.consumer_name,
                        "error": last_error,
                        "envelope": envelope.model_dump(),
                    }
                    self._dlq.append(dlq_record)
                    logger.error(f"Event {envelope.event_id} routed to DLQ for consumer '{handler.consumer_name}'")

        return {
            "event_id": envelope.event_id,
            "delivered_count": delivered_count,
            "failed_count": failed_count,
        }

    def get_dlq_records(self) -> List[Dict[str, Any]]:
        return list(self._dlq)

    def clear_dlq(self) -> None:
        self._dlq.clear()


# Global event bus singleton instance
global_event_bus = EnterpriseEventBus()
