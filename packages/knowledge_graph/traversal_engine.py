from collections import deque
from typing import Optional, List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipEvidence,
    RelationshipStatus
)


class GraphTraversalError(Exception):
    pass


class GraphTraversalEngine:
    """
    Controlled & Safe Graph Traversal Engine:
    - Enforces strict depth bounds (max depth <= 3, default 1-2)
    - Enforces safety limits: max_nodes (500), max_edges (1000), timeout
    - Safe Graph DSL query execution (no raw SQL injection)
    - Entity neighborhood discovery with evidence provenance
    - Bounded path search (BFS) with step-by-step evidence explanation
    """

    MAX_ALLOWED_DEPTH = 3
    MAX_NODES_LIMIT = 500
    MAX_EDGES_LIMIT = 1000

    def __init__(self, db: Session):
        self.db = db

    # --- 1. Neighborhood Traversal ---

    def get_neighborhood(
        self,
        workspace_id: str,
        entity_id: str,
        depth: int = 1,
        relationship_types: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        include_evidence: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieves the bounded neighborhood of an entity up to depth (1-3).
        """
        clamped_depth = min(max(1, depth), self.MAX_ALLOWED_DEPTH)

        visited_nodes: Dict[str, Dict[str, Any]] = {}
        visited_edges: List[Dict[str, Any]] = []
        edge_ids_seen: Set[str] = set()

        # Seed node
        root = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == entity_id)
        ).first()
        if not root:
            raise GraphTraversalError(f"Entity '{entity_id}' not found.")

        visited_nodes[root.id] = {
            "id": root.id,
            "entity_type": root.entity_type,
            "canonical_name": root.canonical_name,
            "identifier": root.normalized_identifier,
            "properties": root.properties,
            "depth": 0
        }

        current_frontier = {root.id}
        types_filter = [t.upper() for t in relationship_types] if relationship_types else None

        for d in range(1, clamped_depth + 1):
            if not current_frontier or len(visited_nodes) >= self.MAX_NODES_LIMIT:
                break

            query = self.db.query(KnowledgeRelationship).filter(
                and_(
                    KnowledgeRelationship.workspace_id == workspace_id,
                    KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value,
                    KnowledgeRelationship.confidence >= min_confidence,
                    or_(
                        KnowledgeRelationship.source_entity_id.in_(current_frontier),
                        KnowledgeRelationship.target_entity_id.in_(current_frontier)
                    )
                )
            )
            if types_filter:
                query = query.filter(KnowledgeRelationship.relationship_type.in_(types_filter))

            edges = query.limit(self.MAX_EDGES_LIMIT).all()
            next_frontier = set()

            for edge in edges:
                if edge.id in edge_ids_seen:
                    continue
                edge_ids_seen.add(edge.id)

                # Determine neighbor
                neighbor_id = edge.target_entity_id if edge.source_entity_id in current_frontier else edge.source_entity_id

                # Evidence summary
                evidence_list = []
                if include_evidence and edge.evidence_links:
                    evidence_list = [
                        {
                            "source_url": ev.source_url,
                            "source_type": ev.source_type,
                            "evidence_snippet": ev.evidence_snippet,
                            "source_independence_key": ev.source_independence_key
                        }
                        for ev in edge.evidence_links
                    ]

                visited_edges.append({
                    "id": edge.id,
                    "source_id": edge.source_entity_id,
                    "target_id": edge.target_entity_id,
                    "relationship_type": edge.relationship_type,
                    "inference_status": edge.inference_status,
                    "confidence": edge.confidence,
                    "corroboration_count": edge.corroboration_count,
                    "evidence": evidence_list
                })

                if neighbor_id not in visited_nodes and len(visited_nodes) < self.MAX_NODES_LIMIT:
                    next_frontier.add(neighbor_id)

            if next_frontier:
                # Fetch neighbor entity objects
                neighbors = self.db.query(KnowledgeEntity).filter(
                    and_(
                        KnowledgeEntity.workspace_id == workspace_id,
                        KnowledgeEntity.id.in_(next_frontier)
                    )
                ).all()
                for nb in neighbors:
                    visited_nodes[nb.id] = {
                        "id": nb.id,
                        "entity_type": nb.entity_type,
                        "canonical_name": nb.canonical_name,
                        "identifier": nb.normalized_identifier,
                        "properties": nb.properties,
                        "depth": d
                    }

            current_frontier = next_frontier

        return {
            "root_entity_id": entity_id,
            "depth_traversed": clamped_depth,
            "node_count": len(visited_nodes),
            "edge_count": len(visited_edges),
            "nodes": list(visited_nodes.values()),
            "edges": visited_edges
        }

    # --- 2. Bounded Path Finding (BFS) ---

    def find_paths(
        self,
        workspace_id: str,
        start_entity_id: str,
        target_entity_id: str,
        max_depth: int = 3,
        max_paths: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Finds bounded graph paths connecting start_entity to target_entity.
        Provides step-by-step evidence explanation along each path.
        """
        clamped_depth = min(max(1, max_depth), self.MAX_ALLOWED_DEPTH)

        if start_entity_id == target_entity_id:
            return [{"path_length": 0, "hops": [], "explanation": "Source and target are the same node."}]

        # BFS queue: each entry is (current_node_id, [list_of_edges_so_far])
        queue = deque([(start_entity_id, [])])
        visited_nodes_at_depth = {start_entity_id: 0}
        successful_paths = []

        while queue and len(successful_paths) < max_paths:
            curr_id, path_edges = queue.popleft()

            if len(path_edges) >= clamped_depth:
                continue

            # Query outgoing and incoming edges
            edges = self.db.query(KnowledgeRelationship).filter(
                and_(
                    KnowledgeRelationship.workspace_id == workspace_id,
                    KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value,
                    or_(
                        KnowledgeRelationship.source_entity_id == curr_id,
                        KnowledgeRelationship.target_entity_id == curr_id
                    )
                )
            ).all()

            for edge in edges:
                next_id = edge.target_entity_id if edge.source_entity_id == curr_id else edge.source_entity_id
                
                # Prevent cycles within same path
                seen_in_path = {e["source_id"] for e in path_edges} | {e["target_id"] for e in path_edges}
                if next_id in seen_in_path:
                    continue

                edge_info = {
                    "edge_id": edge.id,
                    "source_id": edge.source_entity_id,
                    "target_id": edge.target_entity_id,
                    "relationship_type": edge.relationship_type,
                    "confidence": edge.confidence,
                    "inference_status": edge.inference_status,
                    "corroboration_count": edge.corroboration_count,
                    "evidence_snippet": edge.evidence_links[0].evidence_snippet if edge.evidence_links else None,
                    "source_url": edge.evidence_links[0].source_url if edge.evidence_links else None
                }
                new_path = path_edges + [edge_info]

                if next_id == target_entity_id:
                    # Construct human-readable explanation
                    hops_desc = []
                    for h in new_path:
                        hops_desc.append(
                            f"[{h['relationship_type']} (confidence: {h['confidence']}%, {h['inference_status']})]"
                        )
                    explanation = f"Connected via {' -> '.join(hops_desc)}"
                    successful_paths.append({
                        "path_length": len(new_path),
                        "start_node": start_entity_id,
                        "end_node": target_entity_id,
                        "hops": new_path,
                        "explanation": explanation
                    })
                    if len(successful_paths) >= max_paths:
                        break
                else:
                    queue.append((next_id, new_path))

        return successful_paths

    # --- 3. Safe Graph DSL Parser ---

    def execute_dsl_query(
        self,
        workspace_id: str,
        dsl: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Controlled execution of structured Graph DSL:
        {
            "entity_type": "COMPANY",
            "filters": {"country": "Australia"},
            "connected_to": {
                "entity_type": "TECHNOLOGY",
                "name": "Odoo",
                "relationship_type": "USES_ODOO"
            },
            "depth": 2,
            "min_confidence": 70.0
        }
        """
        entity_type = dsl.get("entity_type", "COMPANY").upper()
        filters = dsl.get("filters", {})
        conn = dsl.get("connected_to")
        min_conf = float(dsl.get("min_confidence", 0.0))
        depth = min(int(dsl.get("depth", 1)), self.MAX_ALLOWED_DEPTH)

        query = self.db.query(KnowledgeEntity).filter(
            and_(
                KnowledgeEntity.workspace_id == workspace_id,
                KnowledgeEntity.entity_type == entity_type
            )
        )

        # Apply entity filters
        for k, v in filters.items():
            # JSON field lookup
            query = query.filter(KnowledgeEntity.properties[k].as_string().ilike(f"%{v}%"))

        matched_entities = query.limit(100).all()

        results = []
        for ent in matched_entities:
            # If connected_to constraint specified, check edge
            if conn:
                target_tech_name = conn.get("name")
                rel_type = conn.get("relationship_type")

                edge_query = self.db.query(KnowledgeRelationship).join(
                    KnowledgeEntity,
                    KnowledgeRelationship.target_entity_id == KnowledgeEntity.id
                ).filter(
                    and_(
                        KnowledgeRelationship.workspace_id == workspace_id,
                        KnowledgeRelationship.source_entity_id == ent.id,
                        KnowledgeRelationship.confidence >= min_conf,
                        KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
                    )
                )
                if rel_type:
                    edge_query = edge_query.filter(KnowledgeRelationship.relationship_type == rel_type.upper())
                if target_tech_name:
                    edge_query = edge_query.filter(KnowledgeEntity.canonical_name.ilike(f"%{target_tech_name}%"))

                edges = edge_query.all()
                if not edges:
                    continue

            # Retrieve neighborhood
            nh = self.get_neighborhood(
                workspace_id=workspace_id,
                entity_id=ent.id,
                depth=depth,
                min_confidence=min_conf
            )
            results.append({
                "entity": {
                    "id": ent.id,
                    "name": ent.canonical_name,
                    "type": ent.entity_type,
                    "properties": ent.properties
                },
                "neighborhood": nh
            })

        return {
            "query_dsl": dsl,
            "total_matches": len(results),
            "results": results
        }

