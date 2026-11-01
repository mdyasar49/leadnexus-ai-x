"""
LeadNexus AI X - Phase 45: Remediation Safety Guard & Blast Radius Limiter
Enforces safety boundaries, action cooldowns, hourly execution quotas,
and blast radius limits to prevent remediation cascading failures.
"""

from collections import defaultdict
import time
from typing import Dict, List, Optional, Tuple


class SafetyViolationError(Exception):
    """Raised when a remediation action breaches safety boundaries or cooldowns."""
    pass


class RemediationSafetyGuard:
    """Guards platform stability during automated remediation operations."""

    def __init__(
        self,
        default_cooldown_seconds: int = 300,
        default_max_per_hour: int = 5,
        max_blast_radius_fraction: float = 0.25,
    ):
        self.default_cooldown_seconds = default_cooldown_seconds
        self.default_max_per_hour = default_max_per_hour
        self.max_blast_radius_fraction = max_blast_radius_fraction

        # subsystem -> last execution timestamp
        self._last_execution: Dict[str, float] = {}
        # subsystem -> list of execution timestamps in past hour
        self._hourly_executions: Dict[str, List[float]] = defaultdict(list)
        # incident_id -> consecutive failure count
        self._consecutive_failures: Dict[str, int] = defaultdict(int)

    def check_safety(
        self,
        subsystem: str,
        action_type: str,
        cooldown_seconds: Optional[int] = None,
        max_per_hour: Optional[int] = None,
        affected_fraction: float = 0.1,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether an automated remediation action can safely proceed.
        Returns (is_allowed, error_reason).
        """
        now = time.time()
        cd = cooldown_seconds if cooldown_seconds is not None else self.default_cooldown_seconds
        mph = max_per_hour if max_per_hour is not None else self.default_max_per_hour

        # 1. Cooldown check
        last_time = self._last_execution.get(subsystem, 0.0)
        elapsed = now - last_time
        if elapsed < cd:
            return False, f"Cooldown active for '{subsystem}'. {int(cd - elapsed)}s remaining."

        # 2. Hourly rate limit check
        history = [t for t in self._hourly_executions[subsystem] if now - t <= 3600.0]
        self._hourly_executions[subsystem] = history
        if len(history) >= mph:
            return False, f"Hourly remediation quota ({mph}/hr) exceeded for '{subsystem}'."

        # 3. Blast radius check
        if affected_fraction > self.max_blast_radius_fraction:
            return False, f"Blast radius {affected_fraction:.1%} exceeds safety cap {self.max_blast_radius_fraction:.1%}."

        return True, None

    def record_execution(self, subsystem: str) -> None:
        """Records an authorized execution timestamp."""
        now = time.time()
        self._last_execution[subsystem] = now
        self._hourly_executions[subsystem].append(now)

    def record_outcome(self, incident_id: str, success: bool) -> bool:
        """
        Tracks consecutive failures. If failures >= 3, indicates need for human escalation.
        Returns should_escalate.
        """
        if success:
            self._consecutive_failures[incident_id] = 0
            return False
        else:
            self._consecutive_failures[incident_id] += 1
            return self._consecutive_failures[incident_id] >= 3
