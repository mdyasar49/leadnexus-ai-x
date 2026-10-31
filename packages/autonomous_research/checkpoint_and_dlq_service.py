import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class CheckpointAndDLQService:
    """
    Manages state checkpointing, crash recovery, worker resumption,
    Dead Letter Queue (DLQ) routing, exponential backoff retries,
    and human escalation gates.
    """

    @classmethod
    def create_checkpoint(
        cls,
        run_id: str,
        iteration: int,
        completed_task_ids: List[str],
        pending_task_ids: List[str],
        discovered_entities: List[Dict[str, Any]],
        cost_accrued: float,
        state_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a checkpoint snapshot representing the current state of an autonomous research run.
        """
        return {
            "id": f"chk_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "iteration": iteration,
            "state_snapshot": state_metadata or {},
            "completed_tasks": list(completed_task_ids),
            "pending_tasks": list(pending_task_ids),
            "discovered_entities": list(discovered_entities),
            "cost_accrued": round(cost_accrued, 4),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def restore_from_checkpoint(
        cls,
        checkpoint_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Restores execution state from a checkpoint, recovering completed and pending tasks.
        """
        return {
            "run_id": checkpoint_data["run_id"],
            "resumed_iteration": checkpoint_data["iteration"] + 1,
            "completed_tasks": set(checkpoint_data.get("completed_tasks", [])),
            "pending_tasks": set(checkpoint_data.get("pending_tasks", [])),
            "discovered_entities": checkpoint_data.get("discovered_entities", []),
            "cost_accrued": checkpoint_data.get("cost_accrued", 0.0),
            "state_metadata": checkpoint_data.get("state_snapshot", {}),
        }

    @classmethod
    def calculate_exponential_backoff(
        cls,
        attempt_number: int,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
    ) -> float:
        """Calculates exponential backoff delay in seconds: base * 2^(attempt - 1)."""
        delay = base_delay_seconds * (2 ** max(0, attempt_number - 1))
        return min(max_delay_seconds, round(delay, 2))

    @classmethod
    def route_to_dead_letter_queue(
        cls,
        run_id: str,
        task_id: str,
        failure_reason: str,
        task_payload: Dict[str, Any],
        stack_trace: Optional[str] = None,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Routes an exhausted or unrecoverable failed task to the Research Dead Letter Queue.
        """
        return {
            "id": f"dlq_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "task_id": task_id,
            "failure_reason": failure_reason,
            "payload": task_payload,
            "stack_trace": stack_trace,
            "retry_count": retry_count,
            "resolution_status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def create_human_escalation(
        cls,
        run_id: str,
        escalation_type: str,
        reason: str,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates a human-in-the-loop escalation ticket for high-risk tools,
        ambiguous identity, policy violations, or rate-limit lockouts.
        """
        return {
            "id": f"esc_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "task_id": task_id,
            "escalation_type": escalation_type,
            "reason": reason,
            "status": "OPEN",
            "reviewer_id": None,
            "reviewer_notes": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def resolve_escalation(
        cls,
        escalation_data: Dict[str, Any],
        reviewer_id: str,
        decision: str,  # "APPROVED", "REJECTED", "RESOLVED"
        notes: str,
    ) -> Dict[str, Any]:
        """Resolves an open human escalation."""
        updated = dict(escalation_data)
        updated["status"] = decision.upper()
        updated["reviewer_id"] = reviewer_id
        updated["reviewer_notes"] = notes
        updated["resolved_at"] = datetime.now(timezone.utc).isoformat()
        return updated

