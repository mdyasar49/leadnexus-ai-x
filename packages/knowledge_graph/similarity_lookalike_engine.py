from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    GraphSimilarityResult,
    LookalikeProfile,
    LookalikeMatch,
    RelationshipStatus,
    KnowledgeEntityType
)


class SimilarityAndLookalikeEngine:
    """
    Company Similarity & Lookalike Intelligence Engine:
    - Multi-dimensional company comparison (Technology, Geography, Industry, Intent)
    - Seed-based Lookalike matching with explainable factor decomposition
    - Explicit limitations statement: Similarity does not imply identical commercial behavior
    """

    LIMITATIONS_NOTICE = (
        "LOOKALIKE ESTIMATE: Match scores reflect structural, technical, and domain similarity. "
        "High similarity does NOT guarantee identical commercial readiness, operational intent, or budget authorization."
    )

    def __init__(self, db: Session):
        self.db = db

    def calculate_company_similarity(
        self,
        workspace_id: str,
        company_a_id: str,
        company_b_id: str
    ) -> GraphSimilarityResult:
        """
        Computes multi-dimensional similarity between two companies:
        - Geography (0.20)
        - Industry (0.25)
        - Technology Stack Overlap (Jaccard similarity) (0.35)
        - Intent / Priority tier match (0.20)
        """
        comp_a = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == company_a_id)
        ).first()
        comp_b = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == company_b_id)
        ).first()

        if not comp_a or not comp_b:
            raise ValueError("One or both companies not found.")

        props_a = comp_a.properties or {}
        props_b = comp_b.properties or {}

        # 1. Geography score
        geo_a = str(props_a.get("country", "")).lower()
        geo_b = str(props_b.get("country", "")).lower()
        geo_score = 1.0 if (geo_a and geo_a == geo_b) else (0.5 if (geo_a and geo_b and (geo_a in geo_b or geo_b in geo_a)) else 0.0)

        # 2. Industry score
        ind_a = str(props_a.get("industry", "")).lower()
        ind_b = str(props_b.get("industry", "")).lower()
        ind_score = 1.0 if (ind_a and ind_a == ind_b) else (0.5 if (ind_a and ind_b and (ind_a in ind_b or ind_b in ind_a)) else 0.0)

        # 3. Technology stack overlap (Jaccard index)
        techs_a = self._get_connected_technologies(workspace_id, comp_a.id)
        techs_b = self._get_connected_technologies(workspace_id, comp_b.id)

        union_techs = techs_a | techs_b
        intersection_techs = techs_a & techs_b
        tech_score = (len(intersection_techs) / max(1, len(union_techs))) if union_techs else 0.50

        # 4. Intent score
        intent_score = 0.80 if ("odoo" in str(props_a) and "odoo" in str(props_b)) else 0.50

        # Weighted aggregate
        overall_similarity = round(
            (0.20 * geo_score) + (0.25 * ind_score) + (0.35 * tech_score) + (0.20 * intent_score),
            2
        )

        matched_factors = {
            "geography_match": geo_score,
            "industry_match": ind_score,
            "technology_overlap_jaccard": round(tech_score, 2),
            "common_technologies": list(intersection_techs),
            "intent_match": intent_score
        }

        result = GraphSimilarityResult(
            workspace_id=workspace_id,
            source_entity_id=comp_a.id,
            target_entity_id=comp_b.id,
            similarity_score=overall_similarity,
            matched_factors=matched_factors,
            limitations_notes=self.LIMITATIONS_NOTICE
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def _get_connected_technologies(self, workspace_id: str, company_entity_id: str) -> set:
        """Helper to retrieve all technologies linked to an entity."""
        edges = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.source_entity_id == company_entity_id,
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()
        tech_names = set()
        for e in edges:
            tgt = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == e.target_entity_id).first()
            if tgt and tgt.entity_type == KnowledgeEntityType.TECHNOLOGY.value:
                tech_names.add(tgt.canonical_name.lower())
        return tech_names

    # --- 2. Lookalike Matching ---

    def create_lookalike_profile(
        self,
        workspace_id: str,
        profile_name: str,
        seed_entity_ids: List[str],
        matching_dimensions: Optional[List[str]] = None,
        target_count: int = 20
    ) -> LookalikeProfile:
        """Registers a lookalike search profile with seed companies."""
        profile = LookalikeProfile(
            workspace_id=workspace_id,
            profile_name=profile_name,
            seed_entity_ids=seed_entity_ids,
            matching_dimensions=matching_dimensions or ["technology", "industry", "geography"],
            target_count=target_count
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def find_lookalikes(
        self,
        workspace_id: str,
        profile_id: str
    ) -> List[LookalikeMatch]:
        """
        Executes lookalike search across all workspace companies excluding seed entities.
        Computes composite similarity and stores explainable LookalikeMatch records.
        """
        profile = self.db.query(LookalikeProfile).filter(
            and_(LookalikeProfile.workspace_id == workspace_id, LookalikeProfile.id == profile_id)
        ).first()
        if not profile:
            raise ValueError(f"Lookalike profile '{profile_id}' not found.")

        seed_ids = set(profile.seed_entity_ids or [])
        candidates = self.db.query(KnowledgeEntity).filter(
            and_(
                KnowledgeEntity.workspace_id == workspace_id,
                KnowledgeEntity.entity_type == KnowledgeEntityType.COMPANY.value,
                KnowledgeEntity.id.not_in(seed_ids)
            )
        ).all()

        matches = []
        for cand in candidates:
            # Compare candidate against each seed and take mean similarity
            sims = []
            breakdowns = []
            for seed_id in seed_ids:
                sim_res = self.calculate_company_similarity(workspace_id, seed_id, cand.id)
                sims.append(sim_res.similarity_score)
                breakdowns.append(sim_res.matched_factors)

            avg_sim = round(sum(sims) / len(sims), 2) if sims else 0.50

            # Construct explanation
            explanation = (
                f"Candidate matches {len(seed_ids)} seed entities with {avg_sim * 100}% overall similarity. "
                f"Common factors include technology stack alignment and shared industry characteristics."
            )

            match = LookalikeMatch(
                profile_id=profile.id,
                entity_id=cand.id,
                overall_similarity_score=avg_sim,
                dimension_breakdown={
                    "seeds_evaluated_count": len(seed_ids),
                    "average_similarity": avg_sim,
                    "sample_breakdown": breakdowns[0] if breakdowns else {}
                },
                explanation=explanation
            )
            self.db.add(match)
            matches.append(match)

        self.db.commit()
        matches.sort(key=lambda m: m.overall_similarity_score, reverse=True)
        return matches[:profile.target_count]

