import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


# --- Enums ---

class QueryType(str, enum.Enum):
    ENTITY_LOOKUP = "ENTITY_LOOKUP"
    ENTITY_COMPARISON = "ENTITY_COMPARISON"
    EVIDENCE_LOOKUP = "EVIDENCE_LOOKUP"
    RELATIONSHIP_QUERY = "RELATIONSHIP_QUERY"
    INTENT_QUERY = "INTENT_QUERY"
    TECHNOLOGY_QUERY = "TECHNOLOGY_QUERY"
    RESEARCH_QUERY = "RESEARCH_QUERY"
    ANALYTICS_QUERY = "ANALYTICS_QUERY"
    CHANGE_QUERY = "CHANGE_QUERY"
    SCORE_QUERY = "SCORE_QUERY"
    QUALITY_QUERY = "QUALITY_QUERY"
    CONTACT_QUERY = "CONTACT_QUERY"
    DECISION_MAKER_QUERY = "DECISION_MAKER_QUERY"
    BUYING_COMMITTEE_QUERY = "BUYING_COMMITTEE_QUERY"
    ONTOLOGY_QUERY = "ONTOLOGY_QUERY"
    GRAPH_QUERY = "GRAPH_QUERY"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    RECOMMENDATION_QUERY = "RECOMMENDATION_QUERY"
    FORECAST_QUERY = "FORECAST_QUERY"
    GENERAL_PLATFORM_QUERY = "GENERAL_PLATFORM_QUERY"


class RetrievalMode(str, enum.Enum):
    EXACT = "EXACT"
    KEYWORD = "KEYWORD"
    SEMANTIC = "SEMANTIC"
    VECTOR = "VECTOR"
    GRAPH = "GRAPH"
    TEMPORAL = "TEMPORAL"
    EVIDENCE = "EVIDENCE"
    HYBRID = "HYBRID"


class AnswerState(str, enum.Enum):
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"


class PredictionLabel(str, enum.Enum):
    OBSERVED = "OBSERVED"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"
    PREDICTED = "PREDICTED"
    FORECAST = "FORECAST"
    RECOMMENDED = "RECOMMENDED"


class ModelTier(str, enum.Enum):
    SMALL = "SMALL"      # Fast extraction, normalization, simple classification
    MEDIUM = "MEDIUM"    # Summarization, semantic synthesis, comparison
    LARGE = "LARGE"      # Complex multi-source synthesis, deep research


# --- 1. AI Query & Plans ---

class AIQuery(Base):
    __tablename__ = "ai_queries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    raw_query = Column(Text, nullable=False)
    normalized_query = Column(Text, nullable=False)
    query_type = Column(String(64), nullable=False, default=QueryType.GENERAL_PLATFORM_QUERY.value)
    retrieval_mode = Column(String(32), default=RetrievalMode.HYBRID.value)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    plans = relationship("AIQueryPlan", back_populates="query", cascade="all, delete-orphan")
    executions = relationship("AIQueryExecution", back_populates="query", cascade="all, delete-orphan")


class AIQueryPlan(Base):
    __tablename__ = "ai_query_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id = Column(String(36), ForeignKey("ai_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    query_type = Column(String(64), nullable=False)
    target_entities = Column(JSON, default=list)
    target_concepts = Column(JSON, default=list)
    retrieval_modes = Column(JSON, default=list)
    temporal_constraints = Column(JSON, default=dict)
    minimum_confidence = Column(Float, default=0.70)
    max_evidence_items = Column(Integer, default=15)
    plan_steps = Column(JSON, default=list)
    is_validated = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    query = relationship("AIQuery", back_populates="plans")


class AIQueryExecution(Base):
    __tablename__ = "ai_query_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id = Column(String(36), ForeignKey("ai_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    answer_state = Column(String(32), default=AnswerState.GROUNDED.value)
    response_text = Column(Text, nullable=False)
    reasoning_summary = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)
    has_conflicts = Column(Boolean, default=False)
    conflict_notes = Column(Text, nullable=True)
    total_tokens_used = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    query = relationship("AIQuery", back_populates="executions")
    citations = relationship("AICitation", back_populates="execution", cascade="all, delete-orphan")
    claims = relationship("AIClaim", back_populates="execution", cascade="all, delete-orphan")


# --- 2. RAG Documents, Chunks & Embeddings ---

