"""
LeadNexus AI X - Phase 43: Mission DAG Scheduler
Validates directed acyclic graph topology, detects cycles, calculates dependency readiness,
and manages execution waves for parallel worker dispatch.
"""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple


class CycleDetectedError(Exception):
    """Raised when a circular dependency is detected in the mission DAG."""
    pass


class DAGStep:
    def __init__(
        self,
        step_id: str,
        name: str,
        agent_type: str,
        dependencies: Optional[List[str]] = None,
        max_retries: int = 3,
        input_payload: Optional[Dict[str, Any]] = None,
        requires_human_review: bool = False,
    ):
        self.step_id = step_id
        self.name = name
        self.agent_type = agent_type
        self.dependencies = dependencies or []
        self.max_retries = max_retries
        self.input_payload = input_payload or {}
        self.requires_human_review = requires_human_review

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "dependencies": self.dependencies,
            "max_retries": self.max_retries,
            "input_payload": self.input_payload,
            "requires_human_review": self.requires_human_review,
        }


class DAGScheduler:
    """Manages DAG validation, topological sorting, and readiness evaluation."""

    @classmethod
    def validate_and_sort(cls, steps: List[DAGStep]) -> List[str]:
        """
        Validates that steps form a valid DAG without cycles or missing dependencies.
        Returns topological ordering of step IDs.
        """
        step_map: Dict[str, DAGStep] = {s.step_id: s for s in steps}
        in_degree: Dict[str, int] = {s.step_id: 0 for s in steps}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        # Build adjacency and check for unknown dependencies
        for step in steps:
            for dep in step.dependencies:
                if dep not in step_map:
                    raise ValueError(f"Step '{step.step_id}' depends on nonexistent step '{dep}'")
                adj_list[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        # Kahn's algorithm for topological sorting
        queue = deque([s_id for s_id, deg in in_degree.items() if deg == 0])
        sorted_order: List[str] = []

        while queue:
            curr = queue.popleft()
            sorted_order.append(curr)
            for neighbor in adj_list[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(steps):
            raise CycleDetectedError("Circular dependency detected in mission task DAG")

        return sorted_order

    @classmethod
    def get_ready_steps(
        cls,
        steps: List[DAGStep],
        step_statuses: Dict[str, str],
    ) -> List[DAGStep]:
        """
        Returns list of steps whose dependencies are all COMPLETED and current status is PENDING or READY.
        """
        ready: List[DAGStep] = []
        for step in steps:
            curr_status = step_statuses.get(step.step_id, "PENDING")
            if curr_status not in ["PENDING", "READY"]:
                continue

            all_deps_satisfied = all(
                step_statuses.get(dep) == "COMPLETED" for dep in step.dependencies
            )
            if all_deps_satisfied:
                ready.append(step)

        return ready

    @classmethod
    def compute_downstream(cls, steps: List[DAGStep], failed_step_id: str) -> Set[str]:
        """Calculates all downstream step IDs affected by a failure."""
        adj_list: Dict[str, List[str]] = defaultdict(list)
        for s in steps:
            for dep in s.dependencies:
                adj_list[dep].append(s.step_id)

        affected: Set[str] = set()
        queue = deque([failed_step_id])
        while queue:
            curr = queue.popleft()
            for child in adj_list[curr]:
                if child not in affected:
                    affected.add(child)
                    queue.append(child)
        return affected
