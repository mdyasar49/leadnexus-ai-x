"""
LeadNexus AI X - Phase 43: Priority Worker Pool & Task Dispatcher
Controls concurrency limits, prioritized queuing, worker thread assignment,
and task execution dispatch across autonomous research agents.
"""

from enum import Enum
import heapq
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid


class TaskPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


PRIORITY_WEIGHTS = {
    TaskPriority.CRITICAL: 1,
    TaskPriority.HIGH: 2,
    TaskPriority.NORMAL: 3,
    TaskPriority.LOW: 4,
}


class QueuedTask:
    def __init__(
        self,
        task_id: str,
        step_id: str,
        mission_id: str,
        agent_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
    ):
        self.task_id = task_id
        self.step_id = step_id
        self.mission_id = mission_id
        self.agent_type = agent_type
        self.payload = payload
        self.priority = priority
        self.weight = PRIORITY_WEIGHTS.get(priority, 3)
        self.created_at = time.time()

    def __lt__(self, other: "QueuedTask") -> bool:
        if self.weight != other.weight:
            return self.weight < other.weight
        return self.created_at < other.created_at


class WorkerPool:
    """Manages concurrent worker slots and priority-ordered task queue."""

    def __init__(self, max_concurrency: int = 4):
        self.max_concurrency = max_concurrency
        self._queue: List[QueuedTask] = []
        self._active_workers: Dict[str, QueuedTask] = {}  # worker_id -> QueuedTask
        self._completed_tasks: Dict[str, Dict[str, Any]] = {}

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def active_worker_count(self) -> int:
        return len(self._active_workers)

    @property
    def available_slots(self) -> int:
        return max(0, self.max_concurrency - len(self._active_workers))

    def enqueue(
        self,
        step_id: str,
        mission_id: str,
        agent_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Enqueues a task ordered by priority weight and submission timestamp."""
        task_id = str(uuid.uuid4())
        item = QueuedTask(
            task_id=task_id,
            step_id=step_id,
            mission_id=mission_id,
            agent_type=agent_type,
            payload=payload or {},
            priority=priority,
        )
        heapq.heappush(self._queue, item)
        return task_id

    def poll_and_dispatch(self) -> Optional[Tuple[str, QueuedTask]]:
        """
        Dispatches the next highest-priority task if worker slots are available.
        Returns (worker_id, QueuedTask) or None.
        """
        if not self._queue or self.available_slots <= 0:
            return None

        task = heapq.heappop(self._queue)
        worker_id = f"worker-slot-{len(self._active_workers) + 1}-{uuid.uuid4().hex[:6]}"
        self._active_workers[worker_id] = task
        return worker_id, task

    def complete_task(
        self,
        worker_id: str,
        status: str,
        output_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[QueuedTask]:
        """Frees the worker slot and records completion status."""
        task = self._active_workers.pop(worker_id, None)
        if task:
            self._completed_tasks[task.task_id] = {
                "step_id": task.step_id,
                "mission_id": task.mission_id,
                "status": status,
                "output_payload": output_payload or {},
                "error_message": error_message,
                "completed_at": time.time(),
            }
        return task
