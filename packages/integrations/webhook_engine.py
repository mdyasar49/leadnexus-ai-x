import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class WebhookVerificationError(ValueError):
    """Raised when an incoming webhook signature or timestamp fails verification."""
    pass


class WebhookEngine:
    """
    Manages inbound and outbound webhook processing, HMAC-SHA256 signature
    generation and verification, timestamp replay defense, and idempotency tracking.
    """

    MAX_TIMESTAMP_DRIFT_SECONDS = 300  # 5 minutes replay protection window

    @classmethod
    def compute_hmac_signature(cls, secret_key: str, payload_bytes: bytes) -> str:
        """Computes HMAC-SHA256 hex digest of the raw payload."""
        return hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    @classmethod
    def verify_inbound_signature(
        cls,
        secret_key: str,
        payload_bytes: bytes,
        provided_signature: str,
    ) -> bool:
        """Validates incoming HMAC-SHA256 signature against expected signature."""
        if not provided_signature or not secret_key:
            return False
        expected_sig = cls.compute_hmac_signature(secret_key, payload_bytes)
        # Support raw hex or sha256= prefix
        clean_provided = provided_signature.replace("sha256=", "").strip()
        return hmac.compare_digest(expected_sig, clean_provided)

    @classmethod
    def verify_timestamp(cls, timestamp_str: str) -> bool:
        """Checks if event timestamp is within acceptable replay drift window."""
        try:
            # Can be unix timestamp int/float or ISO 8601
            if timestamp_str.isdigit() or "." in timestamp_str:
                event_ts = float(timestamp_str)
            else:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                event_ts = dt.timestamp()
            now_ts = time.time()
            return abs(now_ts - event_ts) <= cls.MAX_TIMESTAMP_DRIFT_SECONDS
        except Exception:
            return False

    @classmethod
    def process_inbound_webhook(
        cls,
        workspace_id: str,
        provider: str,
        secret_key: str,
        raw_body: bytes,
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Validates, dedups, and parses an inbound webhook into a standard WebhookEvent.
        """
        # Find signature and timestamp from headers (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}
        signature = (
            headers_lower.get("x-leadnexus-signature")
            or headers_lower.get("x-hub-signature-256")
            or headers_lower.get("x-signature")
            or ""
        )
        timestamp_header = (
            headers_lower.get("x-leadnexus-timestamp")
            or headers_lower.get("x-timestamp")
            or str(int(time.time()))
        )

        # 1. Verify Signature
        if not cls.verify_inbound_signature(secret_key, raw_body, signature):
            raise WebhookVerificationError("Webhook HMAC signature verification failed.")

        # 2. Verify Timestamp / Replay Attack Prevention
        if not cls.verify_timestamp(timestamp_header):
            raise WebhookVerificationError("Webhook timestamp is expired or outside replay window.")

        # 3. Compute Payload Hash
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # Parse JSON
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload = {"raw": raw_body.decode("utf-8", errors="ignore")}

        event_type = (
            headers_lower.get("x-leadnexus-event")
            or headers_lower.get("x-github-event")
            or payload.get("event_type")
            or "GENERIC_EVENT"
        )

        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        return {
            "id": event_id,
            "workspace_id": workspace_id,
            "provider": provider,
            "event_type": event_type,
            "payload": payload,
            "payload_hash": payload_hash,
            "signature_verified": True,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def prepare_outbound_delivery(
        cls,
        secret_key: str,
        event_type: str,
        event_id: str,
        payload: Dict[str, Any],
    ) -> Tuple[Dict[str, str], bytes]:
        """
        Signs and formats headers and payload for outbound webhook dispatch.
        """
        raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        timestamp_str = str(int(time.time()))
        signature = cls.compute_hmac_signature(secret_key, raw_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-LeadNexus-Event": event_type,
            "X-LeadNexus-Event-ID": event_id,
            "X-LeadNexus-Timestamp": timestamp_str,
            "X-LeadNexus-Signature": f"sha256={signature}",
            "User-Agent": "LeadNexus-AI-X-Webhook-Engine/1.0",
        }
        return headers, raw_bytes

