"""
LeadNexus AI X - Phase 47: Stream Signal Deduplicator
Suppresses duplicate signals within a sliding time window using cryptographic signatures.
"""

import hashlib
import json
import time
from typing import Any, Dict


class SignalDeduplicator:
    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._seen_signatures: Dict[str, float] = {}

    def is_duplicate(self, signal: Dict[str, Any]) -> bool:
        """
        Calculates signature from company, signal_type, topic, and key payload attributes.
        Returns True if signal was seen within window_seconds.
        """
        now = time.time()
        self._evict_expired(now)

        sig = self._compute_signature(signal)
        if sig in self._seen_signatures:
            return True

        self._seen_signatures[sig] = now
        return False

    def _compute_signature(self, signal: Dict[str, Any]) -> str:
        company = str(signal.get("company_name", "")).lower().strip()
        sig_type = str(signal.get("signal_type", "")).upper()
        topic = str(signal.get("topic", "")).lower()
        payload = signal.get("payload", {})

        # Extract deterministic key fields from payload
        key_parts = [company, sig_type, topic]
        for k in sorted(payload.keys()):
            v = payload[k]
            if isinstance(v, (str, int, float, bool)):
                key_parts.append(f"{k}:{v}")

        raw = "|".join(key_parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _evict_expired(self, now: float):
        expired = [sig for sig, ts in self._seen_signatures.items() if now - ts > self.window_seconds]
        for sig in expired:
            del self._seen_signatures[sig]

    def clear(self):
        self._seen_signatures.clear()
