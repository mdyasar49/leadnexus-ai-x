"""
Phase 34: Enterprise Event-Driven Architecture Package.
"""

from packages.events.event_envelope import EventEnvelope
from packages.events.event_bus import EnterpriseEventBus, global_event_bus
from packages.events.outbox_publisher import TransactionalOutboxService
from packages.events.idempotent_consumer import IdempotentConsumerManager
from packages.events.event_replay_engine import EventReplayService
from packages.events.schema_registry import (
    EventSchemaRegistry,
    BreakingSchemaEvolutionError,
    SchemaValidationError,
)
from packages.events.event_sourcing_engine import (
    EventSourcingEngine,
    ConcurrencyConflictError,
)
from packages.events.cqrs_command_bus import (
    CQRSCommandBus,
    CommandExecutionError,
)
from packages.events.dlq_manager import (
    DeadLetterManager,
    EventLoopDetectedError,
)

__all__ = [
    "EventEnvelope",
    "EnterpriseEventBus",
    "global_event_bus",
    "TransactionalOutboxService",
    "IdempotentConsumerManager",
    "EventReplayService",
    "EventSchemaRegistry",
    "BreakingSchemaEvolutionError",
    "SchemaValidationError",
    "EventSourcingEngine",
    "ConcurrencyConflictError",
    "CQRSCommandBus",
    "CommandExecutionError",
    "DeadLetterManager",
    "EventLoopDetectedError",
]

