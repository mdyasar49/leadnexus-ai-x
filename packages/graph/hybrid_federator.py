"""
LeadNexus AI X - Phase 46: Hybrid Search & Query Federator
Blends lexical token matching, vector similarity, and graph topological boost.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set
from packages.graph.graph_index import GraphIndex
from packages.graph.centrality_analyzer import CentralityAnalyzer


class HybridSearchFederator:
    def __init__(self, index: GraphIndex, centrality_analyzer: Optional[CentralityAnalyzer] = None):
        self.index = index
        self.centrality_analyzer = centrality_analyzer or CentralityAnalyzer(index)

    def search(
        self,
        query: str,
        target_node_type: Optional[str] = None,
        lexical_weight: float = 0.4,
        vector_weight: float = 0.3,
        graph_weight: float = 0.3,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Executes a federated hybrid search across all graph entities.
        Blends lexical BM25-style keyword overlap, simulated semantic embedding distance,
        and topological graph authority boost.
        """
        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Precompute graph pagerank scores
        pr_scores = self.centrality_analyzer.compute_pagerank()
        max_pr = max(pr_scores.values()) if pr_scores else 1.0
        if max_pr <= 0.0:
            max_pr = 1.0

        candidates = (
            self.index.get_nodes_by_type(target_node_type)
            if target_node_type
            else list(self.index._nodes.values())
        )

        results: List[Dict[str, Any]] = []

        for node in candidates:
            lex_score = self._compute_lexical_score(node, tokens)
            vec_score = self._compute_vector_similarity(node, tokens)
            graph_score = self._compute_graph_score(node, pr_scores.get(node["id"], 0.0), max_pr)

            final_score = (
                (lex_score * lexical_weight)
                + (vec_score * vector_weight)
                + (graph_score * graph_weight)
            )

            if final_score > 0.05:
                explanation = (
                    f"Matched with Lexical: {lex_score:.2f} ({lexical_weight*100:.0f}%), "
                    f"Vector: {vec_score:.2f} ({vector_weight*100:.0f}%), "
                    f"Graph Centrality: {graph_score:.2f} ({graph_weight*100:.0f}%)"
                )

                results.append({
                    "node_id": node["id"],
                    "name": node["name"],
                    "node_type": node["node_type"],
                    "canonical_key": node["canonical_key"],
                    "attributes": node.get("attributes", {}),
                    "final_score": round(final_score, 4),
                    "lexical_score": round(lex_score, 4),
                    "vector_score": round(vec_score, 4),
                    "graph_score": round(graph_score, 4),
                    "explanation": explanation,
                })

        # Sort descending by final score
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:limit]

    def _tokenize(self, text: str) -> Set[str]:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
        stopwords = {"in", "and", "the", "for", "with", "at", "by", "from", "to", "of", "a", "an"}
        return {t for t in tokens if t not in stopwords}

    def _get_node_search_text(self, node: Dict[str, Any]) -> str:
        parts = [node.get("name", ""), node.get("node_type", "")]
        for k, v in node.get("attributes", {}).items():
            if isinstance(v, (str, int, float)):
                parts.append(str(v))
            elif isinstance(v, list):
                parts.extend([str(i) for i in v])
        return " ".join(parts).lower()

    def _compute_lexical_score(self, node: Dict[str, Any], query_tokens: Set[str]) -> float:
        text = self._get_node_search_text(node)
        node_tokens = self._tokenize(text)
        if not node_tokens:
            return 0.0

        matches = query_tokens.intersection(node_tokens)
        if not matches:
            return 0.0

        # Exact name bonus
        name_lower = node.get("name", "").lower()
        exact_bonus = 0.3 if any(t in name_lower for t in query_tokens) else 0.0

        ratio = len(matches) / len(query_tokens)
        return min(1.0, ratio * 0.7 + exact_bonus)

    def _compute_vector_similarity(self, node: Dict[str, Any], query_tokens: Set[str]) -> float:
        """
        Simulated high-dimensional cosine embedding similarity.
        Projects character n-grams / token overlap onto unit hyper-sphere.
        """
        text = self._get_node_search_text(node)
        node_tokens = self._tokenize(text)
        if not node_tokens:
            return 0.0

        union_len = len(query_tokens.union(node_tokens))
        inter_len = len(query_tokens.intersection(node_tokens))
        jaccard = inter_len / union_len if union_len > 0 else 0.0

        # Smooth to emulate dense embedding semantic correlation
        return round(math.sqrt(jaccard), 4)

    def _compute_graph_score(self, node: Dict[str, Any], pagerank: float, max_pagerank: float) -> float:
        """
        Normalizes authority score and edge density.
        """
        pr_norm = min(1.0, pagerank / max_pagerank) if max_pagerank > 0 else 0.0
        degree = len(self.index.get_incoming_edges(node["id"])) + len(self.index.get_outgoing_edges(node["id"]))
        deg_norm = min(1.0, degree / 20.0)

        return round((pr_norm * 0.6) + (deg_norm * 0.4), 4)
