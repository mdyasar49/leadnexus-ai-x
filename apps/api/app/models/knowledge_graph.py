from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Boolean,
    Index
)
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# --- Controlled Enums ---

class KnowledgeEntityType(str, Enum):
    TENANT = "TENANT"
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    CONTACT = "CONTACT"
    DOMAIN = "DOMAIN"
    WEBSITE = "WEBSITE"
    TECHNOLOGY = "TECHNOLOGY"
    TECHNOLOGY_VERSION = "TECHNOLOGY_VERSION"
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    INDUSTRY = "INDUSTRY"
    LOCATION = "LOCATION"
    COUNTRY = "COUNTRY"
    STATE = "STATE"
    CITY = "CITY"
    SOURCE = "SOURCE"
    EVIDENCE = "EVIDENCE"
    SIGNAL = "SIGNAL"
    INTENT = "INTENT"
    LEAD = "LEAD"
    CAMPAIGN = "CAMPAIGN"
    JOB = "JOB"
    GITHUB_REPOSITORY = "GITHUB_REPOSITORY"
    GITHUB_ACTOR = "GITHUB_ACTOR"
    RESEARCH_RUN = "RESEARCH_RUN"
    RESEARCH_TASK = "RESEARCH_TASK"
    WORKFLOW = "WORKFLOW"
    ALERT = "ALERT"
    WATCHLIST = "WATCHLIST"


class InferenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    PREDICTED = "PREDICTED"
    UNKNOWN = "UNKNOWN"


class RelationshipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    HISTORICAL = "HISTORICAL"
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"
    SUPPRESSED = "SUPPRESSED"


class ConflictStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CommunityType(str, Enum):
    TECHNOLOGY_ECOSYSTEM = "TECHNOLOGY_ECOSYSTEM"
    INDUSTRY_CLUSTER = "INDUSTRY_CLUSTER"
    PARTNER_ECOSYSTEM = "PARTNER_ECOSYSTEM"
    COMPANY_GROUP = "COMPANY_GROUP"
    RESEARCH_CLUSTER = "RESEARCH_CLUSTER"
    INTENT_CLUSTER = "INTENT_CLUSTER"


# --- 1. Entities & Versions ---

class KnowledgeEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_entities"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)  # KnowledgeEntityType
    canonical_name = Column(String(255), nullable=False, index=True)
    normalized_identifier = Column(String(255), nullable=False, index=True)  # e.g., "domain:sydneyerp.com.au"
    properties = Column(JSON, default=dict, nullable=False)
    is_canonical = Column(Boolean, default=True, nullable=False)
    merged_into_id = Column(String(36), nullable=True)

    __table_args__ = (
        Index("idx_ke_ws_type_ident", "workspace_id", "entity_type", "normalized_identifier"),
        Index("idx_ke_ws_canon_name", "workspace_id", "canonical_name"),
    )


class KnowledgeEntityVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_entity_versions"

    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    properties_snapshot = Column(JSON, default=dict, nullable=False)
    changed_by = Column(String(100), default="system", nullable=False)
    change_reason = Column(String(255), nullable=True)


# --- 2. Relationships, Versions & Evidence ---

class KnowledgeRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_relationships"

    workspace_id = Column(String(36), nullable=False, index=True)
    source_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(100), nullable=False, index=True)  # USES_ODOO, WORKS_AT, etc.
    inference_status = Column(String(50), default=InferenceStatus.OBSERVED.value, nullable=False)
    status = Column(String(50), default=RelationshipStatus.ACTIVE.value, nullable=False, index=True)
    confidence = Column(Float, default=100.0, nullable=False)  # 0 - 100
    confidence_reason = Column(Text, nullable=True)
    confidence_version = Column(String(50), default="v1.0", nullable=False)
    
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    valid_to = Column(DateTime, nullable=True)
    corroboration_count = Column(Integer, default=1, nullable=False)

    evidence_links = relationship("RelationshipEvidence", backref="relationship", cascade="all, delete-orphan", lazy="joined")

    __table_args__ = (
        Index("idx_kr_ws_src_tgt_type", "workspace_id", "source_entity_id", "target_entity_id", "relationship_type"),
        Index("idx_kr_ws_tgt_src", "workspace_id", "target_entity_id", "source_entity_id"),
    )


class KnowledgeRelationshipVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_relationship_versions"

    relationship_id = Column(String(36), ForeignKey("knowledge_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    snapshot = Column(JSON, default=dict, nullable=False)
    changed_by = Column(String(100), default="system", nullable=False)


class RelationshipEvidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "relationship_evidence"

    relationship_id = Column(String(36), ForeignKey("knowledge_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url = Column(String(1000), nullable=False)
    source_type = Column(String(50), default="WEB", nullable=False)
    evidence_snippet = Column(Text, nullable=False)
    evidence_hash = Column(String(64), nullable=False, index=True)
    source_independence_key = Column(String(255), nullable=False, index=True)  # e.g., domain root to detect syndication
    weight = Column(Float, default=1.0, nullable=False)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class RelationshipConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "relationship_conflicts"

    workspace_id = Column(String(36), nullable=False, index=True)
    relationship_id_a = Column(String(36), ForeignKey("knowledge_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_id_b = Column(String(36), ForeignKey("knowledge_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id = Column(String(36), nullable=False, index=True)
    target_entity_id = Column(String(36), nullable=False, index=True)
    conflict_type = Column(String(100), default="CONTRADICTORY_RELATIONSHIP", nullable=False)
    status = Column(String(50), default=ConflictStatus.UNRESOLVED.value, nullable=False, index=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


# --- 3. Graph Snapshots & Time-Travel ---

class GraphSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    snapshot_name = Column(String(255), nullable=False)
    snapshot_type = Column(String(50), default="DAILY", nullable=False)  # DAILY, WEEKLY, EVENT_BASED
    entity_count = Column(Integer, default=0, nullable=False)
    relationship_count = Column(Integer, default=0, nullable=False)
    graph_version = Column(String(50), default="v1.0", nullable=False)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class GraphSnapshotEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_snapshot_entities"

    snapshot_id = Column(String(36), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    properties_snapshot = Column(JSON, default=dict, nullable=False)


class GraphSnapshotRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_snapshot_relationships"

    snapshot_id = Column(String(36), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_id = Column(String(36), nullable=False, index=True)
    source_entity_id = Column(String(36), nullable=False)
    target_entity_id = Column(String(36), nullable=False)
    relationship_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)


# --- 4. Change Events, Queries & Audits ---

class GraphChangeEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_change_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # RELATIONSHIP_CREATED, CONFLICT_DETECTED, etc.
    entity_id = Column(String(36), nullable=True, index=True)
    relationship_id = Column(String(36), nullable=True, index=True)
    significance_score = Column(Float, default=50.0, nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class GraphQuery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_queries"

    workspace_id = Column(String(36), nullable=False, index=True)
    query_name = Column(String(255), nullable=False)
    dsl_query = Column(JSON, default=dict, nullable=False)
    created_by = Column(String(100), default="system", nullable=False)


class GraphQueryExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_query_executions"

    workspace_id = Column(String(36), nullable=False, index=True)
    query_id = Column(String(36), ForeignKey("graph_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_time_ms = Column(Float, default=0.0, nullable=False)
    nodes_returned = Column(Integer, default=0, nullable=False)
    edges_returned = Column(Integer, default=0, nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- 5. Communities & Ecosystem Clusters ---

class GraphCommunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_communities"

    workspace_id = Column(String(36), nullable=False, index=True)
    community_name = Column(String(255), nullable=False)
    community_type = Column(String(50), default=CommunityType.TECHNOLOGY_ECOSYSTEM.value, nullable=False)
    density = Column(Float, default=0.0, nullable=False)
    centrality_node_id = Column(String(36), nullable=True)
    algorithm = Column(String(50), default="CONNECTED_COMPONENTS", nullable=False)


class GraphCommunityMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_community_members"

    community_id = Column(String(36), ForeignKey("graph_communities.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="MEMBER", nullable=False)
    membership_confidence = Column(Float, default=0.90, nullable=False)


# --- 6. Embeddings, Similarity & Lookalikes ---

class GraphEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_embeddings"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(100), default="all-MiniLM-L6-v2", nullable=False)
    model_version = Column(String(50), default="v1.0", nullable=False)
    embedding_vector = Column(JSON, default=list, nullable=False)  # List[float]
    dimension = Column(Integer, default=384, nullable=False)


class GraphSimilarityResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_similarity_results"

    workspace_id = Column(String(36), nullable=False, index=True)
    source_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, default=0.0, nullable=False)  # 0.0 - 1.0
    matched_factors = Column(JSON, default=dict, nullable=False)  # tech, geo, industry, intent
    limitations_notes = Column(Text, default="SIMILARITY ESTIMATE: High structural or semantic similarity does not imply identical commercial behavior.", nullable=False)


class LookalikeProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lookalike_profiles"

    workspace_id = Column(String(36), nullable=False, index=True)
    profile_name = Column(String(255), nullable=False)
    seed_entity_ids = Column(JSON, default=list, nullable=False)  # List[entity_id]
    matching_dimensions = Column(JSON, default=list, nullable=False)  # ["technology", "industry", "geography"]
    target_count = Column(Integer, default=20, nullable=False)


class LookalikeMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lookalike_matches"

    profile_id = Column(String(36), ForeignKey("lookalike_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_similarity_score = Column(Float, default=0.0, nullable=False)
    dimension_breakdown = Column(JSON, default=dict, nullable=False)
    explanation = Column(Text, nullable=False)


# --- 7. Predicted Relationships (Strictly Opt-In & Separate) ---

class PredictedRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "predicted_relationships"

    workspace_id = Column(String(36), nullable=False, index=True)
    source_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    predicted_relationship_type = Column(String(100), nullable=False)
    probability = Column(Float, default=0.50, nullable=False)
    model_name = Column(String(100), default="link_prediction_gnn", nullable=False)
    model_version = Column(String(50), default="v1.0", nullable=False)
    features = Column(JSON, default=dict, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    status = Column(String(50), default="PREDICTED", nullable=False)


# --- 8. Graph Health & Completeness ---

class GraphHealthSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_health_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    total_entities = Column(Integer, default=0, nullable=False)
    total_relationships = Column(Integer, default=0, nullable=False)
    evidence_coverage_pct = Column(Float, default=100.0, nullable=False)
    conflict_rate_pct = Column(Float, default=0.0, nullable=False)
    stale_edge_rate_pct = Column(Float, default=0.0, nullable=False)
    orphan_node_count = Column(Integer, default=0, nullable=False)
    duplicate_rate_pct = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=95.0, nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class GraphCompletenessSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_completeness_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    completeness_score = Column(Float, default=0.0, nullable=False)  # 0 - 100
    missing_dimensions = Column(JSON, default=list, nullable=False)
    has_decision_maker = Column(Boolean, default=False, nullable=False)
    has_technology = Column(Boolean, default=False, nullable=False)
    has_intent = Column(Boolean, default=False, nullable=False)
    has_evidence = Column(Boolean, default=False, nullable=False)


# --- 9. Graph Research Paths & Gap Recommendations ---

class GraphResearchPath(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_research_paths"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    path_description = Column(String(255), nullable=False)
    start_entity = Column(String(100), nullable=False)
    target_missing_entity = Column(String(100), nullable=False)
    hops = Column(JSON, default=list, nullable=False)  # list of entity types / relations
    expected_information_value = Column(Float, default=1.0, nullable=False)


class GraphResearchRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "graph_research_recommendations"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    missing_relationship = Column(String(100), nullable=False)  # e.g., "DECISION_MAKER"
    suggested_source = Column(String(100), nullable=False)
    eiv_score = Column(Float, default=1.5, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)

