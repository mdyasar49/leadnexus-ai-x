from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.semantic_ontology import (
    Ontology,
    OntologyVersion,
    Concept,
    ConceptVersion,
    ConceptAlias,
    ConceptSynonym,
    ConceptRelationship,
    Taxonomy,
    TaxonomyVersion,
    TaxonomyNode,
    SemanticMapping,
    OntologyProposal,
    OntologyProposalReview,
    OntologyValidationError,
    KnowledgeArticle,
    ContextAssembly,
    SemanticQuery,
    OntologyType,
    ConceptStatus,
    ProposalStatus,
    MappingMethod
)

from packages.semantic_ontology.ontology_service import OntologyService
from packages.semantic_ontology.ontology_validator import OntologyValidator
from packages.semantic_ontology.taxonomy_governance_engine import TaxonomyGovernanceEngine
from packages.semantic_ontology.semantic_normalization_engine import SemanticNormalizationEngine
from packages.semantic_ontology.semantic_classification_engine import SemanticClassificationEngine
from packages.semantic_ontology.ai_context_assembly_engine import AIContextAssemblyEngine
from packages.semantic_ontology.semantic_query_dsl_engine import SemanticQueryDSLEngine
from packages.semantic_ontology.knowledge_article_service import KnowledgeArticleService
from packages.semantic_ontology.ontology_research_gap_engine import OntologyResearchGapEngine
from packages.semantic_ontology.taxonomy_io_service import TaxonomyIOService


semantic_ontology_router = APIRouter(
    prefix="/ontology",
    tags=["Enterprise Knowledge Management, Semantic Ontology & AI Context"]
)


# --- Pydantic Request Schemas ---

class CreateConceptRequest(BaseModel):
    ontology_name: str = "core_ontology"
    canonical_name: str
    display_name: str
    ontology_type: str = "CORE_ENTITY"
    parent_concept_id: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class AddAliasRequest(BaseModel):
    concept_id: str
    alias: str
    source: str = "curated"


class SubmitProposalRequest(BaseModel):
    proposal_type: str = "NEW_CONCEPT"
    title: str
    description: Optional[str] = None
    target_ontology_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class ReviewProposalRequest(BaseModel):
    proposal_id: str
    decision: str = "APPROVE"  # APPROVE, REJECT, EDIT, DEFER
    notes: Optional[str] = None


class ClassifyTextRequest(BaseModel):
    classification_type: str = "INTENT"  # INTENT, ODOO_RELATIONSHIP, BUYING_COMMITTEE
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    job_title: Optional[str] = None
    is_partner_listed: bool = False


class NormalizeTermRequest(BaseModel):
    term: str
    source_context: str = "GENERAL"
    ontology_type: Optional[str] = None
    source_url: Optional[str] = None
    evidence_snippet: Optional[str] = None


class ExecuteDSLRequest(BaseModel):
    dsl_query: str
    limit: int = 50


class CreateArticleRequest(BaseModel):
    title: str
    content: str
    article_type: str = "ONTOLOGY_DEFINITION"
    concept_ids: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)


# --- 1. Ontology & Concepts Endpoints ---

