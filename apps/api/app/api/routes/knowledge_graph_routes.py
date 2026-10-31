from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipConflict,
    GraphSnapshot,
    GraphCommunity,
    LookalikeProfile,
    GraphHealthSnapshot,
    GraphCompletenessSnapshot,
    GraphResearchRecommendation,
    KnowledgeEntityType,
    InferenceStatus,
    RelationshipStatus,
    ConflictStatus
)

from packages.knowledge_graph.knowledge_graph_engine import KnowledgeGraphEngine
from packages.knowledge_graph.traversal_engine import GraphTraversalEngine, GraphTraversalError
from packages.knowledge_graph.semantic_search_engine import SemanticSearchEngine
from packages.knowledge_graph.similarity_lookalike_engine import SimilarityAndLookalikeEngine
from packages.knowledge_graph.community_ecosystem_engine import CommunityAndEcosystemEngine
from packages.knowledge_graph.graph_intelligence_engine import GraphIntelligenceEngine


knowledge_graph_router = APIRouter(
    prefix="/graph",
    tags=["Enterprise Knowledge Graph, Semantic Search & Relationship Intelligence"]
)


# --- Pydantic Request Models ---

class CreateEntityRequest(BaseModel):
    entity_type: str = "COMPANY"
    canonical_name: str
    normalized_identifier: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class CreateRelationshipRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    inference_status: str = "OBSERVED"
    base_confidence: float = 80.0
    confidence_reason: Optional[str] = None
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)


class ResolveConflictRequest(BaseModel):
    winning_relationship_id: str
    resolved_by: str = "operator"
    notes: Optional[str] = None


class PathSearchRequest(BaseModel):
    start_entity_id: str
    target_entity_id: str
    max_depth: int = 3
    max_paths: int = 5


class HybridSearchRequest(BaseModel):
    query_text: str
    entity_type: Optional[str] = "COMPANY"
    country: Optional[str] = None
    industry: Optional[str] = None
    must_have_technology: Optional[str] = None
    limit: int = 20


class SemanticSearchRequest(BaseModel):
    prompt: str


class CreateLookalikeProfileRequest(BaseModel):
    profile_name: str
    seed_entity_ids: List[str]
    matching_dimensions: List[str] = Field(default_factory=lambda: ["technology", "industry", "geography"])
    target_count: int = 20


class CreateSnapshotRequest(BaseModel):
    snapshot_name: str
    snapshot_type: str = "DAILY"


# --- 1. Entities & Neighborhood ---

@knowledge_graph_router.post("/entities")
def create_or_update_entity(
    req: CreateEntityRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = KnowledgeGraphEngine(db)
    entity = engine.upsert_entity(
        workspace_id=ws.id,
        entity_type=req.entity_type,
        canonical_name=req.canonical_name,
        normalized_identifier=req.normalized_identifier,
        properties=req.properties,
        changed_by=user.email if hasattr(user, "email") else "system"
    )
    return {
        "status": "success",
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "canonical_name": entity.canonical_name,
        "normalized_identifier": entity.normalized_identifier,
        "properties": entity.properties
    }


@knowledge_graph_router.get("/entities")
def list_entities(
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    query = db.query(KnowledgeEntity).filter(KnowledgeEntity.workspace_id == ws.id)
    if entity_type:
        query = query.filter(KnowledgeEntity.entity_type == entity_type.upper())
    if search:
        query = query.filter(KnowledgeEntity.canonical_name.ilike(f"%{search}%"))

    entities = query.limit(limit).all()
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "canonical_name": e.canonical_name,
            "normalized_identifier": e.normalized_identifier,
            "properties": e.properties
        }
        for e in entities
    ]


