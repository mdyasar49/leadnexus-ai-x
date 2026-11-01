"""
LeadNexus AI X - Phase 47: Stream Signal Aggregator & Anomaly Spike Detector
Maintains windowed signal frequencies to detect sudden buying intent and hiring surges.
"""

from collections import defaultdict
import time
from typing import Any, Dict, List, Optional
import uuid


class SignalAggregator:
    def __init__(self, window_seconds: float = 300.0, spike_threshold: int = 3):
        self.window_seconds = window_seconds
        self.spike_threshold = spike_threshold
        # Mapping: company_name -> List[float (timestamps)]
        self._company_timestamps: Dict[str, List[float]] = defaultdict(list)
        self._detected_alerts: List[Dict[str, Any]] = []

    def record_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Records signal arrival for the company.
        If signal frequency in window exceeds spike_threshold, triggers and returns an anomaly alert.
        """
        now = time.time()
        company = str(signal.get("company_name", "")).strip()
        if not company:
            return None

        # Clean old timestamps
        cutoff = now - self.window_seconds
        self._company_timestamps[company] = [t for t in self._company_timestamps[company] if t >= cutoff]

        # Add current signal
        self._company_timestamps[company].append(now)
        count = len(self._company_timestamps[company])

        if count >= self.spike_threshold:
            # Check if alert was recently emitted for this company within window
            recent_alert = next(
                (
                    a for a in self._detected_alerts
                    if a["company_name"].lower() == company.lower()
                    and now - a["_timestamp_epoch"] < (self.window_seconds / 2.0)
                ),
                None,
            )
            if not recent_alert:
                alert = {
                    "id": f"anom_{uuid.uuid4().hex[:12]}",
                    "company_name": company,
                    "signal_count": count,
                    "window_seconds": int(self.window_seconds),
                    "severity": "CRITICAL" if count >= self.spike_threshold + 2 else "HIGH",
                    "description": (
                        f"Unusual signal surge detected for '{company}': {count} intelligence signals "
                        f"ingested within {int(self.window_seconds)}s window."
                    ),
                    "_timestamp_epoch": now,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                }
                self._detected_alerts.append(alert)
                return alert

        return None

    def get_recent_anomalies(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self._detected_alerts[-limit:]))

    def clear(self):
        self._company_timestamps.clear()
        self._detected_alerts.clear()
