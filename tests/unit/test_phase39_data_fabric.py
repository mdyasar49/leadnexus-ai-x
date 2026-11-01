"""
LeadNexus AI X — Phase 39 Test Suite (ChatGPT Master Roadmap)
Enterprise Data Fabric Platform
Tests: Unified Data Contracts, Data Catalog & Discovery, Lineage DAG Tracking,
Cross-Domain Semantic Relations, Quality Radar Scoring, Policy Privacy Enforcement,
and Federated Access Queries across all 13 canonical enterprise data domains.
"""

import sys
import os
import uuid
import unittest
from datetime import datetime, timezone, timedelta
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
from app.models.enterprise_data_fabric import (
    DataDomainEnum,
    DataClassification,
    ContractStatus,
    PolicyEnforcementAction,
    DataContractRecord,
    DataCatalogEntry,
    DataLineageEdge,
    CrossDomainRelation,
    DataQualityAssessment,
    DataPolicyEnforcement,
)
from app.security.tokens import create_access_token
from packages.data_fabric import (
    UnifiedDataContractEngine,
    ContractValidationError,
    FederatedAccessRouter,
    DataLineageTracker,
    LineageCycleError,
    DataQualityEvaluator,
    DataPolicyEnforcer,
)


class TestPhase39DataFabric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="DataFabric Org", slug="df-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.ws = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.ws:
            cls.ws = Workspace(id=str(uuid.uuid4()), organization_id=cls.org.id, name="DataFabric Workspace", slug="df-ws")
            cls.db.add(cls.ws)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="data_architect@leadnexus.io",
                hashed_password="hash",
                full_name="Chief Data Architect",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}", "X-Workspace-ID": cls.ws.id}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_unified_contract_schema_and_freshness(self):
        schema = {
            "type": "object",
            "required": ["company_name", "domain", "employee_count"],
            "properties": {
                "company_name": {"type": "string"},
                "domain": {"type": "string"},
                "employee_count": {"type": "number"},
                "tags": {"type": "array"},
            },
        }
        quality_rules = [
            {"field": "domain", "type": "REGEX", "pattern": r"\.[a-z]{2,}$", "message": "Valid TLD required"},
            {"field": "employee_count", "type": "RANGE", "min": 1, "max": 1000000},
        ]

        # Valid payload
        valid_payload = {
            "company_name": "Infogenx Technologies",
            "domain": "infogenx.com",
            "employee_count": 250,
            "tags": ["b2b", "enterprise"],
        }
        is_valid, violations = UnifiedDataContractEngine.validate_payload(valid_payload, schema, quality_rules)
        self.assertTrue(is_valid)
        self.assertEqual(len(violations), 0)

        # Invalid payload (missing required field, bad regex, range violation)
        bad_payload = {
            "company_name": "Broken Corp",
            "domain": "not-a-valid-domain",
            "employee_count": 0,
        }
        is_valid_bad, violations_bad = UnifiedDataContractEngine.validate_payload(bad_payload, schema, quality_rules)
        self.assertFalse(is_valid_bad)
        self.assertGreaterEqual(len(violations_bad), 2)

        # Freshness SLA check
        now = datetime.now(timezone.utc)
        recent_ts = now - timedelta(seconds=120)
        is_fresh, age = UnifiedDataContractEngine.check_freshness_sla(recent_ts, sla_freshness_seconds=300)
        self.assertTrue(is_fresh)
        self.assertLessEqual(age, 150)

        stale_ts = now - timedelta(seconds=600)
        is_fresh_stale, _ = UnifiedDataContractEngine.check_freshness_sla(stale_ts, sla_freshness_seconds=300)
        self.assertFalse(is_fresh_stale)

    def test_02_contract_crud_via_api(self):
        payload = {
            "domain": "COMPANIES",
            "asset_name": "canonical_company_master",
            "schema_definition": {
                "type": "object",
                "required": ["name", "website"],
                "properties": {"name": {"type": "string"}, "website": {"type": "string"}},
            },
            "sla_freshness_seconds": 1800,
            "owner_team": "Enterprise Data Architecture",
        }
        res = self.client.post("/api/v1/data-fabric/contracts", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        contract = res.json()["contract"]
        contract_id = contract["id"]
        self.assertEqual(contract["domain"], "COMPANIES")

        # Validate against contract
        val_res = self.client.post(
            f"/api/v1/data-fabric/contracts/{contract_id}/validate",
            json={"name": "Acme Corp", "website": "acme.org"},
            headers=self.headers,
        )
        self.assertEqual(val_res.status_code, 200)
        self.assertTrue(val_res.json()["is_valid"])

    def test_03_data_catalog_registration_and_search(self):
        unique_asset = f"intent_signals_{uuid.uuid4().hex[:6]}"
        entry_payload = {
            "domain": "INTENT",
            "asset_name": unique_asset,
            "entity_type": "SurgeSignal",
            "description": "High-intent buyer topic surges across technology categories",
            "fields": [
                {"name": "topic", "type": "string", "is_pii": False},
                {"name": "surge_score", "type": "number", "is_pii": False},
            ],
            "tags": ["b2b", "intent", "realtime"],
            "classification": "CONFIDENTIAL",
            "owner_email": "intent_leads@leadnexus.io",
        }
        res = self.client.post("/api/v1/data-fabric/catalog", json=entry_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)

        # Search catalog
        search_res = self.client.get("/api/v1/data-fabric/catalog/search?q=SurgeSignal", headers=self.headers)
        self.assertEqual(search_res.status_code, 200)
        self.assertGreaterEqual(search_res.json()["total_matches"], 1)

    def test_04_data_lineage_tracker_and_cycle_defense(self):
        tracker = DataLineageTracker()
        # Edge 1: raw_stream -> cleaned_companies
        tracker.add_edge("SIGNALS", "raw_stream", "COMPANIES", "cleaned_companies", transformation_type="ETL")
        # Edge 2: cleaned_companies -> b2b_leads
        tracker.add_edge("COMPANIES", "cleaned_companies", "LEADS", "b2b_leads", transformation_type="ENRICHMENT")
        # Edge 3: b2b_leads -> executive_analytics
        tracker.add_edge("LEADS", "b2b_leads", "ANALYTICS", "executive_analytics", transformation_type="AGGREGATION")

        # Cycle test: adding edge from executive_analytics back to raw_stream must fail
        with self.assertRaises(LineageCycleError):
            tracker.add_edge("ANALYTICS", "executive_analytics", "SIGNALS", "raw_stream")

        # Downstream trace
        downstream = tracker.trace_downstream_impact("SIGNALS", "raw_stream")
        self.assertEqual(downstream["impacted_count"], 3)
        self.assertIn("ANALYTICS::executive_analytics", downstream["impacted_assets"])

        # Upstream trace
        upstream = tracker.trace_upstream_provenance("ANALYTICS", "executive_analytics")
        self.assertEqual(upstream["upstream_count"], 3)
        self.assertIn("SIGNALS::raw_stream", upstream["source_assets"])

    def test_05_lineage_api_endpoints(self):
        edge_payload = {
            "source_domain": "RESEARCH",
            "source_asset": "autonomous_dossier",
            "target_domain": "EVIDENCE",
            "target_asset": "verified_citations",
            "transformation_type": "INFERENCE",
            "metadata": {"model": "leadnexus-ai-extractor-v2"},
        }
        res = self.client.post("/api/v1/data-fabric/lineage", json=edge_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)

        trace_res = self.client.get(
            "/api/v1/data-fabric/lineage/trace/downstream?domain=RESEARCH&asset=autonomous_dossier",
            headers=self.headers,
        )
        self.assertEqual(trace_res.status_code, 200)
        self.assertGreaterEqual(trace_res.json()["impacted_count"], 1)

    def test_06_cross_domain_semantic_relations(self):
        router_engine = FederatedAccessRouter()
        # Connect Company -> Contact
        router_engine.register_relation("COMPANIES", "cmp-101", "PEOPLE", "ppl-202", "EMPLOYED_AT", confidence_score=0.95)
        # Connect Contact -> Lead
        router_engine.register_relation("PEOPLE", "ppl-202", "LEADS", "lead-303", "QUALIFIED_AS", confidence_score=0.98)
        # Connect Company -> Intent
        router_engine.register_relation("COMPANIES", "cmp-101", "INTENT", "int-404", "SURFACED_TOPIC", confidence_score=0.88)

        # Traverse subgraph
        subgraph = router_engine.build_cross_domain_subgraph("COMPANIES", "cmp-101", max_depth=2)
        self.assertGreaterEqual(subgraph["total_entities"], 4)
        self.assertGreaterEqual(subgraph["total_connections"], 3)

    def test_07_relationships_api_and_subgraph(self):
        rel_payload = {
            "primary_domain": "COMPANIES",
            "primary_entity_id": "cmp-alpha",
            "related_domain": "SIGNALS",
            "related_entity_id": "sig-beta",
            "relationship_type": "HIRING_SURGE",
            "confidence_score": 0.92,
        }
        res = self.client.post("/api/v1/data-fabric/relationships", json=rel_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)

        subgraph_res = self.client.get(
            "/api/v1/data-fabric/relationships/subgraph?domain=COMPANIES&entity_id=cmp-alpha&max_depth=2",
            headers=self.headers,
        )
        self.assertEqual(subgraph_res.status_code, 200)
        self.assertIn("COMPANIES:cmp-alpha", subgraph_res.json()["root"])

    def test_08_multi_dimensional_quality_radar_scoring(self):
        records = [
            {"id": "1", "name": "Alpha Corp", "email": "valid@alpha.com", "updated_at": datetime.now(timezone.utc).isoformat()},
            {"id": "2", "name": "Beta Inc", "email": "contact@beta.com", "updated_at": datetime.now(timezone.utc).isoformat()},
            {"id": "3", "name": "", "email": "malformed_email_no_domain", "updated_at": datetime.now(timezone.utc).isoformat()},
            {"id": "1", "name": "Alpha Corp Duplicate", "email": "dup@alpha.com", "updated_at": datetime.now(timezone.utc).isoformat()},
        ]

        metrics = DataQualityEvaluator.evaluate_records(
            records=records,
            required_fields=["name", "email"],
            unique_key="id",
            sla_seconds=3600,
        )
        self.assertGreater(metrics["completeness"], 0.0)
        self.assertGreater(metrics["uniqueness"], 0.0)
        self.assertGreater(metrics["overall_score"], 0.0)
        self.assertGreaterEqual(metrics["violations_count"], 1)

    def test_09_policy_privacy_enforcement_and_masking(self):
        masked_email = DataPolicyEnforcer.mask_value("sarah.connor@cyberdyne.com")
        self.assertTrue(masked_email.startswith("s***r@cyberdyne.com"))

        masked_phone = DataPolicyEnforcer.mask_value("+1-555-839-2910")
        self.assertIn("****", masked_phone)

        record = {"id": "usr-1", "name": "Sarah Connor", "email": "sarah.connor@cyberdyne.com", "phone": "555-1234"}
        policies = [
            {"target_domain": "PEOPLE", "enforcement_action": PolicyEnforcementAction.MASK, "field_name": "email", "is_active": True},
            {"target_domain": "PEOPLE", "enforcement_action": PolicyEnforcementAction.RESTRICT, "field_name": "phone", "is_active": True},
        ]
        sanitized = DataPolicyEnforcer.enforce_policies(record, "PEOPLE", policies, user_role="member")
        self.assertIn("***", sanitized["email"])
        self.assertEqual(sanitized["phone"], "[RESTRICTED]")

    def test_10_federated_access_query_execution(self):
        query_payload = {
            "domain": "COMPANIES",
            "entity_id": "cmp-9988",
            "include_related": True,
            "max_depth": 2,
        }
        res = self.client.post("/api/v1/data-fabric/federated-query", json=query_payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["domain"], "COMPANIES")
        self.assertEqual(data["entity_id"], "cmp-9988")
        self.assertIn("record", data)


if __name__ == "__main__":
    unittest.main()
