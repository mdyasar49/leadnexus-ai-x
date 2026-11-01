"""
LeadNexus AI X - Phase 42 Test Suite (ChatGPT Master Roadmap)
Document & Unstructured Data Intelligence
Tests: Multi-format parsing, OCR/heuristic extraction, table detection,
named entity extraction, provenance grounding, security sanitization, and workflow invariants.
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
from app.db.session import SessionLocal, sync_engine
from app.db.base import Base
from app.models.tenant import Organization, Workspace
from app.models.user import User
from app.models.saved_lead import SavedLead
from app.models.document_intelligence import (
    DocumentRecord,
    DocumentChunk,
    DocumentTable,
    DocumentExtractedEntity,
    DocumentProvenanceRecord,
)
from app.security.tokens import create_access_token
from packages.documents import (
    DocumentSanitizer,
    DocumentParser,
    TableExtractor,
    EntityExtractor,
    DocumentProvenanceTracker,
    DocumentIntelligencePipeline,
)


class TestPhase42DocumentIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Doc Intel Org", slug="doc-intel-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                name="Doc Intel Workspace",
                slug="doc-intel-workspace",
                organization_id=cls.org.id,
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="doc_architect@leadnexus.internal",
                first_name="Doc",
                last_name="Architect",
                password_hash="hashed_pw_test",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        token = create_access_token(user_id=cls.user.id)
        cls.headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": cls.workspace.id,
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_document_sanitizer_safety_and_hashes(self):
        """Validates security clearance and SHA-256 fingerprinting."""
        clean_text = b"Executive leadership overview for CloudScale Systems Inc. Jane Doe, CEO."
        clean_check = DocumentSanitizer.inspect("overview.txt", clean_text)
        self.assertTrue(clean_check["is_safe"])
        self.assertEqual(clean_check["malware_status"], "CLEAN")
        self.assertEqual(clean_check["quality_score"], 1.0)
        self.assertEqual(len(clean_check["file_hash"]), 64)

        # Malicious payload with script injection and macro
        dirty_text = b"<script>alert('xss');</script> auto_open malicious macro payload."
        dirty_check = DocumentSanitizer.inspect("bad_doc.docm", dirty_text)
        self.assertFalse(dirty_check["is_safe"])
        self.assertIn("SCRIPT_INJECTION", dirty_check["threats_found"])
        self.assertIn("VBA_MACRO", dirty_check["threats_found"])

    def test_02_document_parser_csv_and_tables(self):
        """Validates CSV structure extraction into tabular records and semantic chunks."""
        csv_data = "Company,Industry,Headcount,Contact\nAcme Corp,Software,250,john@acmecorp.com\nBeta Labs,AI,50,sarah@betalabs.io\n"
        parsed = DocumentParser.parse("leads.csv", csv_data.encode("utf-8"))

        self.assertEqual(parsed["file_type"], "CSV")
        self.assertGreaterEqual(len(parsed["tables"]), 1)
        table = parsed["tables"][0]
        self.assertEqual(table["headers"], ["Company", "Industry", "Headcount", "Contact"])
        self.assertEqual(len(table["rows"]), 2)
        self.assertEqual(table["rows"][0][0], "Acme Corp")
        self.assertGreaterEqual(len(parsed["chunks"]), 2)

    def test_03_document_parser_json_and_html(self):
        """Validates JSON and HTML parsing with script stripping and heading extraction."""
        # JSON parsing
        json_data = b'[{"name": "Nova Systems", "tier": "Enterprise", "revenue": "$20M"}]'
        parsed_json = DocumentParser.parse("customers.json", json_data)
        self.assertEqual(parsed_json["file_type"], "JSON")
        self.assertEqual(len(parsed_json["tables"]), 1)
        self.assertEqual(parsed_json["tables"][0]["headers"], ["name", "tier", "revenue"])

        # HTML parsing
        html_data = b"<html><head><script>malicious()</script></head><body><h1>Executive Summary</h1><p>Nexus Corp expands into EMEA with $10M investment.</p></body></html>"
        parsed_html = DocumentParser.parse("brief.html", html_data)
        self.assertEqual(parsed_html["file_type"], "HTML")
        headings = [c for c in parsed_html["chunks"] if c["chunk_type"] == "HEADING"]
        self.assertTrue(any("Executive Summary" in h["content"] for h in headings))
        paragraphs = [c for c in parsed_html["chunks"] if c["chunk_type"] == "PARAGRAPH"]
        self.assertTrue(any("Nexus Corp expands" in p["content"] for p in paragraphs))

    def test_04_markdown_table_extractor(self):
        """Validates extraction of Markdown tables from unstructured text blocks."""
        md_text = """
