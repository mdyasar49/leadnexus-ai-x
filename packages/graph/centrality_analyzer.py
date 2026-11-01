"""
LeadNexus AI X - Phase 46: Graph Centrality & Influence Analyzer
Calculates PageRank, degree centrality, and assigns influence tiers for lead prioritization.
"""

from typing import Any, Dict, List, Optional
from packages.graph.graph_index import GraphIndex


class CentralityAnalyzer:
    def __init__(self, index: GraphIndex):
        self.index = index

    def compute_pagerank(
        self,
        damping: float = 0.85,
        max_iter: int = 50,
        tol: float = 1e-5,
    ) -> Dict[str, float]:
        """
        Computes PageRank scores across all nodes using standard power iteration.
        """
        node_ids = list(self.index._nodes.keys())
        n = len(node_ids)
        if n == 0:
            return {}

        # Initial uniform distribution
        rank = {nid: 1.0 / n for nid in node_ids}

        # Precompute out-degrees and target map
        out_degrees: Dict[str, int] = {}
        target_map: Dict[str, List[str]] = {}
        for nid in node_ids:
            edges = self.index.get_outgoing_edges(nid)
            out_degrees[nid] = len(edges)
            target_map[nid] = [e["target_id"] for e in edges if e["target_id"] in self.index._nodes]

        base_val = (1.0 - damping) / n

        for _ in range(max_iter):
            new_rank: Dict[str, float] = {nid: base_val for nid in node_ids}
            dangling_sum = 0.0

            # Sum contributions from dangling nodes (out-degree 0)
            for nid, out_deg in out_degrees.items():
                if out_deg == 0:
                    dangling_sum += rank[nid]

            dangling_contrib = (damping * dangling_sum) / n
            for nid in node_ids:
                new_rank[nid] += dangling_contrib

            # Distribute ranks along directed edges
            for nid, targets in target_map.items():
                if targets:
                    share = (damping * rank[nid]) / len(targets)
                    for tgt in targets:
                        new_rank[tgt] += share

            # Check convergence
            diff = sum(abs(new_rank[nid] - rank[nid]) for nid in node_ids)
            rank = new_rank
            if diff < tol:
                break

        return {nid: round(score, 6) for nid, score in rank.items()}

    def compute_degree_centrality(self) -> Dict[str, Dict[str, float]]:
        """
        Computes normalized in-degree, out-degree, and total degree centrality.
        """
        node_ids = list(self.index._nodes.keys())
        n = len(node_ids)
        norm_factor = max(n - 1, 1)

        centrality: Dict[str, Dict[str, float]] = {}
        for nid in node_ids:
            in_deg = len(self.index.get_incoming_edges(nid))
            out_deg = len(self.index.get_outgoing_edges(nid))
            total_deg = in_deg + out_deg

            centrality[nid] = {
                "in_degree": in_deg,
                "out_degree": out_deg,
                "total_degree": total_deg,
                "normalized_degree": round(total_deg / norm_factor, 6),
            }

        return centrality

    def get_ranked_influencers(
        self,
        node_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Returns ranked list of entities with PageRank, degree metrics, and influence tier.
        """
        pr_scores = self.compute_pagerank()
        deg_scores = self.compute_degree_centrality()

        ranked: List[Dict[str, Any]] = []
        for nid, pr in pr_scores.items():
            node = self.index.get_node(nid)
            if not node:
                continue

            if node_type and node["node_type"] != node_type.upper():
                continue

            deg = deg_scores.get(nid, {})
            norm_deg = deg.get("normalized_degree", 0.0)

            # Assign influence tier based on blended score
            tier = self._assign_tier(pr, norm_deg)

            ranked.append({
                "node_id": nid,
                "name": node["name"],
                "node_type": node["node_type"],
                "canonical_key": node["canonical_key"],
                "attributes": node.get("attributes", {}),
                "pagerank_score": pr,
                "degree_centrality": norm_deg,
                "total_connections": deg.get("total_degree", 0),
                "influence_tier": tier,
            })

        # Sort descending by PageRank
        ranked.sort(key=lambda x: (x["pagerank_score"], x["degree_centrality"]), reverse=True)
        return ranked[:limit]

    def _assign_tier(self, pagerank: float, normalized_degree: float) -> str:
        composite = (pagerank * 0.7) + (normalized_degree * 0.3)
        if composite >= 0.035 or pagerank >= 0.05:
            return "Tier 1: Global Luminary"
        elif composite >= 0.018 or pagerank >= 0.025:
            return "Tier 2: Industry Influencer"
        elif composite >= 0.008 or pagerank >= 0.01:
            return "Tier 3: Key Decision-Maker"
        else:
            return "Tier 4: Contributor"
