"""
LeadNexus AI X - Phase 47: Stream Backpressure Ring Buffer
Protects memory by maintaining a bounded ring buffer with drop-oldest overflow strategy.
"""

from collections import deque
from typing import Any, Dict, List, Optional
import time


class BackpressureBuffer:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)
        self.total_appended: int = 0
        self.total_dropped: int = 0
        self._last_append_time: float = time.time()

    def append(self, item: Dict[str, Any]) -> bool:
        """
        Appends an item to the ring buffer.
        If buffer is full, deque automatically drops oldest item; we increment dropped counter.
        """
        if len(self._buffer) >= self.capacity:
            self.total_dropped += 1

        self._buffer.append(item)
        self.total_appended += 1
        self._last_append_time = time.time()
        return True

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent N items, newest first."""
        items = list(self._buffer)
        return list(reversed(items[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        drop_rate = (
            (self.total_dropped / self.total_appended * 100.0)
            if self.total_appended > 0
            else 0.0
        )
        return {
            "capacity": self.capacity,
            "current_size": len(self._buffer),
            "utilization_percent": round((len(self._buffer) / self.capacity) * 100.0, 2),
            "total_appended": self.total_appended,
            "total_dropped": self.total_dropped,
            "drop_rate_percent": round(drop_rate, 2),
        }

    def clear(self):
        self._buffer.clear()
        self.total_appended = 0
        self.total_dropped = 0
