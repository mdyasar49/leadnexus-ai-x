import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class RetrievalRankingEngine:
    """
    Multi-Signal Retrieval Ranking & Deduplication Engine:
    - Ranks candidate items using composite scoring:
        Semantic Similarity (35%)
        Keyword Score (25%)
        Exact Match Score (15%)
        Graph Relevance (10%)
        Freshness (8%)
        Source Reliability (7%)
    - Detects syndicated/copied content clusters to prevent echo-chamber ranking inflation
    - Trims candidates to fit strict context budget
    """

    def __init__(
        self,
        semantic_weight: float = 0.35,
        keyword_weight: float = 0.25,
        exact_weight: float = 0.15,
        graph_weight: float = 0.10,
        freshness_weight: float = 0.08,
        reliability_weight: float = 0.07
    ):
        self.w_semantic = semantic_weight
        self.w_keyword = keyword_weight
        self.w_exact = exact_weight
        self.w_graph = graph_weight
        self.w_freshness = freshness_weight
        self.w_reliability = reliability_weight

    @staticmethod
    def extract_apex_domain(url: str) -> str:
        """Extracts normalized hostname/domain to identify syndicated copy networks."""
        if not url:
            return "internal"
        try:
            parsed = urlparse(url.strip())
            host = parsed.netloc or parsed.path
            if ":" in host:
                host = host.split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            return host.lower()
        except Exception:
            return "unknown"

    def rank_and_deduplicate(
        self,
        candidates: List[Dict[str, Any]],
        max_items: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Calculates composite score for each candidate, identifies duplicate clusters,
        applies source independence discount, and returns top-ranked items.
        """
        seen_domains: Dict[str, int] = {}
        seen_snippet_hashes: set = set()
        scored_items: List[Dict[str, Any]] = []

        for item in candidates:
            snippet = item.get("snippet", "")
            snip_hash = hashlib.sha256(snippet[:200].encode("utf-8")).hexdigest()

            # Exact text clone deduplication
            if snip_hash in seen_snippet_hashes:
                continue
            seen_snippet_hashes.add(snip_hash)

            # Source Independence: Track domain frequency
            domain = self.extract_apex_domain(item.get("source_url", ""))
            domain_freq = seen_domains.get(domain, 0) + 1
            seen_domains[domain] = domain_freq

            # Discount subsequent items from the exact same syndicated domain
            independence_factor = 1.0 / (domain_freq ** 0.5)

            # Compute composite ranking score
            sem = item.get("semantic_score", 0.0)
            kw = item.get("keyword_score", 0.0)
            exact = item.get("exact_score", 0.0)
            graph = item.get("graph_score", 0.0)
            fresh = item.get("freshness_score", 1.0)
            rel = item.get("source_reliability", 0.8)

            raw_score = (
                (sem * self.w_semantic) +
                (kw * self.w_keyword) +
                (exact * self.w_exact) +
                (graph * self.w_graph) +
                (fresh * self.w_freshness) +
                (rel * self.w_reliability)
            )

            final_score = round(raw_score * independence_factor, 4)

            scored = dict(item)
            scored["final_score"] = final_score
            scored["source_independence_score"] = round(independence_factor, 2)
            scored["copy_cluster_id"] = domain
            scored_items.append(scored)

        # Sort descending by final score
        scored_items.sort(key=lambda x: x["final_score"], reverse=True)

        # Assign rank and apply max items budget
        ranked = []
        for rank_idx, it in enumerate(scored_items[:max_items], start=1):
            it["rank"] = rank_idx
            ranked.append(it)

        return ranked

