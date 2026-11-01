"""
LeadNexus AI X - Phase 44: Enterprise Analytics, Observability, Cost & Platform Telemetry Routes
Provides endpoints for OpenMetrics/Prometheus scraping, distributed tracing waterfalls,
granular cost allocation summaries, and SLA alert management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.enterprise_telemetry import (
    TelemetryMetricRecord,
    DistributedTraceSpan,
    CostAllocationRecord,
    TelemetryAlertRule,
    TelemetryAlertEvent,
)
from packages.telemetry import (
    EnterpriseTelemetryEngine,
    MetricsCollector,
    DistributedTracer,
    CostAttributor,
    AlertEvaluator,
)

router = APIRouter(prefix="/telemetry", tags=["Enterprise Analytics & Observability"])

# Singleton telemetry engine
global_telemetry_engine = EnterpriseTelemetryEngine()


# Pydantic Schemas
class RecordMetricRequest(BaseModel):
    metric_name: str = Field(..., description="Canonical metric name (e.g. api.requests.total)")
    metric_type: str = Field(default="GAUGE", description="COUNTER, GAUGE, or HISTOGRAM")
    value: float = Field(..., description="Observed numeric metric value")
    labels: Dict[str, str] = Field(default_factory=dict)


class RecordSpanRequest(BaseModel):
    operation_name: str = Field(..., description="Name of the operation (e.g. model_router.dispatch)")
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    service_name: str = Field(default="leadnexus-api")
    duration_ms: float = Field(..., ge=0.0)
    status_code: str = Field(default="OK")
    attributes: Dict[str, Any] = Field(default_factory=dict)


class CreateAlertRuleRequest(BaseModel):
    name: str = Field(..., description="Human-readable alert rule name")
    metric_name: str = Field(..., description="Target metric name to evaluate")
    condition: str = Field(default="GT", description="GT, LT, EQ, GTE, LTE")
    threshold: float = Field(...)
    severity: str = Field(default="WARNING", description="INFO, WARNING, or CRITICAL")


@router.get("/health")
def get_telemetry_health():
    """Returns telemetry engine health and active metric counters."""
    return {
        "status": "HEALTHY",
        "metrics_samples_count": len(global_telemetry_engine.metrics._samples),
        "spans_recorded_count": len(global_telemetry_engine.tracer._completed_spans),
        "active_alerts_count": len(global_telemetry_engine.alerts.get_active_events()),
    }


@router.get("/metrics/prometheus")
def export_prometheus_metrics():
    """OpenMetrics / Prometheus scrapable text format endpoint."""
    text_payload = global_telemetry_engine.metrics.render_prometheus_format()
    return Response(content=text_payload, media_type="text/plain; version=0.0.4")


@router.get("/metrics")
def get_metrics_summary():
    """Returns JSON representation of all counters, gauges, and histogram quantiles."""
    hist_quantiles = {
        name: global_telemetry_engine.metrics.get_quantiles(name)
        for name in global_telemetry_engine.metrics._histograms.keys()
    }
    return {
        "counters": dict(global_telemetry_engine.metrics._counters),
        "gauges": dict(global_telemetry_engine.metrics._gauges),
        "histograms": hist_quantiles,
    }


@router.post("/metrics")
def record_metric_observation(
    request: RecordMetricRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Records a metric sample and evaluates against SLA alert rules."""
    m_type = request.metric_type.upper()
    if m_type == "COUNTER":
        global_telemetry_engine.metrics.increment_counter(request.metric_name, request.value, request.labels)
    elif m_type == "HISTOGRAM":
        global_telemetry_engine.metrics.observe_histogram(request.metric_name, request.value, request.labels)
    else:
        global_telemetry_engine.metrics.set_gauge(request.metric_name, request.value, request.labels)

    # Persist in DB
    db_metric = TelemetryMetricRecord(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        metric_name=request.metric_name,
        metric_type=m_type,
        value=request.value,
        labels=request.labels,
    )
    db.add(db_metric)

    # Evaluate alerts
    triggered = global_telemetry_engine.alerts.evaluate_metric(request.metric_name, request.value)
    for trig in triggered:
        db.add(
            TelemetryAlertEvent(
                id=trig.event_id,
                rule_id=trig.rule_id,
                metric_name=trig.metric_name,
                observed_value=trig.observed_value,
                threshold=trig.threshold,
                status=trig.status,
                details=trig.details,
            )
        )

    db.commit()

    return {
        "recorded": request.model_dump(),
        "alerts_triggered": [t.to_dict() for t in triggered],
    }


