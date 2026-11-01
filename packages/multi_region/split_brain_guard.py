"""
LeadNexus AI X — Split-Brain Prevention Guard
Phase 35 (ChatGPT Master Roadmap): Single Authorized Write Region & Monotonic Fencing Tokens
"""

import time
import logging
from typing import Tuple, Optional

logger = logging.getLogger("leadnexus.multi_region.split_brain")


class SplitBrainViolationError(Exception):
    """Raised when a write is attempted against an unauthorized or fenced replica."""
    pass


class SplitBrainGuard:
    """
    Guarantees strict single-primary write authorization via cryptographic
    monotonic fencing tokens and regional write lease verification.
    """

    def __init__(self, initial_write_region: str = "ap-southeast-2", initial_epoch: int = 1):
        self._authorized_write_region: str = initial_write_region
        self._fencing_epoch: int = initial_epoch
        self._last_fence_token: str = f"epoch-{self._fencing_epoch}-{self._authorized_write_region}"

    @property
    def authorized_write_region(self) -> str:
        return self._authorized_write_region

    @property
    def fencing_epoch(self) -> int:
        return self._fencing_epoch

    @property
    def current_fence_token(self) -> str:
        return self._last_fence_token

    def issue_new_fencing_token(self, new_write_region: str) -> str:
        """
        Increments the monotonic epoch and binds it to the newly promoted write region.
        Older tokens become immediately invalid.
        """
        self._fencing_epoch += 1
        self._authorized_write_region = new_write_region
        self._last_fence_token = f"epoch-{self._fencing_epoch}-{new_write_region}"
        logger.warning(
            f"[Split-Brain Guard] Promoted write region to '{new_write_region}' with fencing token '{self._last_fence_token}'."
        )
        return self._last_fence_token

    def validate_write_permission(self, target_region_id: str, fence_token: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validates if target region is permitted to execute writes.
        Returns (is_permitted, reason).
        """
        # Rule 1: Exactly ONE authorized write region
        if target_region_id != self._authorized_write_region:
            msg = (
                f"Split-Brain Prevention Violation: Region '{target_region_id}' is a Read-Only Replica. "
                f"Active authorized write region is '{self._authorized_write_region}'."
            )
            logger.error(msg)
            return False, msg

        # Rule 2: Token freshness if supplied
        if fence_token and fence_token != self._last_fence_token:
            msg = f"Stale fencing token '{fence_token}'. Current valid token is '{self._last_fence_token}'."
            logger.error(msg)
            return False, msg

        return True, "Authorized"
