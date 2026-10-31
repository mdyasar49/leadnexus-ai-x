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

class OntologyType(str, enum.Enum):
    CORE_ENTITY = "CORE_ENTITY"
    TECHNOLOGY = "TECHNOLOGY"
    ODOO = "ODOO"
    INDUSTRY = "INDUSTRY"
    JOB_ROLE = "JOB_ROLE"
    BUYING_COMMITTEE = "BUYING_COMMITTEE"
    INTENT = "INTENT"
    SIGNAL = "SIGNAL"
    EVIDENCE_CLAIM = "EVIDENCE_CLAIM"
    SEMANTIC_RELATIONSHIP = "SEMANTIC_RELATIONSHIP"
    PROCESS = "PROCESS"


class ConceptStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class ProposalStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class ReviewDecision(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"
    MERGE = "MERGE"
    SPLIT = "SPLIT"
    DEFER = "DEFER"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class MappingMethod(str, enum.Enum):
    HUMAN_APPROVED = "HUMAN_APPROVED"
    RULE = "RULE"
    DICTIONARY = "DICTIONARY"
    EXACT_MATCH = "EXACT_MATCH"
    FUZZY_MATCH = "FUZZY_MATCH"
    ML_CLASSIFIER = "ML_CLASSIFIER"
    LLM_CLASSIFIER = "LLM_CLASSIFIER"
    UNKNOWN = "UNKNOWN"


class ArticleType(str, enum.Enum):
    ONTOLOGY_DEFINITION = "ONTOLOGY_DEFINITION"
    TAXONOMY_GUIDE = "TAXONOMY_GUIDE"
    RESEARCH_GUIDE = "RESEARCH_GUIDE"
    CLASSIFICATION_GUIDE = "CLASSIFICATION_GUIDE"
    SOURCE_GUIDE = "SOURCE_GUIDE"
    ODOO_KNOWLEDGE = "ODOO_KNOWLEDGE"
    TECHNOLOGY_KNOWLEDGE = "TECHNOLOGY_KNOWLEDGE"
    INDUSTRY_KNOWLEDGE = "INDUSTRY_KNOWLEDGE"
    ROLE_KNOWLEDGE = "ROLE_KNOWLEDGE"
    INTENT_GUIDE = "INTENT_GUIDE"
    DATA_QUALITY_GUIDE = "DATA_QUALITY_GUIDE"


class ContextPacketType(str, enum.Enum):
    COMPANY_CONTEXT = "COMPANY_CONTEXT"
    PERSON_CONTEXT = "PERSON_CONTEXT"
    LEAD_CONTEXT = "LEAD_CONTEXT"
    TECHNOLOGY_CONTEXT = "TECHNOLOGY_CONTEXT"
    INTENT_CONTEXT = "INTENT_CONTEXT"
    RESEARCH_CONTEXT = "RESEARCH_CONTEXT"
    BUYING_COMMITTEE_CONTEXT = "BUYING_COMMITTEE_CONTEXT"
    EVIDENCE_CONTEXT = "EVIDENCE_CONTEXT"
    GRAPH_CONTEXT = "GRAPH_CONTEXT"
    ANALYTICS_CONTEXT = "ANALYTICS_CONTEXT"


# --- 1. Ontology & Versions ---

class Ontology(Base):
    __tablename__ = "ontologies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    ontology_type = Column(String(64), nullable=False, default=OntologyType.CORE_ENTITY.value)
    current_version = Column(String(32), nullable=False, default="v1.0")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    versions = relationship("OntologyVersion", back_populates="ontology", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="ontology", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ontologies_ws_name", "workspace_id", "name", unique=True),
    )


class OntologyVersion(Base):
    __tablename__ = "ontology_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ontology_id = Column(String(36), ForeignKey("ontologies.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    change_summary = Column(Text, nullable=True)
    compatibility = Column(String(64), default="BACKWARD_COMPATIBLE")
    status = Column(String(32), default=ConceptStatus.PUBLISHED.value)
    created_by = Column(String(128), default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    ontology = relationship("Ontology", back_populates="versions")


# --- 2. Concepts & Versions ---

class Concept(Base):
    __tablename__ = "concepts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    ontology_id = Column(String(36), ForeignKey("ontologies.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    ontology_type = Column(String(64), nullable=False, index=True)
    parent_concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), default=ConceptStatus.PUBLISHED.value, nullable=False, index=True)
    version = Column(String(32), default="v1.0", nullable=False)
    provenance = Column(String(256), default="leadnexus.canonical")
    properties = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    ontology = relationship("Ontology", back_populates="concepts")
    parent = relationship("Concept", remote_side=[id], backref="children")
    aliases = relationship("ConceptAlias", back_populates="concept", cascade="all, delete-orphan")
    synonyms = relationship("ConceptSynonym", back_populates="concept", cascade="all, delete-orphan")
    versions = relationship("ConceptVersion", back_populates="concept", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_concepts_ws_type_name", "workspace_id", "ontology_type", "canonical_name", unique=True),
    )


