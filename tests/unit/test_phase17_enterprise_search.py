import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

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
from app.models.scoring import LeadScore, AIReasoningResult
from app.models.technology import TechnologyObservation
from app.models.workspace_ui import SavedSearch, SavedView, Bookmark, ResearchNote, ExportJob
from app.services.permission_service import get_active_workspace, get_current_user

from packages.search.search_dsl import (
    SearchDSLParser,
    SearchDSLError,
    NaturalLanguageQueryBuilder,
    ALLOWED_FIELDS
)
from packages.search.search_service import (
    CursorPagination,
    GlobalSearchService
)
from packages.search.lead_workspace_service import (
    LeadWorkspaceService
)
from packages.search.export_service import (
    ExportService,
    sanitize_spreadsheet_value
)


class TestPhase17EnterpriseSearch(unittest.TestCase):
    """Test suite covering Phase 17 Enterprise Search, Query DSL, Lead 360 & Export Engine."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"analyst_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Lead",
            last_name="Analyst",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Search Test Workspace",
            slug=f"search-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed Companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Apex Retail Solutions Pty Ltd",
            normalized_name="apex retail solutions",
            domain="apexretail.com.au",
            website="https://apexretail.com.au",
            country="Australia",
            state="Victoria",
            city="Melbourne",
            industry="Retail & E-commerce",
            description="Leading multi-channel apparel retailer evaluating Odoo 18 migration.",
            employee_count_range="51-200",
            lead_score=88,
            status="QUALIFIED"
        )
        cls.comp_2 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Sydney Logistics Group",
            normalized_name="sydney logistics group",
            domain="sydneylogistics.com.au",
            website="https://sydneylogistics.com.au",
            country="Australia",
            state="New South Wales",
            city="Sydney",
            industry="Logistics & Warehousing",
            description="Freight and 3PL distributor needing ERP barcoding integration.",
            employee_count_range="201-500",
            lead_score=65,
            status="NEW"
        )
        cls.comp_3 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Global BioChem Inc",
            normalized_name="global biochem",
            domain="globalbiochem.com",
            website="https://globalbiochem.com",
            country="United States",
            state="California",
            city="San Francisco",
            industry="Biotechnology",
            description="Pharma research organization using SAP.",
            employee_count_range="501-1000",
            lead_score=35,
            status="DISQUALIFIED"
        )
        cls.db.add_all([cls.comp_1, cls.comp_2, cls.comp_3])
        cls.db.commit()

        # Seed LeadScores
        cls.score_1 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            lead_priority_score=92.5,
            priority_tier="P0_CRITICAL",
            icp_fit_score=95.0,
            intent_score=90.0,
            buying_readiness_score=85.0,
            evidence_confidence_score=94.0,
            data_quality_score=92.0,
            contact_quality_score=88.0,
            freshness_score=98.0
        )
        cls.score_2 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_2.id,
            workspace_id=cls.ws_id,
            lead_priority_score=68.0,
            priority_tier="P2_MEDIUM",
            icp_fit_score=70.0,
            intent_score=65.0,
            buying_readiness_score=60.0,
            evidence_confidence_score=75.0,
            data_quality_score=80.0,
            contact_quality_score=70.0,
            freshness_score=85.0
        )
        cls.db.add_all([cls.score_1, cls.score_2])
        cls.db.commit()

        # Seed Contacts & Buying Committee
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="Sarah Jenkins",
            job_title="Chief Technology Officer",
            department="Executive",
            email="sarah.jenkins@apexretail.com.au",
            email_status="VERIFIED",
            business_phone="+61 3 9988 7766",
            phone_status="VERIFIED",
            source_url="https://apexretail.com.au/leadership",
            is_decision_maker=True,
            confidence_score=0.95
        )
        cls.contact_2 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="David Miller",
            job_title="Operations & ERP Project Manager",
            department="Operations",
            email="david.miller@apexretail.com.au",
            email_status="PUBLICLY_LISTED",
            source_url="https://apexretail.com.au/team",
            is_decision_maker=False,
            confidence_score=0.88
        )
        cls.db.add_all([cls.contact_1, cls.contact_2])
        cls.db.commit()

        # Seed Technologies
        cls.tech_1 = TechnologyObservation(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            technology="Odoo",
            category="ERP",
            version="16.0",
            source_url="https://apexretail.com.au",
            evidence_text="Detected Odoo 16 web assets",
            evidence_hash=uuid.uuid4().hex,
            confidence=0.98
        )
        cls.tech_2 = TechnologyObservation(
            id=str(uuid.uuid4()),
            company_id=cls.comp_2.id,
            workspace_id=cls.ws_id,
            technology="Odoo",
            category="ERP",
            version="15.0",
            source_url="https://sydneylogistics.com.au",
            evidence_text="Detected Odoo 15 web client",
            evidence_hash=uuid.uuid4().hex,
            confidence=0.92
        )
        cls.db.add_all([cls.tech_1, cls.tech_2])
        cls.db.commit()

        # Seed Intent Signals
        cls.signal_1 = IntentSignal(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            source_name="GitHub Issues",
            source_url="https://github.com/apexretail/odoo-custom/issues/12",
            signal_type="ERP_MIGRATION",
            detected_keyword="upgrading Odoo to v18",
            evidence_snippet="We are planning to migrate our retail POS and warehouse modules to Odoo 18 next month.",
            signal_strength=0.95
        )
        cls.db.add(cls.signal_1)
        cls.db.commit()

        # Setup FastAPI TestClient with dependency overrides
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        app.dependency_overrides[get_sync_db] = lambda: cls.db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # 1. Search DSL Unit Tests
    def test_search_dsl_parser_leaf_conditions(self):
        """Test safe filter translation for comparison operators."""
        cond_eq = {"field": "country", "operator": "=", "value": "Australia"}
        clause_eq = SearchDSLParser.parse_condition(cond_eq)
        self.assertIsNotNone(clause_eq)

        cond_gte = {"field": "lead_priority_score", "operator": ">=", "value": 75.0}
        clause_gte = SearchDSLParser.parse_condition(cond_gte)
        self.assertIsNotNone(clause_gte)

        cond_in = {"field": "priority_tier", "operator": "IN", "value": ["P0_CRITICAL", "P1_HIGH"]}
        clause_in = SearchDSLParser.parse_condition(cond_in)
        self.assertIsNotNone(clause_in)

    def test_search_dsl_parser_compound_and_or(self):
        """Test compound AND/OR logical trees."""
        tree = {
            "operator": "AND",
            "conditions": [
                {"field": "country", "operator": "=", "value": "Australia"},
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "priority_tier", "operator": "=", "value": "P0_CRITICAL"},
                        {"field": "lead_priority_score", "operator": ">=", "value": 80.0}
                    ]
                }
            ]
        }
        clauses, virtuals = SearchDSLParser.parse_filters(tree)
        self.assertTrue(len(clauses) >= 1)

    def test_search_dsl_rejects_unwhitelisted_fields(self):
        """Verify strict whitelist blocks SQL injection vectors or forbidden attributes."""
        malicious_cond = {"field": "password_hash", "operator": "=", "value": "123"}
        with self.assertRaises(SearchDSLError):
            SearchDSLParser.parse_condition(malicious_cond)

        unsupported_op = {"field": "country", "operator": "DROP_TABLE", "value": "x"}
        with self.assertRaises(SearchDSLError):
            SearchDSLParser.parse_condition(unsupported_op)

    # 2. Natural Language Query Parser Unit Tests
    def test_natural_language_query_builder(self):
        """Test free-text natural language conversion to safe structured DSL."""
        nl_input = "Show high priority Odoo companies in Australia with score > 75 and verified email"
        result = NaturalLanguageQueryBuilder.parse_nl_query(nl_input)

        self.assertIn("parsed_dsl", result)
        self.assertIn("explanation", result)
        detected = result["detected_criteria"]

        self.assertEqual(detected.get("country"), "Australia")
        self.assertEqual(detected.get("technology"), "odoo")
        self.assertEqual(detected.get("min_score"), 75.0)
        self.assertTrue(detected.get("has_email"))
        self.assertIn("Australia", result["explanation"])

    # 3. Keyset / Cursor Pagination Unit Tests
    def test_cursor_pagination_roundtrip(self):
        """Verify cursor encode and decode works reliably."""
        cursor = CursorPagination.encode(92.5, "comp-uuid-12345")
        self.assertIsInstance(cursor, str)
        val, rec_id = CursorPagination.decode(cursor)
        self.assertEqual(float(val), 92.5)
        self.assertEqual(rec_id, "comp-uuid-12345")

        # Invalid cursor returns None gracefully
        self.assertIsNone(CursorPagination.decode("invalid-base-64--@@"))

    # 4. Global & Faceted Search Service Unit Tests
    def test_global_search_across_entities(self):
        """Test unified search finds matching companies, contacts, technologies, and signals."""
        res = GlobalSearchService.global_search(
            db=self.db,
            workspace_id=self.ws_id,
            query="Apex",
            limit_per_category=5
        )
        self.assertGreaterEqual(res["total_matches"], 1)
        comp_names = [c["name"] for c in res["results"]["companies"]]
        self.assertIn("Apex Retail Solutions Pty Ltd", comp_names)

    def test_lead_search_with_cursor_and_filters(self):
        """Test lead search with filters, sorting, and cursor."""
        res = GlobalSearchService.execute_lead_search(
            db=self.db,
            workspace_id=self.ws_id,
            filters={"country": "Australia"},
            sort_field="lead_priority_score",
            sort_direction="desc",
            limit=2
        )
        self.assertGreaterEqual(res["count"], 1)
        records = res["records"]
        self.assertEqual(records[0]["name"], "Apex Retail Solutions Pty Ltd")

    def test_get_search_facets(self):
        """Verify dynamic facet aggregations for countries, industries, and priority tiers."""
        facets = GlobalSearchService.get_search_facets(
            db=self.db,
            workspace_id=self.ws_id
        )
        self.assertIn("countries", facets)
        self.assertIn("industries", facets)
        self.assertIn("priority_tiers", facets)
        self.assertIn("technologies", facets)

        country_keys = [f["key"] for f in facets["countries"]]
        self.assertIn("Australia", country_keys)

    # 5. Lead 360 Workspace Unit Tests
    def test_lead_360_dossier(self):
        """Test complete Lead 360 view assembly."""
        dossier = LeadWorkspaceService.get_lead_360(
            db=self.db,
            workspace_id=self.ws_id,
            company_id=self.comp_1.id
        )
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier["company"]["name"], "Apex Retail Solutions Pty Ltd")
        self.assertEqual(dossier["scores"]["lead_priority_score"], 92.5)

        # Verify Buying Committee roles assigned
        people = dossier["people"]
        self.assertEqual(len(people), 2)
        cto = next(p for p in people if "Chief Technology Officer" in p["job_title"])
        self.assertEqual(cto["buying_committee_role"], "Economic Buyer")
        pm = next(p for p in people if "Project Manager" in p["job_title"])
        self.assertEqual(pm["buying_committee_role"], "Champion")

        # Verify technologies and intent timeline
        tech_names = [t["name"] for t in dossier["technologies"]]
        self.assertIn("Odoo", tech_names)
        self.assertEqual(len(dossier["intent_timeline"]), 1)

    def test_compare_companies(self):
        """Test side-by-side comparison matrix of 2 companies."""
        matrix = LeadWorkspaceService.compare_companies(
            db=self.db,
            workspace_id=self.ws_id,
            company_ids=[self.comp_1.id, self.comp_2.id]
        )
        self.assertEqual(len(matrix), 2)
        self.assertEqual(matrix[0]["company"]["id"], self.comp_1.id)
        self.assertEqual(matrix[1]["company"]["id"], self.comp_2.id)

    def test_apply_bulk_action(self):
        """Test bulk status update across selected leads."""
        res = LeadWorkspaceService.apply_bulk_action(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            action="SUPPRESS",
            company_ids=[self.comp_2.id]
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["affected_count"], 1)

        # Check DB state updated
        updated_comp = self.db.query(Company).filter(Company.id == self.comp_2.id).first()
        self.assertEqual(updated_comp.status, "DISQUALIFIED")

    # 6. Safe Export Engine Unit Tests
    def test_formula_injection_defense(self):
        """Verify dangerous leading formula characters are escaped with a leading apostrophe."""
        self.assertEqual(sanitize_spreadsheet_value("=1+1"), "'=1+1")
        self.assertEqual(sanitize_spreadsheet_value("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(sanitize_spreadsheet_value("-SUM(A1:A10)"), "'-SUM(A1:A10)")
        self.assertEqual(sanitize_spreadsheet_value("@HYPERLINK('http://malicious')"), "'@HYPERLINK('http://malicious')")
        
        # Normal safe values remain unescaped
        self.assertEqual(sanitize_spreadsheet_value("Apex Retail Solutions"), "Apex Retail Solutions")
        self.assertEqual(sanitize_spreadsheet_value(100), 100)
        self.assertEqual(sanitize_spreadsheet_value(92.5), 92.5)

    def test_export_preview(self):
        """Test pre-export estimation metrics."""
        preview = ExportService.preview_export(
            db=self.db,
            workspace_id=self.ws_id,
            filters={"country": "Australia"}
        )
        self.assertGreaterEqual(preview["record_count"], 1)
        self.assertEqual(preview["formula_injection_defense"], "ENABLED")

    def test_create_csv_and_xlsx_export(self):
        """Test CSV and Excel generation with file persistence and safety verification."""
        export_dir = os.path.join(BASE_DIR, "tests", "temp_exports")
        
        # 1. Test CSV Export
        csv_job = ExportService.create_export_job(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            export_format="CSV",
            filters={"country": "Australia"},
            export_dir=export_dir
        )
        self.assertEqual(csv_job.status, "COMPLETED")
        self.assertTrue(os.path.exists(csv_job.file_path))

        # 2. Test XLSX Export via openpyxl
        xlsx_job = ExportService.create_export_job(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            export_format="XLSX",
            filters={"country": "Australia"},
            export_dir=export_dir
        )
        self.assertEqual(xlsx_job.status, "COMPLETED")
        self.assertTrue(os.path.exists(xlsx_job.file_path))

        # Cleanup test files
        if os.path.exists(csv_job.file_path):
            os.remove(csv_job.file_path)
        if os.path.exists(xlsx_job.file_path):
            os.remove(xlsx_job.file_path)

    # 7. End-to-End API Routes Tests
    def test_api_global_search(self):
        """Test GET /api/v1/search/global endpoint."""
        resp = self.client.get("/api/v1/search/global?q=Retail")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)
        self.assertIn("companies", data["results"])

    def test_api_lead_search_leads(self):
        """Test POST /api/v1/search/leads endpoint."""
        payload = {
            "query": "Retail",
            "filters": {"country": "Australia"},
            "sort_field": "lead_priority_score",
            "limit": 10
        }
        resp = self.client.post("/api/v1/search/leads", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("records", data)
        self.assertGreaterEqual(len(data["records"]), 1)

    def test_api_get_facets(self):
        """Test GET /api/v1/search/facets endpoint."""
        resp = self.client.get("/api/v1/search/facets")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("countries", data)
        self.assertIn("industries", data)

    def test_api_natural_language_query(self):
        """Test POST /api/v1/search/natural-language endpoint."""
        payload = {"query": "Find Odoo migration leads in Australia with high priority"}
        resp = self.client.post("/api/v1/search/natural-language", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("parsed_dsl", data)
        self.assertIn("explanation", data)

    def test_api_lead_360_dossier(self):
        """Test GET /api/v1/leads/{id} endpoint."""
        resp = self.client.get(f"/api/v1/leads/{self.comp_1.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["company"]["name"], "Apex Retail Solutions Pty Ltd")
        self.assertIn("scores", data)
        self.assertIn("people", data)

    def test_api_compare_leads(self):
        """Test POST /api/v1/leads/compare endpoint."""
        payload = {"company_ids": [self.comp_1.id, self.comp_2.id]}
        resp = self.client.post("/api/v1/leads/compare", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)

    def test_api_saved_search_lifecycle(self):
        """Test creating and retrieving saved searches."""
        create_payload = {
            "name": "High Priority Australian Leads",
            "description": "Daily monitoring for Odoo in Australia",
            "query": "Odoo",
            "filters": {"country": "Australia", "priority_tier": "P0_CRITICAL"},
            "alert_enabled": True,
            "alert_channel": "IN_APP"
        }
        resp = self.client.post("/api/v1/search/saved", json=create_payload)
        self.assertEqual(resp.status_code, 201)
        created_id = resp.json()["id"]

        list_resp = self.client.get("/api/v1/search/saved")
        self.assertEqual(list_resp.status_code, 200)
        saved_names = [s["name"] for s in list_resp.json()]
        self.assertIn("High Priority Australian Leads", saved_names)

    def test_api_export_preview_and_create(self):
        """Test POST /api/v1/exports/preview and /create endpoints."""
        preview_resp = self.client.post("/api/v1/exports/preview", json={"filters": {"country": "Australia"}})
        self.assertEqual(preview_resp.status_code, 200)
        self.assertGreaterEqual(preview_resp.json()["record_count"], 1)

        create_resp = self.client.post("/api/v1/exports/create", json={"export_format": "CSV", "filters": {"country": "Australia"}})
        self.assertEqual(create_resp.status_code, 201)
        job_data = create_resp.json()
        self.assertEqual(job_data["status"], "COMPLETED")
        self.assertIn("download_url", job_data)


if __name__ == "__main__":
    unittest.main()
