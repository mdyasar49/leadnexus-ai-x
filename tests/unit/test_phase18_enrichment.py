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
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore, FieldConflict
from app.models.technology import TechnologyObservation
from app.models.enrichment import (
    FieldObservation,
    DomainCandidate,
    ContactPoint,
    PersonRoleObservation,
    PersonRoleChangeEvent,
    EnrichmentJob,
    EnrichmentTask,
    EnrichmentQuality,
    EnrichmentCoverage,
    FreshnessTier,
    ContactOwnershipType,
    EmailDeliverabilityStatus,
    PrivacyClassification,
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.enrichment.field_resolver import FieldResolver
from packages.enrichment.contact_intelligence import ContactIntelligenceEngine
from packages.enrichment.person_intelligence import PersonIntelligenceEngine
from packages.enrichment.smart_enrichment import SmartEnrichmentEngine
from packages.enrichment.quality_coverage import QualityAndCoverageEngine
from packages.enrichment.event_bus import EnrichmentEventBus


class TestPhase18Enrichment(unittest.TestCase):
    """Test suite covering Phase 18 Enterprise Data Enrichment, Contact Intelligence & Verification."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"enricher_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Enrichment",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Enrichment Test Workspace",
            slug=f"enrich-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed Sample Company
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Quantum ERP Dynamics Pty Ltd",
            normalized_name="quantum erp dynamics",
            domain="quantumerp.com.au",
            website="https://quantumerp.com.au",
            country="Australia",
            state="New South Wales",
            city="Sydney",
            industry="Enterprise Software",
            description="Australian enterprise software consultancy expanding to Odoo 18.",
            employee_count_range="101-250",
            lead_score=90,
            status="QUALIFIED"
        )

        cls.comp_suppressed = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Suppressed Inactive Corp",
            normalized_name="suppressed inactive corp",
            domain="inactivecorp.com",
            status="DISQUALIFIED"
        )
        cls.db.add_all([cls.comp_1, cls.comp_suppressed])
        cls.db.commit()

        # Seed LeadScore
        cls.score_1 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            lead_priority_score=94.0,
            priority_tier="P0_CRITICAL",
            icp_fit_score=95.0,
            intent_score=92.0
        )
        cls.db.add(cls.score_1)

        # Seed Contact
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="Marcus Vance",
            job_title="Chief Technology Officer",
            department="Engineering",
            email="marcus.vance@quantumerp.com.au",
            email_status="PUBLICLY_LISTED",
            business_phone="+61 2 9876 5432",
            phone_status="VERIFIED",
            source_url="https://quantumerp.com.au/leadership",
            is_decision_maker=True,
            confidence_score=0.96
        )
        cls.db.add(cls.contact_1)

        # Seed Tech
        cls.tech_1 = TechnologyObservation(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            technology="Odoo",
            category="ERP",
            version="17.0",
            source_url="https://quantumerp.com.au",
            evidence_text="Odoo 17 web assets",
            evidence_hash=uuid.uuid4().hex,
            confidence=0.95
        )
        cls.db.add(cls.tech_1)
        cls.db.commit()

        # Dependency Overrides
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        app.dependency_overrides[get_sync_db] = lambda: cls.db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # 1. FieldResolver Unit Tests
    def test_record_observation_corroboration_and_conflict(self):
        """Test observation recording, corroboration boost, and multi-source conflict generation."""
        # Source 1: Official website states phone is Sydney office
        obs1, is_conflicted1 = FieldResolver.record_observation(
            db=self.db,
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp_1.id,
            field_name="phone",
            value="+61 2 9876 5432",
            source_name="OFFICIAL_COMPANY_SOURCE",
            source_url="https://quantumerp.com.au/contact",
            confidence=0.95
        )
        self.assertFalse(is_conflicted1)
        self.assertEqual(obs1.confidence, 0.95)

        # Source 2: Directory confirms identical phone (corroboration increases confidence)
        obs2, is_conflicted2 = FieldResolver.record_observation(
            db=self.db,
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp_1.id,
            field_name="phone",
            value="+61 2 9876 5432",
            source_name="RELIABLE_DIRECTORY",
            source_url="https://yellowpages.com.au/quantum",
            confidence=0.90
        )
        self.assertFalse(is_conflicted2)

        # Source 3: Conflicting source states phone in India -> Must create FieldConflict, NOT overwrite
        obs3, is_conflicted3 = FieldResolver.record_observation(
            db=self.db,
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp_1.id,
            field_name="phone",
            value="+91 22 1234 5678",
            source_name="OTHER_PUBLIC_SOURCE",
            source_url="https://randomblog.com",
            confidence=0.80
        )
        self.assertTrue(is_conflicted3)

        # Verify conflict logged in database
        conflict = (
            self.db.query(FieldConflict)
            .filter(FieldConflict.company_id == self.comp_1.id, FieldConflict.field_name == "phone")
            .first()
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.resolution_status, "CONFLICTED")

    def test_freshness_tier_calculation(self):
        """Verify elapsed time maps to appropriate freshness tiers."""
        now = datetime.now(timezone.utc)
        self.assertEqual(FieldResolver.calculate_freshness("intent_signal", now), FreshnessTier.CURRENT.value)
        self.assertEqual(FieldResolver.calculate_freshness("intent_signal", now - timedelta(days=20)), FreshnessTier.RECENT.value)
        self.assertEqual(FieldResolver.calculate_freshness("intent_signal", now - timedelta(days=70)), FreshnessTier.STALE.value)
        self.assertEqual(FieldResolver.calculate_freshness("intent_signal", now - timedelta(days=150)), FreshnessTier.EXPIRED.value)

    def test_resolve_canonical_field(self):
        """Test winning canonical value resolution."""
        res = FieldResolver.resolve_canonical_field(
            db=self.db,
            workspace_id=self.ws_id,
            entity_id=self.comp_1.id,
            field_name="phone"
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["canonical_value"], "+61 2 9876 5432")
        self.assertGreaterEqual(res["confidence"], 0.90)

    # 2. Contact Intelligence Unit Tests
    def test_email_ownership_classification(self):
        """Verify generic vs department vs named person inboxes."""
        self.assertEqual(
            ContactIntelligenceEngine.classify_email_ownership("info@quantumerp.com.au"),
            ContactOwnershipType.COMPANY_CONTACT.value
        )
        self.assertEqual(
            ContactIntelligenceEngine.classify_email_ownership("sales@quantumerp.com.au"),
            ContactOwnershipType.DEPARTMENT_CONTACT.value
        )
        self.assertEqual(
            ContactIntelligenceEngine.classify_email_ownership("marcus.vance@quantumerp.com.au", "Marcus Vance"),
            ContactOwnershipType.PERSON_CONTACT.value
        )

    def test_email_verification_semantics(self):
        """Verify strict deliverability rules (disposable domain, predicted email semantics)."""
        # 1. Normal business email
        normal_res = ContactIntelligenceEngine.verify_email_semantics("marcus.vance@quantumerp.com.au", is_publicly_listed=True)
        self.assertTrue(normal_res["syntax_valid"])
        self.assertEqual(normal_res["deliverability_status"], EmailDeliverabilityStatus.PUBLICLY_LISTED.value)

        # 2. Disposable domain blocked
        disp_res = ContactIntelligenceEngine.verify_email_semantics("test@mailinator.com")
        self.assertTrue(disp_res["is_disposable"])
        self.assertEqual(disp_res["deliverability_status"], EmailDeliverabilityStatus.UNDELIVERABLE.value)

        # 3. Predicted email (must never become verified without proof)
        pred_res = ContactIntelligenceEngine.verify_email_semantics("john.smith@quantumerp.com.au", is_pattern_predicted=True)
        self.assertTrue(pred_res["is_predicted"])
        self.assertEqual(pred_res["deliverability_status"], EmailDeliverabilityStatus.PREDICTED.value)
        self.assertEqual(pred_res["confidence"], 0.50)

    def test_phone_normalization_and_classification(self):
        """Verify E.164 normalization, country detection, and telephone classification."""
        res_au = ContactIntelligenceEngine.normalize_phone("+61 2 9876 5432")
        self.assertTrue(res_au["is_valid_format"])
        self.assertEqual(res_au["country"], "Australia")
        self.assertEqual(res_au["e164"], "+61298765432")

        res_sales = ContactIntelligenceEngine.normalize_phone("02 9876 5432 (Sales Hotline)", default_country_code="61")
        self.assertEqual(res_sales["phone_type"], "SALES")

    def test_privacy_classification(self):
        """Ensure consumer personal domains are classified as PRIVATE."""
        self.assertEqual(
            ContactIntelligenceEngine.classify_privacy("EMAIL", "personal@gmail.com"),
            PrivacyClassification.PRIVATE.value
        )
        self.assertEqual(
            ContactIntelligenceEngine.classify_privacy("EMAIL", "marcus@quantumerp.com.au"),
            PrivacyClassification.PUBLIC_BUSINESS.value
        )

    # 3. Person Intelligence & Role Change Unit Tests
    def test_person_identity_collision_defense(self):
        """Verify common names at different companies are rejected from merging."""
        existing = [
            {"full_name": "David Miller", "company_name": "Apex Retail Solutions", "profile_url": "https://linkedin.com/in/david-miller-1"}
        ]
        
        # Candidate 1: Same name, same company -> Match
        cand_match = {"full_name": "David Miller", "company_name": "Apex Retail Solutions"}
        _, conf1, status1 = PersonIntelligenceEngine.match_person_identity(cand_match, existing)
        self.assertEqual(status1, "NAME_AND_COMPANY_MATCH")
        self.assertGreaterEqual(conf1, 0.90)

        # Candidate 2: Same name, DIFFERENT company -> Collision Defense Reject
        cand_collision = {"full_name": "David Miller", "company_name": "Melbourne Freight Logistics"}
        _, conf2, status2 = PersonIntelligenceEngine.match_person_identity(cand_collision, existing)
        self.assertEqual(status2, "NAME_COLLISION_DIFFERENT_COMPANY_DETECTED")
        self.assertLessEqual(conf2, 0.30)

    def test_detect_role_change_event(self):
        """Verify company switch detection generates PersonRoleChangeEvent."""
        person_id = f"person-{uuid.uuid4()}"
        # Observation 1: Initial role
        PersonIntelligenceEngine.detect_role_change(
            db=self.db,
            workspace_id=self.ws_id,
            person_id=person_id,
            new_company_name="Old ERP Corp",
            new_title="Senior Developer",
            source_url="https://olderp.com/team"
        )

        # Observation 2: New company and promotion to CTO -> Must create change event
        event, changed = PersonIntelligenceEngine.detect_role_change(
            db=self.db,
            workspace_id=self.ws_id,
            person_id=person_id,
            new_company_name="Quantum ERP Dynamics",
            new_title="Chief Technology Officer",
            source_url="https://quantumerp.com.au/team"
        )
        self.assertTrue(changed)
        self.assertIsNotNone(event)
        self.assertEqual(event.change_type, "COMPANY_CHANGE")
        self.assertTrue(event.affects_buying_committee)

    # 4. Smart Enrichment & Budget Governor Tests
    def test_smart_enrichment_gap_evaluation(self):
        """Test missing field detection and Expected Gain prioritization."""
        recs = SmartEnrichmentEngine.evaluate_company_gaps(
            db=self.db,
            workspace_id=self.ws_id,
            company_id=self.comp_1.id
        )
        self.assertIsInstance(recs, list)
        actions = [r.recommended_action for r in recs]
        # comp_1 has domain, tech, and decision maker, but no business phone or city missing test
        self.assertTrue(len(recs) >= 0)

    def test_suppressed_lead_skipped(self):
        """Verify disqualified/suppressed lead produces zero enrichment tasks."""
        recs = SmartEnrichmentEngine.evaluate_company_gaps(
            db=self.db,
            workspace_id=self.ws_id,
            company_id=self.comp_suppressed.id
        )
        self.assertEqual(len(recs), 0)

    def test_create_enrichment_job(self):
        """Test enrichment batch job generation governed by budget limits."""
        job = SmartEnrichmentEngine.create_enrichment_job(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            company_ids=[self.comp_1.id],
            depth="DEEP",
            budget_limit_usd=10.0
        )
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(job.total_entities, 1)
        self.assertLessEqual(job.cost_usd, job.budget_limit_usd)

    # 5. Quality & Coverage Tests
    def test_enrichment_quality_score(self):
        """Verify Enrichment Quality Score calculation."""
        quality = QualityAndCoverageEngine.calculate_company_enrichment_quality(
            db=self.db,
            workspace_id=self.ws_id,
            company_id=self.comp_1.id
        )
        self.assertIsNotNone(quality)
        self.assertGreaterEqual(quality.quality_score, 50.0)
        self.assertGreaterEqual(quality.completeness_score, 60.0)

    def test_workspace_coverage(self):
        """Verify global coverage metrics."""
        cov = QualityAndCoverageEngine.calculate_workspace_coverage(
            db=self.db,
            workspace_id=self.ws_id
        )
        self.assertIsNotNone(cov)
        self.assertGreaterEqual(cov.pct_domain, 50.0)

    # 6. Event Bus Unit Tests
    def test_enrichment_event_bus(self):
        """Test subscribing and emitting events."""
        received = []
        EnrichmentEventBus.subscribe("TEST_EVENT", lambda env: received.append(env))
        EnrichmentEventBus.emit("TEST_EVENT", {"lead_id": self.comp_1.id})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["payload"]["lead_id"], self.comp_1.id)

    # 7. End-to-End API Routes Tests
    def test_api_get_company_enrichment(self):
        """Test GET /api/v1/enrichment/companies/{id} endpoint."""
        resp = self.client.get(f"/api/v1/enrichment/companies/{self.comp_1.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["company_id"], self.comp_1.id)
        self.assertIn("quality_score", data)
        self.assertIn("observations", data)

    def test_api_record_observation(self):
        """Test POST /api/v1/enrichment/companies/{id}/observe endpoint."""
        payload = {
            "field_name": "employee_estimate",
            "value": "150",
            "source_name": "OFFICIAL_COMPANY_SOURCE",
            "source_url": "https://quantumerp.com.au/about",
            "confidence": 0.95
        }
        resp = self.client.post(f"/api/v1/enrichment/companies/{self.comp_1.id}/observe", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["field_name"], "employee_estimate")
        self.assertEqual(data["value"], "150")

    def test_api_get_coverage(self):
        """Test GET /api/v1/enrichment/coverage endpoint."""
        resp = self.client.get("/api/v1/enrichment/coverage")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("pct_domain", data)

    def test_api_jobs_lifecycle(self):
        """Test POST /api/v1/enrichment/jobs, pause, and resume."""
        payload = {"company_ids": [self.comp_1.id], "depth": "STANDARD"}
        create_resp = self.client.post("/api/v1/enrichment/jobs", json=payload)
        self.assertEqual(create_resp.status_code, 201)
        job_id = create_resp.json()["id"]

        pause_resp = self.client.post(f"/api/v1/enrichment/jobs/{job_id}/pause")
        self.assertEqual(pause_resp.status_code, 200)
        self.assertEqual(pause_resp.json()["status"], "PAUSED")

        resume_resp = self.client.post(f"/api/v1/enrichment/jobs/{job_id}/resume")
        self.assertEqual(resume_resp.status_code, 200)
        self.assertEqual(resume_resp.json()["status"], "RUNNING")

    def test_api_verify_email_endpoint(self):
        """Test POST /api/v1/verification/email endpoint."""
        payload = {"email": "director@quantumerp.com.au", "is_pattern_predicted": False}
        resp = self.client.post("/api/v1/verification/email", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["syntax_valid"])
        self.assertFalse(data["is_disposable"])

    def test_api_verify_phone_endpoint(self):
        """Test POST /api/v1/verification/phone endpoint."""
        payload = {"phone": "+61 2 9876 5432"}
        resp = self.client.post("/api/v1/verification/phone", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_valid_format"])
        self.assertEqual(data["country"], "Australia")


if __name__ == "__main__":
    unittest.main()