@semantic_ontology_router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_core_taxonomies(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Seeds standard LeadNexus ontologies, taxonomies, and aliases for current workspace."""
    service = OntologyService(db)
    counts = service.seed_core_taxonomies(ws.id)
    return {"status": "SUCCESS", "message": "Standard ontologies seeded.", "counts": counts}


@semantic_ontology_router.get("/concepts")
def list_concepts(
    ontology_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Lists canonical concepts in the active workspace."""
    q = db.query(Concept).filter(Concept.workspace_id == ws.id)
    if ontology_type:
        q = q.filter(Concept.ontology_type == ontology_type.upper())
    if status_filter:
        q = q.filter(Concept.status == status_filter.upper())
    concepts = q.limit(limit).all()

    return [
        {
            "id": c.id,
            "canonical_name": c.canonical_name,
            "display_name": c.display_name,
            "ontology_type": c.ontology_type,
            "parent_concept_id": c.parent_concept_id,
            "version": c.version,
            "status": c.status,
            "confidence": c.confidence,
            "alias_count": len(c.aliases)
        }
        for c in concepts
    ]


@semantic_ontology_router.post("/concepts", status_code=status.HTTP_201_CREATED)
def create_concept(
    req: CreateConceptRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Creates a new canonical concept."""
    service = OntologyService(db)
    ont = service.get_or_create_ontology(
        workspace_id=ws.id,
        name=req.ontology_name,
        display_name=req.ontology_name.replace("_", " ").title(),
        ontology_type=req.ontology_type
    )

    concept = service.upsert_concept(
        workspace_id=ws.id,
        ontology_id=ont.id,
        canonical_name=req.canonical_name,
        display_name=req.display_name,
        ontology_type=req.ontology_type,
        parent_concept_id=req.parent_concept_id,
        description=req.description,
        properties=req.properties,
        changed_by=user.email or user.username
    )
    return {"id": concept.id, "canonical_name": concept.canonical_name, "version": concept.version}


@semantic_ontology_router.get("/concepts/{concept_id}")
def get_concept_detail(
    concept_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Retrieves full concept details including aliases, synonyms, and parent hierarchy."""
    concept = db.query(Concept).filter(
        and_(Concept.workspace_id == ws.id, Concept.id == concept_id)
    ).first()
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found.")

    return {
        "id": concept.id,
        "canonical_name": concept.canonical_name,
        "display_name": concept.display_name,
        "description": concept.description,
        "ontology_type": concept.ontology_type,
        "parent": {
            "id": concept.parent.id,
            "canonical_name": concept.parent.canonical_name
        } if concept.parent else None,
        "aliases": [a.alias for a in concept.aliases],
        "synonyms": [s.synonym for s in concept.synonyms],
        "version": concept.version,
        "status": concept.status,
        "confidence": concept.confidence,
        "created_at": concept.created_at.isoformat() if concept.created_at else None,
        "properties": concept.properties
    }


@semantic_ontology_router.get("/concepts/{concept_id}/children")
def get_concept_children(
    concept_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Retrieves immediate children nodes for a concept."""
    children = db.query(Concept).filter(
        and_(Concept.workspace_id == ws.id, Concept.parent_concept_id == concept_id)
    ).all()
    return [
        {"id": c.id, "canonical_name": c.canonical_name, "display_name": c.display_name, "ontology_type": c.ontology_type}
        for c in children
    ]


@semantic_ontology_router.get("/search")
def search_ontology(
    q: str,
    ontology_type: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Searches concepts and aliases using canonical name or alias match."""
    service = OntologyService(db)
    res = service.resolve_concept_by_name_or_alias(ws.id, q, ontology_type)
    if not res:
        return {"query": q, "resolved": False, "match": None}

    return {
        "query": q,
        "resolved": True,
        "match": {
            "id": res.id,
            "canonical_name": res.canonical_name,
            "display_name": res.display_name,
            "ontology_type": res.ontology_type,
            "confidence": res.confidence
        }
    }


# --- 2. Taxonomies Endpoints ---

@semantic_ontology_router.get("/taxonomies")
def list_taxonomies(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    taxonomies = db.query(Taxonomy).filter(Taxonomy.workspace_id == ws.id).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "display_name": t.display_name,
            "domain": t.domain,
            "current_version": t.current_version,
            "node_count": len(t.nodes)
        }
        for t in taxonomies
    ]


@semantic_ontology_router.get("/taxonomies/{taxonomy_id}/diff")
def get_taxonomy_diff(
    taxonomy_id: str,
    version_a: str = Query(...),
    version_b: str = Query(...),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Compares node counts and changes between two taxonomy version snapshots."""
    gov = TaxonomyGovernanceEngine(db)
    return gov.get_taxonomy_diff(ws.id, taxonomy_id, version_a, version_b)


# --- 3. Aliases, Proposals & Governance ---

@semantic_ontology_router.post("/aliases")
def add_concept_alias(
    req: AddAliasRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    service = OntologyService(db)
    alias_row = service.add_alias(req.concept_id, req.alias, source=req.source)
    return {"id": alias_row.id, "concept_id": req.concept_id, "alias": alias_row.alias}


@semantic_ontology_router.get("/proposals")
def list_proposals(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    q = db.query(OntologyProposal).filter(OntologyProposal.workspace_id == ws.id)
    if status_filter:
        q = q.filter(OntologyProposal.status == status_filter.upper())
    proposals = q.order_by(desc(OntologyProposal.created_at)).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "proposal_type": p.proposal_type,
            "status": p.status,
            "proposed_by": p.proposed_by,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in proposals
    ]


@semantic_ontology_router.post("/proposals", status_code=status.HTTP_201_CREATED)
def submit_proposal(
    req: SubmitProposalRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    gov = TaxonomyGovernanceEngine(db)
    prop = gov.submit_proposal(
        workspace_id=ws.id,
        proposal_type=req.proposal_type,
        title=req.title,
        payload=req.payload,
        description=req.description,
        target_ontology_id=req.target_ontology_id,
        proposed_by=user.email or user.username
    )
    return {"id": prop.id, "title": prop.title, "status": prop.status}


@semantic_ontology_router.post("/reviews")
def review_proposal(
    req: ReviewProposalRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    gov = TaxonomyGovernanceEngine(db)
    prop = gov.review_proposal(
        workspace_id=ws.id,
        proposal_id=req.proposal_id,
        reviewer=user.email or user.username,
        decision=req.decision,
        notes=req.notes
    )
    return {"id": prop.id, "status": prop.status, "updated_at": prop.updated_at.isoformat()}


@semantic_ontology_router.get("/validation")
def validate_ontology(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Runs automated validation (cycles, invalid parents, collisions) on workspace ontology."""
    validator = OntologyValidator(db)
    errors = validator.validate_workspace_ontology(ws.id)
    return {"total_errors": len(errors), "errors": errors}


# --- 4. Semantic Normalization & Classification ---

@semantic_ontology_router.post("/normalize")
def normalize_semantic_term(
    req: NormalizeTermRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Normalizes a raw term to canonical concept via multi-priority engine."""
    norm_eng = SemanticNormalizationEngine(db)
    return norm_eng.normalize_term(
        workspace_id=ws.id,
        raw_term=req.term,
        source_context=req.source_context,
        ontology_type=req.ontology_type,
        source_url=req.source_url,
        evidence_snippet=req.evidence_snippet
    )


@semantic_ontology_router.post("/classify")
def classify_text_evidence(
    req: ClassifyTextRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Classifies raw text evidence into formal intent, odoo relationship, or buying committee role."""
    cls_eng = SemanticClassificationEngine(db)
    c_type = req.classification_type.upper()

    if c_type == "INTENT":
        res = cls_eng.classify_intent(
            workspace_id=ws.id,
            evidence_text=req.text,
            evidence_ids=req.evidence_ids
        )
    elif c_type == "ODOO_RELATIONSHIP":
        res = cls_eng.classify_odoo_relationship(
            workspace_id=ws.id,
            evidence_text=req.text,
            is_partner_listed=req.is_partner_listed,
            evidence_ids=req.evidence_ids
        )
    elif c_type == "BUYING_COMMITTEE":
        res = cls_eng.classify_buying_committee_role(
            workspace_id=ws.id,
            job_title=req.job_title or req.text
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported classification_type '{req.classification_type}'.")

    return {
        "id": res.id,
        "canonical_name": res.canonical_concept_name,
        "ontology_type": res.ontology_type,
        "confidence": res.confidence,
        "classification_method": res.classification_method,
        "reasoning": res.reasoning_summary,
        "review_status": res.review_status
    }


# --- 5. Safe Semantic Query DSL Execution ---

@semantic_ontology_router.post("/query")
def execute_semantic_query(
    req: ExecuteDSLRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Executes a safe Semantic Query DSL statement without raw SQL generation."""
    dsl_eng = SemanticQueryDSLEngine(db)
    try:
        return dsl_eng.execute_query(
            workspace_id=ws.id,
            dsl_text=req.dsl_query,
            limit=req.limit,
            executed_by=user.email or user.username
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 6. AI Context Assembly Endpoints ---

@semantic_ontology_router.get("/context/company/{company_id}")
def assemble_company_context(
    company_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Assembles a secure, prompt-injection-defended context assembly for a company."""
    ctx_eng = AIContextAssemblyEngine(db)
    try:
        assembly = ctx_eng.assemble_company_context(
            workspace_id=ws.id,
            company_id=company_id,
            caller_role=user.role if hasattr(user, "role") else "analyst"
        )
        return {
            "assembly_id": assembly.id,
            "target": assembly.assembly_target,
            "security_verdict": assembly.security_verdict,
            "total_tokens": assembly.total_tokens,
            "assembled_prompt": assembly.assembled_prompt_context
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@semantic_ontology_router.get("/context/research/{company_id}")
def evaluate_company_research_gaps(
    company_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Evaluates ontology-driven research gaps (e.g., ODOO_VERSION_UNKNOWN, DECISION_MAKER_MISSING)."""
    gap_eng = OntologyResearchGapEngine(db)
    try:
        gaps = gap_eng.evaluate_company_research_gaps(ws.id, company_id)
        return {"company_id": company_id, "total_gaps": len(gaps), "research_gaps": gaps}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- 7. Knowledge Articles Endpoints ---

@semantic_ontology_router.get("/articles")
def list_knowledge_articles(
    article_type: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    art_svc = KnowledgeArticleService(db)
    articles = art_svc.list_articles(ws.id, article_type, q)
    return [
        {
            "id": a.id,
            "title": a.title,
            "article_type": a.article_type,
            "version": a.current_version,
            "author": a.author,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None
        }
        for a in articles
    ]


@semantic_ontology_router.post("/articles", status_code=status.HTTP_201_CREATED)
def create_knowledge_article(
    req: CreateArticleRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    art_svc = KnowledgeArticleService(db)
    art = art_svc.create_article(
        workspace_id=ws.id,
        title=req.title,
        content=req.content,
        article_type=req.article_type,
        author=user.email or user.username,
        concept_ids=req.concept_ids,
        source_references=req.source_references
    )
    return {"id": art.id, "title": art.title, "version": art.current_version}


# --- 8. Secure Import & Export Endpoints ---

@semantic_ontology_router.get("/export")
def export_ontology_concepts(
    export_format: str = Query("json", regex="^(json|csv)$"),
    ontology_type: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Exports ontology concepts safely in JSON or CSV with formula injection sanitization."""
    io_svc = TaxonomyIOService(db)
    if export_format == "csv":
        csv_data = io_svc.export_concepts_csv(ws.id, ontology_type)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ontology_export.csv"}
        )
    return io_svc.export_concepts_json(ws.id, ontology_type)


@semantic_ontology_router.post("/import/preview")
def preview_ontology_import(
    payload: List[Dict[str, Any]],
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Pre-validates and previews imported concepts, detecting conflicts prior to application."""
    io_svc = TaxonomyIOService(db)
    return io_svc.preview_json_import(ws.id, payload)

