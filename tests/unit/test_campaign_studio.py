import unittest
import uuid
import sys
import os

# Add base monorepo and apps/api to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app


class CampaignStudioTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

        # Register administrative user
        reg_email = f"lead_researcher_{uuid.uuid4().hex[:6]}@infogenx.com.au"
        reg_payload = {
            "email": reg_email,
            "password": "SecurePassword123!",
            "first_name": "Senior",
            "last_name": "Architect",
            "organization_name": "InfogenX Lead Studio"
        }
        r = cls.client.post("/api/v1/auth/register", json=reg_payload)
        assert r.status_code == 201, f"Registration failed: {r.text}"
        data = r.json()
        token = data["tokens"]["access_token"]
        ws_id = data["active_workspace_id"]
        cls.headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": ws_id
        }

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_01_health_and_readiness(self):
        r_health = self.client.get("/health")
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json()["status"], "ok")

        r_ready = self.client.get("/ready")
        self.assertEqual(r_ready.status_code, 200)
        self.assertEqual(r_ready.json()["status"], "ready")

    def test_02_system_info(self):
        r = self.client.get("/api/v1/system/info")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["application"], "LeadNexus AI X")
        self.assertTrue(data["features"]["campaign_studio"])

    def test_03_source_registry(self):
        r = self.client.get("/api/v1/sources", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        sources = r.json()
        self.assertGreaterEqual(len(sources), 5)
        source_keys = [s["key"] for s in sources]
        self.assertIn("github", source_keys)
        self.assertIn("company_website", source_keys)

    def test_04_campaign_templates(self):
        r = self.client.get("/api/v1/campaigns/templates", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        templates = r.json()
        self.assertGreaterEqual(len(templates), 3)
        template_names = [t["name"] for t in templates]
        self.assertTrue(any("Odoo" in name for name in template_names))

    def test_05_campaign_lifecycle_and_run_orchestration(self):
        # 1. Fetch template
        templates = self.client.get("/api/v1/campaigns/templates", headers=self.headers).json()
        odoo_tpl = [t for t in templates if "Odoo" in t["name"]][0]

        # 2. Instantiate campaign
        unique_name = f"Odoo Australia Automated Run {uuid.uuid4().hex[:6]}"
        inst_payload = {
            "campaign_name": unique_name,
            "overrides": {"maximum_results": 50}
        }
        r_inst = self.client.post(f"/api/v1/campaigns/templates/{odoo_tpl['id']}/instantiate", json=inst_payload, headers=self.headers)
        self.assertEqual(r_inst.status_code, 201)
        campaign = r_inst.json()
        camp_id = campaign["id"]
        self.assertEqual(campaign["status"], "DRAFT")

        # 3. Activate campaign
        r_act = self.client.post(f"/api/v1/campaigns/{camp_id}/activate", headers=self.headers)
        self.assertEqual(r_act.status_code, 200)
        self.assertEqual(r_act.json()["status"], "ACTIVE")

        # 4. Trigger research run
        r_run = self.client.post(f"/api/v1/campaigns/{camp_id}/run", json={"trigger_type": "manual"}, headers=self.headers)
        self.assertEqual(r_run.status_code, 201)
        run = r_run.json()
        run_id = run["id"]
        self.assertEqual(run["status"], "RUNNING")
        self.assertGreater(len(run["jobs"]), 0)

        # 5. Pause run
        r_pause = self.client.post(f"/api/v1/runs/{run_id}/pause", headers=self.headers)
        self.assertEqual(r_pause.status_code, 200)
        self.assertEqual(r_pause.json()["status"], "PAUSED")

        # 6. Resume run
        r_resume = self.client.post(f"/api/v1/runs/{run_id}/resume", headers=self.headers)
        self.assertEqual(r_resume.status_code, 200)
        self.assertEqual(r_resume.json()["status"], "RUNNING")

        # 7. Cancel run
        r_cancel = self.client.post(f"/api/v1/runs/{run_id}/cancel", headers=self.headers)
        self.assertEqual(r_cancel.status_code, 200)
        self.assertEqual(r_cancel.json()["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
