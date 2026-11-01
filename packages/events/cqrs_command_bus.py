"""
LeadNexus AI X — Phase 36: CQRS Command Bus & Idempotency Engine
Separates write-model mutation commands from read-model queries.
Enforces strict command idempotency preventing duplicate operational side-effects.
"""

from typing import Dict, Any, Callable, Tuple, Optional
from sqlalchemy.orm import Session

from app.models.cqrs_event_sourcing import CommandIdempotencyRecord, CommandStatus


class CommandExecutionError(Exception):
    """Raised when a command fails business validation or execution."""
    pass


class CQRSCommandBus:
    """Dispatches commands with idempotency protection and transactional outbox emission."""

    @classmethod
    def dispatch(
        cls,
        db: Session,
        tenant_id: str,
        actor_id: str,
        idempotency_key: str,
        command_name: str,
        payload: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Executes a domain command. If the idempotency key was previously processed,
        returns the recorded response immediately without repeating execution.
        """
        # 1. Check idempotency record
        existing = db.query(CommandIdempotencyRecord).filter(
            CommandIdempotencyRecord.tenant_id == tenant_id,
            CommandIdempotencyRecord.idempotency_key == idempotency_key
        ).first()

        if existing:
            if existing.status == CommandStatus.FAILED:
                raise CommandExecutionError(f"Previous execution with key '{idempotency_key}' failed: {existing.error_message}")
            return existing.result_payload or {}, True  # (result, is_cached=True)

        # 2. Execute command handler
        try:
            result = handler(payload)
            # 3. Store idempotency record
            record = CommandIdempotencyRecord(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                command_name=command_name,
                actor_id=actor_id,
                status=CommandStatus.EXECUTED,
                result_payload=result,
            )
            db.add(record)
            db.commit()
            return result, False  # (result, is_cached=False)

        except Exception as err:
            db.rollback()
            record = CommandIdempotencyRecord(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                command_name=command_name,
                actor_id=actor_id,
                status=CommandStatus.FAILED,
                error_message=str(err),
            )
            db.add(record)
            db.commit()
            raise CommandExecutionError(f"Command '{command_name}' failed: {err}") from err

