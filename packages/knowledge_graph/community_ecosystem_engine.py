from typing import Optional, List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    GraphCommunity,
    GraphCommunityMember,
    CommunityType,
    RelationshipStatus,
    KnowledgeEntityType
)


class CommunityAndEcosystemEngine:
    """
    Graph Community Detection & Specialized Ecosystem Engine:
    - Identifies technology ecosystems, industry clusters, and partner networks
    - Constructs granular Odoo Ecosystem graphs (User vs Implementer vs Partner vs OCA)
    - Distinguishes statistical co-occurrence from verified technical integration
    - Visualizes buying committee roles (Economic Buyer, Technical Evaluator, Champion)
    """

    def __init__(self, db: Session):
        self.db = db

    # --- 1. Community Detection (Connected Components) ---

    def detect_communities(
        self,
        workspace_id: str,
        community_type: str = CommunityType.TECHNOLOGY_ECOSYSTEM.value
    ) -> List[GraphCommunity]:
        """
        Groups entities into connected clusters based on shared active relationships.
        Computes cluster density and designates centrality anchor nodes.
        """
        entities = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.workspace_id == workspace_id).all()
        relationships = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        # Build adjacency graph
        adj: Dict[str, Set[str]] = {e.id: set() for e in entities}
        for rel in relationships:
            if rel.source_entity_id in adj and rel.target_entity_id in adj:
                adj[rel.source_entity_id].add(rel.target_entity_id)
                adj[rel.target_entity_id].add(rel.source_entity_id)

        # BFS Connected Components
        visited = set()
        communities_created = []

        for ent in entities:
            if ent.id in visited:
                continue

            comp_nodes = []
            queue = [ent.id]
            visited.add(ent.id)

            while queue:
                curr = queue.pop(0)
                comp_nodes.append(curr)
                for neighbor in adj.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if len(comp_nodes) >= 2:
                # Find most central node (highest degree in cluster)
                central_node_id = max(comp_nodes, key=lambda nid: len(adj.get(nid, [])))
                density = round(len(relationships) / max(1, len(comp_nodes) * (len(comp_nodes) - 1)), 2)

                comm_name = f"{ent.canonical_name} Ecosystem Cluster"
                comm = GraphCommunity(
                    workspace_id=workspace_id,
                    community_name=comm_name,
                    community_type=community_type,
                    density=min(1.0, density),
                    centrality_node_id=central_node_id,
                    algorithm="CONNECTED_COMPONENTS"
                )
                self.db.add(comm)
                self.db.commit()
                self.db.refresh(comm)

                # Add members
                for nid in comp_nodes:
                    role = "CENTRAL_HUB" if nid == central_node_id else "MEMBER"
                    mem = GraphCommunityMember(
                        community_id=comm.id,
                        entity_id=nid,
                        role=role,
                        membership_confidence=0.95
                    )
                    self.db.add(mem)

                self.db.commit()
                communities_created.append(comm)

        return communities_created

    # --- 2. Odoo Ecosystem Graph ---

    def get_odoo_ecosystem_graph(
        self,
        workspace_id: str,
        min_confidence: float = 70.0
    ) -> Dict[str, Any]:
        """
        Builds the specialized Odoo ecosystem graph, categorizing entities into:
        - End Users (`USES_ODOO`)
        - Implementers / Solution Providers (`IMPLEMENTS_ODOO`)
        - Official Partners (`PARTNER_ECOSYSTEM`)
        - Migration Candidates (`ODOO_MIGRATION`)
        - Community / OCA Contributors (`OCA_CONTRIBUTION`)
        """
        odoo_rel_types = [
            "USES_ODOO", "IMPLEMENTS_ODOO", "SUPPORTS_ODOO",
            "PARTNER_ECOSYSTEM", "ODOO_MIGRATION", "ODOO_UPGRADE",
            "ODOO_INTEGRATION", "ODOO_CUSTOMIZATION"
        ]

        edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.relationship_type.in_(odoo_rel_types),
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value,
                KnowledgeRelationship.confidence >= min_confidence
            )
        ).all()

        nodes_map = {}
        links = []

        categorized_counts = {t: 0 for t in odoo_rel_types}

        for e in edges:
            categorized_counts[e.relationship_type] = categorized_counts.get(e.relationship_type, 0) + 1
            src = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == e.source_entity_id).first()
            tgt = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == e.target_entity_id).first()

            if src and src.id not in nodes_map:
                nodes_map[src.id] = {
                    "id": src.id,
                    "name": src.canonical_name,
                    "type": src.entity_type,
                    "properties": src.properties
                }
            if tgt and tgt.id not in nodes_map:
                nodes_map[tgt.id] = {
                    "id": tgt.id,
                    "name": tgt.canonical_name,
                    "type": tgt.entity_type,
                    "properties": tgt.properties
                }

            links.append({
                "source": e.source_entity_id,
                "target": e.target_entity_id,
                "relationship_type": e.relationship_type,
                "confidence": e.confidence,
                "corroboration_count": e.corroboration_count
            })

        return {
            "ecosystem": "ODOO_ENTERPRISE_ECOSYSTEM",
            "total_nodes": len(nodes_map),
            "total_edges": len(links),
            "category_breakdown": categorized_counts,
            "nodes": list(nodes_map.values()),
            "edges": links
        }

    # --- 3. Technology Ecosystem Graph ---

    def get_technology_ecosystem_graph(
        self,
        workspace_id: str,
        anchor_tech: str = "Odoo"
    ) -> Dict[str, Any]:
        """
        Analyzes technologies that commonly co-occur with anchor technology.
        Explicitly distinguishes co-occurrence from confirmed technical integration.
        """
        # Find anchor tech entity
        anchor = self.db.query(KnowledgeEntity).filter(
            and_(
                KnowledgeEntity.workspace_id == workspace_id,
                KnowledgeEntity.entity_type == KnowledgeEntityType.TECHNOLOGY.value,
                KnowledgeEntity.canonical_name.ilike(f"%{anchor_tech}%")
            )
        ).first()

        if not anchor:
            return {"anchor": anchor_tech, "related_technologies": [], "nodes": [], "edges": []}

        # Companies connected to anchor
        anchor_edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.target_entity_id == anchor.id,
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        comp_ids = [e.source_entity_id for e in anchor_edges]

        # Find other technologies linked to these companies
        co_edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.source_entity_id.in_(comp_ids),
                KnowledgeRelationship.target_entity_id != anchor.id,
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        tech_freq: Dict[str, Dict[str, Any]] = {}
        for ce in co_edges:
            t_ent = self.db.query(KnowledgeEntity).filter(
                and_(
                    KnowledgeEntity.id == ce.target_entity_id,
                    KnowledgeEntity.entity_type == KnowledgeEntityType.TECHNOLOGY.value
                )
            ).first()
            if t_ent:
                t_name = t_ent.canonical_name
                if t_name not in tech_freq:
                    tech_freq[t_name] = {
                        "technology_id": t_ent.id,
                        "technology_name": t_name,
                        "co_occurrence_count": 0,
                        "has_formal_integration_evidence": False,
                        "category": (t_ent.properties or {}).get("category", "SYSTEM")
                    }
                tech_freq[t_name]["co_occurrence_count"] += 1
                if ce.relationship_type in ("INTEGRATES_WITH", "ODOO_INTEGRATION"):
                    tech_freq[t_name]["has_formal_integration_evidence"] = True

        ranked_techs = sorted(tech_freq.values(), key=lambda x: x["co_occurrence_count"], reverse=True)
        return {
            "anchor_technology": anchor.canonical_name,
            "sample_companies_count": len(comp_ids),
            "co_occurring_technologies": ranked_techs
        }

    # --- 4. Buying Committee Graph ---

    def get_buying_committee_graph(
        self,
        workspace_id: str,
        company_entity_id: str
    ) -> Dict[str, Any]:
        """
        Visualizes the buying committee associated with a company:
        - Economic Buyer
        - Technical Evaluator
        - Champion
        - Influencer
        - Procurement
        """
        company = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == company_entity_id)
        ).first()
        if not company:
            raise ValueError(f"Company entity '{company_entity_id}' not found.")

        # Find person relationships
        person_edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.target_entity_id == company.id,
                KnowledgeRelationship.relationship_type.in_(["WORKS_AT", "LEADS", "MANAGES", "DIRECTS"]),
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        committee_members = []
        for pe in person_edges:
            person = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == pe.source_entity_id).first()
            if person and person.entity_type == KnowledgeEntityType.PERSON.value:
                props = person.properties or {}
                title = str(props.get("job_title", "")).lower()

                # Determine committee role
                if any(k in title for k in ["ceo", "managing director", "president", "owner", "cfo", "chief executive"]):
                    role = "ECONOMIC_BUYER"
                elif any(k in title for k in ["cto", "cio", "chief technology officer", "vp engineering", "head of engineering", "lead architect", "head of it", "it director", "technical"]):
                    role = "TECHNICAL_EVALUATOR"
                elif any(k in title for k in ["erp manager", "operations manager", "head of supply chain", "operations director"]):
                    role = "CHAMPION"
                elif any(k in title for k in ["procurement", "purchasing", "finance director"]):
                    role = "PROCUREMENT"
                else:
                    role = "INFLUENCER"

                committee_members.append({
                    "person_id": person.id,
                    "name": person.canonical_name,
                    "job_title": props.get("job_title", "Unknown"),
                    "email": props.get("email"),
                    "committee_role": role,
                    "is_verified_decision_maker": props.get("is_decision_maker", False),
                    "relationship_confidence": pe.confidence,
                    "corroboration_count": pe.corroboration_count
                })

        return {
            "company_id": company.id,
            "company_name": company.canonical_name,
            "total_committee_members": len(committee_members),
            "members": committee_members
        }