### Market Analysis
Here is the current vendor matrix:

| Vendor | Platform | Rating |
| --- | --- | --- |
| AlphaTech | AWS | 4.8 |
| CyberCloud | GCP | 4.5 |

End of vendor section.
        """
        extracted = TableExtractor.extract_from_markdown(md_text)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["headers"], ["Vendor", "Platform", "Rating"])
        self.assertEqual(len(extracted[0]["rows"]), 2)

        records = TableExtractor.to_records(extracted[0])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["Vendor"], "AlphaTech")
        self.assertEqual(records[0]["Platform"], "AWS")

    def test_05_entity_extractor_comprehensive(self):
        """Validates NER extraction of Companies, Persons, Emails, Phones, Titles, Technologies, and Financials."""
        snippet = (
            "Contact Jane Doe, Chief Technology Officer at Nexus Technologies Inc via email "
            "jane.doe@nexustech.io or phone +1-555-432-8921. The firm raised $25M to deploy "
            "PostgreSQL, Kubernetes, and FastAPI microservices."
        )
        entities = EntityExtractor.extract_from_chunk(snippet, page_number=1)
        type_map = {e.entity_type: e for e in entities}

        self.assertIn("EMAIL", type_map)
        self.assertEqual(type_map["EMAIL"].normalized_value, "jane.doe@nexustech.io")

        self.assertIn("PHONE", type_map)
        self.assertIn("5554328921", type_map["PHONE"].normalized_value)

        self.assertIn("COMPANY", type_map)
        self.assertEqual(type_map["COMPANY"].normalized_value, "Nexus Technologies Inc")

        self.assertIn("TITLE", type_map)
        self.assertEqual(type_map["TITLE"].normalized_value, "CHIEF TECHNOLOGY OFFICER")

        self.assertIn("PERSON", type_map)
        self.assertEqual(type_map["PERSON"].normalized_value, "Jane Doe")

        self.assertIn("TECHNOLOGY", type_map)
        self.assertTrue(any(e.normalized_value == "Kubernetes" for e in entities if e.entity_type == "TECHNOLOGY"))

        self.assertIn("FINANCIAL", type_map)
        self.assertTrue(any("$25M" in e.entity_value for e in entities if e.entity_type == "FINANCIAL"))

    def test_06_provenance_citation_and_sha256_proof(self):
        """Validates cryptographic proof generation and source verification."""
        source = "...Nexus Technologies Inc raised $25M in Series B financing..."
        citation = DocumentProvenanceTracker.create_citation(
            document_id="doc-12345",
            claim_text="FINANCIAL: $25M",
            source_snippet=source,
            page_number=2,
            confidence=0.98,
        )

        self.assertEqual(citation["document_id"], "doc-12345")
        self.assertEqual(citation["page_number"], 2)
        self.assertTrue(citation["source_citation"].startswith("doc://doc-12345/p2#sha256:"))

        # Verify cryptographic proof
        is_valid = DocumentProvenanceTracker.verify_proof(source, citation["sha256_proof"])
        self.assertTrue(is_valid)

        # Altered snippet must fail verification
        tampered_source = "...Nexus Technologies Inc raised $50M in Series B financing..."
        is_invalid = DocumentProvenanceTracker.verify_proof(tampered_source, citation["sha256_proof"])
        self.assertFalse(is_invalid)

    def test_07_end_to_end_pipeline(self):
        """Validates DocumentIntelligencePipeline multi-stage processing."""
        doc_body = b"""