class ConceptVersion(Base):
    __tablename__ = "concept_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    canonical_name = Column(String(128), nullable=False)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    parent_concept_id = Column(String(36), nullable=True)
    properties = Column(JSON, default=dict)
    changed_by = Column(String(128), default="system")
    change_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    concept = relationship("Concept", back_populates="versions")


class ConceptAlias(Base):
    __tablename__ = "concept_aliases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(256), nullable=False, index=True)
    normalized_alias = Column(String(256), nullable=False, index=True)
    source = Column(String(128), default="curated")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    concept = relationship("Concept", back_populates="aliases")

    __table_args__ = (
        Index("ix_concept_aliases_norm", "concept_id", "normalized_alias", unique=True),
    )


class ConceptSynonym(Base):
    __tablename__ = "concept_synonyms"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    synonym = Column(String(256), nullable=False, index=True)
    normalized_synonym = Column(String(256), nullable=False, index=True)
    similarity_score = Column(Float, default=0.9)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    concept = relationship("Concept", back_populates="synonyms")


# --- 3. Concept Relationships & Versions ---

class ConceptRelationship(Base):
    __tablename__ = "concept_relationships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    source_concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    target_concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    is_bidirectional = Column(Boolean, default=False)
    status = Column(String(32), default=ConceptStatus.PUBLISHED.value)
    version = Column(String(32), default="v1.0")
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    source_concept = relationship("Concept", foreign_keys=[source_concept_id])
    target_concept = relationship("Concept", foreign_keys=[target_concept_id])


