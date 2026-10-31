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
from app.models.lead import Company, Contact, IntentSignal
from app.models.technology import TechnologyObservation
from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeEntityVersion,
    KnowledgeRelationship,
    RelationshipEvidence,
    RelationshipConflict,
    GraphSnapshot,
    GraphCommunity,
    LookalikeProfile,
    LookalikeMatch,
    GraphHealthSnapshot,
    GraphCompletenessSnapshot,
    GraphResearchRecommendation,
    KnowledgeEntityType,
    InferenceStatus,
    RelationshipStatus,
    ConflictStatus
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.knowledge_graph.knowledge_graph_engine import KnowledgeGraphEngine
from packages.knowledge_graph.traversal_engine import GraphTraversalEngine, GraphTraversalError
from packages.knowledge_graph.semantic_search_engine import SemanticSearchEngine
from packages.knowledge_graph.similarity_lookalike_engine import SimilarityAndLookalikeEngine
from packages.knowledge_graph.community_ecosystem_engine import CommunityAndEcosystemEngine
from packages.knowledge_graph.graph_intelligence_engine import GraphIntelligenceEngine


class TestPhase23KnowledgeGraph(unittest.TestCase):
    """Test suite covering Phase 23 Enterprise Knowledge Graph, Semantic Search & Relationship Intelligence."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"graph_architect_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Graph",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Knowledge Graph Workspace",
            slug=f"kg-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed Companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Sydney Odoo Solutions Pty Ltd",
            normalized_name="sydney odoo solutions",
            domain="sydneyodoo.com.au",
            country="Australia",
            industry="Software & IT",
            lead_score=94,
            status="QUALIFIED"
        )
        cls.comp_2 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Melbourne Retail Imports",
            normalized_name="melbourne retail imports",
            domain="melbourneretail.com.au",
            country="Australia",
            industry="Retail & Ecommerce",
            lead_score=85,
            status="RESEARCHED"
        )
        cls.comp_3 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Brisbane Mining Supplies",
            normalized_name="brisbane mining supplies",
            domain="brisbanemining.com.au",
            country="Australia",
            industry="Mining",
            lead_score=68,
            status="DISCOVERED"
        )
        cls.db.add(cls.comp_1)
        cls.db.add(cls.comp_2)
        cls.db.add(cls.comp_3)

        # Seed Contacts
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            full_name="Sarah Jenkins",
            email="sarah@sydneyodoo.com.au",
            source_url="https://sydneyodoo.com.au/team/sarah",
            job_title="Chief Technology Officer",
            email_status="VERIFIED",
            is_decision_maker=True,
            confidence_score=0.96
        )
        cls.contact_2 = Contact(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_2.id,
            full_name="David Vance",
            email="david@melbourneretail.com.au",
            source_url="https://melbourneretail.com.au/about",
            job_title="Managing Director",
            email_status="VERIFIED",
            is_decision_maker=True,
            confidence_score=0.92
        )
        cls.db.add(cls.contact_1)
        cls.db.add(cls.contact_2)
        cls.db.commit()

        # Seed Knowledge Graph Entities & Relations
        cls.kg_engine = KnowledgeGraphEngine(cls.db)

        # Entity 1: Company Sydney Odoo
        cls.ent_sydney = cls.kg_engine.sync_company_node(cls.comp_1)
        # Entity 2: Company Melbourne Retail
        cls.ent_melbourne = cls.kg_engine.sync_company_node(cls.comp_2)
        # Entity 3: Company Brisbane Mining
        cls.ent_brisbane = cls.kg_engine.sync_company_node(cls.comp_3)

        # Tech Entities
        cls.ent_odoo = cls.kg_engine.sync_technology_node(cls.ws_id, "Odoo ERP", category="ERP")
        cls.ent_shopify = cls.kg_engine.sync_technology_node(cls.ws_id, "Shopify", category="ECOMMERCE")
        cls.ent_azure = cls.kg_engine.sync_technology_node(cls.ws_id, "Microsoft Azure", category="CLOUD_HOSTING")

        # Person Entities
        cls.ent_sarah = cls.kg_engine.sync_person_node(cls.contact_1)
        cls.ent_david = cls.kg_engine.sync_person_node(cls.contact_2)

        # Seed Relationships
        # Sydney Odoo -> IMPLEMENTS_ODOO -> Odoo ERP
        cls.kg_engine.create_or_update_relationship(
            workspace_id=cls.ws_id,
            source_entity_id=cls.ent_sydney.id,
            target_entity_id=cls.ent_odoo.id,
            relationship_type="IMPLEMENTS_ODOO",
            base_confidence=90.0,
            evidence_items=[
                {
                    "source_url": "https://sydneyodoo.com.au/services/erp-implementation",
                    "evidence_snippet": "Official Gold Partner delivering enterprise Odoo 17 migrations across APAC.",
                    "source_type": "WEBSITE"
                }
            ]
        )

        # Melbourne Retail -> USES_ODOO -> Odoo ERP
        cls.kg_engine.create_or_update_relationship(
            workspace_id=cls.ws_id,
            source_entity_id=cls.ent_melbourne.id,
            target_entity_id=cls.ent_odoo.id,
            relationship_type="USES_ODOO",
            base_confidence=85.0,
            evidence_items=[
                {
                    "source_url": "https://melbourneretail.com.au/careers/odoo-specialist",
                    "evidence_snippet": "Seeking ERP admin to oversee Odoo 17 inventory and point of sale systems.",
                    "source_type": "JOB_BOARD"
                }
            ]
        )

        # Melbourne Retail -> USES_TECHNOLOGY -> Shopify
        cls.kg_engine.create_or_update_relationship(
            workspace_id=cls.ws_id,
            source_entity_id=cls.ent_melbourne.id,
            target_entity_id=cls.ent_shopify.id,
            relationship_type="USES_TECHNOLOGY",
            base_confidence=88.0,
            evidence_items=[
                {
                    "source_url": "https://melbourneretail.com.au",
                    "evidence_snippet": "Powered by Shopify e-commerce checkout integration.",
                    "source_type": "WEBSITE"
                }
            ]
        )

        # Sarah Jenkins -> WORKS_AT -> Sydney Odoo
        cls.kg_engine.create_or_update_relationship(
            workspace_id=cls.ws_id,
            source_entity_id=cls.ent_sarah.id,
            target_entity_id=cls.ent_sydney.id,
            relationship_type="WORKS_AT",
            base_confidence=95.0,
            evidence_items=[
                {
                    "source_url": "https://sydneyodoo.com.au/team/sarah",
                    "evidence_snippet": "Sarah Jenkins serves as Chief Technology Officer leading all ERP engineering.",
                    "source_type": "WEBSITE"
                }
            ]
        )

        # David Vance -> LEADS -> Melbourne Retail
        cls.kg_engine.create_or_update_relationship(
            workspace_id=cls.ws_id,
            source_entity_id=cls.ent_david.id,
            target_entity_id=cls.ent_melbourne.id,
            relationship_type="LEADS",
            base_confidence=92.0,
            evidence_items=[
                {
                    "source_url": "https://melbourneretail.com.au/about",
                    "evidence_snippet": "David Vance, Managing Director, founded Melbourne Retail Imports.",
                    "source_type": "WEBSITE"
                }
            ]
        )

        # TestClient override
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.db.close()

    # --- 1. Entity Management & Versioning Tests ---

    def test_01_entity_upsert_and_versioning(self):
        engine = KnowledgeGraphEngine(self.db)
        entity = engine.upsert_entity(
            workspace_id=self.ws_id,
            entity_type="PRODUCT",
            canonical_name="Odoo POS Hardware Kit",
            normalized_identifier="product:odoo-pos-kit-v1",
            properties={"price_aud": 1250.0, "warranty_months": 24}
        )
        self.assertIsNotNone(entity.id)
        self.assertEqual(entity.canonical_name, "Odoo POS Hardware Kit")

        # Update properties to verify immutable version snapshotting
        updated = engine.upsert_entity(
            workspace_id=self.ws_id,
            entity_type="PRODUCT",
            canonical_name="Odoo POS Hardware Kit Enterprise",
            normalized_identifier="product:odoo-pos-kit-v1",
            properties={"price_aud": 1450.0, "warranty_months": 36}
        )
        self.assertEqual(updated.id, entity.id)

        versions = self.db.query(KnowledgeEntityVersion).filter(
            KnowledgeEntityVersion.entity_id == entity.id
        ).all()
        self.assertGreaterEqual(len(versions), 2)

    # --- 2. Multi-Source Corroboration & Independence Rule Tests ---

    def test_02_multi_source_corroboration_boost(self):
        engine = KnowledgeGraphEngine(self.db)
        # Create relation with initial source
        rel, _ = engine.create_or_update_relationship(
            workspace_id=self.ws_id,
            source_entity_id=self.ent_brisbane.id,
            target_entity_id=self.ent_azure.id,
            relationship_type="USES_TECHNOLOGY",
            base_confidence=75.0,
            evidence_items=[
                {"source_url": "https://brisbanemining.com.au/cloud", "evidence_snippet": "Cloud infrastructure hosted on Azure.", "source_type": "WEBSITE"}
            ]
        )
        initial_conf = rel.confidence
        self.assertEqual(rel.corroboration_count, 1)

        # Add second corroborating observation from an INDEPENDENT domain
        rel2, _ = engine.create_or_update_relationship(
            workspace_id=self.ws_id,
            source_entity_id=self.ent_brisbane.id,
            target_entity_id=self.ent_azure.id,
            relationship_type="USES_TECHNOLOGY",
            base_confidence=75.0,
            evidence_items=[
                {"source_url": "https://itnews.com.au/articles/brisbane-mining-azure-migration", "evidence_snippet": "Brisbane Mining migrated its dispatch data to Azure cloud.", "source_type": "ARTICLE"}
            ]
        )
        # 2 independent sources -> boost = 15 * log2(2) = 15.0 -> 75 + 15 = 90.0
        self.assertEqual(rel2.corroboration_count, 2)
        self.assertGreater(rel2.confidence, initial_conf)

        # Add third observation from the SAME domain (syndicated / second page on itnews.com.au)
        rel3, _ = engine.create_or_update_relationship(
            workspace_id=self.ws_id,
            source_entity_id=self.ent_brisbane.id,
            target_entity_id=self.ent_azure.id,
            relationship_type="USES_TECHNOLOGY",
            base_confidence=75.0,
            evidence_items=[
                {"source_url": "https://itnews.com.au/syndicated/brisbane-azure-summary", "evidence_snippet": "Summary of Brisbane Mining Azure adoption.", "source_type": "ARTICLE"}
            ]
        )
        # Invariant: Syndicated copy on same domain must NOT increase corroboration count or confidence
        self.assertEqual(rel3.corroboration_count, 2)
        self.assertEqual(rel3.confidence, rel2.confidence)

    # --- 3. Relationship Conflict & Resolution Tests ---

    def test_03_relationship_conflict_and_resolution(self):
        engine = KnowledgeGraphEngine(self.db)
        # Sydney Odoo already has active IMPLEMENTS_ODOO with Odoo ERP.
        # Now introduce a conflicting edge: DOES_NOT_USE_ODOO
        rel_neg, conflict = engine.create_or_update_relationship(
            workspace_id=self.ws_id,
            source_entity_id=self.ent_sydney.id,
            target_entity_id=self.ent_odoo.id,
            relationship_type="DOES_NOT_USE_ODOO",
            base_confidence=70.0,
            evidence_items=[
                {"source_url": "https://disgruntled-forum.org/threads/sydney-odoo", "evidence_snippet": "Company dropped Odoo entirely.", "source_type": "FORUM"}
            ]
        )
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.status, ConflictStatus.UNRESOLVED.value)
        self.assertEqual(rel_neg.status, RelationshipStatus.CONTESTED.value)

        # Human operator resolves conflict in favor of winning verified edge
        resolved = engine.resolve_conflict(
            workspace_id=self.ws_id,
            conflict_id=conflict.id,
            winning_relationship_id=conflict.relationship_id_a,
            resolved_by="lead_investigator",
            notes="Official website confirms active Gold Partner status; forum post was unverified hearsay."
        )
        self.assertEqual(resolved.status, ConflictStatus.RESOLVED.value)
        self.assertEqual(rel_neg.status, RelationshipStatus.SUPPRESSED.value)

    # --- 4. Temporal Graph & As-Of Time-Travel Tests ---

    def test_04_temporal_graph_as_of_queries(self):
        engine = KnowledgeGraphEngine(self.db)
        past_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mid_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
        future_cutoff = datetime(2024, 12, 31, tzinfo=timezone.utc)

        # Create historical relationship valid during 2023-2024
        past_rel, _ = engine.create_or_update_relationship(
            workspace_id=self.ws_id,
            source_entity_id=self.ent_melbourne.id,
            target_entity_id=self.ent_azure.id,
            relationship_type="LEGACY_CLOUD_PROVIDER",
            base_confidence=80.0,
            valid_from=past_time,
            valid_to=future_cutoff
        )

        # Query as of 2024-06-01 (when past_rel was active)
        active_in_2024 = engine.get_relationships_as_of(
            workspace_id=self.ws_id,
            entity_id=self.ent_melbourne.id,
            as_of=mid_time
        )
        rel_ids_2024 = [r.id for r in active_in_2024]
        self.assertIn(past_rel.id, rel_ids_2024)

        # Query as of 2026 (past_rel should be expired and excluded)
        active_in_2026 = engine.get_relationships_as_of(
            workspace_id=self.ws_id,
            entity_id=self.ent_melbourne.id,
            as_of=datetime(2026, 10, 1, tzinfo=timezone.utc)
        )
        rel_ids_2026 = [r.id for r in active_in_2026]
        self.assertNotIn(past_rel.id, rel_ids_2026)

    # --- 5. Graph Snapshotting Tests ---

    def test_05_graph_snapshot_creation(self):
        engine = KnowledgeGraphEngine(self.db)
        snap = engine.create_snapshot(
            workspace_id=self.ws_id,
            snapshot_name="Weekly Executive Graph Snapshot",
            snapshot_type="WEEKLY"
        )
        self.assertIsNotNone(snap.id)
        self.assertGreater(snap.entity_count, 0)
        self.assertGreater(snap.relationship_count, 0)
        self.assertEqual(snap.graph_version, "v23.1")

    # --- 6. Bounded Graph Traversal & Path Search Tests ---

    def test_06_neighborhood_traversal_bounds(self):
        engine = GraphTraversalEngine(self.db)
        # Depth 1 neighborhood of Melbourne Retail
        nh_1 = engine.get_neighborhood(
            workspace_id=self.ws_id,
            entity_id=self.ent_melbourne.id,
            depth=1
        )
        self.assertEqual(nh_1["depth_traversed"], 1)
        self.assertGreaterEqual(nh_1["node_count"], 3)  # Melbourne, Odoo, Shopify, David

        # Depth 2 neighborhood
        nh_2 = engine.get_neighborhood(
            workspace_id=self.ws_id,
            entity_id=self.ent_melbourne.id,
            depth=2
        )
        self.assertEqual(nh_2["depth_traversed"], 2)
        self.assertGreaterEqual(nh_2["node_count"], nh_1["node_count"])

        # Test safety boundary clamping: requested depth 10 clamped to MAX_ALLOWED_DEPTH (3)
        nh_clamped = engine.get_neighborhood(
            workspace_id=self.ws_id,
            entity_id=self.ent_melbourne.id,
            depth=10
        )
        self.assertEqual(nh_clamped["depth_traversed"], 3)

    def test_07_bounded_path_search_with_evidence(self):
        engine = GraphTraversalEngine(self.db)
        # Find path from Sarah Jenkins -> Odoo ERP
        # Path: Sarah -> Sydney Odoo -> Odoo ERP (2 hops)
        paths = engine.find_paths(
            workspace_id=self.ws_id,
            start_entity_id=self.ent_sarah.id,
            target_entity_id=self.ent_odoo.id,
            max_depth=3
        )
        self.assertGreaterEqual(len(paths), 1)
        p = paths[0]
        self.assertEqual(p["path_length"], 2)
        self.assertIn("WORKS_AT", p["explanation"])
        self.assertIn("IMPLEMENTS_ODOO", p["explanation"])

    def test_08_safe_graph_dsl_execution(self):
        engine = GraphTraversalEngine(self.db)
        dsl = {
            "entity_type": "COMPANY",
            "filters": {"country": "Australia"},
            "connected_to": {
                "entity_type": "TECHNOLOGY",
                "name": "Odoo",
                "relationship_type": "USES_ODOO"
            },
            "depth": 1,
            "min_confidence": 70.0
        }
        res = engine.execute_dsl_query(workspace_id=self.ws_id, dsl=dsl)
        self.assertGreaterEqual(res["total_matches"], 1)
        names = [r["entity"]["name"] for r in res["results"]]
        self.assertIn("Melbourne Retail Imports", names)

    # --- 7. Semantic & Hybrid Search Tests ---

    def test_09_semantic_embedding_and_hybrid_search(self):
        engine = SemanticSearchEngine(self.db)
        # Index embeddings for Sydney Odoo and Melbourne Retail
        emb_1 = engine.index_entity_embedding(self.ws_id, self.ent_sydney.id)
        emb_2 = engine.index_entity_embedding(self.ws_id, self.ent_melbourne.id)
        self.assertEqual(len(emb_1.embedding_vector), 384)

        # Hybrid search for Odoo ERP implementations
        results = engine.hybrid_search(
            workspace_id=self.ws_id,
            query_text="Odoo ERP implementation and migration partners in Australia",
            country="Australia",
            limit=5
        )
        self.assertGreaterEqual(len(results), 1)
        top = results[0]
        self.assertIn("total_score", top)
        self.assertIn("semantic_score", top)
        self.assertIn("keyword_score", top)
        self.assertIn("graph_boost", top)

    def test_10_nl_to_dsl_query_translation(self):
        engine = SemanticSearchEngine(self.db)
        prompt = "Find Australian retail companies using Odoo and Shopify"
        dsl = engine.translate_nl_to_graph_dsl(prompt)
        self.assertEqual(dsl["entity_type"], "COMPANY")
        self.assertEqual(dsl["filters"]["country"], "Australia")
        self.assertEqual(dsl["filters"]["industry"], "Retail")
        self.assertEqual(dsl["connected_to"]["name"], "Odoo")

    # --- 8. Company Similarity & Lookalikes Tests ---

    def test_11_company_similarity_and_lookalikes(self):
        engine = SimilarityAndLookalikeEngine(self.db)
        # Calculate similarity between Sydney Odoo and Melbourne Retail
        sim = engine.calculate_company_similarity(
            workspace_id=self.ws_id,
            company_a_id=self.ent_sydney.id,
            company_b_id=self.ent_melbourne.id
        )
        self.assertGreater(sim.similarity_score, 0.40)
        self.assertIn("technology_overlap_jaccard", sim.matched_factors)
        self.assertIn("LOOKALIKE ESTIMATE", sim.limitations_notes)

        # Create lookalike profile with Sydney Odoo as seed
        profile = engine.create_lookalike_profile(
            workspace_id=self.ws_id,
            profile_name="High-Performing Australian Tech Lookalikes",
            seed_entity_ids=[self.ent_sydney.id],
            matching_dimensions=["technology", "industry", "geography"],
            target_count=5
        )
        self.assertIsNotNone(profile.id)

        # Find lookalike candidates
        matches = engine.find_lookalikes(workspace_id=self.ws_id, profile_id=profile.id)
        self.assertGreaterEqual(len(matches), 1)
        m = matches[0]
        self.assertGreater(m.overall_similarity_score, 0.0)
        self.assertIn("Candidate matches", m.explanation)

    # --- 9. Community Detection & Specialized Ecosystems Tests ---

    def test_12_community_detection_connected_components(self):
        engine = CommunityAndEcosystemEngine(self.db)
        communities = engine.detect_communities(self.ws_id)
        self.assertGreaterEqual(len(communities), 1)
        comm = communities[0]
        self.assertIsNotNone(comm.id)
        self.assertGreater(comm.density, 0.0)

    def test_13_specialized_odoo_ecosystem_graph(self):
        engine = CommunityAndEcosystemEngine(self.db)
        odoo_eco = engine.get_odoo_ecosystem_graph(self.ws_id)
        self.assertEqual(odoo_eco["ecosystem"], "ODOO_ENTERPRISE_ECOSYSTEM")
        self.assertGreaterEqual(odoo_eco["total_nodes"], 2)
        self.assertIn("IMPLEMENTS_ODOO", odoo_eco["category_breakdown"])
        self.assertIn("USES_ODOO", odoo_eco["category_breakdown"])

    def test_14_technology_ecosystem_co_occurrence(self):
        engine = CommunityAndEcosystemEngine(self.db)
        tech_eco = engine.get_technology_ecosystem_graph(self.ws_id, anchor_tech="Odoo")
        self.assertEqual(tech_eco["anchor_technology"], "Odoo ERP")
        co_techs = [t["technology_name"] for t in tech_eco["co_occurring_technologies"]]
        self.assertIn("Shopify", co_techs)

    def test_15_buying_committee_graph_roles(self):
        engine = CommunityAndEcosystemEngine(self.db)
        # Buying committee for Sydney Odoo (Sarah Jenkins - CTO)
        committee = engine.get_buying_committee_graph(self.ws_id, self.ent_sydney.id)
        self.assertGreaterEqual(committee["total_committee_members"], 1)
        member = committee["members"][0]
        self.assertEqual(member["committee_role"], "TECHNICAL_EVALUATOR")
        self.assertTrue(member["is_verified_decision_maker"])

    # --- 10. Graph Completeness, Health & Research Pathfinder Tests ---

    def test_16_graph_completeness_8_dimensions(self):
        engine = GraphIntelligenceEngine(self.db)
        comp_snap = engine.evaluate_entity_completeness(self.ws_id, self.ent_sydney.id)
        self.assertGreaterEqual(comp_snap.completeness_score, 80.0)
        self.assertTrue(comp_snap.has_technology)
        self.assertTrue(comp_snap.has_decision_maker)
        self.assertTrue(comp_snap.has_evidence)

    def test_17_graph_health_scorecard(self):
        engine = GraphIntelligenceEngine(self.db)
        health = engine.evaluate_graph_health(self.ws_id)
        self.assertGreaterEqual(health.total_entities, 5)
        self.assertGreaterEqual(health.total_relationships, 4)
        self.assertGreater(health.evidence_coverage_pct, 50.0)
        self.assertGreater(health.quality_score, 70.0)

    def test_18_graph_gap_detection_and_research_recommendation(self):
        engine = GraphIntelligenceEngine(self.db)
        # Brisbane Mining has active Azure edge but no connected decision maker
        recs = engine.detect_graph_gaps_and_recommend(self.ws_id, limit=5)
        self.assertIsInstance(recs, list)

    # --- 11. REST API Endpoints Tests ---

    def test_19_api_entities_and_relationships(self):
        # Create Entity via API
        res_ent = self.client.post("/api/v1/graph/entities", json={
            "entity_type": "SERVICE",
            "canonical_name": "Odoo Cloud Hosting",
            "normalized_identifier": "service:odoo-cloud-hosting",
            "properties": {"sla_pct": 99.9}
        })
        self.assertEqual(res_ent.status_code, 200)
        ent_id = res_ent.json()["entity_id"]

        # List Entities
        res_list = self.client.get("/api/v1/graph/entities?entity_type=SERVICE")
        self.assertEqual(res_list.status_code, 200)

        # Create Relationship via API
        res_rel = self.client.post("/api/v1/graph/relationships", json={
            "source_entity_id": self.ent_sydney.id,
            "target_entity_id": ent_id,
            "relationship_type": "PROVIDES_SERVICE",
            "base_confidence": 95.0,
            "evidence_items": [
                {
                    "source_url": "https://sydneyodoo.com.au/cloud",
                    "evidence_snippet": "We provide dedicated managed Odoo hosting on AWS and Azure.",
                    "source_type": "WEBSITE"
                }
            ]
        })
        self.assertEqual(res_rel.status_code, 200)
        rel_id = res_rel.json()["relationship_id"]

        # Get Relationship detail with evidence
        res_rel_det = self.client.get(f"/api/v1/graph/relationships/{rel_id}")
        self.assertEqual(res_rel_det.status_code, 200)
        self.assertGreaterEqual(len(res_rel_det.json()["evidence"]), 1)

    def test_20_api_neighborhood_and_paths(self):
        # Neighborhood
        res_nh = self.client.get(f"/api/v1/graph/neighborhood?entity_id={self.ent_sydney.id}&depth=1")
        self.assertEqual(res_nh.status_code, 200)
        self.assertEqual(res_nh.json()["depth_traversed"], 1)

        # Path search
        res_path = self.client.post("/api/v1/graph/path", json={
            "start_entity_id": self.ent_sarah.id,
            "target_entity_id": self.ent_odoo.id,
            "max_depth": 3
        })
        self.assertEqual(res_path.status_code, 200)
        self.assertGreaterEqual(res_path.json()["paths_found"], 1)

    def test_21_api_search_and_ecosystems(self):
        # Hybrid Search
        res_search = self.client.post("/api/v1/graph/search", json={
            "query_text": "Odoo ERP Melbourne",
            "country": "Australia",
            "limit": 5
        })
        self.assertEqual(res_search.status_code, 200)

        # Semantic NL Search
        res_sem = self.client.post("/api/v1/graph/semantic-search", json={
            "prompt": "Australian retail companies using Odoo"
        })
        self.assertEqual(res_sem.status_code, 200)
        self.assertIn("translated_dsl", res_sem.json())

        # Odoo Ecosystem API
        res_odoo = self.client.get("/api/v1/graph/ecosystems/odoo")
        self.assertEqual(res_odoo.status_code, 200)
        self.assertEqual(res_odoo.json()["ecosystem"], "ODOO_ENTERPRISE_ECOSYSTEM")

        # Technology Ecosystem API
        res_tech = self.client.get("/api/v1/graph/ecosystems/technology?anchor=Odoo")
        self.assertEqual(res_tech.status_code, 200)

        # Buying Committee API
        res_bc = self.client.get(f"/api/v1/graph/ecosystems/buying-committee?company_id={self.ent_sydney.id}")
        self.assertEqual(res_bc.status_code, 200)

        # Health & Snapshots API
        res_health = self.client.get("/api/v1/graph/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertIn("quality_score", res_health.json())


if __name__ == "__main__":
    unittest.main()

