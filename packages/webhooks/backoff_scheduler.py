"""
LeadNexus AI X — Exponential Backoff & Jitter Scheduler
Phase 35: Retry Timing Calculation with Full Jitter
"""

import random
from typing import Optional


class BackoffScheduler:
    """
    Computes retry intervals using exponential backoff with full jitter
    to prevent thundering herd spikes against downstream webhook destinations.
    """

    def __init__(
        self,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 300.0,
        exponential_factor: float = 2.0,
    ):
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.exponential_factor = exponential_factor

    def compute_backoff(
        self,
        attempt: int,
        apply_jitter: bool = True,
        seed: Optional[int] = None,
    ) -> float:
        """
        Calculates retry delay for the given attempt index (1-based).
        delay = min(max_delay, base_delay * (factor ** (attempt - 1)))
        if apply_jitter: return uniform(0.5 * delay, delay)
        """
        if attempt < 1:
            attempt = 1

        raw_delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (self.exponential_factor ** (attempt - 1)),
        )

        if not apply_jitter:
            return raw_delay

        rng = random.Random(seed) if seed is not None else random
        # Bounded full jitter: between 50% and 100% of raw_delay
        return rng.uniform(0.5 * raw_delay, raw_delay)

