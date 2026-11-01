"""
LeadNexus AI X — Phase 15 End-to-End Master Workflow Test Suite
Tests:
1. Search with criteria & suggestions
2. Add exactly 3 leads to PostgreSQL/SQLite
3. Verify Saved Leads list contains exactly 3 leads
4. Export CSV and verify exactly 3 rows (+ header) with UTF-8 BOM
5. Export Excel and verify exactly 3 rows (+ header)
6. Add 1 more lead (total 4)
7. Export CSV and Excel again and verify exactly 4 rows
8. Delete 1 saved lead and verify count drops to 3
9. Invariant: Temporary search results NEVER leak into saved leads or exports
"""

import sys
import os
import io
import csv
import uuid
import unittest
import openpyxl
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
from app.models.lead import Company, Contact
from app.models.saved_lead import SavedLead


class TestPhase15LeadSearchE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        # Ensure we have at least 10 companies for testing
        cls.test_companies = []
        cls.ws_id = str(uuid.uuid4())
        for i in range(10):
            cid = f"test-company-{uuid.uuid4().hex[:8]}"
            comp = Company(
                id=cid,
                workspace_id=cls.ws_id,
                name=f"Enterprise Tech {i} Pty Ltd",
                normalized_name=f"enterprise tech {i} pty ltd",
                domain=f"techcorp{i}.com.au",
                industry="Software & Cloud",
                country="Australia",
                city="Sydney",
                employee_count_range="50-200",
                status="NEW",
            )
            cls.db.add(comp)
            cls.test_companies.append(comp)

            # Add contact for company
            contact = Contact(
                id=f"test-contact-{uuid.uuid4().hex[:8]}",
                workspace_id=cls.ws_id,
                company_id=cid,
                full_name=f"Executive {i} Smith",
                job_title="Chief Technology Officer" if i % 2 == 0 else "VP of Engineering",
                email=f"executive{i}@techcorp{i}.com.au",
                source_url=f"https://techcorp{i}.com.au/team",
                is_decision_maker=True,
            )
            cls.db.add(contact)

        cls.db.commit()

        # Clean any prior saved leads for isolation in these specific companies
        cls.db.query(SavedLead).filter(
            SavedLead.company_id.in_([c.id for c in cls.test_companies])
        ).delete(synchronize_session=False)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(SavedLead).filter(
            SavedLead.company_id.in_([c.id for c in cls.test_companies])
        ).delete(synchronize_session=False)
        for c in cls.test_companies:
            cls.db.query(Contact).filter(Contact.company_id == c.id).delete()
            cls.db.query(Company).filter(Company.id == c.id).delete()
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        # Clear saved leads before each test run if needed
        self.db.query(SavedLead).filter(
            SavedLead.company_id.in_([c.id for c in self.test_companies])
        ).delete(synchronize_session=False)
        self.db.commit()

    def test_01_api_health(self):
        """Verify API health check endpoint."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_02_search_suggestions(self):
        """Test debounced categorized search suggestions."""
        res = self.client.get("/api/search/suggestions?q=Tech")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("suggestions", data)
        self.assertGreater(len(data["suggestions"]), 0)
        categories = {s["category"] for s in data["suggestions"]}
        self.assertTrue(len(categories) > 0)

    def test_03_search_results_flow(self):
        """Search for leads and verify at least 10 results returned."""
        res = self.client.post(
            "/api/search",
            json={
                "query": "Enterprise Tech",
                "criteria": [{"category": "Location", "value": "Australia"}],
                "limit": 15,
                "offset": 0,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertGreaterEqual(data["total"], 10)
        self.assertGreaterEqual(len(data["results"]), 10)

        # Verify initial saved state is False
        for lead in data["results"][:3]:
            self.assertFalse(lead["is_saved"])

    def test_04_critical_master_e2e_workflow(self):
        """
        THE CRITICAL PHASE 15 END-TO-END WORKFLOW:
        1. Search for 10 leads.
        2. Add exactly 3.
        3. Open Saved Leads and confirm only 3 appear.
        4. Export CSV and verify exactly 3 saved leads.
        5. Export Excel and verify exactly 3 saved leads.
        6. Add 1 more lead.
        7. Export again and verify exactly 4 saved leads.
        8. Remove 1 lead and verify 3 remaining.
        """
        # Step 1: Search for 10 leads
        search_res = self.client.post(
            "/api/search",
            json={"query": "Enterprise Tech", "limit": 10, "offset": 0},
        )
        self.assertEqual(search_res.status_code, 200)
        leads = search_res.json()["results"]
        self.assertGreaterEqual(len(leads), 10)

        # Step 2: Add exactly 3 leads
        added_ids = []
        for i in range(3):
            lead = leads[i]
            save_res = self.client.post(
                "/api/leads/save",
                json={
                    "company_id": lead["company_id"],
                    "contact_id": lead.get("contact_id"),
                    "source_name": "Australian Business Registry",
                    "source_url": "https://abr.business.gov.au",
                    "evidence": "Verified Public Entity Record",
                    "search_keyword": "Enterprise Tech Australia",
                },
            )
            self.assertEqual(save_res.status_code, 201)
            saved_data = save_res.json()
            self.assertTrue(saved_data["is_new"])
            added_ids.append(saved_data["saved_id"])

        # Step 3: Open Saved Leads and confirm ONLY 3 appear
        list_res = self.client.get("/api/leads")
        self.assertEqual(list_res.status_code, 200)
        saved_list = list_res.json()
        self.assertEqual(saved_list["total"], 3)
        self.assertEqual(len(saved_list["leads"]), 3)

        count_res = self.client.get("/api/leads/count")
        self.assertEqual(count_res.status_code, 200)
        self.assertEqual(count_res.json()["saved_count"], 3)

        # Step 4: Export CSV and verify exactly 3 saved leads (+ header)
        csv_res = self.client.get("/api/export/csv")
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res.headers["content-type"])
        # Check UTF-8 BOM
        self.assertTrue(csv_res.content.startswith(b"\xef\xbb\xbf"))

        csv_text = csv_res.content.decode("utf-8-sig")
        csv_reader = list(csv.reader(io.StringIO(csv_text)))
        header = csv_reader[0]
        data_rows = csv_reader[1:]
        self.assertIn("Company Name", header)
        self.assertIn("Decision Maker", header)
        self.assertEqual(len(data_rows), 3)

        # Step 5: Export Excel and verify exactly 3 saved leads (+ header)
        excel_res = self.client.get("/api/export/excel")
        self.assertEqual(excel_res.status_code, 200)
        self.assertIn("spreadsheetml", excel_res.headers["content-type"])

        wb = openpyxl.load_workbook(io.BytesIO(excel_res.content))
        ws = wb.active
        excel_rows = list(ws.iter_rows(values_only=True))
        excel_header = excel_rows[0]
        excel_data_rows = excel_rows[1:]
        self.assertIn("Company Name", excel_header)
        self.assertEqual(len(excel_data_rows), 3)

        # Step 6: Add 1 more lead (index 3)
        fourth_lead = leads[3]
        save_4th = self.client.post(
            "/api/leads/save",
            json={
                "company_id": fourth_lead["company_id"],
                "contact_id": fourth_lead.get("contact_id"),
                "source_name": "Public Portal",
                "source_url": "https://company.gov.au",
                "evidence": "ABN Active Registration",
                "search_keyword": "Tech 3",
            },
        )
        self.assertEqual(save_4th.status_code, 201)
        self.assertTrue(save_4th.json()["is_new"])
        added_ids.append(save_4th.json()["saved_id"])

        # Step 7: Export again and verify exactly 4 saved leads
        csv_res_2 = self.client.get("/api/export/csv")
        self.assertEqual(csv_res_2.status_code, 200)
        csv_text_2 = csv_res_2.content.decode("utf-8-sig")
        csv_reader_2 = list(csv.reader(io.StringIO(csv_text_2)))
        self.assertEqual(len(csv_reader_2) - 1, 4)

        excel_res_2 = self.client.get("/api/export/excel")
        self.assertEqual(excel_res_2.status_code, 200)
        wb_2 = openpyxl.load_workbook(io.BytesIO(excel_res_2.content))
        ws_2 = wb_2.active
        excel_rows_2 = list(ws_2.iter_rows(values_only=True))
        self.assertEqual(len(excel_rows_2) - 1, 4)

        # Step 8: Remove 1 lead and verify count drops to 3
        del_res = self.client.delete(f"/api/leads/{added_ids[0]}")
        self.assertEqual(del_res.status_code, 200)

        count_after_del = self.client.get("/api/leads/count").json()["saved_count"]
        self.assertEqual(count_after_del, 3)

    def test_05_idempotent_save_handling(self):
        """Saving an already-saved lead must be handled gracefully without duplicate rows."""
        comp = self.test_companies[0]
        contact = self.db.query(Contact).filter(Contact.company_id == comp.id).first()

        res1 = self.client.post(
            "/api/leads/save",
            json={"company_id": comp.id, "contact_id": contact.id if contact else None},
        )
        self.assertEqual(res1.status_code, 201)
        self.assertTrue(res1.json()["is_new"])

        # Attempt to save the exact same lead again
        res2 = self.client.post(
            "/api/leads/save",
            json={"company_id": comp.id, "contact_id": contact.id if contact else None},
        )
        self.assertEqual(res2.status_code, 201)
        self.assertFalse(res2.json()["is_new"])
        self.assertIn("already saved", res2.json()["message"])

        # Count must remain 1
        count = self.client.get("/api/leads/count").json()["saved_count"]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
