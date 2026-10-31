"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering
Latency Profiler: Real-time latency percentile calculations (p50, p90, p95, p99) and performance snapshots.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.performance import LatencyMetricSnapshot


class LatencyProfiler:
    """Calculates statistical latency percentiles and generates performance telemetry snapshots."""

    @classmethod
    def calculate_percentiles(cls, samples: List[float]) -> Dict[str, float]:
        """Calculates p50, p90, p95, p99, and max from a list of latency samples (in ms)."""
        if not samples:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        def get_p(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            idx = max(0, min(idx, n - 1))
            return round(sorted_samples[idx], 2)

        return {
            "p50": get_p(0.50),
            "p90": get_p(0.90),
            "p95": get_p(0.95),
            "p99": get_p(0.99),
            "max": round(sorted_samples[-1], 2),
        }

    def __init__(self, db_session: Any):
        self.db = db_session

    def create_snapshot(
        self,
        operation_name: str,
        samples: List[float],
        window_start: datetime,
        window_end: datetime,
    ) -> LatencyMetricSnapshot:
        percentiles = self.calculate_percentiles(samples)
        snapshot = LatencyMetricSnapshot(
            id=str(uuid.uuid4()),
            operation_name=operation_name,
            sample_count=len(samples),
            p50_ms=percentiles["p50"],
            p90_ms=percentiles["p90"],
            p95_ms=percentiles["p95"],
            p99_ms=percentiles["p99"],
            max_ms=percentiles["max"],
            window_start=window_start,
            window_end=window_end,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

