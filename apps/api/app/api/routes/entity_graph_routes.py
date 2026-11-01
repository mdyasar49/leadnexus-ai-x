"""
LeadNexus AI X - Phase 46: Entity Relationship Graph & Query Federation API Routes
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_sync_db
from app.models.entity_graph import (
    GraphNodeRecord,
    GraphEdgeRecord,
    GraphNodeCreate,
    GraphNodeResponse,
    GraphEdgeCreate,
    GraphEdgeResponse,
    MultiHopQueryRequest,
    ShortestPathRequest,
    ShortestPathResponse,
    CentralityScoreResponse,
    HybridSearchRequest,
    HybridSearchResult,
    NodeType,
    EdgeType,
)
from packages.graph.graph_index import GraphIndex
from packages.graph.multihop_query_engine import MultiHopQueryEngine
from packages.graph.path_navigator import PathNavigator
from packages.graph.centrality_analyzer import CentralityAnalyzer
from packages.graph.hybrid_federator import HybridSearchFederator

router = APIRouter(prefix="/graph", tags=["Entity Graph & Query Federation"])

# Shared in-memory GraphIndex cache for sub-millisecond graph traversals
_shared_index = GraphIndex()
_multihop_engine = MultiHopQueryEngine(_shared_index)
_path_navigator = PathNavigator(_shared_index)
_centrality_analyzer = CentralityAnalyzer(_shared_index)
_hybrid_federator = HybridSearchFederator(_shared_index, _centrality_analyzer)


def _seed_initial_graph_data():
    """Populates realistic B2B enterprise graph data for exploration."""
    if len(_shared_index._nodes) > 0:
        return

    # Companies
    c1 = _shared_index.add_node("comp_odoo_au", "COMPANY", "Odoo Australia Pty Ltd", "company:odoo-au", {
        "industry": "ERP Software", "country": "Australia", "city": "Sydney", "employees": 250, "revenue": "$45M"
    })
    c2 = _shared_index.add_node("comp_atlassian", "COMPANY", "Atlassian Corp", "company:atlassian", {
        "industry": "Enterprise Software", "country": "Australia", "city": "Sydney", "employees": 11000, "revenue": "$3.5B"
    })
    c3 = _shared_index.add_node("comp_canva", "COMPANY", "Canva Inc", "company:canva", {
        "industry": "Design & Collaboration", "country": "Australia", "city": "Sydney", "employees": 4500, "revenue": "$1.8B"
    })
    c4 = _shared_index.add_node("comp_nexus_erp", "COMPANY", "Nexus Cloud Solutions", "company:nexus-cloud", {
        "industry": "ERP Implementation & Consulting", "country": "Australia", "city": "Melbourne", "employees": 180, "revenue": "$28M"
    })

    # Technologies
    t1 = _shared_index.add_node("tech_odoo", "TECHNOLOGY", "Odoo ERP", "tech:odoo", {"category": "ERP", "version": "17.0"})
    t2 = _shared_index.add_node("tech_python", "TECHNOLOGY", "Python", "tech:python", {"category": "Programming Language"})
    t3 = _shared_index.add_node("tech_react", "TECHNOLOGY", "React", "tech:react", {"category": "Frontend Framework"})
    t4 = _shared_index.add_node("tech_postgres", "TECHNOLOGY", "PostgreSQL", "tech:postgres", {"category": "Relational Database"})

    # Locations
    l1 = _shared_index.add_node("loc_sydney", "LOCATION", "Sydney, Australia", "loc:sydney-au", {"country": "Australia", "state": "NSW"})
    l2 = _shared_index.add_node("loc_melbourne", "LOCATION", "Melbourne, Australia", "loc:melbourne-au", {"country": "Australia", "state": "VIC"})

    # People / Decision-Makers
    p1 = _shared_index.add_node("person_sarah", "PERSON", "Sarah Jenkins", "person:sarah-jenkins", {
        "title": "Chief Technology Officer", "seniority": "C-Level", "email": "sarah.jenkins@odoo-au.com", "verified": True
    })
    p2 = _shared_index.add_node("person_david", "PERSON", "David Chen", "person:david-chen", {
        "title": "Head of Enterprise Engineering", "seniority": "Director", "email": "dchen@nexus-cloud.com", "verified": True
    })
    p3 = _shared_index.add_node("person_alex", "PERSON", "Alex Rivera", "person:alex-rivera", {
        "title": "VP of Product Engineering", "seniority": "VP", "email": "alex.rivera@atlassian.com", "verified": True
    })
    p4 = _shared_index.add_node("person_emily", "PERSON", "Emily Zhang", "person:emily-zhang", {
        "title": "Enterprise ERP Architect", "seniority": "Lead", "email": "emily.z@nexus-cloud.com", "verified": True
    })

    # Investors
    inv1 = _shared_index.add_node("inv_sequoia", "INVESTOR", "Sequoia Capital", "inv:sequoia", {"tier": "Tier 1 VC"})

    # Edges
    # Company -> Tech
    _shared_index.add_edge("e1", "comp_odoo_au", "tech_odoo", "USES_TECH", 1.0, 0.99, {"primary": True})
    _shared_index.add_edge("e2", "comp_odoo_au", "tech_python", "USES_TECH", 0.9, 0.98)
    _shared_index.add_edge("e3", "comp_odoo_au", "tech_postgres", "USES_TECH", 0.9, 0.98)
    _shared_index.add_edge("e4", "comp_nexus_erp", "tech_odoo", "USES_TECH", 1.0, 0.95, {"certified_partner": True})
    _shared_index.add_edge("e5", "comp_nexus_erp", "tech_react", "USES_TECH", 0.8, 0.92)

    # Company -> Location
    _shared_index.add_edge("e6", "comp_odoo_au", "loc_sydney", "LOCATED_IN", 1.0, 1.0, {"is_hq": True})
    _shared_index.add_edge("e7", "comp_nexus_erp", "loc_melbourne", "LOCATED_IN", 1.0, 1.0, {"is_hq": True})
    _shared_index.add_edge("e8", "comp_atlassian", "loc_sydney", "LOCATED_IN", 1.0, 1.0, {"is_hq": True})
    _shared_index.add_edge("e9", "comp_canva", "loc_sydney", "LOCATED_IN", 1.0, 1.0, {"is_hq": True})

    # People -> Company
    _shared_index.add_edge("e10", "person_sarah", "comp_odoo_au", "EMPLOYED_AT", 1.0, 0.99, {"is_current": True})
    _shared_index.add_edge("e11", "person_david", "comp_nexus_erp", "EMPLOYED_AT", 1.0, 0.97, {"is_current": True})
    _shared_index.add_edge("e12", "person_alex", "comp_atlassian", "EMPLOYED_AT", 1.0, 0.98, {"is_current": True})
    _shared_index.add_edge("e13", "person_emily", "comp_nexus_erp", "EMPLOYED_AT", 1.0, 0.95, {"is_current": True})

    # Alumni & Colleague relationships (for warm intros)
    _shared_index.add_edge("e14", "person_david", "comp_atlassian", "ALUMNI_OF", 0.8, 0.95, {"years": "2018-2022"})
    _shared_index.add_edge("e15", "person_david", "person_alex", "COLLEAGUE_OF", 0.9, 0.95, {"dept": "Platform Eng"})
    _shared_index.add_edge("e16", "person_sarah", "person_alex", "COLLEAGUE_OF", 0.7, 0.88, {"industry_group": "Sydney Tech Execs"})
    _shared_index.add_edge("e17", "inv_sequoia", "comp_canva", "INVESTED_IN", 1.0, 0.99, {"round": "Series B"})


# Initialize default seed entities
_seed_initial_graph_data()


@router.post("/nodes", response_model=GraphNodeResponse, status_code=status.HTTP_201_CREATED)
def create_graph_node(
    payload: GraphNodeCreate,
    db: Session = Depends(get_sync_db),
):
    """Creates a new entity node in the persistent database and runtime index."""
    import uuid
    node_id = f"node_{uuid.uuid4().hex[:12]}"
    canonical_key = payload.canonical_key or f"{payload.node_type.value.lower()}:{payload.name.lower().strip()}"

    # Check for existing
    existing = _shared_index.get_node_by_key(canonical_key)
    if existing:
        return existing

    record = GraphNodeRecord(
        id=node_id,
        node_type=payload.node_type.value,
        name=payload.name,
        canonical_key=canonical_key,
        attributes=payload.attributes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    node = _shared_index.add_node(
        node_id=record.id,
        node_type=record.node_type,
        name=record.name,
        canonical_key=record.canonical_key,
        attributes=record.attributes,
    )
    return node


@router.get("/nodes/{node_id}")
def get_graph_node(node_id: str):
    """Retrieves an entity node and its immediate 1-hop neighborhood."""
    node = _shared_index.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Entity node not found")
    neighborhood = _shared_index.get_neighborhood(node_id, max_hops=1)
    return {
        "node": node,
        "neighborhood": neighborhood,
    }


@router.post("/edges", response_model=GraphEdgeResponse, status_code=status.HTTP_201_CREATED)
def create_graph_edge(
    payload: GraphEdgeCreate,
    db: Session = Depends(get_sync_db),
):
    """Creates a directed relationship edge between two entities."""
    import uuid
    edge_id = f"edge_{uuid.uuid4().hex[:12]}"

    if not _shared_index.get_node(payload.source_id):
        raise HTTPException(status_code=400, detail="Source node does not exist")
    if not _shared_index.get_node(payload.target_id):
        raise HTTPException(status_code=400, detail="Target node does not exist")

    record = GraphEdgeRecord(
        id=edge_id,
        source_id=payload.source_id,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type.value,
        weight=payload.weight,
        confidence=payload.confidence,
        properties=payload.properties,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    edge = _shared_index.add_edge(
        edge_id=record.id,
        source_id=record.source_id,
        target_id=record.target_id,
        relationship_type=record.relationship_type,
        weight=record.weight,
        confidence=record.confidence,
        properties=record.properties,
    )
    return edge


@router.post("/query")
def execute_multihop_query(payload: MultiHopQueryRequest):
    """Executes a multi-hop federated graph query."""
    return _multihop_engine.execute_query(
        start_node_type=payload.start_node_type,
        start_filters=payload.start_filters,
        hops=[h.model_dump() for h in payload.hops],
        limit=payload.limit,
    )


@router.post("/shortest-path", response_model=ShortestPathResponse)
def find_shortest_warm_intro_path(payload: ShortestPathRequest):
    """Finds the shortest warm introduction path between any two graph entities."""
    result = _path_navigator.find_weighted_path_dijkstra(
        source_id=payload.source_id,
        target_id=payload.target_id,
    )
    if not result or not result["found"]:
        # Fall back to unweighted BFS
        bfs_res = _path_navigator.find_shortest_path_bfs(
            source_id=payload.source_id,
            target_id=payload.target_id,
            max_depth=payload.max_depth,
        )
        if not bfs_res or not bfs_res["found"]:
            return ShortestPathResponse(
                found=False,
                source_id=payload.source_id,
                target_id=payload.target_id,
                degree_of_separation=-1,
                path_nodes=[],
                path_edges=[],
                confidence_score=0.0,
            )
        return ShortestPathResponse(**bfs_res)

    return ShortestPathResponse(
        found=True,
        source_id=result["source_id"],
        target_id=result["target_id"],
        degree_of_separation=result["degree_of_separation"],
        path_nodes=result["path_nodes"],
        path_edges=result["path_edges"],
        confidence_score=result["confidence_score"],
    )


@router.get("/centrality")
def get_graph_centrality(
    node_type: Optional[str] = Query(None, description="Optional node type filter"),
    limit: int = Query(25, ge=1, le=100),
):
    """Calculates PageRank and degree centrality to rank influential decision-makers and companies."""
    return _centrality_analyzer.get_ranked_influencers(node_type=node_type, limit=limit)


@router.post("/hybrid-search", response_model=List[HybridSearchResult])
def execute_hybrid_search(payload: HybridSearchRequest):
    """Blends keyword matching, vector similarity, and graph centrality boost."""
    return _hybrid_federator.search(
        query=payload.query,
        target_node_type=payload.target_node_type,
        lexical_weight=payload.lexical_weight,
        vector_weight=payload.vector_weight,
        graph_weight=payload.graph_weight,
        limit=payload.limit,
    )


@router.get("/stats")
def get_graph_stats():
    """Returns total node counts, edge counts, graph density, and type distributions."""
    return _shared_index.get_stats()


@router.post("/seed")
def seed_graph_entities():
    """Manually triggers or resets default graph entities."""
    _seed_initial_graph_data()
    return {"status": "SUCCESS", "message": "Seed entities and relationships populated", "stats": _shared_index.get_stats()}