Enterprise Prospectus
Acme Solutions LLC announces expansion.
Key Leader: Michael Scott, Chief Executive Officer.
Reach out at michael@acmesolutions.com or (415) 555-0199.
Budget allocated is $5M for Snowflake and TypeScript modernization.
        """
        result = DocumentIntelligencePipeline.process_document(
            filename="prospectus.txt",
            content=doc_body,
            workspace_id=self.workspace.id,
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(result["security"]["is_safe"])
        self.assertGreaterEqual(len(result["chunks"]), 1)
        self.assertGreaterEqual(len(result["entities"]), 4)
        self.assertGreaterEqual(len(result["citations"]), 4)

    def test_08_api_document_upload_and_storage(self):
        """Tests POST /api/v1/documents/upload and database record persistence."""
        payload = {
            "filename": "executive_report.txt",
            "content_text": "TechCorp Inc leadership: Alice Smith, Chief Executive Officer. Email: alice@techcorp.com.",
            "file_type": "TXT",
        }
        res = self.client.post("/api/v1/documents/upload", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        doc_id = data["document"]["id"]
        self.assertEqual(data["document"]["filename"], "executive_report.txt")
        self.assertEqual(data["document"]["status"], "COMPLETED")
        self.assertGreaterEqual(data["summary"]["entities_count"], 2)

        # Verify in database
        saved_doc = self.db.query(DocumentRecord).filter_by(id=doc_id).first()
        self.assertIsNotNone(saved_doc)
        self.assertEqual(saved_doc.filename, "executive_report.txt")

        # Verify chunks persisted
        chunks = self.db.query(DocumentChunk).filter_by(document_id=doc_id).all()
        self.assertGreaterEqual(len(chunks), 1)

        # Verify entities persisted
        entities = self.db.query(DocumentExtractedEntity).filter_by(document_id=doc_id).all()
        self.assertGreaterEqual(len(entities), 2)

    def test_09_api_document_detail_and_entity_filtering(self):
        """Tests GET /api/v1/documents/{id}, /chunks, /entities, /provenance."""
        # Create a document via upload first
        payload = {
            "filename": "financial_filing.txt",
            "content_text": "Global Logistics Corp reported $50M revenue. VP of Sales David Miller can be reached at david@globallogistics.com.",
            "file_type": "TXT",
        }
        res = self.client.post("/api/v1/documents/upload", json=payload, headers=self.headers)
        doc_id = res.json()["document"]["id"]

        # Detail endpoint
        det_res = self.client.get(f"/api/v1/documents/{doc_id}", headers=self.headers)
        self.assertEqual(det_res.status_code, 200)
        self.assertEqual(det_res.json()["filename"], "financial_filing.txt")

        # Chunks endpoint
        chunks_res = self.client.get(f"/api/v1/documents/{doc_id}/chunks", headers=self.headers)
        self.assertEqual(chunks_res.status_code, 200)
        self.assertGreaterEqual(chunks_res.json()["count"], 1)

        # Entities endpoint filtered by EMAIL
        email_res = self.client.get(f"/api/v1/documents/{doc_id}/entities?entity_type=EMAIL", headers=self.headers)
        self.assertEqual(email_res.status_code, 200)
        self.assertGreaterEqual(email_res.json()["count"], 1)
        self.assertEqual(email_res.json()["entities"][0]["normalized_value"], "david@globallogistics.com")

        # Provenance citations endpoint
        cit_res = self.client.get(f"/api/v1/documents/{doc_id}/provenance", headers=self.headers)
        self.assertEqual(cit_res.status_code, 200)
        self.assertGreaterEqual(cit_res.json()["count"], 1)

    def test_10_temporary_document_isolation_invariant(self):
        """
        PRIMARY WORKFLOW INVARIANT:
        Ingesting and parsing documents must NEVER create or pollute SavedLead records
        in canonical PostgreSQL storage without explicit user addition.
        """
        initial_saved_leads = self.db.query(SavedLead).count()

        # Ingest document containing rich lead data
        payload = {
            "filename": "confidential_leads.csv",
            "content_text": "Company,Executive,Email\nSuperCorp Inc,Bob Vance,bob@supercorp.com\nVance Refrigeration,Phyllis Vance,phyllis@vance.com\n",
            "file_type": "CSV",
        }
        res = self.client.post("/api/v1/documents/upload", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)

        # Check that saved leads count has NOT changed
        current_saved_leads = self.db.query(SavedLead).count()
        self.assertEqual(
            current_saved_leads,
            initial_saved_leads,
            "CRITICAL INVARIANT VIOLATION: Document intelligence processing polluted canonical SavedLead table!"
        )


if __name__ == "__main__":
    unittest.main()
