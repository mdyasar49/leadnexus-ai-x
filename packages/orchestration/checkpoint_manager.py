"""
LeadNexus AI X - Phase 43: Mission Checkpoint & Snapshot Manager
Serializes and restores mission execution state, task variables, step histories,
and worker allocations to support node restarts and zero-loss resume.
"""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid


class MissionStateSnapshot:
    def __init__(
        self,
        mission_id: str,
        checkpoint_number: int,
        status: str,
        step_statuses: Dict[str, str],
        step_outputs: Dict[str, Any],
        context_variables: Dict[str, Any],
        reason: str = "STEP_COMPLETION",
        checkpoint_id: Optional[str] = None,
    ):
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())
        self.mission_id = mission_id
        self.checkpoint_number = checkpoint_number
        self.status = status
        self.step_statuses = step_statuses
        self.step_outputs = step_outputs
        self.context_variables = context_variables
        self.reason = reason
        self.created_at = datetime.now(timezone.utc).isoformat()

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "mission_id": self.mission_id,
                "checkpoint_number": self.checkpoint_number,
                "step_statuses": self.step_statuses,
                "context_variables": self.context_variables,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "mission_id": self.mission_id,
            "checkpoint_number": self.checkpoint_number,
            "status": self.status,
            "step_statuses": self.step_statuses,
            "step_outputs": self.step_outputs,
            "context_variables": self.context_variables,
            "reason": self.reason,
            "state_hash": self.compute_hash(),
            "created_at": self.created_at,
        }


class CheckpointManager:
    """Manages creation, storage, and state restoration of mission snapshots."""

    def __init__(self):
        self._checkpoints: Dict[str, List[MissionStateSnapshot]] = {}

    def save_checkpoint(
        self,
        mission_id: str,
        status: str,
        step_statuses: Dict[str, str],
        step_outputs: Dict[str, Any],
        context_variables: Dict[str, Any],
        reason: str = "STEP_COMPLETION",
    ) -> MissionStateSnapshot:
        """Creates and stores a sequential checkpoint for the given mission."""
        history = self._checkpoints.setdefault(mission_id, [])
        checkpoint_num = len(history) + 1

        snapshot = MissionStateSnapshot(
            mission_id=mission_id,
            checkpoint_number=checkpoint_num,
            status=status,
            step_statuses=dict(step_statuses),
            step_outputs=dict(step_outputs),
            context_variables=dict(context_variables),
            reason=reason,
        )
        history.append(snapshot)
        return snapshot

    def get_latest(self, mission_id: str) -> Optional[MissionStateSnapshot]:
        history = self._checkpoints.get(mission_id, [])
        return history[-1] if history else None

    def get_history(self, mission_id: str) -> List[MissionStateSnapshot]:
        return list(self._checkpoints.get(mission_id, []))

    def restore_from_checkpoint(
        self,
        mission_id: str,
        checkpoint_id: str,
    ) -> Optional[MissionStateSnapshot]:
        """Finds a specific checkpoint to restore execution state."""
        history = self._checkpoints.get(mission_id, [])
        for chk in history:
            if chk.checkpoint_id == checkpoint_id:
                return chk
        return None