@router.get("/traces/{trace_id}")
def get_trace_waterfall(
    trace_id: str,
    user: User = Depends(get_current_user),
):
    """Retrieves waterfall timeline and child spans for a distributed trace."""
    waterfall = global_telemetry_engine.tracer.build_waterfall(trace_id)
    if not waterfall:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "trace_id": trace_id,
        "span_count": len(waterfall),
        "total_duration_ms": max(s["offset_ms"] + s["duration_ms"] for s in waterfall),
        "spans": waterfall,
    }


@router.post("/traces/spans")
def record_trace_span(
    request: RecordSpanRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Ingests a finalized distributed trace span."""
    span = global_telemetry_engine.tracer.start_span(
        operation_name=request.operation_name,
        trace_id=request.trace_id,
        parent_span_id=request.parent_span_id,
        service_name=request.service_name,
        attributes=request.attributes,
    )
    span.duration_ms = request.duration_ms
    span.status_code = request.status_code
    global_telemetry_engine.tracer.record_span(span)

    # Persist in DB
    db_span = DistributedTraceSpan(
        id=span.span_id,
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        service_name=span.service_name,
        operation_name=span.operation_name,
        duration_ms=span.duration_ms,
        status_code=span.status_code,
        attributes=span.attributes,
    )
    db.add(db_span)
    db.commit()

    return span.to_dict()


@router.get("/costs/summary")
def get_cost_summary(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves micro-USD and USD cost attribution summary for the active workspace."""
    summary = global_telemetry_engine.costs.get_workspace_cost_summary(workspace.id)
    return summary


@router.get("/alerts/rules")
def list_alert_rules():
    """Lists all active and configured SLA alert rules."""
    rules = [
        {
            "id": r.rule_id,
            "name": r.name,
            "metric_name": r.metric_name,
            "condition": r.condition,
            "threshold": r.threshold,
            "severity": r.severity,
            "is_active": r.is_active,
        }
        for r in global_telemetry_engine.alerts._rules.values()
    ]
    return {"rules": rules, "count": len(rules)}


@router.post("/alerts/rules")
def create_alert_rule(
    request: CreateAlertRuleRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Registers a new metric anomaly alert rule."""
    rule_id = str(uuid.uuid4())
    rule = global_telemetry_engine.alerts.register_rule(
        name=request.name,
        metric_name=request.metric_name,
        condition=request.condition,
        threshold=request.threshold,
        severity=request.severity,
        rule_id=rule_id,
    )

    db_rule = TelemetryAlertRule(
        id=rule_id,
        name=request.name,
        metric_name=request.metric_name,
        condition=request.condition,
        threshold=request.threshold,
        severity=request.severity,
    )
    db.add(db_rule)
    db.commit()

    return {
        "rule_id": rule_id,
        "name": rule.name,
        "metric_name": rule.metric_name,
        "condition": rule.condition,
        "threshold": rule.threshold,
        "severity": rule.severity,
    }


@router.get("/alerts/events")
def list_alert_events():
    """Lists recent triggered and resolved alert events."""
    events = [e.to_dict() for e in global_telemetry_engine.alerts._events]
    return {"events": events, "count": len(events)}


@router.post("/alerts/events/{event_id}/resolve")
def resolve_alert_event(
    event_id: str,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Resolves an active alert event."""
    ev = global_telemetry_engine.alerts.resolve_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Alert event not found")

    db_ev = db.query(TelemetryAlertEvent).filter(TelemetryAlertEvent.id == event_id).first()
    if db_ev:
        db_ev.status = "RESOLVED"
        db_ev.resolved_at = datetime.now(timezone.utc)
        db.commit()

    return ev.to_dict()
