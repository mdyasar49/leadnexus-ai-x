"""
LeadNexus AI X - Phase 44: Enterprise Analytics, Observability, Cost & Platform Telemetry Package
Exposes metrics collection, distributed tracing, cost attribution, and SLA alert evaluation.
"""

from packages.telemetry.metrics_collector import MetricsCollector, MetricSample
from packages.telemetry.tracer import DistributedTracer, TraceSpan
from packages.telemetry.cost_attributor import CostAttributor, DEFAULT_RATES
from packages.telemetry.alert_evaluator import AlertEvaluator, AlertRule, AlertEvent


class EnterpriseTelemetryEngine:
    """Unified telemetry facade combining metrics, traces, costs, and alert rules."""

    def __init__(self):
        self.metrics = MetricsCollector()
        self.tracer = DistributedTracer()
        self.costs = CostAttributor()
        self.alerts = AlertEvaluator()

        # Seed standard SLA alert rules
        self.alerts.register_rule(
            name="API Latency SLA Breach",
            metric_name="api.request.latency",
            condition="GT",
            threshold=1500.0,
            severity="WARNING",
            rule_id="rule-sla-latency",
        )
        self.alerts.register_rule(
            name="Error Spike Threshold",
            metric_name="api.request.error_rate",
            condition="GT",
            threshold=0.05,
            severity="CRITICAL",
            rule_id="rule-error-rate",
        )


__all__ = [
    "MetricsCollector",
    "MetricSample",
    "DistributedTracer",
    "TraceSpan",
    "CostAttributor",
    "DEFAULT_RATES",
    "AlertEvaluator",
    "AlertRule",
    "AlertEvent",
    "EnterpriseTelemetryEngine",
]
