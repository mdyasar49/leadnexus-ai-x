"""
LeadNexus AI X - Phase 43: Autonomous Mission Engine
Coordinates multi-step research missions, DAG resolution, prioritized worker dispatch,
automated state checkpointing, retries with backoff, and human-in-the-loop review checkpoints.
"""

from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from packages.orchestration.dag_scheduler import DAGScheduler, DAGStep, CycleDetectedError
from packages.orchestration.checkpoint_manager import CheckpointManager, MissionStateSnapshot
from packages.orchestration.worker_pool import WorkerPool, TaskPriority


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    AWAITING_REVIEW = "AWAITING_REVIEW"


class MissionInstance:
    """In-memory active execution instance of an autonomous mission."""

    def __init__(
        self,
        mission_id: str,
        name: str,
        goal: str,
        steps: List[DAGStep],
        priority: TaskPriority = TaskPriority.NORMAL,
        configuration: Optional[Dict[str, Any]] = None,
    ):
        self.mission_id = mission_id
        self.name = name
        self.goal = goal
        self.steps = steps
        self.step_map = {s.step_id: s for s in steps}
        self.priority = priority
        self.configuration = configuration or {}
        self.status = MissionStatus.CREATED
        self.step_statuses: Dict[str, StepStatus] = {s.step_id: StepStatus.PENDING for s in steps}
        self.step_outputs: Dict[str, Any] = {}
        self.step_retries: Dict[str, int] = {s.step_id: 0 for s in steps}
        self.context_variables: Dict[str, Any] = {}
        self.pending_human_reviews: Dict[str, Dict[str, Any]] = {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

        # Validate DAG upfront
        DAGScheduler.validate_and_sort(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "name": self.name,
            "goal": self.goal,
            "status": self.status.value,
            "priority": self.priority.value,
            "step_count": len(self.steps),
            "step_statuses": {k: v.value for k, v in self.step_statuses.items()},
            "completed_count": sum(1 for v in self.step_statuses.values() if v == StepStatus.COMPLETED),
            "failed_count": sum(1 for v in self.step_statuses.values() if v == StepStatus.FAILED),
            "pending_review_count": len(self.pending_human_reviews),
            "context_variables": self.context_variables,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class MissionEngine:
    """Core autonomous orchestration engine managing mission lifecycles and DAG execution."""

    def __init__(self, max_concurrency: int = 4):
        self.worker_pool = WorkerPool(max_concurrency=max_concurrency)
        self.checkpoint_manager = CheckpointManager()
        self.active_missions: Dict[str, MissionInstance] = {}

    def create_mission(
        self,
        name: str,
        goal: str,
        steps: List[DAGStep],
        priority: TaskPriority = TaskPriority.NORMAL,
        configuration: Optional[Dict[str, Any]] = None,
        mission_id: Optional[str] = None,
    ) -> MissionInstance:
        """Instantiates and registers a new mission."""
        m_id = mission_id or str(uuid.uuid4())
        instance = MissionInstance(
            mission_id=m_id,
            name=name,
            goal=goal,
            steps=steps,
            priority=priority,
            configuration=configuration,
        )
        self.active_missions[m_id] = instance
        # Initial snapshot
        self.checkpoint_manager.save_checkpoint(
            mission_id=m_id,
            status=instance.status.value,
            step_statuses={k: v.value for k, v in instance.step_statuses.items()},
            step_outputs={},
            context_variables={},
            reason="INITIAL_CREATION",
        )
        return instance

    def start_mission(self, mission_id: str) -> MissionInstance:
        """Transitions mission to RUNNING and advances initial ready steps."""
        mission = self._get_mission(mission_id)
        if mission.status in [MissionStatus.COMPLETED, MissionStatus.CANCELLED]:
            raise ValueError(f"Cannot start mission in terminal status {mission.status.value}")

        mission.status = MissionStatus.RUNNING
        mission.updated_at = datetime.now(timezone.utc)
        self.advance_mission(mission_id)
        return mission

    def pause_mission(self, mission_id: str) -> MissionInstance:
        """Pauses execution and snapshots state for safe resumption."""
        mission = self._get_mission(mission_id)
        if mission.status == MissionStatus.RUNNING:
            mission.status = MissionStatus.PAUSED
            mission.updated_at = datetime.now(timezone.utc)
            self.checkpoint_manager.save_checkpoint(
                mission_id=mission_id,
                status=mission.status.value,
                step_statuses={k: v.value for k, v in mission.step_statuses.items()},
                step_outputs=mission.step_outputs,
                context_variables=mission.context_variables,
                reason="PAUSE_REQUESTED",
            )
        return mission

    def resume_mission(self, mission_id: str) -> MissionInstance:
        """Resumes a paused mission."""
        mission = self._get_mission(mission_id)
        if mission.status == MissionStatus.PAUSED:
            mission.status = MissionStatus.RUNNING
            mission.updated_at = datetime.now(timezone.utc)
            self.advance_mission(mission_id)
        return mission

    def cancel_mission(self, mission_id: str) -> MissionInstance:
        """Cancels an active or paused mission."""
        mission = self._get_mission(mission_id)
        mission.status = MissionStatus.CANCELLED
        mission.updated_at = datetime.now(timezone.utc)
        self.checkpoint_manager.save_checkpoint(
            mission_id=mission_id,
            status=mission.status.value,
            step_statuses={k: v.value for k, v in mission.step_statuses.items()},
            step_outputs=mission.step_outputs,
            context_variables=mission.context_variables,
            reason="CANCELLED_BY_OPERATOR",
        )
        return mission

    def advance_mission(self, mission_id: str) -> Dict[str, Any]:
        """
        Evaluates DAG dependencies, resolves ready tasks, and enqueues them for worker execution.
        If a ready step requires human review, pauses on AWAITING_HUMAN_REVIEW.
        """
        mission = self._get_mission(mission_id)
        if mission.status != MissionStatus.RUNNING:
            return {"status": mission.status.value, "dispatched_steps": []}

        ready_steps = DAGScheduler.get_ready_steps(
            steps=mission.steps,
            step_statuses={k: v.value for k, v in mission.step_statuses.items()},
        )

        dispatched: List[str] = []

        for step in ready_steps:
            if step.requires_human_review:
                # Pause at human checkpoint
                mission.step_statuses[step.step_id] = StepStatus.AWAITING_REVIEW
                review_id = str(uuid.uuid4())
                mission.pending_human_reviews[step.step_id] = {
                    "review_id": review_id,
                    "step_id": step.step_id,
                    "title": f"Review Required: {step.name}",
                    "candidate_data": step.input_payload,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                mission.status = MissionStatus.AWAITING_HUMAN_REVIEW
                break

            # Enqueue to worker pool
            mission.step_statuses[step.step_id] = StepStatus.READY
            self.worker_pool.enqueue(
                step_id=step.step_id,
                mission_id=mission.mission_id,
                agent_type=step.agent_type,
                payload=step.input_payload,
                priority=mission.priority,
            )
            dispatched.append(step.step_id)

        # Process available worker slots
        self._dispatch_workers(mission)

        # Check if entire mission has completed or failed
        self._check_mission_completion(mission)

        return {
            "status": mission.status.value,
            "dispatched_steps": dispatched,
            "ready_count": len(ready_steps),
        }

    def complete_step(
        self,
        mission_id: str,
        step_id: str,
        output_payload: Optional[Dict[str, Any]] = None,
    ) -> MissionInstance:
        """Marks a step as COMPLETED, records outputs, and advances downstream DAG nodes."""
        mission = self._get_mission(mission_id)
        mission.step_statuses[step_id] = StepStatus.COMPLETED
        mission.step_outputs[step_id] = output_payload or {}
        if output_payload:
            mission.context_variables.update(output_payload)

        # Snapshot step completion
        self.checkpoint_manager.save_checkpoint(
            mission_id=mission_id,
            status=mission.status.value,
            step_statuses={k: v.value for k, v in mission.step_statuses.items()},
            step_outputs=mission.step_outputs,
            context_variables=mission.context_variables,
            reason=f"STEP_{step_id}_COMPLETED",
        )

        if mission.status == MissionStatus.RUNNING:
            self.advance_mission(mission_id)

        return mission

    def fail_step(
        self,
        mission_id: str,
        step_id: str,
        error_message: str,
    ) -> MissionInstance:
        """Handles step failure with automatic retry up to max_retries or blocks downstream nodes."""
        mission = self._get_mission(mission_id)
        step = mission.step_map.get(step_id)
        max_retries = step.max_retries if step else 3
        curr_retries = mission.step_retries.get(step_id, 0)

        if curr_retries < max_retries:
            mission.step_retries[step_id] = curr_retries + 1
            mission.step_statuses[step_id] = StepStatus.READY
            # Re-enqueue with retry
            self.worker_pool.enqueue(
                step_id=step_id,
                mission_id=mission_id,
                agent_type=step.agent_type if step else "UnknownAgent",
                payload={"retry_count": curr_retries + 1, "last_error": error_message},
                priority=mission.priority,
            )
        else:
            mission.step_statuses[step_id] = StepStatus.FAILED
            # Block downstream dependencies
            downstream = DAGScheduler.compute_downstream(mission.steps, step_id)
            for d_id in downstream:
                mission.step_statuses[d_id] = StepStatus.BLOCKED

            # Check if mission should fail
            self._check_mission_completion(mission)

        return mission

    def submit_human_decision(
        self,
        mission_id: str,
        step_id: str,
        decision: str,  # APPROVED, REJECTED, MODIFIED
        modified_data: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> MissionInstance:
        """Resolves a human review checkpoint and unblocks execution."""
        mission = self._get_mission(mission_id)
        if step_id not in mission.pending_human_reviews:
            raise ValueError(f"No pending review for step {step_id}")

        del mission.pending_human_reviews[step_id]

        if decision == "APPROVED":
            mission.step_statuses[step_id] = StepStatus.COMPLETED
            if modified_data:
                mission.step_outputs[step_id] = modified_data
        elif decision == "REJECTED":
            mission.step_statuses[step_id] = StepStatus.FAILED
            downstream = DAGScheduler.compute_downstream(mission.steps, step_id)
            for d_id in downstream:
                mission.step_statuses[d_id] = StepStatus.BLOCKED
        elif decision == "MODIFIED":
            mission.step_statuses[step_id] = StepStatus.COMPLETED
            mission.step_outputs[step_id] = modified_data or {}
            if modified_data:
                mission.context_variables.update(modified_data)

        # If no other human reviews pending, resume mission
        if not mission.pending_human_reviews and mission.status == MissionStatus.AWAITING_HUMAN_REVIEW:
            mission.status = MissionStatus.RUNNING
            self.advance_mission(mission_id)

        return mission

    def rollback_to_checkpoint(self, mission_id: str, checkpoint_id: str) -> MissionInstance:
        """Restores mission DAG to state captured in a historical checkpoint."""
        mission = self._get_mission(mission_id)
        snapshot = self.checkpoint_manager.restore_from_checkpoint(mission_id, checkpoint_id)
        if not snapshot:
            raise ValueError(f"Checkpoint {checkpoint_id} not found for mission {mission_id}")

        mission.step_statuses = {k: StepStatus(v) for k, v in snapshot.step_statuses.items()}
        mission.step_outputs = dict(snapshot.step_outputs)
        mission.context_variables = dict(snapshot.context_variables)
        mission.status = MissionStatus(snapshot.status)
        mission.updated_at = datetime.now(timezone.utc)
        return mission

    def _dispatch_workers(self, mission: MissionInstance) -> None:
        while True:
            dispatch_pair = self.worker_pool.poll_and_dispatch()
            if not dispatch_pair:
                break
            worker_id, task = dispatch_pair
            mission.step_statuses[task.step_id] = StepStatus.RUNNING

    def _check_mission_completion(self, mission: MissionInstance) -> None:
        statuses = set(mission.step_statuses.values())
        if all(s == StepStatus.COMPLETED for s in mission.step_statuses.values()):
            mission.status = MissionStatus.COMPLETED
            mission.updated_at = datetime.now(timezone.utc)
        elif StepStatus.FAILED in statuses and not any(s in [StepStatus.RUNNING, StepStatus.READY, StepStatus.PENDING] for s in statuses):
            mission.status = MissionStatus.FAILED
            mission.updated_at = datetime.now(timezone.utc)

    def _get_mission(self, mission_id: str) -> MissionInstance:
        if mission_id not in self.active_missions:
            raise ValueError(f"Mission '{mission_id}' not found")
        return self.active_missions[mission_id]
