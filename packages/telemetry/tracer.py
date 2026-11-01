"""
LeadNexus AI X - Phase 44: Distributed Tracing & Span Manager
OpenTelemetry-compatible span lifecycle manager supporting nested parent-child spans,
error captures, contextual attributes, and waterfall trace serialization.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid


class TraceSpan:
    def __init__(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        service_name: str = "leadnexus-api",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.span_id = str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4()).replace("-", "")
        self.parent_span_id = parent_span_id
        self.service_name = service_name
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self.status_code = "OK"
        self.error_message: Optional[str] = None
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0

    def finish(self, status_code: str = "OK", error_message: Optional[str] = None) -> "TraceSpan":
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 3)
        self.status_code = status_code.upper()
        self.error_message = error_message
        return self

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class DistributedTracer:
    """Manages active distributed trace contexts and span collection."""

    def __init__(self):
        self._completed_spans: List[TraceSpan] = []

    def start_span(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        service_name: str = "leadnexus-api",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Instantiates a new distributed trace span."""
        span = TraceSpan(
            operation_name=operation_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            service_name=service_name,
            attributes=attributes,
        )
        return span

    def record_span(self, span: TraceSpan) -> None:
        """Records a finalized span into storage."""
        if span.end_time is None:
            span.finish()
        self._completed_spans.append(span)

    def get_spans_by_trace(self, trace_id: str) -> List[TraceSpan]:
        """Returns all spans belonging to a specific trace, sorted chronologically."""
        spans = [s for s in self._completed_spans if s.trace_id == trace_id]
        return sorted(spans, key=lambda s: s.start_time)

    def build_waterfall(self, trace_id: str) -> List[Dict[str, Any]]:
        """Constructs a hierarchical waterfall representation of a distributed trace."""
        spans = self.get_spans_by_trace(trace_id)
        if not spans:
            return []

        trace_start = min(s.start_time for s in spans)
        waterfall = []
        for s in spans:
            offset_ms = round((s.start_time - trace_start) * 1000.0, 3)
            d = s.to_dict()
            d["offset_ms"] = offset_ms
            waterfall.append(d)

        return waterfall
