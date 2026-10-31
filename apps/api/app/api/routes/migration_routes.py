"""
LeadNexus AI X - Phase 33: Enterprise Data Migration & Zero-Downtime Upgrade Routes
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.migration import (
    APIVersionContract,
    BackfillJob,
    BackfillStatus,
    MigrationPhase,
    ReconciliationJob,
    ReconciliationStatus,
    SchemaMigrationPlan,
)
from packages.migration.api_versioning_manager import (
    APIVersioningManager,
)
from packages.migration.chunked_backfill_engine import (
    ChunkedBackfillEngine,
)
from packages.migration.data_reconciliation_engine import (
    DataReconciliationEngine,
)
from packages.migration.expand_contract_orchestrator import (
    ExpandContractOrchestrator,
)

router = APIRouter(prefix="/api/v1/migrations", tags=["Enterprise Data Migration & Zero-Downtime"])


# --- Schemas ---

class CreateMigrationPlanRequest(BaseModel):
    id: str
    name: str
    source_version: str
    target_version: str
    plan_definition: Dict[str, Any] = Field(default_factory=dict)


class AdvancePhaseRequest(BaseModel):
    target_phase: str
    reconciliation_parity_pct: Optional[float] = None


class RollbackPlanRequest(BaseModel):
    reason: str


class InitBackfillRequest(BaseModel):
    migration_plan_id: str
    table_name: str
    total_records: int
    chunk_size: int = 500


class RunReconciliationRequest(BaseModel):
    migration_plan_id: str
    table_name: str
    source_column: str
    target_column: str
    sample_records: List[Dict[str, Any]]


class RegisterAPIVersionRequest(BaseModel):
    api_version: str
    is_deprecated: bool = False
    sunset_date: Optional[datetime] = None
    breaking_changes: List[str] = Field(default_factory=list)
    min_supported_client: str = "1.0.0"


# --- Plans ---

@router.get("/plans")
def list_migration_plans(db: Session = Depends(get_sync_db)):
    plans = db.query(SchemaMigrationPlan).order_by(SchemaMigrationPlan.created_at.desc()).all()
    return {"migration_plans": plans}


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_migration_plan(
    req: CreateMigrationPlanRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    orchestrator = ExpandContractOrchestrator(db)
    plan = orchestrator.create_plan(
        plan_id=req.id,
        name=req.name,
        source_version=req.source_version,
        target_version=req.target_version,
        plan_definition=req.plan_definition,
    )
    return {"migration_plan": plan}


@router.post("/plans/{plan_id}/advance")
def advance_migration_phase(
    plan_id: str,
    req: AdvancePhaseRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    orchestrator = ExpandContractOrchestrator(db)
    target_phase = MigrationPhase(req.target_phase) if req.target_phase in [p.value for p in MigrationPhase] else MigrationPhase.EXPANDING
    ok, plan, err = orchestrator.advance_phase(
        plan_id=plan_id,
        target_phase=target_phase,
        reconciliation_parity_pct=req.reconciliation_parity_pct,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"migration_plan": plan, "phase": plan.phase}


@router.post("/plans/{plan_id}/rollback")
def rollback_migration_plan(
    plan_id: str,
    req: RollbackPlanRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    orchestrator = ExpandContractOrchestrator(db)
    plan = orchestrator.rollback(plan_id, req.reason)
    return {"migration_plan": plan, "status": "ROLLED_BACK"}


# --- Backfills ---

@router.get("/backfills")
def list_backfills(db: Session = Depends(get_sync_db)):
    jobs = db.query(BackfillJob).order_by(BackfillJob.started_at.desc()).all()
    return {"backfill_jobs": jobs}


@router.post("/backfills/initialize", status_code=status.HTTP_201_CREATED)
def initialize_backfill(
    req: InitBackfillRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    engine = ChunkedBackfillEngine(db)
    job = engine.initialize_job(
        migration_plan_id=req.migration_plan_id,
        table_name=req.table_name,
        total_records=req.total_records,
        chunk_size=req.chunk_size,
    )
    return {"backfill_job": job}


# --- Reconciliations ---

@router.get("/reconciliations")
def list_reconciliations(db: Session = Depends(get_sync_db)):
    jobs = db.query(ReconciliationJob).order_by(ReconciliationJob.completed_at.desc()).all()
    return {"reconciliation_jobs": jobs}


@router.post("/reconciliations/run")
def run_reconciliation(
    req: RunReconciliationRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    engine = DataReconciliationEngine(db)
    job = engine.reconcile_columns(
        migration_plan_id=req.migration_plan_id,
        table_name=req.table_name,
        source_column=req.source_column,
        target_column=req.target_column,
        records=req.sample_records,
    )
    return {"reconciliation_job": job}


# --- API Versions ---

@router.get("/api-versions")
def list_api_versions(db: Session = Depends(get_sync_db)):
    versions = db.query(APIVersionContract).all()
    return {"api_versions": versions}


@router.post("/api-versions", status_code=status.HTTP_201_CREATED)
def register_api_version(
    req: RegisterAPIVersionRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    mgr = APIVersioningManager(db)
    contract = mgr.register_version(
        api_version=req.api_version,
        is_deprecated=req.is_deprecated,
        sunset_date=req.sunset_date,
        breaking_changes=req.breaking_changes,
        min_supported_client=req.min_supported_client,
    )
    return {"api_version_contract": contract}
