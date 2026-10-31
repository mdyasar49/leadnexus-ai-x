"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering & Cost Optimization Unit Tests
Verifies zero-offset keyset pagination, priority admission control, load shedding,
latency percentiles (p50, p90, p95, p99), dynamic AI model routing, and capacity forecasting.
"""

import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.db.base import Base
from app.db.session import sync_engine, SessionLocal
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.lead import Company
from app.models.performance import (
    AdmissionControlPolicy,
    AIModelCostRecord,
    InfrastructureCapacityForecast,
    LatencyMetricSnapshot,
    ModelTier,
    PriorityTier,
)
from packages.performance.admission_control_service import (
    AdmissionControlService,
)
from packages.performance.ai_model_router_and_cost import (
    AIModelRouterAndCostEngine,
)
from packages.performance.infrastructure_capacity_forecaster import (
    InfrastructureCapacityForecaster,
)
from packages.performance.keyset_pagination import (
    CursorPage,
    KeysetPaginationEngine,
)
from packages.performance.latency_profiler import LatencyProfiler


class TestPhase31Performance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Performance Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Performance Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="perf_lead@leadnexus.test",
                name="Performance Lead Engineer",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

        # Seed sample test companies for keyset pagination
        existing_companies = cls.db.query(Company).filter(Company.workspace_id == cls.workspace.id).count()
        if existing_companies < 15:
            for i in range(15):
                comp = Company(
                    id=f"comp_{i:04d}",
                    workspace_id=cls.workspace.id,
                    name=f"Enterprise Company {i:04d}",
                    normalized_name=f"enterprise company {i:04d}",
                    domain=f"company{i:04d}.test",
                )
                cls.db.add(comp)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. Keyset Pagination Engine ---

    def test_01_keyset_cursor_encode_decode(self):
        cursor = KeysetPaginationEngine.encode_cursor("comp_0010", "2026-10-31")
        self.assertIsInstance(cursor, str)
        last_id, last_sort = KeysetPaginationEngine.decode_cursor(cursor)
        self.assertEqual(last_id, "comp_0010")
        self.assertEqual(last_sort, "2026-10-31")

    def test_02_keyset_pagination_first_page(self):
        query = self.db.query(Company).filter(Company.workspace_id == self.workspace.id)
        page = KeysetPaginationEngine.paginate(
            query=query,
            model_cls=Company,
            cursor=None,
            limit=5,
            sort_field_name="id",
            ascending=True,
        )
        self.assertEqual(len(page.items), 5)
        self.assertTrue(page.has_next_page)
        self.assertIsNotNone(page.next_cursor)
        self.assertEqual(page.items[0].id, "comp_0000")

    def test_03_keyset_pagination_next_page(self):
        query = self.db.query(Company).filter(Company.workspace_id == self.workspace.id)
        page1 = KeysetPaginationEngine.paginate(query=query, model_cls=Company, cursor=None, limit=5)
        page2 = KeysetPaginationEngine.paginate(query=query, model_cls=Company, cursor=page1.next_cursor, limit=5)

        self.assertEqual(len(page2.items), 5)
        # Ensure zero overlap
        page1_ids = {c.id for c in page1.items}
        page2_ids = {c.id for c in page2.items}
        self.assertEqual(len(page1_ids.intersection(page2_ids)), 0)
        self.assertEqual(page2.items[0].id, "comp_0005")

    def test_04_keyset_pagination_last_page(self):
        query = self.db.query(Company).filter(Company.workspace_id == self.workspace.id)
        page = KeysetPaginationEngine.paginate(query=query, model_cls=Company, cursor=None, limit=50)
        # We only seeded 15 items, so 50 will consume all
        self.assertFalse(page.has_next_page)
        self.assertIsNone(page.next_cursor)

    # --- 2. Admission Control & Load Shedding ---

    def test_05_admission_control_get_or_create_policy(self):
        service = AdmissionControlService(self.db)
        p0 = service.get_or_create_policy(PriorityTier.P0_CRITICAL)
        self.assertEqual(p0.priority_tier, PriorityTier.P0_CRITICAL.value)
        self.assertEqual(p0.max_concurrency, 200)

    def test_06_admission_control_admit_and_release(self):
        service = AdmissionControlService(self.db)
        policy = service.get_or_create_policy(PriorityTier.P1_HIGH)
        initial_active = policy.current_active

        admitted, err = service.request_admission(PriorityTier.P1_HIGH)
        self.assertTrue(admitted)
        self.assertIsNone(err)

        self.db.refresh(policy)
        self.assertEqual(policy.current_active, initial_active + 1)

        service.release_admission(PriorityTier.P1_HIGH)
        self.db.refresh(policy)
        self.assertEqual(policy.current_active, initial_active)

    def test_07_admission_control_concurrency_cap(self):
        service = AdmissionControlService(self.db)
        policy = service.get_or_create_policy(PriorityTier.P2_BACKGROUND)
        policy.max_concurrency = 2
        policy.current_active = 2
        self.db.commit()

        admitted, err = service.request_admission(PriorityTier.P2_BACKGROUND)
        self.assertFalse(admitted)
        self.assertIn("Concurrency limit reached", err)

        # Reset active
        policy.current_active = 0
        policy.max_concurrency = 50
        self.db.commit()

    def test_08_admission_control_load_shedding_p2_rejected(self):
        service = AdmissionControlService(self.db)
        service.set_load_shedding(PriorityTier.P2_BACKGROUND, active=True)

        admitted, err = service.request_admission(PriorityTier.P2_BACKGROUND)
        self.assertFalse(admitted)
        self.assertIn("Load shedding active", err)

        # Deactivate
        service.set_load_shedding(PriorityTier.P2_BACKGROUND, active=False)
        admitted_after, _ = service.request_admission(PriorityTier.P2_BACKGROUND)
        self.assertTrue(admitted_after)
        service.release_admission(PriorityTier.P2_BACKGROUND)

    def test_09_admission_control_load_shedding_p0_admitted(self):
        service = AdmissionControlService(self.db)
        service.set_load_shedding(PriorityTier.P0_CRITICAL, active=True)

        # P0 critical requests are never dropped by shedding unless hard cap reached
        admitted, _ = service.request_admission(PriorityTier.P0_CRITICAL)
        self.assertTrue(admitted)
        service.release_admission(PriorityTier.P0_CRITICAL)

    # --- 3. Latency Profiler ---

    def test_10_latency_profiler_percentiles_calculation(self):
        # 100 samples from 1ms to 100ms
        samples = [float(i) for i in range(1, 101)]
        res = LatencyProfiler.calculate_percentiles(samples)
        self.assertEqual(res["p50"], 50.0)
        self.assertEqual(res["p90"], 90.0)
        self.assertEqual(res["p95"], 95.0)
        self.assertEqual(res["p99"], 99.0)
        self.assertEqual(res["max"], 100.0)

    def test_11_latency_profiler_empty_samples(self):
        res = LatencyProfiler.calculate_percentiles([])
        self.assertEqual(res["p50"], 0.0)
        self.assertEqual(res["max"], 0.0)

    def test_12_latency_profiler_create_snapshot(self):
        profiler = LatencyProfiler(self.db)
        samples = [1.5, 2.0, 3.8, 12.4, 25.0]
        now = datetime.now(timezone.utc)
        snap = profiler.create_snapshot("db_test_lookup", samples, now - timedelta(minutes=5), now)
        self.assertEqual(snap.sample_count, 5)
        self.assertEqual(snap.operation_name, "db_test_lookup")
        self.assertEqual(snap.max_ms, 25.0)

    # --- 4. AI Model Router & Cost Engine ---

    def test_13_ai_model_router_task_complexity_mapping(self):
        tier1, model1 = AIModelRouterAndCostEngine.route_task("signal_parsing")
        self.assertEqual(tier1, ModelTier.CHEAP_FAST)
        self.assertEqual(model1, "gemini-1.5-flash-8b")

        tier2, model2 = AIModelRouterAndCostEngine.route_task("company_summarization")
        self.assertEqual(tier2, ModelTier.BALANCED)
        self.assertEqual(model2, "gemini-1.5-flash")

        tier3, model3 = AIModelRouterAndCostEngine.route_task("multi_hop_reasoning")
        self.assertEqual(tier3, ModelTier.PREMIUM)
        self.assertEqual(model3, "gemini-1.5-pro")

    def test_14_ai_model_router_cost_calculation(self):
        cost_fast = AIModelRouterAndCostEngine.calculate_cost(ModelTier.CHEAP_FAST, 1000, 500)
        self.assertAlmostEqual(cost_fast, 0.0001125, places=5)

        cost_pro = AIModelRouterAndCostEngine.calculate_cost(ModelTier.PREMIUM, 1000, 1000)
        self.assertAlmostEqual(cost_pro, 0.00625, places=5)

    def test_15_ai_model_router_record_usage(self):
        engine = AIModelRouterAndCostEngine(self.db)
        record = engine.record_usage(
            workspace_id=self.workspace.id,
            task_type="company_attribute_extraction",
            prompt_tokens=800,
            completion_tokens=250,
            latency_ms=210,
        )
        self.assertEqual(record.model_tier, ModelTier.BALANCED.value)
        self.assertGreater(record.cost_usd, 0.0)
        self.assertEqual(record.latency_ms, 210)

    # --- 5. Infrastructure Capacity Forecaster ---

    def test_16_infrastructure_capacity_forecaster_projections(self):
        forecaster = InfrastructureCapacityForecaster(self.db)
        forecast = forecaster.generate_forecast(
            metric_name="PRIMARY_DATABASE_STORAGE_GB",
            current_value=100.0,
            monthly_growth_rate_pct=10.0,
        )
        # 100 * 1.10 = 110.0
        self.assertEqual(forecast.projected_30d, 110.0)
        # 100 * (1.10)^3 = 133.1
        self.assertEqual(forecast.projected_90d, 133.1)
        self.assertEqual(forecast.growth_rate_pct, 10.0)


if __name__ == "__main__":
    unittest.main()
