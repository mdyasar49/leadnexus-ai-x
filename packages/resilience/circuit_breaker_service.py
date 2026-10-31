"""
LeadNexus AI X - Phase 30: Enterprise Reliability & Resilience
Circuit Breaker Service: Stateful failure thresholds, cooldown timers, and half-open probing.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.resilience import CircuitBreakerState, CircuitState


class CircuitBreakerService:
    """Manages persistent circuit breaker states for external services to prevent cascading failures."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def get_or_create(
        self,
        service_name: str,
        cooldown_seconds: int = 30,
    ) -> CircuitBreakerState:
        cb = self.db.query(CircuitBreakerState).filter(CircuitBreakerState.id == service_name).first()
        if not cb:
            cb = CircuitBreakerState(
                id=service_name,
                state=CircuitState.CLOSED.value,
                consecutive_failures=0,
                cooldown_seconds=cooldown_seconds,
            )
            self.db.add(cb)
            self.db.commit()
            self.db.refresh(cb)
        return cb

    def can_execute(self, service_name: str) -> bool:
        """Determines if calls to service_name are permitted."""
        cb = self.get_or_create(service_name)
        now = datetime.now(timezone.utc)

        if cb.state == CircuitState.CLOSED.value:
            return True

        if cb.state == CircuitState.OPEN.value:
            # Check cooldown expiration
            cooldown = timedelta(seconds=cb.cooldown_seconds)
            if cb.opened_at:
                opened_time = cb.opened_at.replace(tzinfo=timezone.utc if cb.opened_at.tzinfo is None else cb.opened_at.tzinfo)
                if now - opened_time > cooldown:
                    # Transition to HALF_OPEN for trial probe
                    cb.state = CircuitState.HALF_OPEN.value
                    cb.half_opened_at = now
                    self.db.commit()
                    return True
            return False

        # HALF_OPEN: allow trial request
        return True

    def record_success(self, service_name: str) -> CircuitBreakerState:
        cb = self.get_or_create(service_name)
        cb.state = CircuitState.CLOSED.value
        cb.consecutive_failures = 0
        self.db.commit()
        self.db.refresh(cb)
        return cb

    def record_failure(
        self,
        service_name: str,
        failure_threshold: int = 5,
    ) -> CircuitBreakerState:
        cb = self.get_or_create(service_name)
        now = datetime.now(timezone.utc)

        cb.consecutive_failures += 1
        cb.last_failure_at = now

        if cb.state == CircuitState.HALF_OPEN.value or cb.consecutive_failures >= failure_threshold:
            cb.state = CircuitState.OPEN.value
            cb.opened_at = now

        self.db.commit()
        self.db.refresh(cb)
        return cb
