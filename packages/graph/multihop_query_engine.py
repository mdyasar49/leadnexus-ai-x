"""
LeadNexus AI X - Phase 46: Multi-Hop Federated Query Engine
Executes pattern-based multi-hop graph queries across entity types and relationship paths.
"""

from typing import Any, Dict, List, Optional
from packages.graph.graph_index import GraphIndex


class MultiHopQueryEngine:
    def __init__(self, index: GraphIndex):
        self.index = index

    def execute_query(
        self,
        start_node_type: str,
        start_filters: Optional[Dict[str, Any]] = None,
        hops: Optional[List[Dict[str, Any]]] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Executes a multi-hop traversal query starting from nodes of start_node_type matching start_filters.
        Each hop specifies relationship_type and target_node_type, with optional target_filter.
        """
        start_nodes = self.index.get_nodes_by_type(start_node_type)
        if start_filters:
            start_nodes = [n for n in start_nodes if self._matches_filter(n, start_filters)]

        hops = hops or []
        current_paths: List[List[Dict[str, Any]]] = [[n] for n in start_nodes]

        for hop in hops:
            rel_type = hop.get("relationship_type")
            target_type = hop.get("target_node_type")
            target_filter = hop.get("target_filter", {})

            next_paths: List[List[Dict[str, Any]]] = []
            for path in current_paths:
                current_node = path[-1]
                nid = current_node["id"]

                # Explore outgoing edges
                out_edges = self.index.get_outgoing_edges(nid, rel_type)
                for edge in out_edges:
                    target_node = self.index.get_node(edge["target_id"])
                    if not target_node:
                        continue
                    if target_type and target_node["node_type"] != target_type.upper():
                        continue
                    if target_filter and not self._matches_filter(target_node, target_filter):
                        continue
                    next_paths.append(path + [edge, target_node])

                # Explore incoming edges (bidirectional traversal support)
                in_edges = self.index.get_incoming_edges(nid, rel_type)
                for edge in in_edges:
                    source_node = self.index.get_node(edge["source_id"])
                    if not source_node:
                        continue
                    if target_type and source_node["node_type"] != target_type.upper():
                        continue
                    if target_filter and not self._matches_filter(source_node, target_filter):
                        continue
                    next_paths.append(path + [edge, source_node])

            current_paths = next_paths
            if not current_paths:
                break

        # Limit paths
        limited_paths = current_paths[:limit]

        # Extract unique terminal nodes
        terminal_nodes: Dict[str, Dict[str, Any]] = {}
        formatted_paths: List[Dict[str, Any]] = []

        for p in limited_paths:
            term_node = p[-1]
            terminal_nodes[term_node["id"]] = term_node
            formatted_paths.append({
                "start_node": p[0],
                "end_node": p[-1],
                "length": len(p),
                "steps": [item.get("name", item.get("relationship_type", "UNKNOWN")) for item in p],
            })

        return {
            "query_summary": {
                "start_node_type": start_node_type,
                "hops_count": len(hops),
                "total_paths_found": len(current_paths),
                "returned_paths": len(limited_paths),
                "unique_target_entities": len(terminal_nodes),
            },
            "target_entities": list(terminal_nodes.values()),
            "paths": formatted_paths,
        }

    def _matches_filter(self, node: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Evaluates whether node attributes match given filters."""
        for k, v in filters.items():
            # Check top-level or in attributes
            node_val = node.get(k)
            if node_val is None:
                node_val = node.get("attributes", {}).get(k)

            if node_val is None:
                return False

            if isinstance(v, str):
                if v.lower() not in str(node_val).lower():
                    return False
            elif node_val != v:
                return False
        return True
