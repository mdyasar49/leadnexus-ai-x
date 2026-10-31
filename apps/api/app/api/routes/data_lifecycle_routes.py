"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle, Archival, Retention & Backup Governance Routes
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

from app.models.data_lifecycle import (
    ArchivePackage,
    ArchiveStatus,
    ArchiveTombstone,
    DataRetentionPolicy,
    LifecycleTransitionEvent,
    StorageTier,
)
from packages.data_lifecycle.archival_package_service import (
    ArchivalPackageService,
)
from packages.data_lifecycle.ephemeral_ai_cache_cleaner import (
    EphemeralAICacheCleaner,
)
from packages.data_lifecycle.retention_policy_engine import (
    RetentionPolicyEngine,
)
from packages.data_lifecycle.staging_restoration_service import (
    StagingRestorationService,
)

router = APIRouter(prefix="/api/v1/lifecycle", tags=["Enterprise Data Lifecycle & Archival"])


# --- Schemas ---

class CreateRetentionPolicyRequest(BaseModel):
    entity_type: str
    retention_days: int = 90
    target_tier: str = "ARCHIVED"


class CreateArchivePackageRequest(BaseModel):
    package_name: str
    entity_type: str
    records: List[Dict[str, Any]]


class RestoreRecordRequest(BaseModel):
    entity_id: str


class PurgeAICacheRequest(BaseModel):
    ttl_days: int = 14


# --- Retention Policies ---

@router.get("/policies")
def list_retention_policies(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    policies = db.query(DataRetentionPolicy).filter(
        DataRetentionPolicy.workspace_id == workspace.id
    ).all()
    return {"retention_policies": policies}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_retention_policy(
    req: CreateRetentionPolicyRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    policy = DataRetentionPolicy(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        entity_type=req.entity_type,
        retention_days=req.retention_days,
        target_tier=req.target_tier,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"policy": policy}


# --- Archive Packages ---

@router.get("/packages")
def list_archive_packages(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    packages = db.query(ArchivePackage).filter(
        ArchivePackage.workspace_id == workspace.id
    ).order_by(ArchivePackage.created_at.desc()).all()
    return {"packages": packages}


@router.post("/packages/create", status_code=status.HTTP_201_CREATED)
def create_archive_package(
    req: CreateArchivePackageRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    svc = ArchivalPackageService(db)
    pkg, tombstones = svc.create_archive_package(
        workspace_id=workspace.id,
        package_name=req.package_name,
        entity_type=req.entity_type,
        records=req.records,
    )
    return {
        "package": {
            "id": pkg.id,
            "package_name": pkg.package_name,
            "records_count": pkg.records_count,
            "checksum_sha256": pkg.checksum_sha256,
            "storage_uri": pkg.storage_uri,
        },
        "tombstones_created": len(tombstones),
    }


@router.get("/packages/{package_id}/preview")
def preview_archive_package(
    package_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    svc = StagingRestorationService(db)
    preview = svc.preview_archive(package_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Archive package not found.")
    return {"archive_preview": preview}


@router.post("/packages/{package_id}/restore")
def restore_archived_entity(
    package_id: str,
    req: RestoreRecordRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    svc = StagingRestorationService(db)
    ok, record, err = svc.restore_record(workspace.id, package_id, req.entity_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"status": "RESTORED", "restored_entity": record}


# --- Tombstones ---

@router.get("/tombstones")
def list_tombstones(
    entity_type: Optional[str] = None,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    q = db.query(ArchiveTombstone).filter(ArchiveTombstone.workspace_id == workspace.id)
    if entity_type:
        q = q.filter(ArchiveTombstone.entity_type == entity_type)
    tombstones = q.limit(50).all()
    return {"tombstones": tombstones}


# --- AI Cache Cleaner ---

@router.post("/ai-cache/purge")
def purge_ai_cache(
    req: PurgeAICacheRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    cleaner = EphemeralAICacheCleaner(db)
    purged_messages = cleaner.purge_stale_conversation_turns(req.ttl_days)
    purged_chunks = cleaner.purge_transient_rag_chunks(req.ttl_days * 2)
    return {
        "status": "PURGED",
        "purged_messages_count": purged_messages,
        "purged_rag_chunks_count": purged_chunks,
    }
