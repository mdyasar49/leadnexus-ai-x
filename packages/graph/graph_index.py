"""
LeadNexus AI X - Phase 46: Entity Relationship Graph Index
High-performance in-memory index for entities, relationships, and neighborhood lookups.
"""

from typing import Any, Dict, List, Optional, Set, Tuple


class GraphIndex:
    def __init__(self):
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: Dict[str, Dict[str, Any]] = {}
        self._key_to_id: Dict[str, str] = {}
        self._type_to_ids: Dict[str, Set[str]] = {}
        self._adj: Dict[str, List[Dict[str, Any]]] = {}
        self._rev_adj: Dict[str, List[Dict[str, Any]]] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        canonical_key: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        key = canonical_key or f"{node_type.lower()}:{name.lower().strip()}"
        node = {
            "id": node_id,
            "node_type": node_type.upper(),
            "name": name,
            "canonical_key": key,
            "attributes": attributes or {},
        }
        self._nodes[node_id] = node
        self._key_to_id[key] = node_id

        nt = node_type.upper()
        if nt not in self._type_to_ids:
            self._type_to_ids[nt] = set()
        self._type_to_ids[nt].add(node_id)

        if node_id not in self._adj:
            self._adj[node_id] = []
        if node_id not in self._rev_adj:
            self._rev_adj[node_id] = []

        return node

    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        relationship_type: str,
        weight: float = 1.0,
        confidence: float = 0.95,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        edge = {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type.upper(),
            "weight": weight,
            "confidence": confidence,
            "properties": properties or {},
        }
        self._edges[edge_id] = edge

        if source_id not in self._adj:
            self._adj[source_id] = []
        self._adj[source_id].append(edge)

        if target_id not in self._rev_adj:
            self._rev_adj[target_id] = []
        self._rev_adj[target_id].append(edge)

        return edge

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(node_id)

    def get_node_by_key(self, canonical_key: str) -> Optional[Dict[str, Any]]:
        node_id = self._key_to_id.get(canonical_key)
        return self.get_node(node_id) if node_id else None

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        ids = self._type_to_ids.get(node_type.upper(), set())
        return [self._nodes[nid] for nid in ids if nid in self._nodes]

    def get_outgoing_edges(self, node_id: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        edges = self._adj.get(node_id, [])
        if relationship_type:
            rel = relationship_type.upper()
            return [e for e in edges if e["relationship_type"] == rel]
        return edges

    def get_incoming_edges(self, node_id: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        edges = self._rev_adj.get(node_id, [])
        if relationship_type:
            rel = relationship_type.upper()
            return [e for e in edges if e["relationship_type"] == rel]
        return edges

    def get_neighborhood(self, node_id: str, max_hops: int = 1) -> Dict[str, Any]:
        """Returns reachable subgraph up to max_hops away."""
        visited_nodes: Set[str] = {node_id}
        frontier: Set[str] = {node_id}
        collected_edges: List[Dict[str, Any]] = []

        for _ in range(max_hops):
            next_frontier: Set[str] = set()
            for current in frontier:
                # Outgoing edges
                for edge in self._adj.get(current, []):
                    collected_edges.append(edge)
                    tgt = edge["target_id"]
                    if tgt not in visited_nodes:
                        visited_nodes.add(tgt)
                        next_frontier.add(tgt)
                # Incoming edges
                for edge in self._rev_adj.get(current, []):
                    collected_edges.append(edge)
                    src = edge["source_id"]
                    if src not in visited_nodes:
                        visited_nodes.add(src)
                        next_frontier.add(src)
            frontier = next_frontier

        # Deduplicate edges
        dedup_edges = {e["id"]: e for e in collected_edges}
        nodes = [self._nodes[nid] for nid in visited_nodes if nid in self._nodes]

        return {
            "center_node_id": node_id,
            "nodes": nodes,
            "edges": list(dedup_edges.values()),
            "total_nodes": len(nodes),
            "total_edges": len(dedup_edges),
        }

    def get_stats(self) -> Dict[str, Any]:
        type_counts = {t: len(ids) for t, ids in self._type_to_ids.items()}
        edge_rel_counts: Dict[str, int] = {}
        for edge in self._edges.values():
            rel = edge["relationship_type"]
            edge_rel_counts[rel] = edge_rel_counts.get(rel, 0) + 1

        total_nodes = len(self._nodes)
        total_edges = len(self._edges)
        density = (
            (2.0 * total_edges) / (total_nodes * (total_nodes - 1))
            if total_nodes > 1
            else 0.0
        )

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "graph_density": round(density, 6),
            "node_type_distribution": type_counts,
            "edge_relationship_distribution": edge_rel_counts,
        }

    def clear(self):
        self._nodes.clear()
        self._edges.clear()
        self._key_to_id.clear()
        self._type_to_ids.clear()
        self._adj.clear()
        self._rev_adj.clear()
