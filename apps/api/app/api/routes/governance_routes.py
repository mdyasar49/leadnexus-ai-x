"""
LeadNexus AI X - Phase 29: Enterprise Governance, Policy Engine, Data Contracts & Compliance Routes
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.governance import (
    ContractEnforcementMode,
    DataContract,
    DataContractViolation,
    GovernancePolicy,
    LegalHold,
    PolicyEffect,
    PolicyEvaluationEvent,
    PolicyType,
    SuppressionRecord,
    SuppressionType,
    TenantQuota,
)
from packages.governance.data_contract_engine import DataContractEngine
from packages.governance.field_masking_service import FieldMaskingService
from packages.governance.policy_engine import (
    PolicyContext,
    PolicyEngine,
    PolicyEvaluationResult,
)
from packages.governance.suppression_and_legal_hold_service import (
    SuppressionAndLegalHoldService,
)
from packages.governance.tenant_quota_service import TenantQuotaService

router = APIRouter(prefix="/api/v1/governance", tags=["Enterprise Governance & Data Contracts"])


# --- Schemas ---

class CreatePolicyRequest(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None
    policy_type: str = Field(default="ACCESS")
    effect: str = Field(default="DENY")
    rules_dsl: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100)


class EvaluatePolicyRequest(BaseModel):
    action: str
    resource_type: str
    resource_data: Dict[str, Any] = Field(default_factory=dict)
    actor_roles: List[str] = Field(default_factory=list)


class MaskRecordRequest(BaseModel):
    record: Dict[str, Any]
    fields_to_mask: Optional[List[str]] = None


class CreateContractRequest(BaseModel):
    id: str
    name: str
    entity_type: str
    version: str = "1.0.0"
    schema_definition: Dict[str, Any]
    sla_freshness_hours: int = 72
    min_completeness_score: float = 0.70
    enforcement_mode: str = "STRICT_REJECT"


class ValidatePayloadRequest(BaseModel):
    contract_id: str
    payload: Dict[str, Any]


class CreateSuppressionRequest(BaseModel):
    suppression_type: str = Field(default="DOMAIN")
    pattern: str = Field(..., min_length=2)
    reason: str = Field(..., min_length=2)


class CheckSuppressionRequest(BaseModel):
    suppression_type: str
    value: str


class PlaceLegalHoldRequest(BaseModel):
    name: str
    target_entity_type: str
    case_reference: str
    target_entity_id: Optional[str] = None
    notes: Optional[str] = None


class UpdateQuotaRequest(BaseModel):
    max_daily_research_budget_usd: Optional[float] = None
    max_concurrent_runs: Optional[int] = None
    max_monthly_exports: Optional[int] = None
    is_enforced: Optional[bool] = None


# --- Policies ---

@router.get("/policies")
def list_policies(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    policies = db.query(GovernancePolicy).filter(GovernancePolicy.workspace_id == workspace.id).all()
    return {"policies": policies}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_policy(
    req: CreatePolicyRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    policy = GovernancePolicy(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name=req.name,
        description=req.description,
        policy_type=req.policy_type,
        effect=req.effect,
        rules_dsl=req.rules_dsl,
        priority=req.priority,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"policy": policy}


@router.post("/policies/evaluate")
def evaluate_policies(
    req: EvaluatePolicyRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    policies = db.query(GovernancePolicy).filter(
        GovernancePolicy.workspace_id == workspace.id,
        GovernancePolicy.is_active == True,
    ).all()
    policies_dicts = [p.__dict__ for p in policies]

    ctx = PolicyContext(
        workspace_id=workspace.id,
        actor_id=user.id,
        actor_roles=req.actor_roles or ["MEMBER"],
        action=req.action,
        resource_type=req.resource_type,
        resource_data=req.resource_data,
    )

    result = PolicyEngine.evaluate(policies_dicts, ctx)

    # Log evaluation event
    event = PolicyEvaluationEvent(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        policy_id=result.matched_policy_id,
        action=req.action,
        actor_id=user.id,
        resource_type=req.resource_type,
        decision=result.decision.value,
        matched_rule=result.matched_rule_name,
        evaluated_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    return {
        "decision": result.decision.value,
        "matched_policy_id": result.matched_policy_id,
        "matched_rule_name": result.matched_rule_name,
        "reason": result.reason,
    }


# --- Field Masking ---

@router.post("/mask")
def mask_record(
    req: MaskRecordRequest,
    user: User = Depends(get_current_user),
):
    masked = FieldMaskingService.mask_record(req.record, req.fields_to_mask)
    return {"masked_record": masked}


# --- Data Contracts ---

@router.get("/contracts")
def list_data_contracts(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    contracts = db.query(DataContract).filter(DataContract.workspace_id == workspace.id).all()
    return {"contracts": contracts}


@router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_data_contract(
    req: CreateContractRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    contract = DataContract(
        id=req.id,
        workspace_id=workspace.id,
        name=req.name,
        entity_type=req.entity_type,
        version=req.version,
        schema_definition=req.schema_definition,
        sla_freshness_hours=req.sla_freshness_hours,
        min_completeness_score=req.min_completeness_score,
        enforcement_mode=req.enforcement_mode,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return {"contract": contract}


@router.post("/contracts/validate")
def validate_contract_payload(
    req: ValidatePayloadRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    contract = db.query(DataContract).filter(
        DataContract.id == req.contract_id,
        DataContract.workspace_id == workspace.id,
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail=f"Data contract '{req.contract_id}' not found.")

    res = DataContractEngine.validate_payload(req.payload, contract.__dict__)

    if not res.is_valid:
        # Record violation in DB
        violation = DataContractViolation(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            workspace_id=workspace.id,
            producer_id=user.id,
            violation_type="CONTRACT_VALIDATION_FAILURE",
            details={"violations": res.violations, "completeness": res.completeness_score},
            detected_at=datetime.now(timezone.utc),
        )
        db.add(violation)
        db.commit()

    return {
        "is_valid": res.is_valid,
        "is_accepted": res.is_accepted,
        "completeness_score": res.completeness_score,
        "violations": res.violations,
        "freshness_hours": res.freshness_hours,
    }


# --- Suppressions ---

@router.get("/suppressions")
def list_suppressions(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    records = db.query(SuppressionRecord).filter(SuppressionRecord.workspace_id == workspace.id).all()
    return {"suppressions": records}


@router.post("/suppressions", status_code=status.HTTP_201_CREATED)
def add_suppression(
    req: CreateSuppressionRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = SuppressionAndLegalHoldService(db)
    rec = service.add_suppression(
        workspace_id=workspace.id,
        suppression_type=SuppressionType(req.suppression_type) if req.suppression_type in [t.value for t in SuppressionType] else SuppressionType.DOMAIN,
        pattern=req.pattern,
        reason=req.reason,
        created_by=user.id,
    )
    return {"suppression": rec}


@router.post("/suppressions/check")
def check_suppression(
    req: CheckSuppressionRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = SuppressionAndLegalHoldService(db)
    is_suppressed, reason = service.is_suppressed(
        workspace_id=workspace.id,
        suppression_type=req.suppression_type,
        value=req.value,
    )
    return {"is_suppressed": is_suppressed, "reason": reason}


# --- Legal Holds ---

@router.get("/legal-holds")
def list_legal_holds(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    holds = db.query(LegalHold).filter(LegalHold.workspace_id == workspace.id).all()
    return {"legal_holds": holds}


@router.post("/legal-holds", status_code=status.HTTP_201_CREATED)
def place_legal_hold(
    req: PlaceLegalHoldRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = SuppressionAndLegalHoldService(db)
    hold = service.place_legal_hold(
        workspace_id=workspace.id,
        name=req.name,
        target_entity_type=req.target_entity_type,
        case_reference=req.case_reference,
        target_entity_id=req.target_entity_id,
        notes=req.notes,
        placed_by=user.id,
    )
    return {"legal_hold": hold}


@router.post("/legal-holds/{hold_id}/release")
def release_legal_hold(
    hold_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = SuppressionAndLegalHoldService(db)
    hold = service.release_legal_hold(hold_id)
    if not hold:
        raise HTTPException(status_code=404, detail="Legal hold not found.")
    return {"legal_hold": hold, "status": "RELEASED"}


# --- Tenant Quotas ---

@router.get("/quotas")
def get_quota(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = TenantQuotaService(db)
    quota = service.get_or_create_quota(workspace.id)
    return {"quota": quota}


@router.patch("/quotas")
def update_quota(
    req: UpdateQuotaRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = TenantQuotaService(db)
    quota = service.get_or_create_quota(workspace.id)
    if req.max_daily_research_budget_usd is not None:
        quota.max_daily_research_budget_usd = req.max_daily_research_budget_usd
    if req.max_concurrent_runs is not None:
        quota.max_concurrent_runs = req.max_concurrent_runs
    if req.max_monthly_exports is not None:
        quota.max_monthly_exports = req.max_monthly_exports
    if req.is_enforced is not None:
        quota.is_enforced = req.is_enforced

    quota.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(quota)
    return {"quota": quota}

