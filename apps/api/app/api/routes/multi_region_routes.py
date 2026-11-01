"""
LeadNexus AI X — Multi-Region Global Architecture Routes
Phase 35 (ChatGPT Master Roadmap): Tenant Region Affinity, Failover & Split-Brain Prevention
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.user import User
from app.models.tenant import Workspace
from app.models.multi_region import (
    RegionNode,
    TenantRegionAffinity,
    FailoverExecutionJob,
    RegionalHealthHeartbeat,
)
from packages.multi_region import (
    global_split_brain_guard,
    global_traffic_router,
    global_failover_orchestrator,
    ReplicationLagThresholdExceededError,
    DataSovereigntyViolationError,
)

router = APIRouter(prefix="/multi-region", tags=["Multi-Region Global Architecture"])


# --- Schemas ---

class CreateRegionNodeRequest(BaseModel):
    id: str = Field(..., example="ap-southeast-2")
    name: str = Field(..., example="Asia Pacific (Sydney)")
    cloud_provider: str = Field(default="AWS", example="AWS")
    is_primary_write: bool = Field(default=False)
    latency_ms: float = Field(default=12.5)
    replication_lag_seconds: float = Field(default=0.05)


class UpdateTenantAffinityRequest(BaseModel):
    primary_region_id: str = Field(default="ap-southeast-2")
    failover_region_id: str = Field(default="ap-southeast-1")
    data_residency_requirement: str = Field(default="AU_ONLY", example="AU_ONLY")
    strict_sovereignty_enforced: bool = Field(default=True)


class InitiateFailoverRequest(BaseModel):
    source_region_id: str = Field(..., example="ap-southeast-2")
    target_region_id: str = Field(..., example="ap-southeast-1")
    job_type: str = Field(default="PLANNED_FAILOVER", example="PLANNED_FAILOVER")
    max_allowed_lag_s: float = Field(default=1.0, ge=0.1, le=10.0)


class RouteDecisionRequest(BaseModel):
    method: str = Field(default="POST", example="POST")
    client_country: Optional[str] = Field(default="AU", example="AU")


class HeartbeatRequest(BaseModel):
    region_id: str
    database_replica_status: str = "HEALTHY"
    replication_lag_bytes: int = 0
    replication_lag_seconds: float = 0.05
    queue_depth: int = 0
    p99_latency_ms: float = 22.0
    error_rate_pct: float = 0.0


# --- Endpoints ---

@router.get("/nodes")
def list_region_nodes(db: Session = Depends(get_sync_db)):
    """
    Lists all active regional nodes and identifies the single authorized write primary.
    """
    nodes = db.query(RegionNode).all()
    if not nodes:
        # Seed default Sydney and Singapore nodes if empty
        node_sydney = RegionNode(
            id="ap-southeast-2",
            name="Asia Pacific (Sydney)",
            cloud_provider="AWS",
            status="ACTIVE",
            is_primary_write=True,
            latency_ms=11.2,
            replication_lag_seconds=0.0,
        )
        node_singapore = RegionNode(
            id="ap-southeast-1",
            name="Asia Pacific (Singapore)",
            cloud_provider="AWS",
            status="ACTIVE",
            is_primary_write=False,
            latency_ms=78.5,
            replication_lag_seconds=0.08,
        )
        db.add_all([node_sydney, node_singapore])
        db.commit()
        nodes = [node_sydney, node_singapore]

    return [
        {
            "id": n.id,
            "name": n.name,
            "cloud_provider": n.cloud_provider,
            "status": n.status,
            "is_primary_write": n.is_primary_write,
            "latency_ms": n.latency_ms,
            "replication_lag_seconds": n.replication_lag_seconds,
            "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
        }
        for n in nodes
    ]


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_or_update_node(
    req: CreateRegionNodeRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """
    Registers a new cloud region node.
    """
    node = db.query(RegionNode).filter(RegionNode.id == req.id).first()
    if not node:
        node = RegionNode(
            id=req.id,
            name=req.name,
            cloud_provider=req.cloud_provider,
            is_primary_write=req.is_primary_write,
            latency_ms=req.latency_ms,
            replication_lag_seconds=req.replication_lag_seconds,
        )
        db.add(node)
    else:
        node.name = req.name
        node.cloud_provider = req.cloud_provider
        node.latency_ms = req.latency_ms
        node.replication_lag_seconds = req.replication_lag_seconds

    db.commit()
    db.refresh(node)
    return {"message": "Node saved successfully", "id": node.id}


@router.get("/tenant-affinity")
def get_tenant_affinity(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Retrieves the tenant's regional binding and data sovereignty policy.
    """
    affinity = db.query(TenantRegionAffinity).filter(
        TenantRegionAffinity.tenant_id == workspace.id
    ).first()

    if not affinity:
        affinity = TenantRegionAffinity(
            tenant_id=workspace.id,
            primary_region_id="ap-southeast-2",
            failover_region_id="ap-southeast-1",
            data_residency_requirement="AU_ONLY",
            strict_sovereignty_enforced=True,
        )
        db.add(affinity)
        db.commit()
        db.refresh(affinity)

    return {
        "tenant_id": affinity.tenant_id,
        "primary_region_id": affinity.primary_region_id,
        "failover_region_id": affinity.failover_region_id,
        "data_residency_requirement": affinity.data_residency_requirement,
        "strict_sovereignty_enforced": affinity.strict_sovereignty_enforced,
    }


