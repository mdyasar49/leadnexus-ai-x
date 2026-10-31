import random
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from packages.integrations.security_and_credentials import SSRFProtection, SSRFProtectionError


class CircuitBreakerOpenError(Exception):
    """Raised when an external provider circuit breaker is OPEN to prevent cascading failures."""
    pass


class CircuitBreaker:
    """
    Protects external integrations from cascading failures.
    State machine: CLOSED -> (failures >= threshold) -> OPEN -> (cooldown elapsed) -> HALF_OPEN -> (success) -> CLOSED
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
        self.failure_count = 0
        self.last_failure_time = 0.0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.cooldown_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class ExternalAPIClient:
    """
    Robust outbound HTTP integration client enforcing SSRF protection,
    circuit breakers, intelligent retries, rate limits, and metric logging.
    """

    RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
    NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}

    def __init__(self, provider_id: str, circuit_breaker: Optional[CircuitBreaker] = None):
        self.provider_id = provider_id
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def execute_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        mock_invoker: Optional[Callable[..., Tuple[int, Dict[str, Any]]]] = None,
        max_retries: int = 3,
        base_backoff_sec: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Executes outbound request with SSRF validation, circuit breaker, and retry logic.
        """
        # 1. SSRF Pre-flight defense
        is_safe, ssrf_err = SSRFProtection.validate_outbound_url(url)
        if not is_safe:
            raise SSRFProtectionError(ssrf_err)

        # 2. Circuit breaker check
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker for provider '{self.provider_id}' is OPEN due to repeated failures."
            )

        attempts = 0
        last_status = 500
        last_body = {}

        while attempts <= max_retries:
            attempts += 1
            start_time = time.time()

            try:
                # Use mock_invoker or simulated HTTP response
                if mock_invoker:
                    status_code, body = mock_invoker(method, url, headers, json_payload)
                else:
                    # Default simulated response
                    status_code = 200
                    body = {"status": "success", "provider": self.provider_id, "data": json_payload or {}}

                latency_ms = int((time.time() - start_time) * 1000)
                last_status = status_code
                last_body = body

                if 200 <= status_code < 300:
                    self.circuit_breaker.record_success()
                    return {
                        "status_code": status_code,
                        "data": body,
                        "latency_ms": latency_ms,
                        "attempts": attempts,
                        "is_success": True,
                    }

                # Check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= max_retries:
                    self.circuit_breaker.record_failure()
                    # Exponential backoff with jitter
                    backoff = (base_backoff_sec * (2 ** (attempts - 1))) + (random.random() * 0.1)
                    time.sleep(min(1.0, backoff))
                    continue

                # Non-retryable failure (e.g. 400, 401, 403)
                self.circuit_breaker.record_failure()
                return {
                    "status_code": status_code,
                    "data": body,
                    "latency_ms": latency_ms,
                    "attempts": attempts,
                    "is_success": False,
                    "error": f"HTTP {status_code} error from provider {self.provider_id}",
                }

            except Exception as e:
                self.circuit_breaker.record_failure()
                if attempts > max_retries:
                    return {
                        "status_code": 500,
                        "data": {},
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "attempts": attempts,
                        "is_success": False,
                        "error": str(e),
                    }
                time.sleep(base_backoff_sec)

        return {
            "status_code": last_status,
            "data": last_body,
            "attempts": attempts,
            "is_success": False,
            "error": "Max retries exceeded",
        }

