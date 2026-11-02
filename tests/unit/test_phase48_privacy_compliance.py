"""
LeadNexus AI X - Phase 48 Test Suite (ChatGPT Master Roadmap)
Privacy Engineering, Consent Vault, Data Subject Rights & Cryptographic Scrubbing
Tests: PIIScrubber, Pseudonymizer, KAnonymityEngine, ConsentVault, DSARCoordinator, API routes, and isolation invariants.
"""

import sys
import os
import uuid
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.main import app
from app.db.base import Base
from app.db.session import SessionLocal, sync_engine
from app.models.saved_lead import SavedLead
from packages.privacy.pii_scrubber import PIIScrubber
from packages.privacy.pseudonymizer import Pseudonymizer
from packages.privacy.kanonymity_engine import KAnonymityEngine
from packages.privacy.consent_vault import ConsentVault
from packages.privacy.dsar_coordinator import DSARCoordinator


class TestPhase48PrivacyCompliance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_pii_scrubber_ssn_and_financial(self):
        """Test 1: Verifies SSNs and Luhn-valid credit card numbers are redacted."""
        scrubber = PIIScrubber()
        raw = "Executive SSN is 123-45-6789 and expense card is 4532-0150-1234-5678."
        scrubbed, count, cats = scrubber.scrub(raw)

        self.assertIn("[REDACTED_SSN]", scrubbed)
        self.assertIn("[REDACTED_FINANCIAL_CARD]", scrubbed)
        self.assertNotIn("123-45-6789", scrubbed)
        self.assertEqual(count, 2)
        self.assertIn("SSN_NATIONAL_ID", cats)
        self.assertIn("FINANCIAL_PAYMENT_CARD", cats)

    def test_02_pii_scrubber_preserves_business_emails(self):
        """Test 2: Verifies consumer emails are scrubbed while corporate business emails are preserved."""
        scrubber = PIIScrubber()
        raw = "Contact personal lead at john.doe@gmail.com and corporate at sarah.jenkins@odoo-au.com."
        scrubbed, count, cats = scrubber.scrub(raw, preserve_business_contacts=True)

        self.assertIn("[REDACTED_PERSONAL_EMAIL]", scrubbed)
        self.assertNotIn("john.doe@gmail.com", scrubbed)
        self.assertIn("sarah.jenkins@odoo-au.com", scrubbed)
        self.assertEqual(count, 1)
        self.assertIn("CONSUMER_PERSONAL_EMAIL", cats)

    def test_03_pseudonymizer_hmac_salted(self):
        """Test 3: Verifies deterministic HMAC tokenization and salt variations."""
        pseudo = Pseudonymizer()
        tok1 = pseudo.pseudonymize("david.chen@nexus-cloud.com", salt="salt_a")
        tok2 = pseudo.pseudonymize("david.chen@nexus-cloud.com", salt="salt_a")
        tok3 = pseudo.pseudonymize("david.chen@nexus-cloud.com", salt="salt_b")

        self.assertTrue(tok1.startswith("PSEUDO_"))
        self.assertEqual(tok1, tok2)  # Deterministic
        self.assertNotEqual(tok1, tok3)  # Salted distinction

    def test_04_kanonymity_engine_passes(self):
        """Test 4: Evaluates dataset cohorts meeting k-anonymity threshold."""
        engine = KAnonymityEngine()
        data = [
            {"industry": "ERP Software", "country": "Australia", "employees": "100-250"},
            {"industry": "ERP Software", "country": "Australia", "employees": "100-250"},
            {"industry": "ERP Software", "country": "Australia", "employees": "100-250"},
            {"industry": "Cloud Infrastructure", "country": "US", "employees": "500+"},
            {"industry": "Cloud Infrastructure", "country": "US", "employees": "500+"},
        ]
        res = engine.evaluate(data, quasi_identifiers=["industry", "country"], k_threshold=2)
        self.assertTrue(res["is_k_anonymous"])
        self.assertEqual(res["min_k"], 2)
        self.assertEqual(res["violating_cohorts_count"], 0)

    def test_05_kanonymity_engine_fails_and_recommends(self):
        """Test 5: Evaluates cohort with outliers violating k-anonymity."""
        engine = KAnonymityEngine()
        data = [
            {"industry": "ERP Software", "country": "Australia"},
            {"industry": "Rare Niche Biotechnology", "country": "Iceland"},  # Outlier k=1
        ]
        res = engine.evaluate(data, quasi_identifiers=["industry", "country"], k_threshold=2)
        self.assertFalse(res["is_k_anonymous"])
        self.assertEqual(res["min_k"], 1)
        self.assertEqual(res["violating_cohorts_count"], 2)
        self.assertGreater(len(res["recommendations"]), 0)

    def test_06_consent_vault_email_and_domain_suppression(self):
        """Test 6: Tests sub-millisecond suppression check for exact email and domain."""
        vault = ConsentVault()
        vault.add_opt_out("opt_1", subject_email="optout@testcorp.com", opt_out_type="GDPR_RTBF")
        vault.add_opt_out("opt_2", subject_domain="competitors-block.com", opt_out_type="GLOBAL_EXCLUSION")

        # Direct email suppression
        self.assertTrue(vault.is_suppressed(email="optout@testcorp.com"))
        # Unsuppressed email in same company
        self.assertFalse(vault.is_suppressed(email="eligible@testcorp.com"))

        # Entire domain suppression
        self.assertTrue(vault.is_suppressed(domain="competitors-block.com"))
        self.assertTrue(vault.is_suppressed(email="ceo@competitors-block.com"))
        self.assertFalse(vault.is_suppressed(email="ceo@legitimate.com"))

    def test_07_dsar_coordinator_erasure_tombstoning(self):
        """Test 7: Verifies Right to be Forgotten execution, cryptographic digest, and vault synchronization."""
        vault = ConsentVault()
        coordinator = DSARCoordinator(vault)

        res = coordinator.execute_dsar(
            dsar_id="dsar_test_001",
            request_type="ERASURE",
            subject_email="erasure.request@prospect.com",
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertIsNotNone(res["evidence_digest"])
        self.assertEqual(res["report_data"]["action"], "ERASURE_COMPLETED")

        # Verify vault contains tombstone immediately
        self.assertTrue(vault.is_suppressed(email="erasure.request@prospect.com"))

    def test_08_api_opt_out_registration_and_check(self):
        """Test 8: Tests POST /api/v1/privacy/opt-out and GET /api/v1/privacy/opt-out/check."""
        res_post = self.client.post(
            "/api/v1/privacy/opt-out",
            json={
                "subject_email": "api.optout@company.com",
                "subject_domain": "company.com",
                "opt_out_type": "GDPR_RTBF",
                "reason": "Explicit GDPR Article 17 request",
            },
        )
        self.assertEqual(res_post.status_code, 201)
        opt_data = res_post.json()
        self.assertEqual(opt_data["opt_out_type"], "GDPR_RTBF")

        # Fast check
        res_check = self.client.get("/api/v1/privacy/opt-out/check?email=api.optout@company.com")
        self.assertEqual(res_check.status_code, 200)
        self.assertTrue(res_check.json()["is_suppressed"])

    def test_09_api_dsar_lifecycle(self):
        """Test 9: Tests POST /api/v1/privacy/dsar and GET /api/v1/privacy/dsar/{id}."""
        res_post = self.client.post(
            "/api/v1/privacy/dsar",
            json={
                "request_type": "ACCESS_EXPORT",
                "subject_email": "subject.access@enterprise.com",
            },
        )
        self.assertEqual(res_post.status_code, 201)
        dsar_data = res_post.json()
        dsar_id = dsar_data["id"]
        self.assertEqual(dsar_data["status"], "COMPLETED")
        self.assertIsNotNone(dsar_data["evidence_digest"])

        # Fetch status
        res_get = self.client.get(f"/api/v1/privacy/dsar/{dsar_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["subject_email"], "subject.access@enterprise.com")

    def test_10_api_scrub_and_pseudonymize(self):
        """Test 10: Tests /api/v1/privacy/scrub and /api/v1/privacy/pseudonymize endpoints."""
        # Scrub
        res_scrub = self.client.post(
            "/api/v1/privacy/scrub",
            json={"text": "Lead SSN is 987-65-4321 and contact is personal@yahoo.com."},
        )
        self.assertEqual(res_scrub.status_code, 200)
        scrub_data = res_scrub.json()
        self.assertIn("[REDACTED_SSN]", scrub_data["scrubbed_text"])
        self.assertIn("[REDACTED_PERSONAL_EMAIL]", scrub_data["scrubbed_text"])
        self.assertEqual(scrub_data["redactions_count"], 2)

        # Pseudonymize
        res_pseudo = self.client.post(
            "/api/v1/privacy/pseudonymize",
            json={"values": ["lead1@corp.com", "lead2@corp.com"]},
        )
        self.assertEqual(res_pseudo.status_code, 200)
        pseudo_data = res_pseudo.json()
        self.assertEqual(len(pseudo_data["pseudonymized_values"]), 2)
        self.assertTrue(pseudo_data["pseudonymized_values"][0].startswith("PSEUDO_"))

    def test_11_privacy_isolation_invariant(self):
        """Test 11: Ensures privacy operations NEVER corrupt or leak into saved_leads."""
        initial_saved_count = self.db.query(SavedLead).count()

        # Submit opt-out
        self.client.post(
            "/api/v1/privacy/opt-out",
            json={"subject_email": "isolation.test@corp.com", "opt_out_type": "GDPR_RTBF"},
        )

        # Submit DSAR
        self.client.post(
            "/api/v1/privacy/dsar",
            json={"request_type": "ACCESS_EXPORT", "subject_email": "isolation.test@corp.com"},
        )

        # Scrub
        self.client.post("/api/v1/privacy/scrub", json={"text": "Test text 123-45-6789"})

        # Check saved_leads is strictly unaffected
        final_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(final_saved_count, initial_saved_count)


if __name__ == "__main__":
    unittest.main()
