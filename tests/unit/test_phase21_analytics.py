import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, SessionLocal, get_sync_db
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore, EvidenceClaim, ICPProfile
from app.models.source import ResearchSource
from app.models.operations import ResearchCostEvent
from app.models.analytics import (
    AnalyticsMetric,
    AnalyticsMetricVersion,
    AnalyticsDimension,
    AnalyticsView,
    AnalyticsReport,
    AnalyticsReportExecution,
    AnalyticsAnomaly,
    AnalyticsTrend,
    Prediction,
    LeadSnapshot,
    ScoreSnapshot
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.analytics.dsl import AnalyticsDSLQuery, AnalyticsDSLError
from packages.analytics.snapshot_engine import SnapshotEngine
from packages.analytics.intelligence_analytics import IntelligenceAnalyticsService
from packages.analytics.predictive_engine import PredictiveEngine
from packages.analytics.anomaly_detector import AnomalyAndTrendDetector
from packages.analytics.report_generator import ReportGenerator, sanitize_csv_cell
from packages.analytics.nl_query import NaturalLanguageAnalytics


class TestPhase21Analytics(unittest.TestCase):
    """Test suite covering Phase 21 Enterprise Analytics, Intelligence Reporting & Predictive Insights."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"analytics_director_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Analytics",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Analytics Intelligence Workspace",
            slug=f"analytics-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Odoo Australia Solutions",
            normalized_name="odoo australia solutions",
            domain="odooaustralia.com.au",
            country="Australia",
            industry="Software & IT",
            lead_score=88,
            status="QUALIFIED"
        )
        cls.comp_2 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Perth Mining Technologies",
            normalized_name="perth mining technologies",
            domain="perthmining.com.au",
            country="Australia",
            industry="Mining",
            lead_score=82,
            status="RESEARCHED"
        )
        cls.comp_3 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Legacy Logistics Global",
            normalized_name="legacy logistics global",
            domain="legacylogistics.com",
            country="United States",
            industry="Logistics",
            lead_score=45,
            status="DISCOVERED"
        )
        cls.db.add(cls.comp_1)
        cls.db.add(cls.comp_2)
        cls.db.add(cls.comp_3)

        # Seed LeadScores
        cls.score_1 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            lead_priority_score=88.5,
            priority_tier="P1_HIGH",
            intent_score=90.0,
            icp_fit_score=92.0
        )
        cls.score_2 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_2.id,
            workspace_id=cls.ws_id,
            lead_priority_score=81.0,
            priority_tier="P1_HIGH",
            intent_score=80.0,
            icp_fit_score=85.0
        )
        cls.db.add(cls.score_1)
        cls.db.add(cls.score_2)

        # Seed Contacts
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="Marcus Vance",
            first_name="Marcus",
            last_name="Vance",
            job_title="Chief Technology Officer",
            email="marcus.vance@odooaustralia.com.au",
            email_status="VERIFIED",
            phone_status="VALID",
            source_url="https://odooaustralia.com.au/team/marcus"
        )
        cls.contact_2 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="Eleanor Rigby",
            first_name="Eleanor",
            last_name="Rigby",
            job_title="Managing Director",
            email="eleanor@odooaustralia.com.au",
            email_status="VERIFIED",
            source_url="https://odooaustralia.com.au/team/eleanor"
        )
        cls.db.add(cls.contact_1)
        cls.db.add(cls.contact_2)

        # Seed Intent Signals
        cls.intent_1 = IntentSignal(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            source_name="Careers Portal",
            source_url="https://odooaustralia.com.au/careers/erp",
            signal_type="MIGRATION_INTENT",
            detected_keyword="Odoo migration",
            evidence_snippet="Active recruitment for Odoo 17 ERP migration leads.",
            signal_strength=92.0
        )
        cls.intent_2 = IntentSignal(
            id=str(uuid.uuid4()),
            company_id=cls.comp_2.id,
            workspace_id=cls.ws_id,
            source_name="Job Board",
            source_url="https://perthmining.com.au/jobs",
            signal_type="IMPLEMENTATION_INTENT",
            detected_keyword="Odoo implementation",
            evidence_snippet="Evaluating Odoo for fleet maintenance tracking.",
            signal_strength=85.0
        )
        cls.db.add(cls.intent_1)
        cls.db.add(cls.intent_2)

        # Seed Evidence Claims
        cls.claim_1 = EvidenceClaim(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            claim_type="ERP_MIGRATION",
            claim_text="Odoo 17 Migration planned",
            supporting_evidence_ids=["https://odooaustralia.com.au/careers/erp-lead", "https://github.com/odooaustralia/addons"],
            confidence=0.95,
            status="SUPPORTED"
        )
        cls.claim_2 = EvidenceClaim(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_2.id,
            claim_type="TECH_EVALUATION",
            claim_text="Evaluating Odoo for logistics",
            supporting_evidence_ids=["https://perthmining.com.au/jobs"],
            confidence=0.88,
            status="SUPPORTED"
        )
        cls.db.add(cls.claim_1)
        cls.db.add(cls.claim_2)

        # Seed Source & Cost
        src_code = f"github_observer_{uuid.uuid4().hex[:6]}"
        cls.src = ResearchSource(
            id=str(uuid.uuid4()),
            code=src_code,
            key=src_code,
            name="GitHub Public Observer",
            source_type="API",
            is_active=True
        )
        cls.db.add(cls.src)

        cls.cost_event = ResearchCostEvent(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            source_key="GITHUB",
            cost_usd=15.50
        )
        cls.db.add(cls.cost_event)
        cls.db.commit()

        # TestClient dependency overrides
        def override_get_active_workspace():
            return cls.ws

        def override_get_current_user():
            return cls.user

        def override_get_sync_db():
            yield cls.db

        app.dependency_overrides[get_active_workspace] = override_get_active_workspace
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_sync_db] = override_get_sync_db

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.db.close()

    def test_kpi_registration_and_versioning(self):
        """Verify centralized KPI registration, formula storage, and version increments."""
        metric = AnalyticsMetric(
            workspace_id=self.ws_id,
            metric_code="HIGH_PRIORITY_CONVERSION_RATE",
            name="High Priority Lead Conversion Rate",
            category="LEAD",
            metric_type="RATE",
            formula="HIGH_PRIORITY_LEADS / TOTAL_LEADS",
            owner="architect"
        )
        self.db.add(metric)
        self.db.commit()

        ver1 = AnalyticsMetricVersion(
            metric_id=metric.id,
            version_number=1,
            formula=metric.formula,
            change_reason="Initial formula definition"
        )
        self.db.add(ver1)
        self.db.commit()

        self.assertIsNotNone(metric.id)
        self.assertEqual(metric.metric_code, "HIGH_PRIORITY_CONVERSION_RATE")
        self.assertEqual(ver1.version_number, 1)

    def test_safe_analytics_dsl_execution(self):
        """Verify execution of safe analytics DSL with filters, grouping, and comparison."""
        dsl_engine = AnalyticsDSLQuery(self.db)
        query_dsl = {
            "entity": "companies",
            "filters": [
                {"field": "country", "op": "=", "val": "Australia"}
            ],
            "time_range": "last_30_days",
            "order_by": "lead_score",
            "order_direction": "desc",
            "compare_period": True
        }

        res = dsl_engine.execute(workspace_id=self.ws_id, query_dsl=query_dsl)
        self.assertEqual(res["entity"], "companies")
        self.assertGreaterEqual(res["total_count"], 2)
        self.assertIn("results", res)
        self.assertIn("comparison", res)

    def test_safe_analytics_dsl_explain_and_injection_defense(self):
        """Verify DSL explain plan output and that unpermitted entities or operators are rejected."""
        dsl_engine = AnalyticsDSLQuery(self.db)

        # 1. Explain
        explain = dsl_engine.explain(
            workspace_id=self.ws_id,
            query_dsl={"entity": "companies", "filters": [{"field": "country", "op": "=", "val": "Australia"}]}
        )
        self.assertEqual(explain["estimated_complexity"], "LOW")
        self.assertTrue(explain["tenant_isolated"])

        # 2. Injection defense: Disallowed entity
        with self.assertRaises(AnalyticsDSLError):
            dsl_engine.execute(self.ws_id, {"entity": "users; DROP TABLE users;--"})

        # 3. Injection defense: Disallowed operator
        with self.assertRaises(AnalyticsDSLError):
            dsl_engine.execute(self.ws_id, {
                "entity": "companies",
                "filters": [{"field": "name", "op": "EXEC_SQL", "val": "evil"}]
            })

    def test_snapshot_engine_and_score_history(self):
        """Verify capture of snapshots and preservation of chronological score history."""
        snap_engine = SnapshotEngine(self.db)

        # 1. Lead snapshot
        lead_snap = snap_engine.capture_lead_snapshot(workspace_id=self.ws_id)
        self.assertIsNotNone(lead_snap.id)
        self.assertGreaterEqual(lead_snap.total_leads, 3)

        # 2. Company snapshot
        company_snaps = snap_engine.capture_company_snapshots(workspace_id=self.ws_id)
        self.assertGreaterEqual(len(company_snaps), 1)

        # 3. Historical score preservation (Oct 1 -> 52, Oct 10 -> 64, Oct 20 -> 81, Oct 31 -> 87)
        hist_scores = [52.0, 64.0, 81.0, 87.0]
        for s in hist_scores:
            snap_engine.record_score_snapshot(
                workspace_id=self.ws_id,
                company_id=self.comp_1.id,
                lead_priority_score=s,
                intent_score=s + 2,
                icp_fit_score=90.0,
                priority_tier="P1_HIGH" if s >= 80 else "P2_MEDIUM"
            )

        history = snap_engine.get_score_history(workspace_id=self.ws_id, company_id=self.comp_1.id)
        self.assertGreaterEqual(len(history), 4)
        scores_extracted = [h["lead_priority_score"] for h in history]
        for s in hist_scores:
            self.assertIn(s, scores_extracted)

    def test_lead_intelligence_funnel_and_aging(self):
        """Verify Lead Intelligence Funnel stages, conversions, velocity, and aging buckets."""
        analytics_svc = IntelligenceAnalyticsService(self.db)

        # 1. Funnel
        funnel = analytics_svc.get_lead_funnel(workspace_id=self.ws_id)
        self.assertIn("funnel_stages", funnel)
        self.assertGreaterEqual(funnel["total_discovered_leads"], 3)
        stages = [s["stage"] for s in funnel["funnel_stages"]]
        self.assertEqual(stages[0], "DISCOVERED")
        self.assertEqual(stages[-1], "READY")

        # 2. Aging
        aging = analytics_svc.get_lead_aging(workspace_id=self.ws_id)
        self.assertIn("aging_distribution", aging)
        self.assertIn("FRESH", aging["aging_distribution"])

    def test_priority_and_icp_analytics(self):
        """Verify lead priority distribution and ICP match statistics."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        res = analytics_svc.get_priority_and_icp_analytics(workspace_id=self.ws_id)
        self.assertIn("priority_distribution", res)
        self.assertIn("icp_fit_distribution", res)
        self.assertGreater(res["average_icp_score"], 80.0)

    def test_intent_analytics_and_temporal_decay(self):
        """Verify intent category aggregations, timeline, and decay factor application."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        intent_res = analytics_svc.get_intent_analytics(workspace_id=self.ws_id)
        self.assertGreaterEqual(intent_res["total_intent_signals"], 2)
        self.assertIn("timeline", intent_res)
        cats = [c["intent_type"] for c in intent_res["categories"]]
        self.assertTrue(any("MIGRATION" in c or "IMPLEMENTATION" in c for c in cats))

    def test_signal_effectiveness_and_evidence_coverage(self):
        """Verify evidence coverage percentages and signal correlation scores."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        res = analytics_svc.get_signal_and_evidence_analytics(workspace_id=self.ws_id)
        self.assertGreaterEqual(res["companies_with_evidence"], 1)
        self.assertGreaterEqual(res["multi_source_corroborated_percentage"], 1.0)
        self.assertIn("signal_effectiveness_score", res)

    def test_source_intelligence_efficiency_ranking(self):
        """Verify source intelligence efficiency calculation (useful intelligence / research cost)."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        sources_res = analytics_svc.get_source_analytics(workspace_id=self.ws_id)
        self.assertIn("sources", sources_res)
        self.assertGreaterEqual(len(sources_res["sources"]), 1)
        first_src = sources_res["sources"][0]
        self.assertIn("intelligence_efficiency", first_src)
        self.assertIn("rank_tier", first_src)

    def test_contact_and_buying_committee_completeness(self):
        """Verify contact quality and buying committee role coverage."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        ct_res = analytics_svc.get_contact_and_buying_committee_analytics(workspace_id=self.ws_id)
        self.assertGreaterEqual(ct_res["verified_emails"], 1)
        self.assertIn("buying_committee_role_breakdown", ct_res)
        self.assertGreaterEqual(ct_res["buying_committee_role_breakdown"]["Technical Evaluator"], 1)

    def test_geographic_and_australian_market_intelligence(self):
        """Verify geographic distribution and Australia-specific company insights."""
        analytics_svc = IntelligenceAnalyticsService(self.db)
        geo_res = analytics_svc.get_geographic_and_industry_analytics(workspace_id=self.ws_id)
        self.assertIn("Australia", geo_res["countries"])
        self.assertGreaterEqual(geo_res["australian_intelligence"]["australian_lead_count"], 2)

    def test_predictive_engine_lead_priority_and_staleness(self):
        """Verify bounded predictive model calculations and explainable feature contributions."""
        pred_engine = PredictiveEngine(self.db)

        # 1. Lead Priority Probability
        pred = pred_engine.predict_lead_priority_probability(self.ws_id, self.comp_1.id)
        self.assertIsNotNone(pred.id)
        self.assertEqual(pred.entity_id, self.comp_1.id)
        self.assertGreater(pred.probability, 0.5)
        self.assertIn("intent_contribution", pred.feature_contributions)
        self.assertIn("v1.2", pred.model_version)

        # 2. Staleness Risk
        stale_pred = pred_engine.predict_staleness_risk(self.ws_id, self.comp_1.id)
        self.assertIsNotNone(stale_pred.id)
        self.assertGreaterEqual(stale_pred.probability, 0.1)

        # 3. Prediction Evaluation
        eval_rec = pred_engine.record_prediction_evaluation(
            workspace_id=self.ws_id,
            prediction_id=pred.id,
            actual_outcome="HIGH_PRIORITY_VERIFIED",
            is_accurate=True
        )
        self.assertTrue(eval_rec.is_accurate)

    def test_anomaly_and_trend_detection(self):
        """Verify statistical anomaly detection (z-score >= 2.0) and trend velocity calculation."""
        detector = AnomalyAndTrendDetector(self.db)

        # 1. Anomaly: 5 baseline values around 10, then observed spike to 50
        anomaly = detector.detect_anomalies(
            workspace_id=self.ws_id,
            metric_code="RESEARCH_FAILURES",
            observed_value=50.0,
            historical_values=[10.0, 11.0, 9.0, 10.0, 12.0],
            time_window="7_DAYS"
        )
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly.severity, "CRITICAL")
        self.assertIn("spike", anomaly.description)

        # 2. Trend: Increasing velocity
        now = datetime.now(timezone.utc)
        points = [
            (now - timedelta(days=20), 10.0),
            (now - timedelta(days=15), 15.0),
            (now - timedelta(days=10), 30.0),
            (now - timedelta(days=5), 45.0)
        ]
        trend = detector.analyze_trend(
            workspace_id=self.ws_id,
            topic="ODOO_INTENT_GROWTH",
            time_series_points=points
        )
        self.assertEqual(trend.direction, "INCREASING")
        self.assertGreater(trend.velocity, 25.0)

    def test_report_generator_and_cwe1236_safe_export(self):
        """Verify report creation, execution snapshot persistence, and formula-injection-safe export."""
        gen = ReportGenerator(self.db)

        # 1. Create or get report definition
        report = gen.create_or_get_report_definition(
            workspace_id=self.ws_id,
            name="Executive Lead Intelligence Weekly",
            report_type="EXECUTIVE_INTELLIGENCE"
        )
        self.assertIsNotNone(report.id)

        # 2. Run report
        execution = gen.run_report(
            workspace_id=self.ws_id,
            report_id=report.id,
            generated_by=self.user_id,
            export_format="CSV"
        )
        self.assertIsNotNone(execution.id)
        self.assertIn("executive_summary", execution.data_snapshot)

        # 3. Export CSV with CWE-1236 Formula Injection Sanitization
        csv_content = gen.export_execution(execution, format_type="CSV")
        self.assertIn("Executive Lead Intelligence Weekly", csv_content)

        # Direct test of CWE-1236 sanitizer
        malicious = "=1+1;cmd"
        sanitized = sanitize_csv_cell(malicious)
        self.assertTrue(sanitized.startswith("'="))

    def test_natural_language_analytics(self):
        """Verify translation of natural language queries into safe Analytics DSL AST and execution."""
        nl_engine = NaturalLanguageAnalytics(self.db)

        prompt = "Show Australian companies with Odoo intent this month"
        res = nl_engine.execute_nl_query(workspace_id=self.ws_id, prompt=prompt)

        self.assertIn("dsl", res)
        self.assertIn("interpretation", res)
        self.assertEqual(res["dsl"]["time_range"], "last_30_days")
        self.assertIn("data", res)

    def test_fastapi_analytics_rest_endpoints(self):
        """Verify REST API routes for KPIs, leads, intent, signals, sources, geography, reports, and NL query."""
        # 1. KPIs
        kpi_resp = self.client.get("/api/v1/analytics/kpis")
        self.assertEqual(kpi_resp.status_code, 200)
        self.assertIsInstance(kpi_resp.json(), list)

        # 2. Leads Funnel
        lead_resp = self.client.get("/api/v1/analytics/leads")
        self.assertEqual(lead_resp.status_code, 200)
        self.assertIn("funnel", lead_resp.json())

        # 3. Intent
        intent_resp = self.client.get("/api/v1/analytics/intent")
        self.assertEqual(intent_resp.status_code, 200)
        self.assertIn("categories", intent_resp.json())

        # 4. Signals
        sig_resp = self.client.get("/api/v1/analytics/signals")
        self.assertEqual(sig_resp.status_code, 200)
        self.assertIn("evidence_coverage_percentage", sig_resp.json())

        # 5. Sources
        src_resp = self.client.get("/api/v1/analytics/sources")
        self.assertEqual(src_resp.status_code, 200)
        self.assertIn("sources", src_resp.json())

        # 6. Geography
        geo_resp = self.client.get("/api/v1/analytics/geography")
        self.assertEqual(geo_resp.status_code, 200)
        self.assertIn("australian_intelligence", geo_resp.json())

        # 7. Predictions
        pred_resp = self.client.post("/api/v1/analytics/predictions/lead-priority", json={
            "company_id": self.comp_1.id
        })
        self.assertEqual(pred_resp.status_code, 200)
        self.assertIn("probability", pred_resp.json())

        # 8. Snapshots capture
        snap_resp = self.client.post("/api/v1/analytics/snapshots/capture")
        self.assertEqual(snap_resp.status_code, 201)
        self.assertEqual(snap_resp.json()["status"], "success")

        # 9. Safe DSL Query & Explain
        explain_resp = self.client.post("/api/v1/analytics/explain", json={
            "entity": "companies",
            "filters": [{"field": "country", "op": "=", "val": "Australia"}]
        })
        self.assertEqual(explain_resp.status_code, 200)
        self.assertEqual(explain_resp.json()["estimated_complexity"], "LOW")

        query_resp = self.client.post("/api/v1/analytics/query", json={
            "entity": "companies",
            "filters": [{"field": "country", "op": "=", "val": "Australia"}]
        })
        self.assertEqual(query_resp.status_code, 200)
        self.assertGreaterEqual(query_resp.json()["total_count"], 2)

        # 10. Natural Language Query
        nl_resp = self.client.post("/api/v1/analytics/nl-query", json={
            "prompt": "Show Australian companies"
        })
        self.assertEqual(nl_resp.status_code, 200)
        self.assertIn("interpretation", nl_resp.json())

        # 11. Reports & Run
        rep_resp = self.client.post("/api/v1/analytics/reports", json={
            "name": "Executive Intelligence Dashboard Report",
            "report_type": "EXECUTIVE_INTELLIGENCE"
        })
        self.assertEqual(rep_resp.status_code, 201)
        rep_id = rep_resp.json()["id"]

        run_resp = self.client.post(f"/api/v1/analytics/reports/{rep_id}/run?export_format=CSV")
        self.assertEqual(run_resp.status_code, 200)
        exec_id = run_resp.json()["id"]

        # Export CSV
        export_resp = self.client.get(f"/api/v1/analytics/reports/executions/{exec_id}/export?format_type=CSV")
        self.assertEqual(export_resp.status_code, 200)
        self.assertIn("text/csv", export_resp.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
