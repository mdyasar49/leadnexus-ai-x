import unittest
import os
import sys
import uuid
from unittest.mock import patch, MagicMock

# Add base monorepo and apps/api to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, init_sync_db
from app.models.tenant import Organization, Workspace
from app.models.campaign import Campaign, CampaignConfig, CampaignStatus
from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadPriorityTier, LeadScore

# Phase 16 Core Engines
from packages.scoring.icp_engine import ICPEngine
from packages.scoring.intent_engine import IntentEngine
from packages.scoring.readiness_engine import BuyingReadinessEngine
from packages.scoring.evidence_reasoner import EvidenceReasoner, LeadReasoningResult
from packages.scoring.composite_scorer import CompositeScorer
from packages.scoring.recommendation_engine import RecommendationEngine
from packages.scoring.nl_query import NaturalLanguageQueryBuilder


class Phase16AIQualificationTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_sync_db()
        cls.db = SessionLocal()
        cls.client = TestClient(app)
        cls.client.__enter__()

        # Register administrative user
        reg_email = f"ai_architect_{uuid.uuid4().hex[:6]}@infogenx.com.au"
        reg_payload = {
            "email": reg_email,
            "password": "SecurePassword123!",
            "first_name": "AI",
            "last_name": "Architect",
            "organization_name": "InfogenX AI Enterprise"
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

        # Create test company lead in DB
        cls.test_company = Company(
            workspace_id=ws_id,
            name="Pacific Retail Supplies Pty Ltd",
            normalized_name="pacific retail supplies",
            domain="pacificretail.com.au",
            website="https://www.pacificretail.com.au",
            country="Australia",
            industry="Retail & Distribution",
            employee_count_range="50-200",
            status="NEW"
        )
        cls.db.add(cls.test_company)
        cls.db.flush()

        # Add decision maker contact
        cls.test_contact = Contact(
            company_id=cls.test_company.id,
            workspace_id=ws_id,
            full_name="Marcus Vance",
            job_title="IT Director & ERP Lead",
            email="m.vance@pacificretail.com.au",
            email_status="PUBLICLY_LISTED",
            business_phone="+61 2 9876 5432",
            phone_status="PUBLICLY_LISTED",
            source_url="https://www.pacificretail.com.au/team"
        )
        cls.db.add(cls.test_contact)

        # Add high-intent signal
        cls.test_signal = IntentSignal(
            company_id=cls.test_company.id,
            workspace_id=ws_id,
            source_name="github",
            source_url="https://github.com/OCA/pos/issues/999",
            signal_type="GITHUB_INTENT_SIGNAL",
            detected_keyword="looking for Odoo partner",
            evidence_snippet="We are actively looking for an Odoo partner in Sydney to assist with migrating from v14 to v17.",
            signal_strength=1.5,
            raw_data={"evidence_hash": "a1b2c3d4e5f6", "detected_keyword": "looking for Odoo partner", "source_name": "github"}
        )
        cls.db.add(cls.test_signal)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.db.close()

    # ----------------------------------------------------
    # 1. ICP Intelligence Engine Tests
    # ----------------------------------------------------
    def test_01_icp_fit_evaluation_strong_match(self):
        comp = {
            "name": "Acme Retail",
            "country": "Australia",
            "industry": "Retail",
            "technologies": ["Odoo", "Shopify"],
            "contacts": [{"job_title": "IT Manager"}],
            "employee_count_range": "50-200"
        }
        res = ICPEngine.evaluate_fit(comp)
        self.assertGreaterEqual(res["icp_fit_score"], 80.0)
        self.assertTrue(res["is_target_fit"])
        self.assertEqual(len(res["components"]), 5)

    def test_02_icp_fit_weak_geography_mismatch(self):
        comp = {
            "name": "Foreign Corp",
            "country": "Brazil",
            "industry": "Agriculture",
            "technologies": ["Legacy SAP"],
            "contacts": []
        }
        res = ICPEngine.evaluate_fit(comp)
        self.assertLess(res["icp_fit_score"], 50.0)
        self.assertFalse(res["is_target_fit"])

    # ----------------------------------------------------
    # 2. Intent Context & Taxonomy Tests
    # ----------------------------------------------------
    def test_03_intent_engine_detects_high_buying_intent(self):
        signals = [
            {
                "detected_keyword": "looking for an Odoo partner",
                "evidence_snippet": "We are seeking an Odoo partner in Sydney for migration",
                "source_name": "github",
                "evidence_hash": "hash_123"
            }
        ]
        res = IntentEngine.assess_company_intent(signals, company_text_corpus="Pacific retail enterprise.")
        self.assertGreaterEqual(res["intent_score"], 85.0)
        self.assertEqual(res["primary_intent"], "BUYING_INTENT")
        self.assertFalse(res["is_service_provider"])

    def test_04_intent_engine_classifies_service_provider_false_positive(self):
        # Service provider phrasing should be classified as negative intent
        vendor_corpus = "We provide Odoo implementation services and custom module development for our clients."
        signals = [{"detected_keyword": "Odoo implementation", "source_name": "web"}]
        res = IntentEngine.assess_company_intent(signals, company_text_corpus=vendor_corpus)
        self.assertTrue(res["is_service_provider"])
        self.assertEqual(res["primary_intent"], "SERVICE_PROVIDER")
        self.assertLessEqual(res["intent_score"], 15.0)

    def test_05_temporal_decay_model(self):
        # 2 days old -> very fresh
        recent_date = "2026-10-29T10:00:00Z"
        decay_recent = IntentEngine.calculate_temporal_decay(recent_date)
        self.assertGreaterEqual(decay_recent, 0.95)

        # 250 days old -> stale
        old_date = "2025-10-01T10:00:00Z"
        decay_old = IntentEngine.calculate_temporal_decay(old_date)
        self.assertLessEqual(decay_old, 0.30)

    # ----------------------------------------------------
    # 3. Buying Readiness & Evidence Reasoning
    # ----------------------------------------------------
    def test_06_buying_readiness_scoring(self):
        comp = {
            "signals": [{"signal_type": "HIRING_SIGNAL"}],
            "contacts": [{"job_title": "CTO"}]
        }
        intent_data = {"primary_intent": "BUYING_INTENT", "corroboration_count": 2}
        readiness = BuyingReadinessEngine.evaluate_readiness(comp, intent_data)
        self.assertGreaterEqual(readiness["buying_readiness_score"], 80.0)
        self.assertEqual(readiness["timeline_indicator"], "IMMEDIATE")

    def test_07_evidence_reasoner_structured_output(self):
        comp = {
            "name": "Pacific Retail",
            "domain": "pacificretail.com.au",
            "signals": [{"evidence_hash": "hash_aaa"}],
            "contacts": [{"job_title": "IT Director"}]
        }
        icp_data = {"icp_fit_score": 90.0}
        intent_data = {"intent_score": 92.0, "primary_intent": "BUYING_INTENT", "secondary_intents": []}
        readiness_data = {"buying_readiness_score": 85.0, "has_decision_maker_identified": True}

        res = EvidenceReasoner.reason_over_lead(comp, icp_data, intent_data, readiness_data)
        self.assertIsInstance(res, LeadReasoningResult)
        self.assertEqual(res.primary_intent, "BUYING_INTENT")
        self.assertIn("hash_aaa", res.positive_evidence_ids)
        self.assertEqual(len(res.contradictions), 0)

    # ----------------------------------------------------
    # 4. Composite Scoring & Explainable Priority
    # ----------------------------------------------------
    def test_08_composite_scorer_priority_tier_assignment(self):
        comp = {
            "name": "Target Lead",
            "domain": "targetlead.com.au",
            "country": "Australia",
            "signals": [{"evidence_hash": "hash_1"}, {"evidence_hash": "hash_2"}],
            "contacts": [{"job_title": "CTO", "email_status": "PUBLICLY_LISTED", "business_phone": "+61298765432"}]
        }
        icp_data = {"icp_fit_score": 95.0}
        intent_data = {"intent_score": 90.0, "primary_intent": "BUYING_INTENT", "temporal_decay_factor": 1.0}
        readiness_data = {"buying_readiness_score": 85.0, "has_decision_maker_identified": True}

        score_res = CompositeScorer.calculate_lead_score(comp, icp_data, intent_data, readiness_data)
        self.assertGreaterEqual(score_res["lead_priority_score"], 80.0)
        self.assertEqual(score_res["priority_tier"], LeadPriorityTier.P0_CRITICAL.value)
        self.assertGreater(len(score_res["positive_factors"]), 2)

    def test_09_recommendation_engine_next_best_action(self):
        # Missing decision maker should recommend executive research
        comp = {"name": "No DM Corp", "business_phone": "+6123456789"}
        score_data = {"components": {"contact_quality_score": 20.0, "freshness_score": 90.0}}
        rec = RecommendationEngine.determine_next_action(comp, score_data, gaps=[])
        self.assertEqual(rec["recommended_action"], "RESEARCH_DECISION_MAKER")
        self.assertGreater(rec["expected_information_value"], 10.0)

    # ----------------------------------------------------
    # 5. Natural Language Safe Query Builder
    # ----------------------------------------------------
    def test_10_nl_query_safe_translation(self):
        nl = "Find Australian companies with strong Odoo migration intent and decision maker"
        res = NaturalLanguageQueryBuilder.parse_query(nl)
        self.assertTrue(res["is_safe"])
        self.assertEqual(res["execution_mode"], "PARAMETERIZED_FILTER")
        filters = res["structured_filters"]
        self.assertEqual(filters["country"], "Australia")
        self.assertEqual(filters["technology"], "Odoo")
        self.assertGreaterEqual(filters["intent_min"], 70.0)
        self.assertTrue(filters["has_decision_maker"])

    # ----------------------------------------------------
    # 6. REST API Endpoints Verification
    # ----------------------------------------------------
    def test_11_api_qualify_and_explain_lead(self):
        # Execute lead qualification
        r = self.client.post(f"/api/v1/ai/qualify/{self.test_company.id}", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["lead_id"], self.test_company.id)
        self.assertIn("lead_priority_score", data)
        self.assertIn("priority_tier", data)

        # Get granular explanation
        r_exp = self.client.get(f"/api/v1/scoring/explanation/{self.test_company.id}", headers=self.headers)
        self.assertEqual(r_exp.status_code, 200)
        exp_data = r_exp.json()
        self.assertEqual(len(exp_data["components"]), 8)
        self.assertIn("positive_factors", exp_data)

    def test_12_api_ai_reasoning_and_intent(self):
        r_reason = self.client.get(f"/api/v1/ai/reason/{self.test_company.id}", headers=self.headers)
        self.assertEqual(r_reason.status_code, 200)
        reason_data = r_reason.json()
        self.assertIn("primary_intent", reason_data)
        self.assertIn("reasoning_summary", reason_data)

        r_intent = self.client.get(f"/api/v1/intelligence/intent/{self.test_company.id}", headers=self.headers)
        self.assertEqual(r_intent.status_code, 200)
        self.assertIn("intent_score", r_intent.json())

    def test_13_api_icp_profile_management(self):
        icp_payload = {
            "name": "Mid-Market Odoo Australia",
            "target_industries": ["Retail", "Manufacturing"],
            "target_countries": ["Australia"],
            "target_technologies": ["Odoo"],
            "target_job_titles": ["CTO", "IT Director"]
        }
        r = self.client.post("/api/v1/icp/profiles", json=icp_payload, headers=self.headers)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["name"], "Mid-Market Odoo Australia")

    def test_14_api_nl_search_and_model_catalog(self):
        r_search = self.client.post(
            "/api/v1/ai/nl-search",
            json={"query": "Find Australian Odoo leads with high intent"},
            headers=self.headers
        )
        self.assertEqual(r_search.status_code, 200)
        self.assertEqual(r_search.json()["structured_filters"]["country"], "Australia")

        r_models = self.client.get("/api/v1/ai/models", headers=self.headers)
        self.assertEqual(r_models.status_code, 200)
        self.assertGreaterEqual(len(r_models.json()["available_models"]), 2)


if __name__ == "__main__":
    unittest.main()

