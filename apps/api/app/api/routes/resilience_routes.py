"""
LeadNexus AI X - Phase 30: Enterprise Reliability, Resilience & Self-Healing Routes
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.resilience import (
    BackupSnapshot,
    BackupStatus,
    CircuitBreakerState,
    CircuitState,
    DeadLetterMessage,
    DLQStatus,
    IncidentSeverity,
    IncidentStatus,
    PlatformIncident,
    SelfHealingAction,
    TaskLease,
)
from packages.resilience.backup_and_disaster_recovery import (
    BackupAndDisasterRecoveryService,
)
from packages.resilience.circuit_breaker_service import CircuitBreakerService
from packages.resilience.dead_letter_queue_service import DeadLetterQueueService
from packages.resilience.distributed_lease_manager import DistributedLeaseManager
from packages.resilience.self_healing_engine import SelfHealingEngine

router = APIRouter(prefix="/api/v1/resilience", tags=["Enterprise Reliability & Resilience"])


# --- Schemas ---

class AcquireLeaseRequest(BaseModel):
    task_id: str
    worker_id: str
    ttl_seconds: int = 60


class RenewLeaseRequest(BaseModel):
    task_id: str
    worker_id: str
    fencing_token: int
    ttl_seconds: int = 60


class ReleaseLeaseRequest(BaseModel):
    task_id: str
    worker_id: str
    fencing_token: int


class QuarantineRequest(BaseModel):
    queue_name: str
    task_id: str
    payload: Dict[str, Any]
    error_message: str


class CreateBackupRequest(BaseModel):
    snapshot_name: str
    storage_path: str
    records_count: int
    data_content: str  # text data to encode as bytes


class CreateIncidentRequest(BaseModel):
    title: str
    severity: str = "MAJOR"
    affected_components: List[str] = Field(default_factory=list)
    root_cause: Optional[str] = None


class UpdateIncidentRequest(BaseModel):
    status: str
    root_cause: Optional[str] = None


# --- Probes ---

@router.get("/health/liveness")
def liveness_probe():
    return {"status": "LIVE", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/readiness")
def readiness_probe(db: Session = Depends(get_sync_db)):
    checks = {}
    is_ready = True

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "HEALTHY"
    except Exception as e:
        checks["database"] = f"DEGRADED: {str(e)}"
        is_ready = False

    # 2. Open Circuit Breakers
    open_circuits = db.query(CircuitBreakerState).filter(
        CircuitBreakerState.state == CircuitState.OPEN.value
    ).all()
    checks["open_circuits_count"] = len(open_circuits)
    if len(open_circuits) > 3:
        checks["circuit_breakers"] = "WARNING_MULTIPLE_SERVICES_DOWN"

    return {
        "status": "READY" if is_ready else "NOT_READY",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# --- Leases ---

@router.get("/leases")
def list_leases(db: Session = Depends(get_sync_db)):
    leases = db.query(TaskLease).filter(TaskLease.is_active == True).all()
    return {"active_leases": leases}


@router.post("/leases/acquire")
def acquire_lease(req: AcquireLeaseRequest, db: Session = Depends(get_sync_db)):
    mgr = DistributedLeaseManager(db)
    success, lease, err = mgr.acquire_lease(req.task_id, req.worker_id, req.ttl_seconds)
    if not success:
        raise HTTPException(status_code=409, detail=err)
    return {"lease": lease}


@router.post("/leases/renew")
def renew_lease(req: RenewLeaseRequest, db: Session = Depends(get_sync_db)):
    mgr = DistributedLeaseManager(db)
    success = mgr.renew_lease(req.task_id, req.worker_id, req.fencing_token, req.ttl_seconds)
    if not success:
        raise HTTPException(status_code=404, detail="Active lease not found or invalid token.")
    return {"status": "RENEWED"}


@router.post("/leases/release")
def release_lease(req: ReleaseLeaseRequest, db: Session = Depends(get_sync_db)):
    mgr = DistributedLeaseManager(db)
    success = mgr.release_lease(req.task_id, req.worker_id, req.fencing_token)
    if not success:
        raise HTTPException(status_code=404, detail="Active lease not found or invalid token.")
    return {"status": "RELEASED"}


# --- DLQ ---

@router.get("/dlq")
def list_quarantined_messages(
    queue_name: Optional[str] = None,
    db: Session = Depends(get_sync_db),
):
    dlq_svc = DeadLetterQueueService(db)
    messages = dlq_svc.list_quarantined(queue_name)
    return {"quarantined_messages": messages}


@router.post("/dlq/{dlq_id}/redrive")
def redrive_message(dlq_id: str, db: Session = Depends(get_sync_db)):
    dlq_svc = DeadLetterQueueService(db)
    msg = dlq_svc.redrive_message(dlq_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found in DLQ.")
    return {"message": msg, "status": "REDRIVEN"}


@router.post("/dlq/{dlq_id}/discard")
def discard_message(dlq_id: str, db: Session = Depends(get_sync_db)):
    dlq_svc = DeadLetterQueueService(db)
    msg = dlq_svc.discard_message(dlq_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found in DLQ.")
    return {"message": msg, "status": "DISCARDED"}


# --- Circuit Breakers ---

@router.get("/circuit-breakers")
def list_circuit_breakers(db: Session = Depends(get_sync_db)):
    cbs = db.query(CircuitBreakerState).all()
    return {"circuit_breakers": cbs}


@router.post("/circuit-breakers/{service_name}/reset")
def reset_circuit_breaker(service_name: str, db: Session = Depends(get_sync_db)):
    cb_svc = CircuitBreakerService(db)
    cb = cb_svc.record_success(service_name)
    return {"circuit_breaker": cb, "status": "RESET_TO_CLOSED"}


# --- Backups ---

@router.get("/backups")
def list_backups(db: Session = Depends(get_sync_db)):
    backups = db.query(BackupSnapshot).all()
    return {"backups": backups}


@router.post("/backups/create", status_code=status.HTTP_201_CREATED)
def create_backup_snapshot(req: CreateBackupRequest, db: Session = Depends(get_sync_db)):
    svc = BackupAndDisasterRecoveryService(db)
    data_bytes = req.data_content.encode("utf-8")
    snapshot = svc.create_snapshot(
        snapshot_name=req.snapshot_name,
        storage_path=req.storage_path,
        records_count=req.records_count,
        data_bytes=data_bytes,
    )
    return {"snapshot": snapshot}


# --- Self-Healing ---

@router.post("/self-healing/remediate")
def run_self_healing_remediation(db: Session = Depends(get_sync_db)):
    engine = SelfHealingEngine(db)
    actions = engine.execute_zombie_task_remediation()
    return {"remediation_actions_count": len(actions), "actions": actions}


# --- Incidents ---

@router.get("/incidents")
def list_incidents(db: Session = Depends(get_sync_db)):
    incidents = db.query(PlatformIncident).all()
    return {"incidents": incidents}


@router.post("/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(req: CreateIncidentRequest, db: Session = Depends(get_sync_db)):
    engine = SelfHealingEngine(db)
    inc = engine.create_incident(
        title=req.title,
        severity=IncidentSeverity(req.severity) if req.severity in [s.value for s in IncidentSeverity] else IncidentSeverity.MAJOR,
        affected_components=req.affected_components,
        root_cause=req.root_cause,
    )
    return {"incident": inc}


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: str, req: UpdateIncidentRequest, db: Session = Depends(get_sync_db)):
    engine = SelfHealingEngine(db)
    inc = engine.update_incident_status(
        incident_id=incident_id,
        status=IncidentStatus(req.status) if req.status in [s.value for s in IncidentStatus] else IncidentStatus.INVESTIGATING,
        root_cause=req.root_cause,
    )
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return {"incident": inc}