@knowledge_graph_router.get("/entities/{entity_id}")
def get_entity_detail(
    entity_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    entity = db.query(KnowledgeEntity).filter(
        KnowledgeEntity.workspace_id == ws.id,
        KnowledgeEntity.id == entity_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "canonical_name": entity.canonical_name,
        "normalized_identifier": entity.normalized_identifier,
        "properties": entity.properties,
        "is_canonical": entity.is_canonical,
        "created_at": entity.created_at
    }


@knowledge_graph_router.get("/neighborhood")
def get_entity_neighborhood(
    entity_id: str = Query(...),
    depth: int = Query(default=1, ge=1, le=3),
    relationship_types: Optional[str] = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=100.0),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    types_list = [t.strip() for t in relationship_types.split(",")] if relationship_types else None
    engine = GraphTraversalEngine(db)
    try:
        res = engine.get_neighborhood(
            workspace_id=ws.id,
            entity_id=entity_id,
            depth=depth,
            relationship_types=types_list,
            min_confidence=min_confidence
        )
        return res
    except GraphTraversalError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- 2. Relationships, Corroboration & Evidence ---

@knowledge_graph_router.post("/relationships")
def create_or_update_relationship(
    req: CreateRelationshipRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = KnowledgeGraphEngine(db)
    rel, conflict = engine.create_or_update_relationship(
        workspace_id=ws.id,
        source_entity_id=req.source_entity_id,
        target_entity_id=req.target_entity_id,
        relationship_type=req.relationship_type,
        inference_status=req.inference_status,
        base_confidence=req.base_confidence,
        evidence_items=req.evidence_items,
        confidence_reason=req.confidence_reason
    )
    return {
        "status": "success",
        "relationship_id": rel.id,
        "relationship_type": rel.relationship_type,
        "inference_status": rel.inference_status,
        "confidence": rel.confidence,
        "corroboration_count": rel.corroboration_count,
        "conflict_detected": conflict is not None,
        "conflict_id": conflict.id if conflict else None
    }


@knowledge_graph_router.get("/relationships")
def list_relationships(
    relationship_type: Optional[str] = None,
    min_confidence: float = 0.0,
    status_filter: Optional[str] = "ACTIVE",
    limit: int = 50,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    query = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.workspace_id == ws.id,
        KnowledgeRelationship.confidence >= min_confidence
    )
    if relationship_type:
        query = query.filter(KnowledgeRelationship.relationship_type == relationship_type.upper())
    if status_filter:
        query = query.filter(KnowledgeRelationship.status == status_filter.upper())

    rels = query.limit(limit).all()
    return [
        {
            "id": r.id,
            "source_id": r.source_entity_id,
            "target_id": r.target_entity_id,
            "relationship_type": r.relationship_type,
            "inference_status": r.inference_status,
            "confidence": r.confidence,
            "corroboration_count": r.corroboration_count,
            "status": r.status
        }
        for r in rels
    ]


@knowledge_graph_router.get("/relationships/{relationship_id}")
def get_relationship_detail(
    relationship_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    rel = db.query(KnowledgeRelationship).filter(
        KnowledgeRelationship.workspace_id == ws.id,
        KnowledgeRelationship.id == relationship_id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {
        "id": rel.id,
        "source_id": rel.source_entity_id,
        "target_id": rel.target_entity_id,
        "relationship_type": rel.relationship_type,
        "inference_status": rel.inference_status,
        "confidence": rel.confidence,
        "corroboration_count": rel.corroboration_count,
        "status": rel.status,
        "valid_from": rel.valid_from,
        "valid_to": rel.valid_to,
        "evidence": [
            {
                "source_url": ev.source_url,
                "source_type": ev.source_type,
                "evidence_snippet": ev.evidence_snippet,
                "source_independence_key": ev.source_independence_key
            }
            for ev in rel.evidence_links
        ]
    }


# --- 3. Bounded Path Search & DSL ---

@knowledge_graph_router.post("/path")
def find_graph_path(
    req: PathSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = GraphTraversalEngine(db)
    paths = engine.find_paths(
        workspace_id=ws.id,
        start_entity_id=req.start_entity_id,
        target_entity_id=req.target_entity_id,
        max_depth=req.max_depth,
        max_paths=req.max_paths
    )
    return {
        "status": "success",
        "paths_found": len(paths),
        "paths": paths
    }


# --- 4. Semantic Search & Hybrid Search ---

@knowledge_graph_router.post("/search")
def hybrid_search(
    req: HybridSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SemanticSearchEngine(db)
    results = engine.hybrid_search(
        workspace_id=ws.id,
        query_text=req.query_text,
        entity_type=req.entity_type,
        country=req.country,
        industry=req.industry,
        must_have_technology=req.must_have_technology,
        limit=req.limit
    )
    return {
        "status": "success",
        "query": req.query_text,
        "total_results": len(results),
        "results": results
    }


@knowledge_graph_router.post("/semantic-search")
def natural_language_semantic_search(
    req: SemanticSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    sem_engine = SemanticSearchEngine(db)
    dsl = sem_engine.translate_nl_to_graph_dsl(req.prompt)

    trav_engine = GraphTraversalEngine(db)
    res = trav_engine.execute_dsl_query(workspace_id=ws.id, dsl=dsl)
    return {
        "status": "success",
        "prompt": req.prompt,
        "translated_dsl": dsl,
        "matches": res["results"]
    }


# --- 5. Similarity & Lookalikes ---

@knowledge_graph_router.get("/similar")
def get_company_similarity(
    company_a_id: str = Query(...),
    company_b_id: str = Query(...),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SimilarityAndLookalikeEngine(db)
    try:
        sim = engine.calculate_company_similarity(
            workspace_id=ws.id,
            company_a_id=company_a_id,
            company_b_id=company_b_id
        )
        return {
            "similarity_score": sim.similarity_score,
            "matched_factors": sim.matched_factors,
            "limitations_notes": sim.limitations_notes
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@knowledge_graph_router.post("/lookalikes/profiles")
def create_lookalike_profile(
    req: CreateLookalikeProfileRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SimilarityAndLookalikeEngine(db)
    profile = engine.create_lookalike_profile(
        workspace_id=ws.id,
        profile_name=req.profile_name,
        seed_entity_ids=req.seed_entity_ids,
        matching_dimensions=req.matching_dimensions,
        target_count=req.target_count
    )
    return {
        "status": "success",
        "profile_id": profile.id,
        "profile_name": profile.profile_name,
        "seeds_count": len(profile.seed_entity_ids)
    }


@knowledge_graph_router.post("/lookalikes/profiles/{profile_id}/find")
def find_lookalike_matches(
    profile_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SimilarityAndLookalikeEngine(db)
    try:
        matches = engine.find_lookalikes(workspace_id=ws.id, profile_id=profile_id)
        return [
            {
                "match_id": m.id,
                "entity_id": m.entity_id,
                "overall_similarity_score": m.overall_similarity_score,
                "explanation": m.explanation,
                "dimension_breakdown": m.dimension_breakdown
            }
            for m in matches
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- 6. Communities & Specialized Ecosystems ---

@knowledge_graph_router.post("/communities/detect")
def detect_communities(
    community_type: str = "TECHNOLOGY_ECOSYSTEM",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CommunityAndEcosystemEngine(db)
    communities = engine.detect_communities(
        workspace_id=ws.id,
        community_type=community_type
    )
    return [
        {
            "id": c.id,
            "community_name": c.community_name,
            "community_type": c.community_type,
            "density": c.density,
            "centrality_node_id": c.centrality_node_id
        }
        for c in communities
    ]


@knowledge_graph_router.get("/ecosystems/odoo")
def get_odoo_ecosystem(
    min_confidence: float = 70.0,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CommunityAndEcosystemEngine(db)
    return engine.get_odoo_ecosystem_graph(workspace_id=ws.id, min_confidence=min_confidence)


@knowledge_graph_router.get("/ecosystems/technology")
def get_technology_ecosystem(
    anchor: str = "Odoo",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CommunityAndEcosystemEngine(db)
    return engine.get_technology_ecosystem_graph(workspace_id=ws.id, anchor_tech=anchor)


@knowledge_graph_router.get("/ecosystems/buying-committee")
def get_buying_committee(
    company_id: str = Query(...),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CommunityAndEcosystemEngine(db)
    try:
        return engine.get_buying_committee_graph(workspace_id=ws.id, company_entity_id=company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- 7. Conflicts & Resolutions ---

@knowledge_graph_router.get("/conflicts")
def list_conflicts(
    status_filter: Optional[str] = "UNRESOLVED",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    query = db.query(RelationshipConflict).filter(RelationshipConflict.workspace_id == ws.id)
    if status_filter:
        query = query.filter(RelationshipConflict.status == status_filter.upper())
    conflicts = query.all()
    return [
        {
            "id": c.id,
            "relationship_id_a": c.relationship_id_a,
            "relationship_id_b": c.relationship_id_b,
            "conflict_type": c.conflict_type,
            "status": c.status,
            "resolution_notes": c.resolution_notes
        }
        for c in conflicts
    ]


@knowledge_graph_router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    req: ResolveConflictRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = KnowledgeGraphEngine(db)
    try:
        res = engine.resolve_conflict(
            workspace_id=ws.id,
            conflict_id=conflict_id,
            winning_relationship_id=req.winning_relationship_id,
            resolved_by=req.resolved_by,
            notes=req.notes
        )
        return {
            "status": "success",
            "conflict_id": res.id,
            "conflict_status": res.status,
            "resolved_by": res.resolved_by,
            "resolved_at": res.resolved_at
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- 8. Graph Snapshots ---

@knowledge_graph_router.post("/snapshots")
def create_snapshot(
    req: CreateSnapshotRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = KnowledgeGraphEngine(db)
    snap = engine.create_snapshot(
        workspace_id=ws.id,
        snapshot_name=req.snapshot_name,
        snapshot_type=req.snapshot_type
    )
    return {
        "status": "success",
        "snapshot_id": snap.id,
        "name": snap.snapshot_name,
        "entity_count": snap.entity_count,
        "relationship_count": snap.relationship_count,
        "snapshot_date": snap.snapshot_date
    }


@knowledge_graph_router.get("/snapshots")
def list_snapshots(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    snaps = db.query(GraphSnapshot).filter(GraphSnapshot.workspace_id == ws.id).order_by(desc(GraphSnapshot.snapshot_date)).all()
    return [
        {
            "id": s.id,
            "snapshot_name": s.snapshot_name,
            "snapshot_type": s.snapshot_type,
            "entity_count": s.entity_count,
            "relationship_count": s.relationship_count,
            "snapshot_date": s.snapshot_date
        }
        for s in snaps
    ]


# --- 9. Health & Completeness ---

@knowledge_graph_router.get("/health")
def get_graph_health(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = GraphIntelligenceEngine(db)
    health = engine.evaluate_graph_health(workspace_id=ws.id)
    return {
        "total_entities": health.total_entities,
        "total_relationships": health.total_relationships,
        "evidence_coverage_pct": health.evidence_coverage_pct,
        "conflict_rate_pct": health.conflict_rate_pct,
        "stale_edge_rate_pct": health.stale_edge_rate_pct,
        "orphan_node_count": health.orphan_node_count,
        "quality_score": health.quality_score,
        "calculated_at": health.calculated_at
    }


@knowledge_graph_router.get("/completeness")
def get_entity_completeness(
    entity_id: str = Query(...),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = GraphIntelligenceEngine(db)
    try:
        comp = engine.evaluate_entity_completeness(workspace_id=ws.id, entity_id=entity_id)
        return {
            "entity_id": comp.entity_id,
            "completeness_score": comp.completeness_score,
            "missing_dimensions": comp.missing_dimensions,
            "has_decision_maker": comp.has_decision_maker,
            "has_technology": comp.has_technology,
            "has_intent": comp.has_intent,
            "has_evidence": comp.has_evidence
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@knowledge_graph_router.post("/recommendations/detect")
def detect_graph_recommendations(
    limit: int = 10,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = GraphIntelligenceEngine(db)
    recs = engine.detect_graph_gaps_and_recommend(workspace_id=ws.id, limit=limit)
    return [
        {
            "id": r.id,
            "entity_id": r.entity_id,
            "missing_relationship": r.missing_relationship,
            "suggested_source": r.suggested_source,
            "eiv_score": r.eiv_score,
            "status": r.status
        }
        for r in recs
    ]


@knowledge_graph_router.get("/recommendations")
def list_graph_recommendations(
    status_filter: Optional[str] = "PENDING",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    query = db.query(GraphResearchRecommendation).filter(GraphResearchRecommendation.workspace_id == ws.id)
    if status_filter:
        query = query.filter(GraphResearchRecommendation.status == status_filter.upper())
    recs = query.limit(50).all()
    return [
        {
            "id": r.id,
            "entity_id": r.entity_id,
            "missing_relationship": r.missing_relationship,
            "suggested_source": r.suggested_source,
            "eiv_score": r.eiv_score,
            "status": r.status
        }
        for r in recs
    ]

