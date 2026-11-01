"""
Enterprise Data Fabric API Routes (Phase 39)
Provides Unified Data Contracts, Catalog Discovery, Lineage DAG Tracking,
Cross-Domain Semantic Relations, Quality Radar Scoring, and Policy Enforcement across all 13 domains:
COMPANIES, PEOPLE, CONTACTS, LEADS, EVIDENCE, SIGNALS, INTENT, RESEARCH,
GRAPH, ANALYTICS, WORKFLOWS, MONITORING, INTEGRATIONS.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.enterprise_data_fabric import (
    DataDomainEnum,
    DataClassification,
    ContractStatus,
    PolicyEnforcementAction,
    DataContractRecord,
    DataCatalogEntry,
    DataLineageEdge,
    CrossDomainRelation,
    DataQualityAssessment,
    DataPolicyEnforcement,
)
from packages.data_fabric.unified_contracts import UnifiedDataContractEngine, ContractValidationError
from packages.data_fabric.federated_access import FederatedAccessRouter
from packages.data_fabric.data_lineage_tracker import DataLineageTracker, LineageCycleError
from packages.data_fabric.quality_evaluator import DataQualityEvaluator
from packages.data_fabric.policy_enforcer import DataPolicyEnforcer

router = APIRouter(prefix="/data-fabric", tags=["Enterprise Data Fabric"])


# --- Schemas ---

class ContractCreate(BaseModel):
    domain: str
    asset_name: str
    schema_definition: Dict[str, Any]
    sla_freshness_seconds: int = 3600
    quality_rules: List[Dict[str, Any]] = Field(default_factory=list)
    owner_team: str = "Data Platform"


class ContractValidateRequest(BaseModel):
    contract_id: str
    payload: Dict[str, Any]


class CatalogEntryCreate(BaseModel):
    domain: str
    asset_name: str
    entity_type: str
    description: str
    fields: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    classification: str = DataClassification.INTERNAL
    owner_email: str


class LineageEdgeCreate(BaseModel):
    source_domain: str
    source_asset: str
    target_domain: str
    target_asset: str
    transformation_type: str = "ETL"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CrossDomainRelationCreate(BaseModel):
    primary_domain: str
    primary_entity_id: str
    related_domain: str
    related_entity_id: str
    relationship_type: str
    confidence_score: float = 1.0


class QualityAssessmentRequest(BaseModel):
    domain: str
    asset_name: str
    records: List[Dict[str, Any]]
    required_fields: List[str]
    unique_key: Optional[str] = None
    sla_seconds: int = 3600


class PolicyCreate(BaseModel):
    policy_name: str
    target_domain: str
    enforcement_action: str = PolicyEnforcementAction.MASK
    field_name: Optional[str] = None
    condition_expression: Optional[str] = None


class FederatedQueryRequest(BaseModel):
    domain: str
    entity_id: str
    include_related: bool = True
    max_depth: int = 2


# --- 1. Unified Data Contracts ---

@router.get("/contracts")
def list_contracts(
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DataContractRecord).filter(DataContractRecord.workspace_id == ws.id)
    if domain:
        query = query.filter(DataContractRecord.domain == domain.upper())
    return {"contracts": query.all()}


@router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    dom = payload.domain.upper()
    if dom not in DataDomainEnum.ALL_DOMAINS:
        raise HTTPException(status_code=400, detail=f"Invalid data domain: {payload.domain}. Allowed: {DataDomainEnum.ALL_DOMAINS}")

    contract = DataContractRecord(
        workspace_id=ws.id,
        domain=dom,
        asset_name=payload.asset_name,
        schema_definition=payload.schema_definition,
        sla_freshness_seconds=payload.sla_freshness_seconds,
        quality_rules=payload.quality_rules,
        owner_team=payload.owner_team,
        status=ContractStatus.ACTIVE,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return {"status": "created", "contract": contract}


@router.post("/contracts/{contract_id}/validate")
def validate_payload_against_contract(
    contract_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    contract = db.query(DataContractRecord).filter(
        DataContractRecord.id == contract_id,
        DataContractRecord.workspace_id == ws.id,
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    is_valid, violations = UnifiedDataContractEngine.validate_payload(
        payload=payload,
        schema_definition=contract.schema_definition,
        quality_rules=contract.quality_rules,
    )

    return {
        "contract_id": contract.id,
        "domain": contract.domain,
        "asset_name": contract.asset_name,
        "is_valid": is_valid,
        "violations": violations,
    }


# --- 2. Data Catalog & Discovery ---

@router.get("/catalog")
def list_catalog_entries(
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DataCatalogEntry).filter(DataCatalogEntry.workspace_id == ws.id)
    if domain:
        query = query.filter(DataCatalogEntry.domain == domain.upper())
    return {"catalog_entries": query.all()}


@router.post("/catalog", status_code=status.HTTP_201_CREATED)
def register_catalog_entry(
    payload: CatalogEntryCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    entry = DataCatalogEntry(
        workspace_id=ws.id,
        domain=payload.domain.upper(),
        asset_name=payload.asset_name,
        entity_type=payload.entity_type,
        description=payload.description,
        fields=payload.fields,
        tags=payload.tags,
        classification=payload.classification.upper(),
        owner_email=payload.owner_email,
        freshness_updated_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"status": "registered", "catalog_entry": entry}


@router.get("/catalog/search")
def search_catalog(
    q: str = Query(...),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Searches catalog across all 13 domains by keywords in asset name, description, or tags."""
    pattern = f"%{q.lower()}%"
    entries = db.query(DataCatalogEntry).filter(
        DataCatalogEntry.workspace_id == ws.id,
        (
            DataCatalogEntry.asset_name.ilike(pattern)
            | DataCatalogEntry.description.ilike(pattern)
            | DataCatalogEntry.domain.ilike(pattern)
            | DataCatalogEntry.entity_type.ilike(pattern)
        ),
    ).all()
    return {"query": q, "total_matches": len(entries), "results": entries}


