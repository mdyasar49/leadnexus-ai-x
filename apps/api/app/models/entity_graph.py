"""
LeadNexus AI X - Phase 46: Entity Relationship Graph & Complex Query Federation Models
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Float, JSON, Integer, ForeignKey, Index
from app.db.base import Base


class NodeType(str, Enum):
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    TECHNOLOGY = "TECHNOLOGY"
    LOCATION = "LOCATION"
    INDUSTRY = "INDUSTRY"
    INVESTOR = "INVESTOR"


class EdgeType(str, Enum):
    EMPLOYED_AT = "EMPLOYED_AT"
    USES_TECH = "USES_TECH"
    LOCATED_IN = "LOCATED_IN"
    OPERATES_IN = "OPERATES_IN"
    ALUMNI_OF = "ALUMNI_OF"
    COLLEAGUE_OF = "COLLEAGUE_OF"
    INVESTED_IN = "INVESTED_IN"
    PARTNERED_WITH = "PARTNERED_WITH"


class GraphNodeRecord(Base):
    __tablename__ = "graph_nodes"

    id = Column(String(64), primary_key=True, default=lambda: f"node_{uuid.uuid4().hex[:12]}")
    node_type = Column(String(32), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    canonical_key = Column(String(255), unique=True, nullable=False, index=True)
    attributes = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class GraphEdgeRecord(Base):
    __tablename__ = "graph_edges"

    id = Column(String(64), primary_key=True, default=lambda: f"edge_{uuid.uuid4().hex[:12]}")
    source_id = Column(String(64), nullable=False, index=True)
    target_id = Column(String(64), nullable=False, index=True)
    relationship_type = Column(String(32), nullable=False, index=True)
    weight = Column(Float, default=1.0)
    confidence = Column(Float, default=0.95)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# --- Pydantic Schemas ---

class GraphNodeCreate(BaseModel):
    node_type: NodeType
    name: str
    canonical_key: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphNodeResponse(BaseModel):
    id: str
    node_type: str
    name: str
    canonical_key: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class GraphEdgeCreate(BaseModel):
    source_id: str
    target_id: str
    relationship_type: EdgeType
    weight: float = 1.0
    confidence: float = 0.95
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    weight: float
    confidence: float
    properties: Dict[str, Any] = Field(default_factory=dict)


class MultiHopHopStep(BaseModel):
    relationship_type: Optional[str] = None
    target_node_type: Optional[str] = None
    target_filter: Dict[str, Any] = Field(default_factory=dict)


class MultiHopQueryRequest(BaseModel):
    start_node_type: str
    start_filters: Dict[str, Any] = Field(default_factory=dict)
    hops: List[MultiHopHopStep] = Field(default_factory=list)
    limit: int = 50


class ShortestPathRequest(BaseModel):
    source_id: str
    target_id: str
    max_depth: int = 4


class ShortestPathResponse(BaseModel):
    found: bool
    source_id: str
    target_id: str
    degree_of_separation: int
    path_nodes: List[Dict[str, Any]]
    path_edges: List[Dict[str, Any]]
    confidence_score: float


class CentralityScoreResponse(BaseModel):
    node_id: str
    name: str
    node_type: str
    pagerank_score: float
    degree_centrality: float
    influence_tier: str


class HybridSearchRequest(BaseModel):
    query: str
    target_node_type: Optional[str] = None
    lexical_weight: float = 0.4
    vector_weight: float = 0.3
    graph_weight: float = 0.3
    limit: int = 20


class HybridSearchResult(BaseModel):
    node_id: str
    name: str
    node_type: str
    attributes: Dict[str, Any]
    final_score: float
    lexical_score: float
    vector_score: float
    graph_score: float
    explanation: str