class ConceptRelationshipVersion(Base):
    __tablename__ = "concept_relationship_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("concept_relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    status = Column(String(32), default=ConceptStatus.PUBLISHED.value)
    confidence = Column(Float, default=1.0)
    changed_by = Column(String(128), default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- 4. Taxonomy & Taxonomy Nodes ---

class Taxonomy(Base):
    __tablename__ = "taxonomies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String(64), nullable=False, default="GENERAL")
    current_version = Column(String(32), default="v1.0", nullable=False)
    status = Column(String(32), default=ConceptStatus.PUBLISHED.value)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    versions = relationship("TaxonomyVersion", back_populates="taxonomy", cascade="all, delete-orphan")
    nodes = relationship("TaxonomyNode", back_populates="taxonomy", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_taxonomies_ws_name", "workspace_id", "name", unique=True),
    )


class TaxonomyVersion(Base):
    __tablename__ = "taxonomy_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    taxonomy_id = Column(String(36), ForeignKey("taxonomies.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    change_summary = Column(Text, nullable=True)
    node_count = Column(Integer, default=0)
    created_by = Column(String(128), default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    taxonomy = relationship("Taxonomy", back_populates="versions")


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    taxonomy_id = Column(String(36), ForeignKey("taxonomies.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_node_id = Column(String(36), ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    level = Column(Integer, default=1)
    path = Column(String(512), nullable=False, index=True)  # e.g., /ERP/ODOO/ODOO_17
    sort_order = Column(Integer, default=0)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    taxonomy = relationship("Taxonomy", back_populates="nodes")
    parent_node = relationship("TaxonomyNode", remote_side=[id], backref="child_nodes")
    concept = relationship("Concept")


# --- 5. Semantic Mapping & Evidence ---

class SemanticMapping(Base):
    __tablename__ = "semantic_mappings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    source_term = Column(String(256), nullable=False, index=True)
    normalized_source_term = Column(String(256), nullable=False, index=True)
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    source_context = Column(String(128), default="GENERAL")  # e.g., GITHUB, JOB_BOARD, WEBSITE
    mapping_method = Column(String(64), default=MappingMethod.EXACT_MATCH.value, nullable=False)
    confidence = Column(Float, default=1.0)
    is_human_approved = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    ontology_version = Column(String(32), default="v1.0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    concept = relationship("Concept")
    evidence_items = relationship("SemanticMappingEvidence", back_populates="mapping", cascade="all, delete-orphan")


class SemanticMappingEvidence(Base):
    __tablename__ = "semantic_mapping_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mapping_id = Column(String(36), ForeignKey("semantic_mappings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url = Column(String(512), nullable=True)
    evidence_snippet = Column(Text, nullable=True)
    source_type = Column(String(64), default="WEB")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    mapping = relationship("SemanticMapping", back_populates="evidence_items")


# --- 6. Classification Rules & Results ---

class ClassificationRule(Base):
    __tablename__ = "classification_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    rule_type = Column(String(64), nullable=False)  # REGEX, KEYWORD, CONDITION
    target_ontology_type = Column(String(64), nullable=False)
    target_concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    pattern = Column(Text, nullable=False)
    priority = Column(Integer, default=50)  # Lower is evaluated earlier
    confidence_weight = Column(Float, default=0.9)
    version = Column(String(32), default="v1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    target_concept = relationship("Concept")
    versions = relationship("ClassificationRuleVersion", back_populates="rule", cascade="all, delete-orphan")


class ClassificationRuleVersion(Base):
    __tablename__ = "classification_rule_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("classification_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    pattern = Column(Text, nullable=False)
    change_summary = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    rule = relationship("ClassificationRule", back_populates="versions")


class ClassificationResult(Base):
    __tablename__ = "classification_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    raw_input_text = Column(Text, nullable=False)
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True)
    canonical_concept_name = Column(String(128), nullable=False)
    ontology_type = Column(String(64), nullable=False)
    confidence = Column(Float, default=0.0)
    classification_method = Column(String(64), nullable=False)
    model_name = Column(String(128), default="leadnexus_classifier")
    model_version = Column(String(32), default="v1.0")
    ontology_version = Column(String(32), default="v1.0")
    evidence_ids = Column(JSON, default=list)
    reasoning_summary = Column(Text, nullable=True)
    review_status = Column(String(32), default="AUTO_ACCEPTED")
    human_decision = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    concept = relationship("Concept")


# --- 7. Ontology Governance: Proposals, Reviews & Validation ---

class OntologyProposal(Base):
    __tablename__ = "ontology_proposals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    proposal_type = Column(String(64), nullable=False)  # NEW_CONCEPT, ALIAS, SYNONYM, RELATIONSHIP, MERGE, SPLIT, DEPRECATE
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    target_ontology_id = Column(String(36), nullable=True)
    payload = Column(JSON, default=dict)
    status = Column(String(32), default=ProposalStatus.PROPOSED.value, nullable=False, index=True)
    proposed_by = Column(String(128), default="operator")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reviews = relationship("OntologyProposalReview", back_populates="proposal", cascade="all, delete-orphan")


class OntologyProposalReview(Base):
    __tablename__ = "ontology_proposal_reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String(36), ForeignKey("ontology_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer = Column(String(128), nullable=False)
    decision = Column(String(32), nullable=False)  # APPROVE, REJECT, EDIT, DEFER, etc.
    notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    proposal = relationship("OntologyProposal", back_populates="reviews")


class OntologyValidationError(Base):
    __tablename__ = "ontology_validation_errors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    error_code = Column(String(64), nullable=False, index=True)  # CIRCULAR_DEPENDENCY, INVALID_PARENT, INVALID_RELATIONSHIP, DUPLICATE_CONCEPT
    severity = Column(String(32), default="ERROR")  # ERROR, WARNING
    entity_id = Column(String(36), nullable=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    is_resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- 8. Knowledge Management Articles ---

class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    article_type = Column(String(64), default=ArticleType.ONTOLOGY_DEFINITION.value, nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(128), default="system")
    current_version = Column(String(32), default="v1.0")
    status = Column(String(32), default="PUBLISHED")
    source_references = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    versions = relationship("KnowledgeArticleVersion", back_populates="article", cascade="all, delete-orphan")
    concepts = relationship("KnowledgeArticleConcept", back_populates="article", cascade="all, delete-orphan")


class KnowledgeArticleVersion(Base):
    __tablename__ = "knowledge_article_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    change_summary = Column(String(256), nullable=True)
    created_by = Column(String(128), default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    article = relationship("KnowledgeArticle", back_populates="versions")


class KnowledgeArticleConcept(Base):
    __tablename__ = "knowledge_article_concepts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("knowledge_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(String(36), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)

    article = relationship("KnowledgeArticle", back_populates="concepts")
    concept = relationship("Concept")


# --- 9. AI Context Packets & Assemblies ---

class ContextPacket(Base):
    __tablename__ = "context_packets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    packet_type = Column(String(64), nullable=False)  # COMPANY_CONTEXT, PERSON_CONTEXT, etc.
    ontology_version = Column(String(32), default="v1.0")
    payload = Column(JSON, default=dict)
    data_quality_score = Column(Float, default=100.0)
    freshness_score = Column(Float, default=100.0)
    token_count = Column(Integer, default=0)
    redacted_fields = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    items = relationship("ContextPacketItem", back_populates="packet", cascade="all, delete-orphan")


class ContextPacketItem(Base):
    __tablename__ = "context_packet_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    packet_id = Column(String(36), ForeignKey("context_packets.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(64), nullable=False)  # FACT, EVIDENCE, CLAIM, RELATIONSHIP, GAP
    content = Column(JSON, default=dict)
    is_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    packet = relationship("ContextPacket", back_populates="items")


class ContextAssembly(Base):
    __tablename__ = "context_assemblies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    assembly_target = Column(String(128), nullable=False)
    assembled_prompt_context = Column(Text, nullable=False)
    ontology_version = Column(String(32), default="v1.0")
    total_tokens = Column(Integer, default=0)
    security_verdict = Column(String(32), default="CLEAN")  # CLEAN, SANITIZED, REJECTED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    evidence_links = relationship("ContextAssemblyEvidence", back_populates="assembly", cascade="all, delete-orphan")


class ContextAssemblyEvidence(Base):
    __tablename__ = "context_assembly_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assembly_id = Column(String(36), ForeignKey("context_assemblies.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(String(64), nullable=False)
    source_url = Column(String(512), nullable=True)
    snippet = Column(Text, nullable=True)

    assembly = relationship("ContextAssembly", back_populates="evidence_links")


# --- 10. Semantic Query & Execution ---

class SemanticQuery(Base):
    __tablename__ = "semantic_queries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(128), nullable=True)
    dsl_query = Column(Text, nullable=False)
    compiled_plan = Column(JSON, default=dict)
    created_by = Column(String(128), default="operator")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    executions = relationship("SemanticQueryExecution", back_populates="query", cascade="all, delete-orphan")


class SemanticQueryExecution(Base):
    __tablename__ = "semantic_query_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id = Column(String(36), ForeignKey("semantic_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    result_count = Column(Integer, default=0)
    execution_time_ms = Column(Float, default=0.0)
    status = Column(String(32), default="SUCCESS")
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    query = relationship("SemanticQuery", back_populates="executions")


# --- 11. Ontology Audit & Change Events ---

class OntologyChangeEvent(Base):
    __tablename__ = "ontology_change_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)  # CONCEPT_CREATED, CONCEPT_UPDATED, TAXONOMY_PUBLISHED, etc.
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(36), nullable=False)
    change_summary = Column(Text, nullable=True)
    diff = Column(JSON, default=dict)
    actor = Column(String(128), default="system")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class OntologyAuditEvent(Base):
    __tablename__ = "ontology_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(36), nullable=False)
    details = Column(JSON, default=dict)
    ip_address = Column(String(64), nullable=True)
    performed_by = Column(String(128), default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
