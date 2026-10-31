from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipEvidence,
    RelationshipConflict,
    GraphHealthSnapshot,
    GraphCompletenessSnapshot,
    GraphResearchPath,
    GraphResearchRecommendation,
    GraphChangeEvent,
    RelationshipStatus,
    ConflictStatus,
    KnowledgeEntityType
)


class GraphIntelligenceEngine:
    """
    Graph Completeness, Health & Research Pathfinder Engine:
    - Computes 8-dimension Graph Completeness scores per entity
    - Monitors graph health (orphan nodes, stale edges, conflict rates, evidence coverage)
    - Discovers graph gaps and generates prioritized Graph Research Recommendations
    - Emits GraphChangeEvents to trigger real-time alerts
    """

    def __init__(self, db: Session):
        self.db = db

    # --- 1. Graph Completeness Evaluation ---

    def evaluate_entity_completeness(
        self,
        workspace_id: str,
        entity_id: str
    ) -> GraphCompletenessSnapshot:
        """
        Evaluates entity completeness across 8 essential dimensions:
        1. Identity (canonical name & normalized identifier)
        2. Domain (domain property)
        3. Geography (country/state/city)
        4. Technology (at least 1 technology edge)
        5. People (at least 1 person/contact edge)
        6. Decision Maker (at least 1 verified decision maker)
        7. Intent (intent signals or migration edges)
        8. Evidence (evidence records backing relationships)
        """
        entity = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == entity_id)
        ).first()
        if not entity:
            raise ValueError(f"Entity '{entity_id}' not found.")

        props = entity.properties or {}
        missing_dims = []
        score = 0.0

        # 1. Identity (10 pts)
        if entity.canonical_name and entity.normalized_identifier:
            score += 10.0
        else:
            missing_dims.append("IDENTITY")

        # 2. Domain (10 pts)
        if props.get("domain") or "domain:" in entity.normalized_identifier:
            score += 10.0
        else:
            missing_dims.append("DOMAIN")

        # 3. Geography (10 pts)
        if props.get("country") or props.get("city"):
            score += 10.0
        else:
            missing_dims.append("GEOGRAPHY")

        # Query connected edges
        edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                or_(
                    KnowledgeRelationship.source_entity_id == entity.id,
                    KnowledgeRelationship.target_entity_id == entity.id
                ),
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        has_tech = False
        has_people = False
        has_dm = False
        has_intent = False
        has_evidence = False

        for e in edges:
            other_id = e.target_entity_id if e.source_entity_id == entity.id else e.source_entity_id
            other_ent = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == other_id).first()

            if other_ent:
                if other_ent.entity_type == KnowledgeEntityType.TECHNOLOGY.value:
                    has_tech = True
                elif other_ent.entity_type == KnowledgeEntityType.PERSON.value:
                    has_people = True
                    if (other_ent.properties or {}).get("is_decision_maker"):
                        has_dm = True

            if "MIGRATION" in e.relationship_type or "INTENT" in e.relationship_type:
                has_intent = True

            if e.evidence_links and len(e.evidence_links) > 0:
                has_evidence = True

        # 4. Technology (15 pts)
        if has_tech:
            score += 15.0
        else:
            missing_dims.append("TECHNOLOGY")

        # 5. People (15 pts)
        if has_people:
            score += 15.0
        else:
            missing_dims.append("PEOPLE")

        # 6. Decision Maker (20 pts)
        if has_dm:
            score += 20.0
        else:
            missing_dims.append("DECISION_MAKER")

        # 7. Intent (10 pts)
        if has_intent or "odoo" in str(props).lower():
            score += 10.0
            has_intent = True
        else:
            missing_dims.append("INTENT")

        # 8. Evidence (10 pts)
        if has_evidence:
            score += 10.0
        else:
            missing_dims.append("EVIDENCE")

        snap = GraphCompletenessSnapshot(
            workspace_id=workspace_id,
            entity_id=entity.id,
            completeness_score=round(score, 1),
            missing_dimensions=missing_dims,
            has_decision_maker=has_dm,
            has_technology=has_tech,
            has_intent=has_intent,
            has_evidence=has_evidence
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap

    # --- 2. Graph Health & Quality Assessment ---

    def evaluate_graph_health(self, workspace_id: str) -> GraphHealthSnapshot:
        """
        Calculates graph health metrics across all entities and relationships in the workspace.
        """
        now = datetime.now(timezone.utc)
        entities = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.workspace_id == workspace_id).all()
        relationships = self.db.query(KnowledgeRelationship).filter(KnowledgeRelationship.workspace_id == workspace_id).all()

        total_ents = len(entities)
        total_rels = len(relationships)

        if total_rels == 0:
            evidence_cov = 100.0
            conflict_rate = 0.0
            stale_edge_rate = 0.0
        else:
            rels_with_ev = sum(1 for r in relationships if r.evidence_links and len(r.evidence_links) > 0)
            evidence_cov = round((rels_with_ev / total_rels) * 100.0, 1)

            conflicted_rels = sum(1 for r in relationships if r.status == RelationshipStatus.CONTESTED.value)
            conflict_rate = round((conflicted_rels / total_rels) * 100.0, 1)

            stale_cutoff = now - timedelta(days=180)

            def _is_stale(dt):
                if not dt:
                    return False
                if dt.tzinfo is None and stale_cutoff.tzinfo is not None:
                    dt = dt.replace(tzinfo=timezone.utc)
                elif dt.tzinfo is not None and stale_cutoff.tzinfo is None:
                    return dt < stale_cutoff.replace(tzinfo=timezone.utc)
                return dt < stale_cutoff

            stale_rels = sum(1 for r in relationships if _is_stale(r.observed_at))
            stale_edge_rate = round((stale_rels / total_rels) * 100.0, 1)

        # Orphan entities (degree = 0)
        connected_node_ids = set()
        for r in relationships:
            connected_node_ids.add(r.source_entity_id)
            connected_node_ids.add(r.target_entity_id)

        orphan_count = sum(1 for e in entities if e.id not in connected_node_ids)

        # Composite quality score
        quality = max(0.0, min(100.0, (
            (evidence_cov * 0.40) +
            ((100.0 - conflict_rate) * 0.30) +
            ((100.0 - stale_edge_rate) * 0.20) +
            ((1.0 - (orphan_count / max(1, total_ents))) * 10.0)
        )))

        health = GraphHealthSnapshot(
            workspace_id=workspace_id,
            total_entities=total_ents,
            total_relationships=total_rels,
            evidence_coverage_pct=evidence_cov,
            conflict_rate_pct=conflict_rate,
            stale_edge_rate_pct=stale_edge_rate,
            orphan_node_count=orphan_count,
            duplicate_rate_pct=0.0,
            quality_score=round(quality, 1),
            calculated_at=now
        )
        self.db.add(health)
        self.db.commit()
        self.db.refresh(health)
        return health

    # --- 3. Graph Research Recommendations & Gap Pathfinder ---

    def detect_graph_gaps_and_recommend(
        self,
        workspace_id: str,
        limit: int = 10
    ) -> List[GraphResearchRecommendation]:
        """
        Discovers high-priority graph gaps (e.g. Company with USES_ODOO but no Decision Maker)
        and generates prioritized research paths and recommendations.
        """
        # Find companies with active Odoo relationship
        odoo_edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.relationship_type.in_(["USES_ODOO", "IMPLEMENTS_ODOO", "ODOO_MIGRATION"]),
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).limit(50).all()

        recs = []
        for oe in odoo_edges:
            comp_id = oe.source_entity_id
            comp = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == comp_id).first()
            if not comp:
                continue

            # Check if company has connected decision maker
            person_edges = self.db.query(KnowledgeRelationship).filter(
                and_(
                    KnowledgeRelationship.workspace_id == workspace_id,
                    KnowledgeRelationship.target_entity_id == comp_id,
                    KnowledgeRelationship.relationship_type.in_(["WORKS_AT", "LEADS", "MANAGES"]),
                    KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
                )
            ).all()

            has_dm = False
            for pe in person_edges:
                person = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == pe.source_entity_id).first()
                if person and (person.properties or {}).get("is_decision_maker"):
                    has_dm = True
                    break

            if not has_dm:
                # Found high-value gap!
                rec = GraphResearchRecommendation(
                    workspace_id=workspace_id,
                    entity_id=comp.id,
                    missing_relationship="DECISION_MAKER",
                    suggested_source="Company Team Page / Public Leadership Registry",
                    eiv_score=2.25,
                    status="PENDING"
                )
                self.db.add(rec)
                recs.append(rec)

                # Store research path
                path = GraphResearchPath(
                    workspace_id=workspace_id,
                    entity_id=comp.id,
                    path_description=f"Investigate {comp.canonical_name} executive leadership team",
                    start_entity="COMPANY",
                    target_missing_entity="PERSON:DECISION_MAKER",
                    hops=["COMPANY", "DOMAIN", "WEBSITE_LEADERSHIP", "DECISION_MAKER"],
                    expected_information_value=2.25
                )
                self.db.add(path)

            if len(recs) >= limit:
                break

        self.db.commit()
        return recs
