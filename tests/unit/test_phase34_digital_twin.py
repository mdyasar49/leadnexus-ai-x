"""
LeadNexus AI X — Phase 34 Test Suite (ChatGPT Master Roadmap)
Enterprise Digital Twin & Operational Simulation Platform
STRICT INVARIANT: Simulations must NEVER mutate production data.
"""

import sys
import os
import uuid
import unittest
from fastapi.testclient import TestClient

# Ensure API and root are in python path
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
from app.models.lead import Company, Contact
from app.models.digital_twin import (
    SimulationScenario,
    SimulationRun,
    OperationalCapacityModel,
)
from app.security.tokens import create_access_token
from packages.simulation.digital_twin_engine import DigitalTwinEngine


class TestPhase34DigitalTwin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Digital Twin Org", slug="dt-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Digital Twin Workspace",
                slug="dt-ws",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="twin_admin@leadnexus.ai",
                hashed_password="mock_password",
                is_active=True,
                is_superuser=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_baseline_snapshot_capture(self):
        """Verifies capture of non-mutating baseline snapshot from DB."""
        snapshot = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        self.assertIn("total_companies", snapshot)
        self.assertIn("browser_worker_pool", snapshot)
        self.assertIn("browser_worker_utilization_pct", snapshot)
        self.assertIn("primary_region", snapshot)
        self.assertGreaterEqual(snapshot["total_companies"], 0)

    def test_02_simulation_invariant_zero_production_mutation(self):
        """CRITICAL INVARIANT: Running simulation must NEVER mutate production records."""
        initial_companies = self.db.query(Company).count()
        initial_contacts = self.db.query(Contact).count()

        # Run high-impact 10x simulation
        params = {"lead_volume_multiplier": 10.0, "ai_cost_multiplier": 4.0}
        DigitalTwinEngine.execute_run(
            db=self.db,
            tenant_id=self.workspace.id,
            executed_by=str(self.user.id),
            custom_params=params,
        )

        after_companies = self.db.query(Company).count()
        after_contacts = self.db.query(Contact).count()

        self.assertEqual(initial_companies, after_companies, "Company count must remain unchanged.")
        self.assertEqual(initial_contacts, after_contacts, "Contact count must remain unchanged.")

    def test_03_lead_volume_surge_bottleneck_detection(self):
        """Tests that a 5x lead volume surge triggers browser worker pool exhaustion."""
        baseline = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        res = DigitalTwinEngine.simulate_scenario(baseline, {"lead_volume_multiplier": 5.0})

        self.assertEqual(res["projections"]["projected_leads_hourly"], 600)
        self.assertGreater(res["projections"]["projected_worker_utilization_pct"], 100.0)
        self.assertTrue(any("Worker Pool Exhaustion" in b for b in res["bottlenecks"]))
        self.assertTrue(any("Scale Browser Worker Pool" in r for r in res["recommendations"]))

    def test_04_source_outage_degradation_modeling(self):
        """Tests that a simulated source outage reduces discovery efficiency and prescribes fallback."""
        baseline = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        res = DigitalTwinEngine.simulate_scenario(baseline, {"source_unavailable": "github"})

        self.assertEqual(res["projections"]["projected_discovery_efficiency_pct"], 65.0)
        self.assertTrue(any("Single-Source Degradation" in b for b in res["bottlenecks"]))
        self.assertTrue(any("Activate secondary syndication" in r for r in res["recommendations"]))

    def test_05_finops_ai_cost_doubling_breach(self):
        """Tests that AI cost surges simulate FinOps budget breach and recommend token pruning."""
        baseline = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        res = DigitalTwinEngine.simulate_scenario(baseline, {"ai_cost_multiplier": 3.0, "lead_volume_multiplier": 4.0})

        self.assertGreater(res["projections"]["projected_monthly_spend_usd"], baseline["monthly_budget_usd"])
        self.assertTrue(any("FinOps Budget Breach" in b for b in res["bottlenecks"]))
        self.assertTrue(any("Flash-Lite" in r for r in res["recommendations"]))

    def test_06_regional_failure_cascade_projection(self):
        """Tests that primary regional failure redirects to secondary region with failover latency delta."""
        baseline = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        res = DigitalTwinEngine.simulate_scenario(baseline, {"region_failed": "ap-southeast-2"})

        self.assertIn("Singapore", res["projections"]["active_serving_region"])
        self.assertTrue(any("Regional Outage Cascade" in b for b in res["bottlenecks"]))
        self.assertTrue(any("Pre-warm standby PostgreSQL" in r for r in res["recommendations"]))

    def test_07_verification_backlog_sla_breach(self):
        """Tests that verification backlog spike predicts SLA breach."""
        baseline = DigitalTwinEngine.capture_baseline_snapshot(self.db, self.workspace.id)
        res = DigitalTwinEngine.simulate_scenario(baseline, {"verification_backlog_multiplier": 3.5})

        self.assertGreater(res["projections"]["projected_verification_latency_sec"], 10.0)
        self.assertTrue(any("Verification SLA Breach" in b for b in res["bottlenecks"]))

    def test_08_simulation_run_persistence_and_isolation(self):
        """Verifies that simulation run outputs are safely persisted in simulation_runs table."""
        run = DigitalTwinEngine.execute_run(
            db=self.db,
            tenant_id=self.workspace.id,
            executed_by=str(self.user.id),
            custom_params={"lead_volume_multiplier": 2.5},
        )
        self.assertIsNotNone(run.id)
        self.assertEqual(run.status, "COMPLETED")
        self.assertIn("projected_leads_hourly", run.simulated_projections)

    def test_09_api_scenario_creation_and_execution(self):
        """Tests REST API endpoints for creating scenarios and running simulations."""
        # Create scenario
        create_res = self.client.post(
            "/api/v1/simulation/scenarios",
            json={
                "name": "Black Friday Traffic Surge",
                "scenario_type": "CAPACITY_TEST",
                "parameters": {"lead_volume_multiplier": 6.0},
            },
            headers=self.headers,
        )
        self.assertEqual(create_res.status_code, 201)
        scenario_id = create_res.json()["id"]

        # Run scenario
        run_res = self.client.post(f"/api/v1/simulation/scenarios/{scenario_id}/run", headers=self.headers)
        self.assertEqual(run_res.status_code, 200)
        run_data = run_res.json()
        self.assertEqual(run_data["scenario_id"], scenario_id)
        self.assertEqual(run_data["status"], "COMPLETED")

    def test_10_api_quick_what_if_and_capacity_query(self):
        """Tests quick what-if endpoint and capacity listing."""
        quick_res = self.client.post(
            "/api/v1/simulation/quick-what-if",
            json={"lead_volume_multiplier": 2.0, "ai_cost_multiplier": 1.2},
            headers=self.headers,
        )
        self.assertEqual(quick_res.status_code, 200)
        self.assertIn("simulated_projections", quick_res.json())

        cap_res = self.client.get("/api/v1/simulation/capacity", headers=self.headers)
        self.assertEqual(cap_res.status_code, 200)
        caps = cap_res.json()
        self.assertTrue(len(caps) >= 1)


if __name__ == "__main__":
    unittest.main()
