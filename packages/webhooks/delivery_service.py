"""
LeadNexus AI X — Enterprise Webhook Delivery Service
Phase 35: Signed Dispatch, Circuit Breaker Integration, Retry Logic & DLQ Routing
"""

import time
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Callable
from sqlalchemy.orm import Session

from app.models.webhooks import (
    EnterpriseWebhookEndpoint,
    EnterpriseWebhookDelivery,
)
from packages.webhooks.signature_signer import WebhookSignatureSigner
from packages.webhooks.circuit_breaker import WebhookCircuitBreaker, CircuitState
from packages.webhooks.backoff_scheduler import BackoffScheduler

logger = logging.getLogger("leadnexus.webhooks.delivery")


class WebhookDeliveryService:
    """
    Orchestrates secure delivery of outbound webhook events to subscriber endpoints.
    Enforces HMAC-SHA256 signing, circuit breaking, exponential backoff, and DLQ.
    """

    def __init__(
        self,
        circuit_breaker: Optional[WebhookCircuitBreaker] = None,
        backoff_scheduler: Optional[BackoffScheduler] = None,
        http_transport: Optional[Callable[[str, Dict[str, str], str, float], tuple[int, str]]] = None,
    ):
        self.circuit_breaker = circuit_breaker or WebhookCircuitBreaker()
        self.backoff_scheduler = backoff_scheduler or BackoffScheduler()
        # http_transport(url, headers, body, timeout_sec) -> (status_code, response_body)
        self._http_transport = http_transport

    def _default_transport(
        self,
        url: str,
        headers: Dict[str, str],
        body: str,
        timeout: float = 5.0,
    ) -> tuple[int, str]:
        """Default HTTP POST transport using standard library urllib."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.getcode()
                resp_text = response.read().decode("utf-8", errors="replace")
                return status, resp_text
        except urllib.error.HTTPError as e:
            err_text = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
            return e.code, err_text
        except Exception as e:
            logger.error(f"Network error delivering webhook to {url}: {e}")
            return 500, f"Transport Error: {str(e)}"

    def dispatch(
        self,
        db: Session,
        endpoint: EnterpriseWebhookEndpoint,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        attempt_number: int = 1,
        max_retries: int = 5,
        now_epoch: Optional[int] = None,
    ) -> EnterpriseWebhookDelivery:
        """
        Executes a single delivery attempt for a target endpoint.
        """
        epoch = now_epoch if now_epoch is not None else int(time.time())
        now_dt = datetime.now(timezone.utc)

        # 1. Check Circuit Breaker
        can_proceed, breaker_reason = self.circuit_breaker.can_dispatch(endpoint.id)
        if not can_proceed:
            logger.warning(f"Webhook dispatch blocked by circuit breaker for endpoint {endpoint.id}")
            delivery = EnterpriseWebhookDelivery(
                id=str(uuid.uuid4()),
                tenant_id=endpoint.tenant_id,
                endpoint_id=endpoint.id,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                headers={},
                status_code=503,
                execution_duration_ms=0.0,
                status="FAILED",
                attempt_number=attempt_number,
                max_retries=max_retries,
                error_message=breaker_reason,
                created_at=now_dt,
            )
            db.add(delivery)
            db.commit()
            db.refresh(delivery)
            return delivery

        # 2. Build signed headers
        canonical_str = WebhookSignatureSigner.canonicalize_payload(payload)
        signed_headers = WebhookSignatureSigner.generate_signed_headers(
            payload=payload,
            secret=endpoint.secret_token,
            timestamp=epoch,
        )

        # 3. Perform HTTP Call
        transport_fn = self._http_transport or self._default_transport
        start_time = time.perf_counter()
        status_code = 500
        response_text = ""
        error_msg = None

        try:
            status_code, response_text = transport_fn(
                endpoint.url,
                signed_headers,
                canonical_str,
                5.0,
            )
        except Exception as ex:
            status_code = 500
            error_msg = str(ex)

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 4. Evaluate Success vs Failure
        is_success = 200 <= status_code < 300
        if is_success:
            self.circuit_breaker.record_success(endpoint.id)
            endpoint.circuit_status = CircuitState.CLOSED.value
            endpoint.consecutive_failures = 0
            endpoint.last_success_at = now_dt
            delivery_status = "SUCCESS"
            next_retry = None
        else:
            new_circuit_state = self.circuit_breaker.record_failure(endpoint.id)
            endpoint.circuit_status = new_circuit_state.value
            endpoint.consecutive_failures = (endpoint.consecutive_failures or 0) + 1
            endpoint.last_failure_at = now_dt

            if attempt_number >= max_retries:
                delivery_status = "DEAD_LETTER"
                next_retry = None
                error_msg = error_msg or f"Max retries ({max_retries}) exceeded. Routed to Dead-Letter Queue."
            else:
                delivery_status = "RETRYING"
                delay_sec = self.backoff_scheduler.compute_backoff(attempt=attempt_number)
                next_retry = now_dt + timedelta(seconds=delay_sec)
                error_msg = error_msg or f"HTTP {status_code}: {response_text[:200]}"

        # 5. Persist Delivery Row
        delivery = EnterpriseWebhookDelivery(
            id=str(uuid.uuid4()),
            tenant_id=endpoint.tenant_id,
            endpoint_id=endpoint.id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            headers=signed_headers,
            status_code=status_code,
            execution_duration_ms=round(latency_ms, 2),
            status=delivery_status,
            attempt_number=attempt_number,
            max_retries=max_retries,
            next_retry_at=next_retry,
            error_message=error_msg,
            created_at=now_dt,
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        return delivery