class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    document_type = Column(String(64), nullable=False)  # EVIDENCE, COMPANY, ARTICLE, GITHUB, JOB
    title = Column(String(256), nullable=False)
    source_url = Column(String(512), nullable=True)
    source_type = Column(String(64), default="WEB")
    source_reliability = Column(Float, default=0.85)
    entity_id = Column(String(36), nullable=True, index=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    observed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    chunks = relationship("RAGDocumentChunk", back_populates="document", cascade="all, delete-orphan")


class RAGDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, default=0, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_hash = Column(String(64), nullable=False, index=True)
    entity_ids = Column(JSON, default=list)
    concept_ids = Column(JSON, default=list)
    evidence_ids = Column(JSON, default=list)
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("RAGDocument", back_populates="chunks")
    embeddings = relationship("RAGEmbedding", back_populates="chunk", cascade="all, delete-orphan")


class RAGEmbedding(Base):
    __tablename__ = "rag_embeddings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chunk_id = Column(String(36), ForeignKey("rag_document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_model = Column(String(128), default="leadnexus-semantic-v1", nullable=False)
    embedding_version = Column(String(32), default="v1.0", nullable=False)
    dimensions = Column(Integer, default=384, nullable=False)
    vector = Column(JSON, nullable=False)  # Normalized float vector
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    chunk = relationship("RAGDocumentChunk", back_populates="embeddings")


# --- 3. Retrieval Ranking & Results ---

class RetrievalQuery(Base):
    __tablename__ = "retrieval_queries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    raw_query = Column(Text, nullable=False)
    retrieval_mode = Column(String(32), default=RetrievalMode.HYBRID.value)
    filters = Column(JSON, default=dict)
    limit = Column(Integer, default=20)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    results = relationship("RetrievalResult", back_populates="retrieval_query", cascade="all, delete-orphan")


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    retrieval_query_id = Column(String(36), ForeignKey("retrieval_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(36), nullable=False)
    entity_id = Column(String(36), nullable=True)
    evidence_id = Column(String(36), nullable=True)
    source_url = Column(String(512), nullable=True)
    score = Column(Float, default=0.0)
    semantic_score = Column(Float, default=0.0)
    keyword_score = Column(Float, default=0.0)
    graph_relevance_score = Column(Float, default=0.0)
    freshness_score = Column(Float, default=1.0)
    source_independence_score = Column(Float, default=1.0)
    copy_cluster_id = Column(String(64), nullable=True)
    snippet = Column(Text, nullable=False)
    rank = Column(Integer, default=1)

    retrieval_query = relationship("RetrievalQuery", back_populates="results")


# --- 4. Grounding Citations, Claims & Validation ---

class AICitation(Base):
    __tablename__ = "ai_citations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("ai_query_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    citation_number = Column(Integer, default=1)
    entity_id = Column(String(36), nullable=True, index=True)
    evidence_id = Column(String(36), nullable=True)
    source_id = Column(String(36), nullable=True)
    claim_id = Column(String(36), nullable=True)
    source_url = Column(String(512), nullable=True)
    source_title = Column(String(256), default="Verified Intelligence Source")
    evidence_snippet = Column(Text, nullable=False)
    observed_at = Column(DateTime, nullable=True)
    confidence = Column(Float, default=1.0)
    freshness_status = Column(String(32), default="CURRENT")

    execution = relationship("AIQueryExecution", back_populates="citations")


class AIClaim(Base):
    __tablename__ = "ai_claims"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), ForeignKey("ai_query_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_type = Column(String(64), nullable=False)  # e.g., COMPANY_USES_TECHNOLOGY, PERSON_HOLDS_ROLE
    subject = Column(String(256), nullable=False)
    predicate = Column(String(64), nullable=False)
    object_value = Column(String(256), nullable=False)
    prediction_label = Column(String(32), default=PredictionLabel.OBSERVED.value)
    certainty = Column(String(32), default="SUPPORTED")  # SUPPORTED, INSUFFICIENT, CONTRADICTED
    evidence_count = Column(Integer, default=1)

    execution = relationship("AIQueryExecution", back_populates="claims")
    evidence_items = relationship("AIClaimEvidence", back_populates="claim", cascade="all, delete-orphan")


class AIClaimEvidence(Base):
    __tablename__ = "ai_claim_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("ai_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(String(36), nullable=False)
    source_url = Column(String(512), nullable=True)
    snippet = Column(Text, nullable=True)

    claim = relationship("AIClaim", back_populates="evidence_items")


class AIAnswerValidation(Base):
    __tablename__ = "ai_answer_validations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String(36), nullable=False, index=True)
    is_grounded = Column(Boolean, default=True)
    groundedness_score = Column(Float, default=1.0)
    total_claims = Column(Integer, default=0)
    supported_claims = Column(Integer, default=0)
    unsupported_claims_count = Column(Integer, default=0)
    has_hallucinations = Column(Boolean, default=False)
    validation_status = Column(String(32), default="PASSED")  # PASSED, REJECTED, REGENERATE
    details = Column(JSON, default=dict)
    validated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- 5. Conversations & Interactive Research Sessions ---

class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    title = Column(String(256), default="Research Conversation")
    context_type = Column(String(64), default="GENERAL")  # COMPANY, LEAD, ANALYTICS
    entity_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("AIConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class AIConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    citations_payload = Column(JSON, default=list)
    claims_payload = Column(JSON, default=list)
    reasoning_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    conversation = relationship("AIConversation", back_populates="messages")


class AIResearchSession(Base):
    __tablename__ = "ai_research_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    target_entity_id = Column(String(36), nullable=False, index=True)
    objective = Column(Text, nullable=False)
    current_status = Column(String(32), default="ACTIVE")  # ACTIVE, PAUSED, COMPLETED, CANCELLED
    current_step = Column(Integer, default=1)
    max_steps = Column(Integer, default=5)
    budget_tokens = Column(Integer, default=50000)
    used_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    steps = relationship("AIResearchStep", back_populates="session", cascade="all, delete-orphan")


class AIResearchStep(Base):
    __tablename__ = "ai_research_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("ai_research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    description = Column(String(256), nullable=False)
    status = Column(String(32), default="COMPLETED")
    findings_summary = Column(Text, nullable=True)
    gaps_identified = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("AIResearchSession", back_populates="steps")
    tool_calls = relationship("AIResearchToolCall", back_populates="step", cascade="all, delete-orphan")


class AIResearchToolCall(Base):
    __tablename__ = "ai_research_tool_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    step_id = Column(String(36), ForeignKey("ai_research_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(128), nullable=False)  # Allowed tools only (e.g. search, retrieve_evidence, retrieve_graph)
    parameters = Column(JSON, default=dict)
    result_count = Column(Integer, default=0)
    is_authorized = Column(Boolean, default=True)
    execution_time_ms = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    step = relationship("AIResearchStep", back_populates="tool_calls")


# --- 6. Model Routing, Cost & Budgets ---

class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, index=True)
    provider = Column(String(64), nullable=False)  # internal, gemini, anthropic, openai
    tier = Column(String(32), default=ModelTier.MEDIUM.value)
    cost_per_1k_input_tokens = Column(Float, default=0.001)
    cost_per_1k_output_tokens = Column(Float, default=0.002)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    routes = relationship("AIModelRoute", back_populates="model", cascade="all, delete-orphan")


class AIModelRoute(Base):
    __tablename__ = "ai_model_routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    task_type = Column(String(64), nullable=False)  # CLASSIFICATION, EXTRACTION, SUMMARIZATION, RESEARCH
    model_id = Column(String(36), ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False, index=True)
    temperature = Column(Float, default=0.1)
    max_tokens = Column(Integer, default=2048)
    is_default = Column(Boolean, default=True)

    model = relationship("AIModel", back_populates="routes")


class AIBudget(Base):
    __tablename__ = "ai_budgets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    monthly_budget_usd = Column(Float, default=200.0)
    current_month_spent_usd = Column(Float, default=0.0)
    daily_token_limit = Column(Integer, default=500000)
    current_day_tokens = Column(Integer, default=0)
    is_throttled = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ai_budgets_ws", "workspace_id", unique=True),
    )


# --- 7. Evaluation, Feedback & Metrics ---

class AIFeedback(Base):
    __tablename__ = "ai_feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    execution_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    rating = Column(String(32), nullable=False)  # HELPFUL, UNHELPFUL, INACCURATE, MISSING_EVIDENCE
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AIEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    evaluation_name = Column(String(128), nullable=False)
    dataset_size = Column(Integer, default=0)
    average_groundedness = Column(Float, default=1.0)
    average_citation_coverage = Column(Float, default=1.0)
    average_latency_ms = Column(Float, default=0.0)
    unsupported_claim_rate = Column(Float, default=0.0)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