# --- 3. Data Lineage DAG Tracking ---

@router.get("/lineage")
def list_lineage_edges(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    edges = db.query(DataLineageEdge).filter(DataLineageEdge.workspace_id == ws.id).all()
    return {"edges": edges}


@router.post("/lineage", status_code=status.HTTP_201_CREATED)
def add_lineage_edge(
    payload: LineageEdgeCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    # Verify no cycle
    tracker = DataLineageTracker()
    existing_edges = db.query(DataLineageEdge).filter(DataLineageEdge.workspace_id == ws.id).all()
    for e in existing_edges:
        try:
            tracker.add_edge(e.source_domain, e.source_asset, e.target_domain, e.target_asset, e.transformation_type)
        except LineageCycleError:
            pass

    try:
        tracker.add_edge(
            payload.source_domain,
            payload.source_asset,
            payload.target_domain,
            payload.target_asset,
            payload.transformation_type,
        )
    except LineageCycleError as err:
        raise HTTPException(status_code=400, detail=str(err))

    edge = DataLineageEdge(
        workspace_id=ws.id,
        source_domain=payload.source_domain.upper(),
        source_asset=payload.source_asset,
        target_domain=payload.target_domain.upper(),
        target_asset=payload.target_asset,
        transformation_type=payload.transformation_type,
        lineage_metadata=payload.metadata,
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return {"status": "created", "edge": edge}


@router.get("/lineage/trace/downstream")
def trace_downstream(
    domain: str = Query(...),
    asset: str = Query(...),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    tracker = DataLineageTracker()
    edges = db.query(DataLineageEdge).filter(DataLineageEdge.workspace_id == ws.id).all()
    for e in edges:
        try:
            tracker.add_edge(e.source_domain, e.source_asset, e.target_domain, e.target_asset, e.transformation_type)
        except LineageCycleError:
            pass

    trace = tracker.trace_downstream_impact(domain, asset)
    return trace


@router.get("/lineage/trace/upstream")
def trace_upstream(
    domain: str = Query(...),
    asset: str = Query(...),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    tracker = DataLineageTracker()
    edges = db.query(DataLineageEdge).filter(DataLineageEdge.workspace_id == ws.id).all()
    for e in edges:
        try:
            tracker.add_edge(e.source_domain, e.source_asset, e.target_domain, e.target_asset, e.transformation_type)
        except LineageCycleError:
            pass

    trace = tracker.trace_upstream_provenance(domain, asset)
    return trace


# --- 4. Cross-Domain Semantic Relationships ---

@router.get("/relationships")
def list_relations(
    domain: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CrossDomainRelation).filter(CrossDomainRelation.workspace_id == ws.id)
    if domain:
        query = query.filter(
            (CrossDomainRelation.primary_domain == domain.upper())
            | (CrossDomainRelation.related_domain == domain.upper())
        )
    if entity_id:
        query = query.filter(
            (CrossDomainRelation.primary_entity_id == entity_id)
            | (CrossDomainRelation.related_entity_id == entity_id)
        )
    return {"relations": query.all()}


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
def create_relation(
    payload: CrossDomainRelationCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    rel = CrossDomainRelation(
        workspace_id=ws.id,
        primary_domain=payload.primary_domain.upper(),
        primary_entity_id=payload.primary_entity_id,
        related_domain=payload.related_domain.upper(),
        related_entity_id=payload.related_entity_id,
        relationship_type=payload.relationship_type,
        confidence_score=payload.confidence_score,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return {"status": "created", "relation": rel}


@router.get("/relationships/subgraph")
def get_subgraph(
    domain: str = Query(...),
    entity_id: str = Query(...),
    max_depth: int = Query(2),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    router_engine = FederatedAccessRouter()
    relations = db.query(CrossDomainRelation).filter(CrossDomainRelation.workspace_id == ws.id).all()
    for r in relations:
        router_engine.register_relation(
            r.primary_domain,
            r.primary_entity_id,
            r.related_domain,
            r.related_entity_id,
            r.relationship_type,
            r.confidence_score,
        )

    subgraph = router_engine.build_cross_domain_subgraph(domain, entity_id, max_depth=max_depth)
    return subgraph


# --- 5. Data Quality Radar Assessments ---

@router.post("/quality/assess", status_code=status.HTTP_201_CREATED)
def assess_quality(
    payload: QualityAssessmentRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Evaluates multi-dimensional data quality scores across records."""
    metrics = DataQualityEvaluator.evaluate_records(
        records=payload.records,
        required_fields=payload.required_fields,
        unique_key=payload.unique_key,
        sla_seconds=payload.sla_seconds,
    )

    assessment = DataQualityAssessment(
        workspace_id=ws.id,
        domain=payload.domain.upper(),
        asset_name=payload.asset_name,
        completeness_score=metrics["completeness"],
        validity_score=metrics["validity"],
        timeliness_score=metrics["timeliness"],
        uniqueness_score=metrics["uniqueness"],
        overall_quality_score=metrics["overall_score"],
        violations=metrics["violations"],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {"status": "evaluated", "assessment": assessment, "metrics": metrics}


@router.get("/quality/metrics")
def list_quality_assessments(
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DataQualityAssessment).filter(DataQualityAssessment.workspace_id == ws.id)
    if domain:
        query = query.filter(DataQualityAssessment.domain == domain.upper())
    return {"assessments": query.order_by(DataQualityAssessment.evaluated_at.desc()).limit(50).all()}


# --- 6. Data Policies & Privacy Enforcement ---

@router.get("/policies")
def list_policies(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    policies = db.query(DataPolicyEnforcement).filter(DataPolicyEnforcement.workspace_id == ws.id).all()
    return {"policies": policies}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: PolicyCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    policy = DataPolicyEnforcement(
        workspace_id=ws.id,
        policy_name=payload.policy_name,
        target_domain=payload.target_domain.upper(),
        enforcement_action=payload.enforcement_action.upper(),
        field_name=payload.field_name,
        condition_expression=payload.condition_expression,
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"status": "created", "policy": policy}


# --- 7. Federated Access Query ---

@router.post("/federated-query")
def execute_federated_query(
    payload: FederatedQueryRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Executes a unified cross-domain query with automatic policy enforcement and relationship graph stitching."""
    dom = payload.domain.upper()
    ent_id = payload.entity_id

    # Simulated canonical record lookup
    canonical_record = {
        "id": ent_id,
        "domain": dom,
        "name": f"Enterprise Entity {ent_id}",
        "email": f"contact_{ent_id}@company.com",
        "phone": "+1-555-0199",
        "status": "ACTIVE",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Fetch and apply policies
    policies = db.query(DataPolicyEnforcement).filter(
        DataPolicyEnforcement.workspace_id == ws.id,
        DataPolicyEnforcement.is_active == True,
    ).all()
    policy_dicts = [
        {
            "target_domain": p.target_domain,
            "enforcement_action": p.enforcement_action,
            "field_name": p.field_name,
            "is_active": p.is_active,
        }
        for p in policies
    ]

    sanitized_record = DataPolicyEnforcer.enforce_policies(
        record=canonical_record,
        domain=dom,
        policies=policy_dicts,
        user_role="member",
    )

    # Subgraph
    related_graph = None
    if payload.include_related:
        router_engine = FederatedAccessRouter()
        relations = db.query(CrossDomainRelation).filter(CrossDomainRelation.workspace_id == ws.id).all()
        for r in relations:
            router_engine.register_relation(
                r.primary_domain,
                r.primary_entity_id,
                r.related_domain,
                r.related_entity_id,
                r.relationship_type,
                r.confidence_score,
            )
        related_graph = router_engine.build_cross_domain_subgraph(dom, ent_id, max_depth=payload.max_depth)

    return {
        "domain": dom,
        "entity_id": ent_id,
        "record": sanitized_record,
        "related_subgraph": related_graph,
        "policies_applied": len(policies),
    }
