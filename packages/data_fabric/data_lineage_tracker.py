"""
Data Lineage Tracker (Phase 39)
Maintains directed acyclic graphs (DAG) of data asset provenance, upstream dependencies,
and downstream impact analysis across the enterprise data fabric.
"""

from typing import Any, Dict, List, Set, Optional
from collections import defaultdict


class LineageCycleError(Exception):
    """Raised when adding a lineage edge would introduce a directed cycle."""
    pass


class DataLineageTracker:
    """Tracks cross-domain data transformation lineage and impact graphs."""

    def __init__(self):
        # source -> set of targets
        self._forward_graph: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # target -> set of sources
        self._reverse_graph: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    @staticmethod
    def _asset_key(domain: str, asset: str) -> str:
        return f"{domain.upper()}::{asset}"

    def add_edge(
        self,
        source_domain: str,
        source_asset: str,
        target_domain: str,
        target_asset: str,
        transformation_type: str = "ETL",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Registers a directed lineage transformation edge from source to target asset."""
        src = self._asset_key(source_domain, source_asset)
        tgt = self._asset_key(target_domain, target_asset)

        if src == tgt:
            raise LineageCycleError(f"Self-referential lineage loop detected on {src}.")

        # Cycle check: verify target does not already lead to source
        if self._can_reach(tgt, src):
            raise LineageCycleError(f"Lineage cycle detected: adding edge {src} -> {tgt} would cause a loop.")

        edge_data = {
            "source": src,
            "target": tgt,
            "source_domain": source_domain.upper(),
            "source_asset": source_asset,
            "target_domain": target_domain.upper(),
            "target_asset": target_asset,
            "transformation": transformation_type,
            "metadata": metadata or {},
        }

        self._forward_graph[src].append(edge_data)
        self._reverse_graph[tgt].append(edge_data)
        return edge_data

    def _can_reach(self, start: str, end: str) -> bool:
        """DFS to check if start can reach end in forward graph."""
        visited: Set[str] = set()
        stack = [start]
        while stack:
            curr = stack.pop()
            if curr == end:
                return True
            if curr not in visited:
                visited.add(curr)
                for edge in self._forward_graph[curr]:
                    stack.append(edge["target"])
        return False

    def trace_downstream_impact(self, domain: str, asset: str) -> Dict[str, Any]:
        """Traces all downstream assets affected if this source asset changes."""
        start_key = self._asset_key(domain, asset)
        impacted_nodes: Set[str] = set()
        edges_traversed: List[Dict[str, Any]] = []

        stack = [start_key]
        while stack:
            curr = stack.pop()
            for edge in self._forward_graph[curr]:
                target = edge["target"]
                edges_traversed.append(edge)
                if target not in impacted_nodes:
                    impacted_nodes.add(target)
                    stack.append(target)

        return {
            "origin": start_key,
            "impacted_count": len(impacted_nodes),
            "impacted_assets": sorted(list(impacted_nodes)),
            "lineage_path": edges_traversed,
        }

    def trace_upstream_provenance(self, domain: str, asset: str) -> Dict[str, Any]:
        """Traces all upstream sources that feed into this target asset."""
        target_key = self._asset_key(domain, asset)
        source_nodes: Set[str] = set()
        edges_traversed: List[Dict[str, Any]] = []

        stack = [target_key]
        while stack:
            curr = stack.pop()
            for edge in self._reverse_graph[curr]:
                source = edge["source"]
                edges_traversed.append(edge)
                if source not in source_nodes:
                    source_nodes.add(source)
                    stack.append(source)

        return {
            "target": target_key,
            "upstream_count": len(source_nodes),
            "source_assets": sorted(list(source_nodes)),
            "lineage_path": edges_traversed,
        }
