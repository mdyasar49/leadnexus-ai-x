"""
LeadNexus AI X - Phase 44: Time-Series Metrics Collector
Provides counter, gauge, and histogram metric aggregation, quantile calculations (p50/p95/p99),
and Prometheus/OpenMetrics text format rendering.
"""

from collections import defaultdict
from datetime import datetime, timezone
import math
import time
from typing import Any, Dict, List, Optional, Tuple


class MetricSample:
    def __init__(
        self,
        name: str,
        value: float,
        metric_type: str = "GAUGE",
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ):
        self.name = name
        self.value = value
        self.metric_type = metric_type.upper()
        self.labels = labels or {}
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "metric_type": self.metric_type,
            "labels": self.labels,
            "timestamp": self.timestamp,
        }


class MetricsCollector:
    """In-memory and scrapable time-series metric aggregator."""

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._samples: List[MetricSample] = []

    def increment_counter(self, name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> float:
        """Increments a monotonic counter."""
        self._counters[name] += amount
        sample = MetricSample(name=name, value=self._counters[name], metric_type="COUNTER", labels=labels)
        self._samples.append(sample)
        return self._counters[name]

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Sets a point-in-time gauge value."""
        self._gauges[name] = value
        sample = MetricSample(name=name, value=value, metric_type="GAUGE", labels=labels)
        self._samples.append(sample)
        return value

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Appends an observation to a histogram (e.g. latency)."""
        self._histograms[name].append(value)
        sample = MetricSample(name=name, value=value, metric_type="HISTOGRAM", labels=labels)
        self._samples.append(sample)

    def get_quantiles(self, name: str) -> Dict[str, float]:
        """Calculates min, max, avg, p50, p90, p95, and p99 for a histogram."""
        values = sorted(self._histograms.get(name, []))
        if not values:
            return {"count": 0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}

        n = len(values)

        def quantile(q: float) -> float:
            idx = int(math.ceil(q * n)) - 1
            return values[max(0, min(idx, n - 1))]

        return {
            "count": n,
            "min": round(values[0], 4),
            "max": round(values[-1], 4),
            "avg": round(sum(values) / n, 4),
            "p50": round(quantile(0.50), 4),
            "p90": round(quantile(0.90), 4),
            "p95": round(quantile(0.95), 4),
            "p99": round(quantile(0.99), 4),
        }

    def render_prometheus_format(self) -> str:
        """Generates OpenMetrics / Prometheus standard scrapable text."""
        lines = []

        # Counters
        for name, val in self._counters.items():
            clean_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# HELP {clean_name} Monotonic counter")
            lines.append(f"# TYPE {clean_name} counter")
            lines.append(f"{clean_name} {val}")

        # Gauges
        for name, val in self._gauges.items():
            clean_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# HELP {clean_name} Real-time gauge")
            lines.append(f"# TYPE {clean_name} gauge")
            lines.append(f"{clean_name} {val}")

        # Histograms
        for name, values in self._histograms.items():
            clean_name = name.replace(".", "_").replace("-", "_")
            q = self.get_quantiles(name)
            lines.append(f"# HELP {clean_name}_ms Request duration histogram")
            lines.append(f"# TYPE {clean_name}_ms summary")
            lines.append(f'{clean_name}_ms{{quantile="0.5"}} {q["p50"]}')
            lines.append(f'{clean_name}_ms{{quantile="0.9"}} {q["p90"]}')
            lines.append(f'{clean_name}_ms{{quantile="0.95"}} {q["p95"]}')
            lines.append(f'{clean_name}_ms{{quantile="0.99"}} {q["p99"]}')
            lines.append(f"{clean_name}_ms_sum {sum(values)}")
            lines.append(f"{clean_name}_ms_count {len(values)}")

        return "\n".join(lines) + "\n"
