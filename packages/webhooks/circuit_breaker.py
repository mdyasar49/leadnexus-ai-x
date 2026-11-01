"""
LeadNexus AI X — Webhook Circuit Breaker Engine
Phase 35: Endpoint Health Protection, Fail-Fast Throttling & Half-Open Probing
"""

import time
import logging
from enum import Enum
from typing import Dict, Tuple

logger = logging.getLogger("leadnexus.webhooks.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class WebhookCircuitBreaker:
    """
    Per-endpoint circuit breaker protecting target infrastructure from
    cascading failures and thread pool starvation.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        # Maps endpoint_id -> dict(state, consecutive_failures, opened_at, half_open_probe_in_flight)
        self._registry: Dict[str, dict] = {}

    def get_state(self, endpoint_id: str, current_time: float | None = None) -> CircuitState:
        """Computes current circuit state considering recovery timeout."""
        now = current_time or time.time()
        info = self._registry.get(endpoint_id)
        if not info:
            return CircuitState.CLOSED

        state = info.get("state", CircuitState.CLOSED)
        if state == CircuitState.OPEN:
            opened_at = info.get("opened_at", 0)
            if (now - opened_at) >= self.recovery_timeout_seconds:
                info["state"] = CircuitState.HALF_OPEN
                logger.info(f"Circuit for endpoint '{endpoint_id}' shifted to HALF_OPEN probe state.")
                return CircuitState.HALF_OPEN

        return state

    def can_dispatch(self, endpoint_id: str, current_time: float | None = None) -> Tuple[bool, str]:
        """Returns True if delivery can proceed, False if circuit is OPEN."""
        state = self.get_state(endpoint_id, current_time)
        if state == CircuitState.OPEN:
            return False, "Circuit breaker is OPEN (Fail-Fast: Destination experiencing high error rate)."
        return True, "Permitted"

    def record_success(self, endpoint_id: str) -> None:
        """Records successful dispatch, resetting circuit to CLOSED."""
        info = self._registry.setdefault(endpoint_id, {})
        info["state"] = CircuitState.CLOSED
        info["consecutive_failures"] = 0
        info["opened_at"] = None
        logger.info(f"Circuit for endpoint '{endpoint_id}' is CLOSED (Healthy).")

    def record_failure(self, endpoint_id: str, current_time: float | None = None) -> CircuitState:
        """Records delivery failure, potentially tripping circuit to OPEN."""
        now = current_time or time.time()
        info = self._registry.setdefault(endpoint_id, {
            "state": CircuitState.CLOSED,
            "consecutive_failures": 0,
            "opened_at": None,
        })

        info["consecutive_failures"] = info.get("consecutive_failures", 0) + 1
        current_state = info.get("state", CircuitState.CLOSED)

        if current_state == CircuitState.HALF_OPEN:
            info["state"] = CircuitState.OPEN
            info["opened_at"] = now
            logger.warning(f"HALF_OPEN probe failed. Circuit for '{endpoint_id}' tripped back to OPEN.")
        elif info["consecutive_failures"] >= self.failure_threshold:
            info["state"] = CircuitState.OPEN
            info["opened_at"] = now
            logger.warning(f"Circuit for '{endpoint_id}' tripped to OPEN after {info['consecutive_failures']} consecutive failures.")

        return info["state"]
