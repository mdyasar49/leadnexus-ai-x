"""
LeadNexus AI X — Enterprise Webhook Cryptographic Signature Signer & Verifier
Phase 35: HMAC-SHA256 Signing, Constant-Time Comparison, Tamper Prevention
"""

import hmac
import hashlib
import secrets
import json
from typing import Dict, Any, Tuple


class WebhookSignatureSigner:
    """
    Enterprise-grade HMAC-SHA256 Webhook Signer and Verifier.
    Implements standard signature specification:
    Signed Message: "t={timestamp},n={nonce},p={canonical_payload}"
    Header format:
      X-LeadNexus-Signature-256: v1={hex_digest}
      X-LeadNexus-Timestamp: {epoch_seconds}
      X-LeadNexus-Nonce: {random_hex_16}
    """

    HEADER_SIGNATURE = "X-LeadNexus-Signature-256"
    HEADER_TIMESTAMP = "X-LeadNexus-Timestamp"
    HEADER_NONCE = "X-LeadNexus-Nonce"

    @staticmethod
    def generate_secret_token(prefix: str = "whsec_") -> str:
        """Generates a cryptographically secure 256-bit secret token."""
        return f"{prefix}{secrets.token_hex(32)}"

    @staticmethod
    def canonicalize_payload(payload: Any) -> str:
        """Serializes payload into deterministic canonical JSON string."""
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def compute_signature(
        cls,
        payload_str: str,
        secret: str,
        timestamp: int,
        nonce: str,
    ) -> str:
        """
        Computes HMAC-SHA256 hex digest over:
        t={timestamp},n={nonce},p={payload_str}
        """
        sign_bytes = f"t={timestamp},n={nonce},p={payload_str}".encode("utf-8")
        secret_bytes = secret.encode("utf-8")
        return hmac.new(secret_bytes, sign_bytes, hashlib.sha256).hexdigest()

    @classmethod
    def generate_signed_headers(
        cls,
        payload: Any,
        secret: str,
        timestamp: int,
        nonce: str | None = None,
    ) -> Dict[str, str]:
        """
        Builds complete tamper-evident headers for outgoing webhook requests.
        """
        if nonce is None:
            nonce = secrets.token_hex(16)
        
        canonical_str = cls.canonicalize_payload(payload)
        digest = cls.compute_signature(canonical_str, secret, timestamp, nonce)

        return {
            "Content-Type": "application/json",
            cls.HEADER_SIGNATURE: f"v1={digest}",
            cls.HEADER_TIMESTAMP: str(timestamp),
            cls.HEADER_NONCE: nonce,
        }

    @classmethod
    def verify_signature(
        cls,
        payload_str: str,
        secret: str,
        signature_header: str,
        timestamp: int,
        nonce: str,
    ) -> bool:
        """
        Verifies received webhook signature using constant-time digest comparison.
        """
        if not signature_header or not secret:
            return False

        # Parse signature header (format: v1=...)
        expected_prefix = "v1="
        if not signature_header.startswith(expected_prefix):
            return False
        
        provided_digest = signature_header[len(expected_prefix):]
        computed_digest = cls.compute_signature(payload_str, secret, timestamp, nonce)

        return hmac.compare_digest(provided_digest, computed_digest)
