"""
LeadNexus AI X - Phase 47: Signal Stream Orchestrator Hub
Unified engine managing WebSocket subscribers, topics, buffers, and signal dispatch.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid
from packages.streaming.backpressure_buffer import BackpressureBuffer
from packages.streaming.signal_deduplicator import SignalDeduplicator
from packages.streaming.stream_filter_engine import StreamFilterEngine
from packages.streaming.signal_aggregator import SignalAggregator


class SignalStreamHub:
    def __init__(
        self,
        buffer_capacity: int = 1000,
        dedup_window_seconds: float = 60.0,
        spike_window_seconds: float = 300.0,
        spike_threshold: int = 3,
    ):
        self.buffer = BackpressureBuffer(capacity=buffer_capacity)
        self.deduplicator = SignalDeduplicator(window_seconds=dedup_window_seconds)
        self.filter_engine = StreamFilterEngine()
        self.aggregator = SignalAggregator(
            window_seconds=spike_window_seconds, spike_threshold=spike_threshold
        )

        # In-memory subscriptions: sub_id -> {topic, filter_criteria, callback}
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        # Active topics set
        self._active_topics: Set[str] = set()

        # Throughput tracking
        self._start_time = time.time()
        self._signals_published_count = 0
        self._recent_timestamps: List[float] = []

    def subscribe(
        self,
        topic: str,
        filter_criteria: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        subscription_id: Optional[str] = None,
    ) -> str:
        """Registers a subscription to a topic with optional criteria."""
        sub_id = subscription_id or f"sub_{uuid.uuid4().hex[:12]}"
        self._subscriptions[sub_id] = {
            "id": sub_id,
            "topic": topic,
            "filter_criteria": filter_criteria or {},
            "callback": callback,
            "created_at": time.time(),
        }
        self._active_topics.add(topic)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            topic = self._subscriptions[subscription_id]["topic"]
            del self._subscriptions[subscription_id]
            # Check if topic still has active subscribers
            if not any(s["topic"] == topic for s in self._subscriptions.values()):
                self._active_topics.discard(topic)
            return True
        return False

    def publish(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests a new signal into the streaming pipeline:
        1. Checks deduplication.
        2. Evaluates intent spike / anomaly detection.
        3. Appends to backpressure ring buffer.
        4. Dispatches to matching topic subscriptions.
        """
        now = time.time()
        self._signals_published_count += 1
        self._recent_timestamps.append(now)

        # Add id and timestamp if missing
        if "id" not in signal:
            signal["id"] = f"sig_{uuid.uuid4().hex[:12]}"
        if "timestamp" not in signal:
            signal["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        topic = signal.get("topic", "signals.general")
        self._active_topics.add(topic)

        # 1. Deduplication Check
        is_dup = self.deduplicator.is_duplicate(signal)
        if is_dup:
            return {
                "status": "DUPLICATE_SUPPRESSED",
                "signal_id": signal["id"],
                "dispatched_subscribers": 0,
            }

        # 2. Anomaly Spike Check
        anomaly_alert = self.aggregator.record_signal(signal)

        # 3. Buffer Storage
        self.buffer.append(signal)

        # 4. Dispatch to matching subscribers
        matched_count = 0
        for sub in list(self._subscriptions.values()):
            sub_topic = sub["topic"]
            # Match wildcard or exact topic
            if sub_topic == "*" or sub_topic == topic or topic.startswith(sub_topic.rstrip("*")):
                if self.filter_engine.matches(signal, sub["filter_criteria"]):
                    matched_count += 1
                    cb = sub.get("callback")
                    if cb and callable(cb):
                        try:
                            cb(signal)
                        except Exception:
                            pass

        return {
            "status": "PUBLISHED",
            "signal_id": signal["id"],
            "dispatched_subscribers": matched_count,
            "anomaly_detected": anomaly_alert is not None,
            "anomaly": anomaly_alert,
        }

    def get_recent_signals(
        self,
        topic: Optional[str] = None,
        filter_criteria: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Queries buffered signals with topic and criteria matching."""
        buffered = self.buffer.get_recent(limit=self.buffer.capacity)
        results = []
        for sig in buffered:
            if topic and topic != "*" and sig.get("topic") != topic:
                continue
            if filter_criteria and not self.filter_engine.matches(sig, filter_criteria):
                continue
            results.append(sig)
            if len(results) >= limit:
                break
        return results

    def get_stats(self) -> Dict[str, Any]:
        now = time.time()
        # Clean rolling 60s timestamps for rate calculation
        self._recent_timestamps = [t for t in self._recent_timestamps if now - t <= 60.0]
        throughput = len(self._recent_timestamps) / 60.0

        buf_stats = self.buffer.get_stats()
        return {
            "active_subscriptions": len(self._subscriptions),
            "active_websocket_clients": 0,  # dynamically updated by route handlers
            "buffered_signals": buf_stats["current_size"],
            "buffer_capacity": buf_stats["capacity"],
            "total_signals_published": self._signals_published_count,
            "throughput_signals_per_sec": round(throughput, 2),
            "drop_rate_percent": buf_stats["drop_rate_percent"],
            "active_topics": sorted(list(self._active_topics)),
        }

    def clear(self):
        self.buffer.clear()
        self.deduplicator.clear()
        self.aggregator.clear()
        self._subscriptions.clear()
        self._active_topics.clear()
        self._signals_published_count = 0
        self._recent_timestamps.clear()
