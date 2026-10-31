from datetime import datetime, timezone
from typing import Dict, Any, List, Callable, Optional


class EnrichmentEventBus:
    """Event bus for decoupled enrichment and continuous verification lifecycle events."""

    _subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    @classmethod
    def subscribe(cls, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener for a specific enrichment event type."""
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        cls._subscribers[event_type].append(handler)

    @classmethod
    def emit(cls, event_type: str, payload: Dict[str, Any]) -> None:
        """Dispatches an event with timestamp and payload to all registered handlers."""
        envelope = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        handlers = cls._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                handler(envelope)
            except Exception as exc:
                # Event dispatch must be resilient and not crash main pipeline
                pass

    @classmethod
    def clear(cls) -> None:
        """Resets all event subscribers (useful for testing)."""
        cls._subscribers = {}
