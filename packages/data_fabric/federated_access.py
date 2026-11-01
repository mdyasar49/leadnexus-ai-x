"""
Federated Access Router (Phase 39)
Provides unified querying and graph traversal across all 13 canonical enterprise data domains:
COMPANIES, PEOPLE, CONTACTS, LEADS, EVIDENCE, SIGNALS, INTENT, RESEARCH,
GRAPH, ANALYTICS, WORKFLOWS, MONITORING, INTEGRATIONS.
"""

from typing import Any, Dict, List, Optional
from collections import defaultdict


class FederatedAccessRouter:
    """Dispatches queries and traverses cross-domain relationships across the enterprise data fabric."""

    def __init__(self):
        # In-memory indices for quick routing and relationships
        self._relations: List[Dict[str, Any]] = []

    def register_relation(
        self,
        primary_domain: str,
        primary_id: str,
        related_domain: str,
        related_id: str,
        relationship_type: str,
        confidence_score: float = 1.0,
    ) -> Dict[str, Any]:
        """Registers a cross-domain relationship edge."""
        rel = {
            "primary_domain": primary_domain.upper(),
            "primary_id": str(primary_id),
            "related_domain": related_domain.upper(),
            "related_id": str(related_id),
            "relationship_type": relationship_type,
            "confidence_score": confidence_score,
        }
        self._relations.append(rel)
        return rel

    def get_related_entities(
        self,
        domain: str,
        entity_id: str,
        target_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Finds all entities related to a given domain entity."""
        target_d = target_domain.upper() if target_domain else None
        dom = domain.upper()
        ent_id = str(entity_id)

        results = []
        for r in self._relations:
            if r["primary_domain"] == dom and r["primary_id"] == ent_id:
                if target_d is None or r["related_domain"] == target_d:
                    results.append({
                        "domain": r["related_domain"],
                        "entity_id": r["related_id"],
                        "relationship": r["relationship_type"],
                        "direction": "OUTBOUND",
                        "confidence": r["confidence_score"],
                    })
            elif r["related_domain"] == dom and r["related_id"] == ent_id:
                if target_d is None or r["primary_domain"] == target_d:
                    results.append({
                        "domain": r["primary_domain"],
                        "entity_id": r["primary_id"],
                        "relationship": r["relationship_type"],
                        "direction": "INBOUND",
                        "confidence": r["confidence_score"],
                    })

        return results

    def build_cross_domain_subgraph(
        self,
        domain: str,
        entity_id: str,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """Constructs an integrated multi-domain relationship graph around an entity."""
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        visited = set()

        def dfs(current_domain: str, current_id: str, depth: int):
            node_key = f"{current_domain}:{current_id}"
            if depth > max_depth or node_key in visited:
                return
            visited.add(node_key)
            nodes[node_key] = {"domain": current_domain, "id": current_id}

            related = self.get_related_entities(current_domain, current_id)
            for item in related:
                rel_domain = item["domain"]
                rel_id = item["entity_id"]
                target_key = f"{rel_domain}:{rel_id}"

                edges.append({
                    "source": node_key,
                    "target": target_key,
                    "relationship": item["relationship"],
                    "confidence": item["confidence"],
                })
                dfs(rel_domain, rel_id, depth + 1)

        dfs(domain.upper(), str(entity_id), 0)
        return {
            "root": f"{domain.upper()}:{entity_id}",
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_entities": len(nodes),
            "total_connections": len(edges),
        }