@router.put("/tenant-affinity")
def update_tenant_affinity(
    req: UpdateTenantAffinityRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Updates data residency requirements (e.g. AU_ONLY for Australian Privacy Principles).
    """
    affinity = db.query(TenantRegionAffinity).filter(
        TenantRegionAffinity.tenant_id == workspace.id
    ).first()

    if not affinity:
        affinity = TenantRegionAffinity(tenant_id=workspace.id)
        db.add(affinity)

    affinity.primary_region_id = req.primary_region_id
    affinity.failover_region_id = req.failover_region_id
    affinity.data_residency_requirement = req.data_residency_requirement
    affinity.strict_sovereignty_enforced = req.strict_sovereignty_enforced

    db.commit()
    return {"message": "Tenant region affinity updated successfully"}


@router.post("/failover")
def execute_failover_cutover(
    req: InitiateFailoverRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """
    Executes an audited failover or failback with pre-flight replication lag verification.
    """
    try:
        job = global_failover_orchestrator.execute_failover(
            db=db,
            source_region_id=req.source_region_id,
            target_region_id=req.target_region_id,
            initiated_by=str(user.id),
            job_type=req.job_type,
            max_allowed_lag_s=req.max_allowed_lag_s,
        )
        return {
            "job_id": job.id,
            "status": job.status,
            "job_type": job.job_type,
            "source_region_id": job.source_region_id,
            "target_region_id": job.target_region_id,
            "split_brain_fence_token": job.split_brain_fence_token,
            "duration_seconds": job.duration_seconds,
        }
    except ReplicationLagThresholdExceededError as lag_err:
        raise HTTPException(status_code=412, detail=str(lag_err))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/routing-decision")
def evaluate_routing_decision(
    req: RouteDecisionRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Simulates global traffic router resolution for reads vs writes and checks data residency.
    """
    affinity = db.query(TenantRegionAffinity).filter(
        TenantRegionAffinity.tenant_id == workspace.id
    ).first()
    aff_dict = {
        "primary_region_id": affinity.primary_region_id if affinity else "ap-southeast-2",
        "failover_region_id": affinity.failover_region_id if affinity else "ap-southeast-1",
        "data_residency_requirement": affinity.data_residency_requirement if affinity else "AU_ONLY",
        "strict_sovereignty_enforced": affinity.strict_sovereignty_enforced if affinity else True,
    }

    try:
        target, meta = global_traffic_router.resolve_target_region(
            method=req.method,
            tenant_affinity=aff_dict,
            client_country=req.client_country,
        )
        return {
            "target_region_id": target,
            "route_type": meta["route_type"],
            "is_write": meta["is_write"],
            "fencing_token": meta["fencing_token"],
            "sovereignty_compliant": True,
        }
    except DataSovereigntyViolationError as sov_err:
        return {
            "target_region_id": None,
            "error": str(sov_err),
            "sovereignty_compliant": False,
        }


@router.post("/heartbeat")
def post_heartbeat(
    req: HeartbeatRequest,
    db: Session = Depends(get_sync_db),
):
    """
    Ingests heartbeat telemetry from a regional database replica.
    """
    hb = RegionalHealthHeartbeat(
        region_id=req.region_id,
        database_replica_status=req.database_replica_status,
        replication_lag_bytes=req.replication_lag_bytes,
        replication_lag_seconds=req.replication_lag_seconds,
        queue_depth=req.queue_depth,
        p99_latency_ms=req.p99_latency_ms,
        error_rate_pct=req.error_rate_pct,
    )
    db.add(hb)

    node = db.query(RegionNode).filter(RegionNode.id == req.region_id).first()
    if node:
        node.replication_lag_seconds = req.replication_lag_seconds
        node.latency_ms = req.p99_latency_ms

    db.commit()
    return {"message": "Heartbeat recorded successfully"}
