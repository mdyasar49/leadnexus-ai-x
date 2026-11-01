"""
LeadNexus AI X - Phase 44 Test Suite (ChatGPT Master Roadmap)
Enterprise Analytics, Observability, Cost & Platform Telemetry
Tests: Time-series metrics, quantiles, OpenMetrics/Prometheus export,
distributed tracing waterfalls, micro-USD cost attribution, SLA alerts, and workflow invariants.
"""

import sys
import os
import uuid
import unittest
import time
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.main import app
from app.db.session import SessionLocal, sync_engine
from app.db.base import Base
from app.models.tenant import Organization, Workspace
from app.models.user import User
from app.models.saved_lead import SavedLead
from app.models.enterprise_telemetry import (
    TelemetryMetricRecord,
    DistributedTraceSpan,
    CostAllocationRecord,
    TelemetryAlertRule,
    TelemetryAlertEvent,
)
from app.security.tokens import create_access_token
from packages.telemetry import (
    EnterpriseTelemetryEngine,
    MetricsCollector,
    DistributedTracer,
    CostAttributor,
    AlertEvaluator,
)


class TestPhase44Telemetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Telemetry Org", slug="telemetry-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                name="Telemetry Workspace",
                slug="telemetry-workspace",
                organization_id=cls.org.id,
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="telemetry_admin@leadnexus.internal",
                first_name="Telemetry",
                last_name="Admin",
                password_hash="hashed_pw_test",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        token = create_access_token(user_id=cls.user.id)
        cls.headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": cls.workspace.id,
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_metrics_collector_counters_and_gauges(self):
        """Validates counter incrementation and gauge value updates."""
        collector = MetricsCollector()
        c1 = collector.increment_counter("leads.searched", 10.0)
        c2 = collector.increment_counter("leads.searched", 5.0)
        self.assertEqual(c2, 15.0)

        g1 = collector.set_gauge("worker.pool.utilization", 0.75)
        self.assertEqual(g1, 0.75)
        g2 = collector.set_gauge("worker.pool.utilization", 0.50)
        self.assertEqual(g2, 0.50)

    def test_02_metrics_collector_histograms_and_quantiles(self):
        """Validates observation recording and accurate p50, p90, p95, and p99 calculation."""
        collector = MetricsCollector()
        for i in range(1, 101):
            collector.observe_histogram("api.request.latency", float(i * 10))  # 10ms to 1000ms

        q = collector.get_quantiles("api.request.latency")
        self.assertEqual(q["count"], 100)
        self.assertEqual(q["min"], 10.0)
        self.assertEqual(q["max"], 1000.0)
        self.assertEqual(q["p50"], 500.0)
        self.assertEqual(q["p90"], 900.0)
        self.assertEqual(q["p95"], 950.0)
        self.assertEqual(q["p99"], 990.0)

    def test_03_prometheus_openmetrics_render(self):
        """Validates standard Prometheus text rendering."""
        collector = MetricsCollector()
        collector.increment_counter("api.requests.total", 42.0)
        collector.set_gauge("active.sessions", 8.0)
        collector.observe_histogram("db.query.latency", 25.0)

        rendered = collector.render_prometheus_format()
        self.assertIn("# TYPE api_requests_total counter", rendered)
        self.assertIn("api_requests_total 42.0", rendered)
        self.assertIn("# TYPE active_sessions gauge", rendered)
        self.assertIn("active_sessions 8.0", rendered)
        self.assertIn("db_query_latency_ms{quantile=\"0.5\"}", rendered)

    def test_04_distributed_tracer_spans_and_duration(self):
        """Validates span creation, tag setting, and duration calculation."""
        tracer = DistributedTracer()
        span = tracer.start_span("model_router.dispatch", service_name="ai-engine")
        span.set_attribute("model.name", "gemini-1.5-pro")
        time.sleep(0.01)
        span.finish(status_code="OK")
        tracer.record_span(span)

        self.assertGreater(span.duration_ms, 5.0)
        self.assertEqual(span.status_code, "OK")
        self.assertEqual(span.attributes["model.name"], "gemini-1.5-pro")

    def test_05_distributed_tracer_waterfall_generation(self):
        """Validates hierarchical waterfall timeline construction."""
        tracer = DistributedTracer()
        trace_id = "trace-test-123456"

        root_span = tracer.start_span("http.request", trace_id=trace_id)
        time.sleep(0.005)

        child_1 = tracer.start_span("database.query", trace_id=trace_id, parent_span_id=root_span.span_id)
        time.sleep(0.005)
        child_1.finish()
        tracer.record_span(child_1)

        child_2 = tracer.start_span("agent.reasoning", trace_id=trace_id, parent_span_id=root_span.span_id)
        time.sleep(0.005)
        child_2.finish()
        tracer.record_span(child_2)

        root_span.finish()
        tracer.record_span(root_span)

        waterfall = tracer.build_waterfall(trace_id)
        self.assertEqual(len(waterfall), 3)
        self.assertTrue(all("offset_ms" in s for s in waterfall))
        self.assertTrue(all("duration_ms" in s for s in waterfall))

    def test_06_cost_attributor_ai_tokens_and_compute(self):
        """Validates micro-USD operational cost calculations and workspace aggregation."""
        attributor = CostAttributor()
        ws_id = "ws-cost-test"

        # Record AI inference: 10,000 in, 2,000 out on Gemini Pro
        ai_cost = attributor.record_ai_inference_cost(
            workspace_id=ws_id,
            model_name="gemini-1.5-pro",
            input_tokens=10000,
            output_tokens=2000,
        )
        self.assertGreater(ai_cost, 0)

        # Record worker compute: 5,000 ms
        compute_cost = attributor.record_compute_cost(
            workspace_id=ws_id,
            subsystem="agent_worker",
            duration_ms=5000.0,
        )
        self.assertGreater(compute_cost, 0)

        summary = attributor.get_workspace_cost_summary(ws_id)
        self.assertEqual(summary["record_count"], 2)
        self.assertGreater(summary["total_micros"], 0)
        self.assertIn("AI_INFERENCE", summary["by_category_usd"])
        self.assertIn("WORKER_COMPUTE", summary["by_category_usd"])

    def test_07_alert_evaluator_threshold_triggering(self):
        """Validates alert rule threshold condition evaluation."""
        evaluator = AlertEvaluator()
        evaluator.register_rule(
            name="High Latency Warning",
            metric_name="api.latency",
            condition="GT",
            threshold=500.0,
            severity="WARNING",
            rule_id="rule-latency-warning",
        )

        # Below threshold -> no events
        no_events = evaluator.evaluate_metric("api.latency", 400.0)
        self.assertEqual(len(no_events), 0)

        # Above threshold -> event triggered
        events = evaluator.evaluate_metric("api.latency", 620.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule_id, "rule-latency-warning")
        self.assertEqual(events[0].observed_value, 620.0)
        self.assertEqual(events[0].status, "TRIGGERED")

    def test_08_alert_event_resolution(self):
        """Validates resolving an active alert event."""
        evaluator = AlertEvaluator()
        evaluator.register_rule(
            name="Error Spike",
            metric_name="error.rate",
            condition="GT",
            threshold=0.05,
            severity="CRITICAL",
        )
        events = evaluator.evaluate_metric("error.rate", 0.12)
        self.assertEqual(len(events), 1)
        ev = events[0]

        resolved = evaluator.resolve_event(ev.event_id)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.status, "RESOLVED")
        self.assertIsNotNone(resolved.resolved_at)

    def test_09_api_telemetry_endpoints(self):
        """Validates /metrics, /metrics/prometheus, /traces/spans, /costs/summary via TestClient."""
        # Record metric via API
        m_payload = {
            "metric_name": "leadnexus.search.queries",
            "metric_type": "COUNTER",
            "value": 5.0,
            "labels": {"channel": "b2b"},
        }
        res_m = self.client.post("/api/v1/telemetry/metrics", json=m_payload, headers=self.headers)
        self.assertEqual(res_m.status_code, 200)

        # Scrape Prometheus format
        res_prom = self.client.get("/api/v1/telemetry/metrics/prometheus")
        self.assertEqual(res_prom.status_code, 200)
        self.assertIn("text/plain", res_prom.headers["content-type"])

        # Cost summary
        res_cost = self.client.get("/api/v1/telemetry/costs/summary", headers=self.headers)
        self.assertEqual(res_cost.status_code, 200)

        # Record span via API
        s_payload = {
            "operation_name": "api.search.leads",
            "trace_id": "trace-api-test-99",
            "duration_ms": 45.2,
            "status_code": "OK",
            "attributes": {"leads_count": 25},
        }
        res_s = self.client.post("/api/v1/telemetry/traces/spans", json=s_payload, headers=self.headers)
        self.assertEqual(res_s.status_code, 200)

        # Fetch trace waterfall
        res_wf = self.client.get("/api/v1/telemetry/traces/trace-api-test-99", headers=self.headers)
        self.assertEqual(res_wf.status_code, 200)
        self.assertEqual(res_wf.json()["span_count"], 1)

    def test_10_primary_workflow_invariant_preservation(self):
        """
        PRIMARY WORKFLOW INVARIANT:
        Telemetry recording, trace spans, metrics aggregation, and cost accounting
        must NEVER pollute canonical PostgreSQL SavedLead records.
        """
        initial_saved_count = self.db.query(SavedLead).count()

        engine = EnterpriseTelemetryEngine()
        # Record numerous metrics, spans, and costs
        for i in range(20):
            engine.metrics.increment_counter("system.ops", 1.0)
            engine.metrics.set_gauge("system.load", 0.45)
            engine.metrics.observe_histogram("api.latency", 120.0)
            span = engine.tracer.start_span(f"op_{i}")
            span.finish()
            engine.tracer.record_span(span)
            engine.costs.record_ai_inference_cost("test-ws", "gemini-1.5-flash", 100, 50)

        current_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(
            current_saved_count,
            initial_saved_count,
            "CRITICAL INVARIANT VIOLATION: Telemetry subsystem mutated canonical SavedLead table!"
        )


if __name__ == "__main__":
    unittest.main()
