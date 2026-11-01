"""
LeadNexus AI X - Phase 46: Warm Introduction & Shortest Path Navigator
Discovers shortest connection paths and degree of separation for executive introductions.
"""

import heapq
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple
from packages.graph.graph_index import GraphIndex


class PathNavigator:
    def __init__(self, index: GraphIndex):
        self.index = index

    def find_shortest_path_bfs(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Finds shortest unweighted path using bidirectional-friendly BFS."""
        if source_id == target_id:
            src_node = self.index.get_node(source_id)
            if not src_node:
                return None
            return {
                "found": True,
                "source_id": source_id,
                "target_id": target_id,
                "degree_of_separation": 0,
                "path_nodes": [src_node],
                "path_edges": [],
                "confidence_score": 1.0,
            }

        # Queue contains: (current_node_id, path_of_nodes, path_of_edges, accumulated_confidence)
        queue: deque = deque([(source_id, [self.index.get_node(source_id)], [], 1.0)])
        visited: Set[str] = {source_id}

        while queue:
            curr_id, node_path, edge_path, conf = queue.popleft()

            if len(edge_path) >= max_depth:
                continue

            # Outgoing edges
            for edge in self.index.get_outgoing_edges(curr_id):
                nxt_id = edge["target_id"]
                nxt_node = self.index.get_node(nxt_id)
                if not nxt_node:
                    continue

                new_conf = conf * edge.get("confidence", 0.95)
                if nxt_id == target_id:
                    return {
                        "found": True,
                        "source_id": source_id,
                        "target_id": target_id,
                        "degree_of_separation": len(edge_path) + 1,
                        "path_nodes": node_path + [nxt_node],
                        "path_edges": edge_path + [edge],
                        "confidence_score": round(new_conf, 4),
                    }

                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append((nxt_id, node_path + [nxt_node], edge_path + [edge], new_conf))

            # Incoming edges (treat graph as undirected for connection discovery)
            for edge in self.index.get_incoming_edges(curr_id):
                nxt_id = edge["source_id"]
                nxt_node = self.index.get_node(nxt_id)
                if not nxt_node:
                    continue

                new_conf = conf * edge.get("confidence", 0.95)
                if nxt_id == target_id:
                    return {
                        "found": True,
                        "source_id": source_id,
                        "target_id": target_id,
                        "degree_of_separation": len(edge_path) + 1,
                        "path_nodes": node_path + [nxt_node],
                        "path_edges": edge_path + [edge],
                        "confidence_score": round(new_conf, 4),
                    }

                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append((nxt_id, node_path + [nxt_node], edge_path + [edge], new_conf))

        return {
            "found": False,
            "source_id": source_id,
            "target_id": target_id,
            "degree_of_separation": -1,
            "path_nodes": [],
            "path_edges": [],
            "confidence_score": 0.0,
        }

    def find_weighted_path_dijkstra(
        self,
        source_id: str,
        target_id: str,
        max_cost: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the highest-confidence shortest path where edge cost = 1.0 - confidence + weight.
        """
        if source_id == target_id:
            src_node = self.index.get_node(source_id)
            if not src_node:
                return None
            return {
                "found": True,
                "source_id": source_id,
                "target_id": target_id,
                "degree_of_separation": 0,
                "path_nodes": [src_node],
                "path_edges": [],
                "confidence_score": 1.0,
            }

        # Min-heap priority queue: (cumulative_cost, node_id, node_ids_path, edge_ids_path, cumulative_confidence)
        pq: List[Tuple[float, str, List[str], List[str], float]] = [
            (0.0, source_id, [source_id], [], 1.0)
        ]
        best_costs: Dict[str, float] = {source_id: 0.0}

        while pq:
            cost, curr_id, node_ids, edge_ids, conf = heapq.heappop(pq)

            if curr_id == target_id:
                nodes = [self.index.get_node(nid) for nid in node_ids]
                edges = [self.index._edges[eid] for eid in edge_ids]
                return {
                    "found": True,
                    "source_id": source_id,
                    "target_id": target_id,
                    "degree_of_separation": len(edge_ids),
                    "path_nodes": nodes,
                    "path_edges": edges,
                    "confidence_score": round(conf, 4),
                    "total_cost": round(cost, 4),
                }

            if cost > best_costs.get(curr_id, float("inf")):
                continue

            # Check neighbors
            neighbors: List[Tuple[str, Dict[str, Any]]] = []
            for e in self.index.get_outgoing_edges(curr_id):
                neighbors.append((e["target_id"], e))
            for e in self.index.get_incoming_edges(curr_id):
                neighbors.append((e["source_id"], e))

            for nxt_id, edge in neighbors:
                e_conf = edge.get("confidence", 0.95)
                e_weight = edge.get("weight", 1.0)
                edge_cost = (1.0 - e_conf) + (0.5 * e_weight)
                next_cost = cost + edge_cost

                if next_cost < best_costs.get(nxt_id, float("inf")) and next_cost <= max_cost:
                    best_costs[nxt_id] = next_cost
                    new_conf = conf * e_conf
                    heapq.heappush(
                        pq,
                        (
                            next_cost,
                            nxt_id,
                            node_ids + [nxt_id],
                            edge_ids + [edge["id"]],
                            new_conf,
                        ),
                    )

        return {
            "found": False,
            "source_id": source_id,
            "target_id": target_id,
            "degree_of_separation": -1,
            "path_nodes": [],
            "path_edges": [],
            "confidence_score": 0.0,
        }
