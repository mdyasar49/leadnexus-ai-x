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
from app.models.source import ResearchSource, SourceType
from app.models.operations import ResearchCostEvent
from app.models.decision_intelligence import (
    AnalyticsCohort,
    CohortSnapshot,
    AnalyticsSegment,
    SegmentSnapshot,
    Forecast,
    ForecastPoint,
    ForecastEvaluation,
    Scenario,
    ScenarioRun,
    ScenarioResult,
    CapacityForecast,
    QueueForecast,
    SLAForecast,
    InformationValueAssessment,
    ResearchRecommendation,
    DecisionRecommendation,
    RecommendationStatus,
    Benchmark,
    AnalyticsTarget,
    Scorecard,
    ScorecardHealth,
    DriverAnalysis,
    CorrelationAnalysis,
    Experiment,
    ExperimentResult,
    DecisionBrief,
    DecisionBriefExecution
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.decision_intelligence.cohort_engine import CohortEngine
from packages.decision_intelligence.segmentation_engine import SegmentationEngine
from packages.decision_intelligence.forecasting_engine import ForecastingEngine
from packages.decision_intelligence.scenario_engine import ScenarioEngine
from packages.decision_intelligence.capacity_sla_engine import CapacitySLAEngine
from packages.decision_intelligence.recommendation_engine import RecommendationEngine
from packages.decision_intelligence.benchmark_scorecard_engine import BenchmarkScorecardEngine
from packages.decision_intelligence.driver_correlation_engine import DriverCorrelationEngine
from packages.decision_intelligence.experiment_engine import ExperimentEngine
from packages.decision_intelligence.decision_brief_generator import DecisionBriefGenerator


class TestPhase22DecisionIntelligence(unittest.TestCase):
    """Test suite covering Phase 22 Decision Intelligence, BI, Forecasting, Cohorts & Strategic Planning."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"decision_architect_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Decision",
            last_name="Scientist",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Decision Intelligence Workspace",
            slug=f"decision-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed Companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Sydney ERP Modernization Group",
            normalized_name="sydney erp modernization group",
            domain="sydneyerp.com.au",
            country="Australia",
            industry="Software & IT",
            lead_score=92,
            status="QUALIFIED"
        )
        cls.comp_2 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Melbourne Digital Logistics",
            normalized_name="melbourne digital logistics",
            domain="melbournelogistics.com.au",
            country="Australia",
            industry="Logistics",
            lead_score=84,
            status="RESEARCHED"
        )
        cls.comp_3 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Perth Minerals Corp",
            normalized_name="perth minerals corp",
            domain="perthminerals.com.au",
            country="Australia",
            industry="Mining",
            lead_score=65,
            status="DISCOVERED"
        )
        cls.db.add(cls.comp_1)
        cls.db.add(cls.comp_2)
        cls.db.add(cls.comp_3)

        # Seed LeadScores
        cls.score_1 = LeadScore(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            lead_priority_score=92.0,
            priority_tier="P1_HIGH",
            buying_readiness_score=88.0,
            icp_fit_score=95.0,
            intent_score=90.0,
            evidence_confidence_score=90.0,
            data_quality_score=92.0
        )
        cls.score_2 = LeadScore(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_2.id,
            lead_priority_score=84.0,
            priority_tier="P1_HIGH",
            buying_readiness_score=82.0,
            icp_fit_score=85.0,
            intent_score=80.0,
            evidence_confidence_score=85.0,
            data_quality_score=88.0
        )
        cls.score_3 = LeadScore(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_3.id,
            lead_priority_score=65.0,
            priority_tier="P2_MEDIUM",
            buying_readiness_score=60.0,
            icp_fit_score=70.0,
            intent_score=55.0,
            evidence_confidence_score=65.0,
            data_quality_score=70.0
        )
        cls.db.add(cls.score_1)
        cls.db.add(cls.score_2)
        cls.db.add(cls.score_3)

        # Seed Contacts
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            full_name="Marcus Vance",
            email="marcus@sydneyerp.com.au",
            source_url="https://sydneyerp.com.au/team/marcus",
            job_title="Chief Technology Officer",
            email_status="VERIFIED",
            is_decision_maker=True,
            confidence_score=0.95
        )
        cls.db.add(cls.contact_1)

        # Seed Intent Signals
        cls.sig_1 = IntentSignal(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            signal_type="MIGRATION_INTENT",
            signal_strength=94.0,
            source_name="Careers Page",
            source_url="https://sydneyerp.com.au/careers/lead-odoo-dev",
            detected_keyword="Odoo 17 migration",
            evidence_snippet="Looking for Senior Odoo Developer to lead ERP migration"
        )
        cls.sig_2 = IntentSignal(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_2.id,
            signal_type="ERP_RESEARCH",
            signal_strength=82.0,
            source_name="Tech Blog",
            source_url="https://melbournelogistics.com.au/tech/erp-upgrade",
            detected_keyword="ERP selection",
            evidence_snippet="Evaluating top ERP platforms for distribution fleet"
        )
        cls.db.add(cls.sig_1)
        cls.db.add(cls.sig_2)

        # Seed Research Source
        cls.source_1 = ResearchSource(
            id=str(uuid.uuid4()),
            code=f"australia_jobs_{uuid.uuid4().hex[:6]}",
            key=f"australia_jobs_{uuid.uuid4().hex[:6]}",
            name="Australian Tech Jobs Collector",
            source_type=SourceType.JOB_BOARD,
            is_active=True
        )
        cls.db.add(cls.source_1)
        cls.db.commit()

        # TestClient override
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.db.close()

    # --- 1. Cohort Analytics Tests ---

    def test_01_cohort_creation_and_snapshot(self):
        engine = CohortEngine(self.db)
        cohort = engine.create_cohort(
            workspace_id=self.ws_id,
            name="Q4 2026 ERP Modernization Cohort",
            cohort_type="DISCOVERY_TIME",
            criteria={"country": "Australia"},
            period_type="MONTHLY"
        )
        self.assertIsNotNone(cohort.id)
        self.assertEqual(cohort.name, "Q4 2026 ERP Modernization Cohort")

        snapshot = engine.evaluate_cohort_snapshot(
            workspace_id=self.ws_id,
            cohort_id=cohort.id,
            period_label="OCT_2026"
        )
        self.assertIsNotNone(snapshot.id)
        self.assertGreaterEqual(snapshot.cohort_size, 3)
        self.assertGreater(snapshot.average_priority_score, 50.0)

    def test_02_cohort_intent_persistence(self):
        engine = CohortEngine(self.db)
        cohort = engine.create_cohort(
            workspace_id=self.ws_id,
            name="Intent Persistence Test Cohort",
            cohort_type="INTENT_TYPE"
        )
        persistence = engine.track_intent_persistence(self.ws_id, cohort.id)
        self.assertIn("day_0", persistence)
        self.assertIn("day_7", persistence)
        self.assertIn("day_30", persistence)
        self.assertIn("day_60", persistence)
        self.assertIn("day_90", persistence)
        self.assertEqual(persistence["day_0"]["retained_ratio"], 1.0)
        self.assertLessEqual(persistence["day_90"]["retained_ratio"], 1.0)

    # --- 2. Advanced Segmentation & Emerging Segments Tests ---

    def test_03_segmentation_and_emerging_detection(self):
        engine = SegmentationEngine(self.db)
        segment = engine.create_segment(
            workspace_id=self.ws_id,
            name="Australian Odoo Modernizers",
            segment_type="INDUSTRY_MOMENTUM",
            criteria={"country": "Australia", "industry": "Software & IT"},
            dimensions=["country", "industry"]
        )
        self.assertIsNotNone(segment.id)

        snapshot = engine.evaluate_segment_snapshot(self.ws_id, segment.id)
        self.assertGreaterEqual(snapshot.company_count, 1)
        self.assertGreaterEqual(snapshot.momentum_score, 0.0)

        emerging = engine.detect_emerging_segments(self.ws_id, min_growth_pct=5.0)
        self.assertIsInstance(emerging, list)

    # --- 3. Bounded Forecasting Tests ---

    def test_04_bounded_forecasting_and_bounds(self):
        engine = ForecastingEngine(self.db)
        history = [120.0, 135.0, 150.0, 168.0, 190.0, 215.0]
        forecast = engine.forecast_bounded(
            workspace_id=self.ws_id,
            target_metric="NEW_DISCOVERIES",
            historical_values=history,
            horizon_days=30,
            model_name="EXPONENTIAL_SMOOTHING"
        )
        self.assertIsNotNone(forecast.id)
        self.assertEqual(len(forecast.points), 30)
        # Verify confidence intervals: lower_bound <= point_forecast <= upper_bound
        for pt in forecast.points:
            self.assertLessEqual(pt.lower_bound_80, pt.point_forecast)
            self.assertGreaterEqual(pt.upper_bound_80, pt.point_forecast)

    def test_05_forecast_failure_safety_on_insufficient_data(self):
        engine = ForecastingEngine(self.db)
        history = [50.0, 55.0]  # Less than 5 required points
        forecast = engine.forecast_bounded(
            workspace_id=self.ws_id,
            target_metric="DISCOVERIES",
            historical_values=history,
            horizon_days=30
        )
        self.assertEqual(forecast.model_name, "FORECAST_UNAVAILABLE")
        self.assertEqual(len(forecast.points), 0)

    def test_06_forecast_accuracy_evaluation(self):
        engine = ForecastingEngine(self.db)
        history = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        forecast = engine.forecast_bounded(
            workspace_id=self.ws_id,
            target_metric="ACCURACY_TEST",
            historical_values=history,
            horizon_days=7
        )
        actuals = [62.0, 64.0, 67.0, 71.0, 73.0, 76.0, 80.0]
        evaluation = engine.evaluate_accuracy(self.ws_id, forecast.id, actuals)
        self.assertIsNotNone(evaluation.id)
        self.assertGreater(evaluation.mae, 0.0)
        self.assertGreater(evaluation.rmse, 0.0)
        self.assertGreater(evaluation.mape, 0.0)

    # --- 4. What-If Scenarios & Simulations Tests ---

    def test_07_scenario_simulation_no_data_mutation(self):
        engine = ScenarioEngine(self.db)
        # Snapshot existing company count
        initial_comp_count = self.db.query(Company).filter(Company.workspace_id == self.ws_id).count()

        scenario = engine.create_scenario(
            workspace_id=self.ws_id,
            name="2x Crawler Scale & 10% Cost Reduction",
            description="Testing capacity impact of doubling collection speed",
            parameters={"multiplier": 2.0}
        )
        self.assertIsNotNone(scenario.id)

        sim_res = engine.run_simulation(
            workspace_id=self.ws_id,
            scenario_id=scenario.id,
            simulated_by="analytics_architect",
            workload_multiplier=2.0,
            cost_adjustment_pct=-10.0
        )
        self.assertIsNotNone(sim_res.id)
        self.assertGreater(sim_res.simulated_discoveries, 0)
        self.assertGreater(sim_res.simulated_spend_usd, 0.0)

        # Invariant check: production company count MUST NOT have mutated
        after_comp_count = self.db.query(Company).filter(Company.workspace_id == self.ws_id).count()
        self.assertEqual(initial_comp_count, after_comp_count)

    # --- 5. Capacity Planning & SLA Risk Tests ---

    def test_08_capacity_and_sla_forecasting(self):
        engine = CapacitySLAEngine(self.db)
        capacity_forecasts = engine.evaluate_capacity_forecast(self.ws_id, horizon_days=30)
        self.assertGreaterEqual(len(capacity_forecasts), 4)  # Workers, Browser, API, DB
        for cf in capacity_forecasts:
            self.assertIn(cf.breach_risk, ["LOW", "MEDIUM", "HIGH"])

        queue_forecasts = engine.evaluate_queue_forecast(self.ws_id)
        self.assertGreaterEqual(len(queue_forecasts), 3)

        sla_forecast = engine.forecast_sla_status(
            workspace_id=self.ws_id,
            workload_type="RESEARCH_RUN",
            target_hours=24.0,
            current_queue_depth=40
        )
        self.assertIn(sla_forecast.sla_status, ["ON_TRACK", "AT_RISK", "LIKELY_BREACH"])

    # --- 6. Expected Information Value & Recommendations Tests ---

    def test_09_expected_information_value_calculation(self):
        engine = RecommendationEngine(self.db)
        eiv_assessment = engine.calculate_expected_information_value(
            workspace_id=self.ws_id,
            company_id=self.comp_1.id,
            missing_field="decision_maker",
            importance=2.0,
            prob_finding=0.85,
            estimated_cost=2.00
        )
        # EIV = (0.85 * 2.0) / 2.00 = 0.85
        self.assertEqual(eiv_assessment.expected_information_value, 0.85)

    def test_10_recommendations_and_decision_lifecycle(self):
        engine = RecommendationEngine(self.db)
        recs = engine.recommend_priority_investigations(self.ws_id)
        self.assertGreaterEqual(len(recs), 1)
        rec = recs[0]

        # Process human decision: ACCEPT
        decision = engine.process_decision(
            workspace_id=self.ws_id,
            recommendation_id=rec.id,
            action="ACCEPTED",
            decided_by="senior_researcher",
            notes="Approved for priority investigation"
        )
        self.assertEqual(decision.status, "ACCEPTED")

    # --- 7. Benchmarks, Targets & Strategic Scorecard Tests ---

    def test_11_targets_benchmarks_and_scorecard(self):
        engine = BenchmarkScorecardEngine(self.db)
        target = engine.create_or_update_target(
            workspace_id=self.ws_id,
            target_name="Lead Quality Target Q4",
            metric_code="BUYING_READINESS",
            target_value=85.0
        )
        self.assertEqual(target.target_value, 85.0)

        bm = engine.register_benchmark(
            workspace_id=self.ws_id,
            benchmark_name="High-Performing Software Leads",
            dimension="LEAD_QUALITY",
            metric_code="BUYING_READINESS",
            baseline_value=60.0,
            top_quartile_value=85.0
        )
        self.assertIsNotNone(bm.id)

        scorecard = engine.calculate_scorecard(self.ws_id)
        self.assertIsNotNone(scorecard.id)
        self.assertIn(
            scorecard.overall_health,
            [h.value for h in ScorecardHealth]
        )

    # --- 8. Drivers & Correlations Tests ---

    def test_12_statistical_drivers_and_correlations(self):
        engine = DriverCorrelationEngine(self.db)
        x = [10.0, 20.0, 30.0, 40.0, 50.0]
        y = [15.0, 25.0, 35.0, 45.0, 55.0]  # Perfect positive correlation (r=1.0)
        corr = engine.calculate_correlation(
            workspace_id=self.ws_id,
            variable_x="intent_strength",
            variable_y="buying_readiness",
            series_x=x,
            series_y=y
        )
        self.assertAlmostEqual(corr.pearson_r, 1.0, places=2)
        self.assertAlmostEqual(corr.spearman_rho, 1.0, places=2)

        driver = engine.record_driver_analysis(
            workspace_id=self.ws_id,
            target_metric="BUYING_READINESS",
            driver_feature="intent_strength",
            importance_weight=0.92,
            correlation_coeff=0.88
        )
        self.assertIsNotNone(driver.id)

    # --- 9. A/B Strategy Testing Tests ---

    def test_13_ab_experiment_and_relative_lift(self):
        engine = ExperimentEngine(self.db)
        exp = engine.create_experiment(
            workspace_id=self.ws_id,
            name="Deep Research vs Standard Discovery",
            hypothesis="Deep multi-source research increases lead qualification rate by 25%",
            strategy_a="STANDARD_DISCOVERY",
            strategy_b="DEEP_MULTI_SOURCE_RESEARCH",
            target_metric="BUYING_READINESS"
        )
        self.assertIsNotNone(exp.id)

        values_a = [70.0, 72.0, 68.0, 74.0, 71.0]
        values_b = [85.0, 88.0, 82.0, 90.0, 86.0]
        result = engine.evaluate_experiment(
            workspace_id=self.ws_id,
            experiment_id=exp.id,
            metric_name="BUYING_READINESS",
            values_a=values_a,
            values_b=values_b
        )
        self.assertGreater(result.relative_lift_pct, 15.0)
        self.assertLess(result.p_value, 0.05)
        self.assertTrue(result.statistically_significant)

    # --- 10. Strategic Decision Brief Tests ---

    def test_14_decision_brief_generation_and_execution(self):
        generator = DecisionBriefGenerator(self.db)
        brief = generator.generate_brief(
            workspace_id=self.ws_id,
            title="Executive Weekly Strategic Intelligence Brief"
        )
        self.assertIsNotNone(brief.id)
        self.assertIn("Strategic Intelligence Summary", brief.executive_summary)
        self.assertIsNotNone(brief.emerging_segments)
        self.assertIsNotNone(brief.intent_trends)
        self.assertIsNotNone(brief.source_performance)
        self.assertIsNotNone(brief.lead_quality)

        execution = generator.record_brief_execution(
            workspace_id=self.ws_id,
            brief_id=brief.id,
            executed_by="research_vp",
            export_format="MARKDOWN"
        )
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.export_format, "MARKDOWN")

    # --- 11. REST API Endpoints Tests ---

    def test_15_api_cohorts_endpoints(self):
        # Create
        res = self.client.post("/api/v1/decision-intelligence/cohorts", json={
            "name": "API Test Cohort",
            "cohort_type": "INDUSTRY",
            "criteria": {"industry": "Software & IT"},
            "period_type": "MONTHLY"
        })
        self.assertEqual(res.status_code, 200)
        cohort_id = res.json()["cohort_id"]

        # List
        res_list = self.client.get("/api/v1/decision-intelligence/cohorts")
        self.assertEqual(res_list.status_code, 200)
        self.assertIsInstance(res_list.json(), list)

        # Evaluate
        res_eval = self.client.post(f"/api/v1/decision-intelligence/cohorts/{cohort_id}/evaluate")
        self.assertEqual(res_eval.status_code, 200)
        self.assertEqual(res_eval.json()["status"], "success")

        # Persistence
        res_pers = self.client.get(f"/api/v1/decision-intelligence/cohorts/{cohort_id}/persistence")
        self.assertEqual(res_pers.status_code, 200)
        self.assertIn("intent_persistence", res_pers.json())

    def test_16_api_segments_and_emerging(self):
        # Create
        res = self.client.post("/api/v1/decision-intelligence/segments", json={
            "name": "API Segment APAC Growth",
            "segment_type": "GEOGRAPHIC_MOMENTUM",
            "criteria": {"country": "Australia"},
            "dimensions": ["country"]
        })
        self.assertEqual(res.status_code, 200)
        segment_id = res.json()["segment_id"]

        # List
        res_list = self.client.get("/api/v1/decision-intelligence/segments")
        self.assertEqual(res_list.status_code, 200)

        # Emerging
        res_em = self.client.get("/api/v1/decision-intelligence/segments/emerging")
        self.assertEqual(res_em.status_code, 200)
        self.assertIsInstance(res_em.json(), list)

    def test_17_api_forecasts_and_scenarios(self):
        # Forecast generate
        res_fc = self.client.post("/api/v1/decision-intelligence/forecasts/generate", json={
            "target_metric": "QUALIFIED_LEADS",
            "historical_values": [50.0, 58.0, 65.0, 72.0, 80.0, 91.0],
            "forecast_horizon_days": 14,
            "model_name": "EXPONENTIAL_SMOOTHING"
        })
        self.assertEqual(res_fc.status_code, 200)
        forecast_id = res_fc.json()["forecast_id"]

        # Forecast evaluate
        res_eval = self.client.post(
            f"/api/v1/decision-intelligence/forecasts/{forecast_id}/evaluate",
            json={"actual_values": [93.0, 96.0, 99.0, 102.0, 106.0, 110.0, 115.0]}
        )
        self.assertEqual(res_eval.status_code, 200)

        # Create scenario
        res_sc = self.client.post("/api/v1/decision-intelligence/scenarios", json={
            "name": "Simulation Q1 Budget Bump",
            "description": "Evaluate 1.5x throughput",
            "parameters": {"multiplier": 1.5}
        })
        self.assertEqual(res_sc.status_code, 200)
        scenario_id = res_sc.json()["scenario_id"]

        # Run scenario
        res_run = self.client.post(f"/api/v1/decision-intelligence/scenarios/{scenario_id}/run", json={
            "workload_multiplier": 1.5,
            "cost_adjustment_pct": 5.0
        })
        self.assertEqual(res_run.status_code, 200)
        self.assertIn("simulated_discoveries", res_run.json())

    def test_18_api_capacity_sla_scorecard(self):
        # Capacity
        res_cap = self.client.get("/api/v1/decision-intelligence/capacity")
        self.assertEqual(res_cap.status_code, 200)
        self.assertIsInstance(res_cap.json(), list)

        # Queues
        res_q = self.client.get("/api/v1/decision-intelligence/capacity/queues")
        self.assertEqual(res_q.status_code, 200)

        # SLA
        res_sla = self.client.get("/api/v1/decision-intelligence/capacity/sla")
        self.assertEqual(res_sla.status_code, 200)

        # Scorecard
        res_sc = self.client.get("/api/v1/decision-intelligence/scorecard")
        self.assertEqual(res_sc.status_code, 200)
        self.assertIn("overall_health", res_sc.json())

    def test_19_api_recommendations_and_briefs(self):
        # EIV
        res_eiv = self.client.post("/api/v1/decision-intelligence/recommendations/eiv", json={
            "company_id": self.comp_1.id,
            "missing_field": "tech_stack",
            "importance": 1.8,
            "prob_finding": 0.90,
            "estimated_cost": 1.50
        })
        self.assertEqual(res_eiv.status_code, 200)

        # Generate Recommendations
        res_rec = self.client.post("/api/v1/decision-intelligence/recommendations/generate")
        self.assertEqual(res_rec.status_code, 200)

        # Generate Decision Brief
        res_brief = self.client.post("/api/v1/decision-intelligence/briefs/generate", json={
            "title": "API Generated Executive Decision Brief"
        })
        self.assertEqual(res_brief.status_code, 200)
        brief_id = res_brief.json()["brief_id"]

        # Execute Brief
        res_exec = self.client.post(f"/api/v1/decision-intelligence/briefs/{brief_id}/execute", json={
            "executed_by": "api_user",
            "export_format": "PDF"
        })
        self.assertEqual(res_exec.status_code, 200)
        self.assertEqual(res_exec.json()["export_format"], "PDF")


if __name__ == "__main__":
    unittest.main()
