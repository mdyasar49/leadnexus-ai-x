"""
LeadNexus AI X - Phase 46 Test Suite (ChatGPT Master Roadmap)
Advanced Search, Entity Graph & Complex Query Federation
Tests: GraphIndex, MultiHopQueryEngine, PathNavigator, CentralityAnalyzer, HybridFederator, API routes, and isolation invariants.
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
from app.models.tenant import Organization, Workspace
from app.models.user import User
from app.models.saved_lead import SavedLead
from app.models.entity_graph import GraphNodeRecord, GraphEdgeRecord
from packages.graph.graph_index import GraphIndex
from packages.graph.multihop_query_engine import MultiHopQueryEngine
from packages.graph.path_navigator import PathNavigator
from packages.graph.centrality_analyzer import CentralityAnalyzer
from packages.graph.hybrid_federator import HybridSearchFederator


class TestPhase46EntityGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        # Build isolated test graph
        cls.test_graph = GraphIndex()
        # Nodes
        cls.test_graph.add_node("c_acme", "COMPANY", "Acme ERP Solutions", "company:acme", {"country": "Australia", "city": "Sydney"})
        cls.test_graph.add_node("c_beta", "COMPANY", "Beta Cloud Technologies", "company:beta", {"country": "Australia", "city": "Melbourne"})
        cls.test_graph.add_node("t_odoo", "TECHNOLOGY", "Odoo", "tech:odoo", {"category": "ERP"})
        cls.test_graph.add_node("t_python", "TECHNOLOGY", "Python", "tech:python", {"category": "Language"})
        cls.test_graph.add_node("p_alice", "PERSON", "Alice Walker", "person:alice", {"title": "Chief Executive Officer", "seniority": "Executive"})
        cls.test_graph.add_node("p_bob", "PERSON", "Bob Smith", "person:bob", {"title": "CTO", "seniority": "Executive"})
        cls.test_graph.add_node("p_charlie", "PERSON", "Charlie Davis", "person:charlie", {"title": "VP Engineering", "seniority": "VP"})

        # Edges
        cls.test_graph.add_edge("e1", "c_acme", "t_odoo", "USES_TECH", 1.0, 0.98)
        cls.test_graph.add_edge("e2", "c_beta", "t_odoo", "USES_TECH", 1.0, 0.95)
        cls.test_graph.add_edge("e3", "c_acme", "t_python", "USES_TECH", 0.8, 0.90)
        cls.test_graph.add_edge("e4", "p_alice", "c_acme", "EMPLOYED_AT", 1.0, 0.99)
        cls.test_graph.add_edge("e5", "p_bob", "c_beta", "EMPLOYED_AT", 1.0, 0.97)
        cls.test_graph.add_edge("e6", "p_alice", "p_charlie", "COLLEAGUE_OF", 0.9, 0.92)
        cls.test_graph.add_edge("e7", "p_charlie", "p_bob", "COLLEAGUE_OF", 0.8, 0.88)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_graph_index_node_and_edge_creation(self):
        """Test 1: Verifies node and edge addition, canonical key lookups, and types."""
        node = self.test_graph.get_node("c_acme")
        self.assertIsNotNone(node)
        self.assertEqual(node["name"], "Acme ERP Solutions")
        self.assertEqual(self.test_graph.get_node_by_key("company:acme")["id"], "c_acme")
        self.assertEqual(len(self.test_graph.get_nodes_by_type("COMPANY")), 2)
        self.assertEqual(len(self.test_graph.get_nodes_by_type("PERSON")), 3)
        self.assertEqual(len(self.test_graph.get_outgoing_edges("c_acme", "USES_TECH")), 2)

    def test_02_graph_index_neighborhood(self):
        """Test 2: Verifies 1-hop and 2-hop neighborhood expansion and edge collection."""
        nh_1 = self.test_graph.get_neighborhood("c_acme", max_hops=1)
        node_ids = {n["id"] for n in nh_1["nodes"]}
        self.assertIn("c_acme", node_ids)
        self.assertIn("t_odoo", node_ids)
        self.assertIn("t_python", node_ids)
        self.assertIn("p_alice", node_ids)
        self.assertGreaterEqual(nh_1["total_edges"], 3)

    def test_03_graph_index_stats(self):
        """Test 3: Verifies graph stats including node counts, edge distributions, and density."""
        stats = self.test_graph.get_stats()
        self.assertEqual(stats["total_nodes"], 7)
        self.assertEqual(stats["total_edges"], 7)
        self.assertGreater(stats["graph_density"], 0.0)
        self.assertEqual(stats["node_type_distribution"]["COMPANY"], 2)
        self.assertEqual(stats["node_type_distribution"]["PERSON"], 3)
        self.assertIn("USES_TECH", stats["edge_relationship_distribution"])

    def test_04_multihop_query_traversal(self):
        """Test 4: Verifies multi-hop traversal query from Company to Technology."""
        engine_query = MultiHopQueryEngine(self.test_graph)
        result = engine_query.execute_query(
            start_node_type="COMPANY",
            start_filters={"city": "Sydney"},
            hops=[
                {"relationship_type": "USES_TECH", "target_node_type": "TECHNOLOGY", "target_filter": {"name": "Odoo"}},
            ],
        )
        self.assertEqual(result["query_summary"]["total_paths_found"], 1)
        target_names = [n["name"] for n in result["target_entities"]]
        self.assertIn("Odoo", target_names)

    def test_05_multihop_query_executive_path(self):
        """Test 5: Verifies traversal from Person to Company to Tech."""
        engine_query = MultiHopQueryEngine(self.test_graph)
        result = engine_query.execute_query(
            start_node_type="PERSON",
            start_filters={"title": "Chief"},
            hops=[
                {"relationship_type": "EMPLOYED_AT", "target_node_type": "COMPANY"},
                {"relationship_type": "USES_TECH", "target_node_type": "TECHNOLOGY"},
            ],
        )
        self.assertGreaterEqual(result["query_summary"]["total_paths_found"], 2)
        target_ids = {n["id"] for n in result["target_entities"]}
        self.assertIn("t_odoo", target_ids)
        self.assertIn("t_python", target_ids)

    def test_06_path_navigator_bfs_shortest_path(self):
        """Test 6: Verifies unweighted degree of separation for warm introduction."""
        nav = PathNavigator(self.test_graph)
        path = nav.find_shortest_path_bfs("p_alice", "p_bob", max_depth=4)
        self.assertTrue(path["found"])
        self.assertEqual(path["degree_of_separation"], 2)
        self.assertEqual(len(path["path_nodes"]), 3)
        self.assertGreater(path["confidence_score"], 0.75)

    def test_07_path_navigator_dijkstra_weighted(self):
        """Test 7: Verifies weighted highest-confidence pathfinding."""
        nav = PathNavigator(self.test_graph)
        res = nav.find_weighted_path_dijkstra("p_alice", "p_bob")
        self.assertTrue(res["found"])
        self.assertEqual(res["degree_of_separation"], 2)
        self.assertAlmostEqual(res["confidence_score"], 0.92 * 0.88, places=2)

    def test_08_centrality_analyzer_pagerank(self):
        """Test 8: Verifies PageRank score convergence and ranking."""
        analyzer = CentralityAnalyzer(self.test_graph)
        pr = analyzer.compute_pagerank()
        self.assertEqual(len(pr), 7)
        total_pr = sum(pr.values())
        self.assertAlmostEqual(total_pr, 1.0, places=1)

        ranked = analyzer.get_ranked_influencers()
        self.assertGreater(len(ranked), 0)
        self.assertIn("pagerank_score", ranked[0])
        self.assertIn("influence_tier", ranked[0])

    def test_09_hybrid_search_federator(self):
        """Test 9: Verifies hybrid search combining keyword, vector, and graph centrality boost."""
        federator = HybridSearchFederator(self.test_graph)
        results = federator.search(
            query="Odoo ERP Sydney",
            lexical_weight=0.5,
            vector_weight=0.3,
            graph_weight=0.2,
            limit=5,
        )
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertGreater(top["final_score"], 0.0)
        self.assertIn("lexical_score", top)
        self.assertIn("vector_score", top)
        self.assertIn("graph_score", top)
        self.assertIn("explanation", top)

    def test_10_entity_graph_isolation_invariant(self):
        """Test 10: Ensures entity graph traversals and queries NEVER mutate saved_leads."""
        initial_saved_count = self.db.query(SavedLead).count()

        # Run multi-hop query
        res = self.client.post(
            "/api/v1/graph/query",
            json={
                "start_node_type": "COMPANY",
                "start_filters": {},
                "hops": [{"relationship_type": "USES_TECH", "target_node_type": "TECHNOLOGY"}],
                "limit": 10,
            },
        )
        self.assertEqual(res.status_code, 200)

        # Run hybrid search
        res2 = self.client.post(
            "/api/v1/graph/hybrid-search",
            json={"query": "Odoo Australia", "limit": 10},
        )
        self.assertEqual(res2.status_code, 200)

        # Check saved_leads count is strictly untouched
        final_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(final_saved_count, initial_saved_count)

    def test_11_entity_graph_api_endpoints(self):
        """Test 11: Validates API endpoints /stats, /query, /shortest-path, /centrality, /hybrid-search."""
        # Stats
        r_stats = self.client.get("/api/v1/graph/stats")
        self.assertEqual(r_stats.status_code, 200)
        stats = r_stats.json()
        self.assertGreaterEqual(stats["total_nodes"], 4)
        self.assertGreaterEqual(stats["total_edges"], 4)

        # Centrality
        r_cent = self.client.get("/api/v1/graph/centrality?limit=10")
        self.assertEqual(r_cent.status_code, 200)
        influencers = r_cent.json()
        self.assertGreater(len(influencers), 0)
        self.assertIn("influence_tier", influencers[0])

        # Shortest path (between Sarah Jenkins and David Chen)
        r_path = self.client.post(
            "/api/v1/graph/shortest-path",
            json={"source_id": "person_sarah", "target_id": "person_david", "max_depth": 5},
        )
        self.assertEqual(r_path.status_code, 200)
        path_data = r_path.json()
        self.assertTrue(path_data["found"])
        self.assertGreaterEqual(path_data["degree_of_separation"], 1)

        # Hybrid Search
        r_search = self.client.post(
            "/api/v1/graph/hybrid-search",
            json={"query": "Atlassian Sydney", "limit": 5},
        )
        self.assertEqual(r_search.status_code, 200)
        hits = r_search.json()
        self.assertGreater(len(hits), 0)


if __name__ == "__main__":
    unittest.main()
