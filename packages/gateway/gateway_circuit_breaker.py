"""
LeadNexus AI X — Phase 37: Gateway Circuit Breaker & Upstream Health Guard
Monitors upstream failure rates, trips to OPEN when failures exceed thresholds,
and transitions to HALF_OPEN probe state for autonomous recovery.
"""

import time
from typing import Dict, Any, Callable, Optional
from app.models.api_gateway import GatewayCircuitStatus


class GatewayCircuitOpenError(Exception):
    """Raised when request is blocked because target service circuit is OPEN."""
    def __init__(self, service_name: str, message: str, fallback_available: bool = True):
        super().__init__(message)
        self.service_name = service_name
        self.fallback_available = fallback_available


class GatewayCircuitBreaker:
    """Manages circuit state transitions and probe testing per upstream service."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = GatewayCircuitStatus.CLOSED
        self.failure_count = 0
        self.consecutive_successes = 0
        self.tripped_at: Optional[float] = None

    def execute(self, upstream_fn: Callable[[], Any], fallback_fn: Optional[Callable[[], Any]] = None) -> Any:
        """Executes upstream call with circuit protection and optional graceful fallback."""
        now = time.time()

        # Check if OPEN circuit should transition to HALF_OPEN probe
        if self.state == GatewayCircuitStatus.OPEN:
            if self.tripped_at and (now - self.tripped_at) >= self.recovery_timeout:
                self.state = GatewayCircuitStatus.HALF_OPEN
                self.consecutive_successes = 0
            else:
                if fallback_fn:
                    return fallback_fn()
                raise GatewayCircuitOpenError(
                    self.service_name,
                    f"Circuit breaker for upstream service '{self.service_name}' is OPEN. Requests blocked.",
                    fallback_available=bool(fallback_fn)
                )

        try:
            result = upstream_fn()
            self._on_success()
            return result
        except Exception as err:
            self._on_failure()
            if fallback_fn:
                return fallback_fn()
            raise err

    def _on_success(self) -> None:
        """Handles successful upstream execution."""
        if self.state == GatewayCircuitStatus.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.success_threshold:
                # Recovered
                self.state = GatewayCircuitStatus.CLOSED
                self.failure_count = 0
                self.tripped_at = None
        else:
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Handles failed upstream execution."""
        self.failure_count += 1
        if self.state == GatewayCircuitStatus.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = GatewayCircuitStatus.OPEN
            self.tripped_at = time.time()
            self.consecutive_successes = 0


# Registry of circuit breakers for system services
_registry: Dict[str, GatewayCircuitBreaker] = {}

def get_circuit_breaker(service_name: str) -> GatewayCircuitBreaker:
    if service_name not in _registry:
        _registry[service_name] = GatewayCircuitBreaker(service_name)
    return _registry[service_name]

