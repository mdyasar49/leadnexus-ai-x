"""
LeadNexus AI X — Webhook Replay Attack Defense Guard
Phase 35: Timestamp Drift Verification & Nonce Deduplication
"""

import time
import logging
from typing import Tuple, Set

logger = logging.getLogger("leadnexus.webhooks.replay_defense")


class ReplayDefenseGuard:
    """
    Guards incoming and outgoing webhook verifications against replay attacks
    via strict timestamp drift tolerances and bounded nonce caches.
    """

    def __init__(self, tolerance_seconds: int = 300):
        self.tolerance_seconds = tolerance_seconds
        # In-memory sliding window cache of nonces: (nonce, expiry_epoch)
        self._nonce_cache: dict[str, float] = {}

    def clean_expired_nonces(self, current_time: float | None = None) -> None:
        """Prunes nonces whose validity window has passed."""
        now = current_time or time.time()
        expired = [nonce for nonce, exp in self._nonce_cache.items() if exp < now]
        for nonce in expired:
            del self._nonce_cache[nonce]

    def validate_request(
        self,
        timestamp: int,
        nonce: str,
        current_time: float | None = None,
    ) -> Tuple[bool, str]:
        """
        Validates timestamp freshness and nonce uniqueness.
        Returns (is_valid, reason).
        """
        now = current_time or time.time()
        self.clean_expired_nonces(now)

        # 1. Check timestamp age (cannot be older than tolerance_seconds)
        age = now - timestamp
        if age > self.tolerance_seconds:
            logger.warning(f"Webhook rejected: Timestamp expired. Age={age:.1f}s > {self.tolerance_seconds}s")
            return False, f"Timestamp expired. Delta: {age:.1f}s"

        # 2. Check future timestamp (allow at most 60s clock skew)
        if age < -60:
            logger.warning(f"Webhook rejected: Timestamp in future. Delta={age:.1f}s")
            return False, f"Timestamp is futuristic. Clock skew: {abs(age):.1f}s"

        # 3. Check nonce replay
        if nonce in self._nonce_cache:
            logger.warning(f"Webhook rejected: Nonce {nonce} has already been used (Replay attack detected).")
            return False, "Replay attack detected: Nonce has already been consumed."

        # Register nonce with expiration
        self._nonce_cache[nonce] = now + self.tolerance_seconds
        return True, "Valid"
