"""
LeadNexus AI X - Phase 43: Autonomous Orchestration API Routes
Provides endpoints for mission creation, DAG execution, checkpoint management,
worker pool telemetry, and human-in-the-loop review approvals.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.autonomous_orchestration import (
    MissionRecord,
    MissionStepRecord,
    MissionCheckpoint,
    MissionHumanReviewItem,
)
from packages.orchestration import (
    DAGScheduler,
    DAGStep,
    CycleDetectedError,
    WorkerPool,
    TaskPriority,
    MissionEngine,
    MissionStatus,
    StepStatus,
)

router = APIRouter(prefix="/orchestration", tags=["Autonomous Orchestration & Missions"])

# Singleton engine instance for in-memory execution and state
global_mission_engine = MissionEngine(max_concurrency=8)


# Pydantic Schemas
class CreateStepSchema(BaseModel):
    step_id: str = Field(..., description="Unique step identifier within the mission DAG")
    name: str = Field(..., description="Human-readable step name")
    agent_type: str = Field(..., description="Specialized agent class to execute this step")
    dependencies: List[str] = Field(default_factory=list, description="IDs of prerequisite steps")
    max_retries: int = Field(default=3, ge=0, le=10)
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    requires_human_review: bool = Field(default=False)


class CreateMissionRequest(BaseModel):
    name: str = Field(..., description="Mission title (e.g. EMEA Fintech Discovery)")
    goal: str = Field(..., description="High-level autonomous objective")
    steps: List[CreateStepSchema] = Field(..., min_length=1)
    priority: str = Field(default="NORMAL")
    configuration: Dict[str, Any] = Field(default_factory=dict)


class HumanDecisionRequest(BaseModel):
    decision: str = Field(..., description="APPROVED, REJECTED, or MODIFIED")
    modified_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class RollbackRequest(BaseModel):
    checkpoint_id: str = Field(..., description="Target checkpoint snapshot ID to restore")


@router.get("/health")
def get_orchestration_health():
    """Returns engine status, worker slots, queue depth, and active missions."""
    return {
        "status": "HEALTHY",
        "active_missions_count": len(global_mission_engine.active_missions),
        "worker_pool": {
            "max_concurrency": global_mission_engine.worker_pool.max_concurrency,
            "active_workers": global_mission_engine.worker_pool.active_worker_count,
            "available_slots": global_mission_engine.worker_pool.available_slots,
            "queue_depth": global_mission_engine.worker_pool.queue_depth,
        },
    }


@router.post("/missions")
def create_mission(
    request: CreateMissionRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Creates a new durable autonomous mission and validates its DAG."""
    dag_steps = [
        DAGStep(
            step_id=s.step_id,
            name=s.name,
            agent_type=s.agent_type,
            dependencies=s.dependencies,
            max_retries=s.max_retries,
            input_payload=s.input_payload,
            requires_human_review=s.requires_human_review,
        )
        for s in request.steps
    ]

    try:
        priority_enum = TaskPriority(request.priority.upper())
    except ValueError:
        priority_enum = TaskPriority.NORMAL

    mission_id = str(uuid.uuid4())

    try:
        instance = global_mission_engine.create_mission(
            name=request.name,
            goal=request.goal,
            steps=dag_steps,
            priority=priority_enum,
            configuration=request.configuration,
            mission_id=mission_id,
        )
    except CycleDetectedError as e:
        raise HTTPException(status_code=400, detail=f"DAG validation failed: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Persist in DB
    mission_rec = MissionRecord(
        id=mission_id,
        workspace_id=workspace.id,
        name=request.name,
        goal=request.goal,
        status="CREATED",
        priority=priority_enum.value,
        total_steps=len(dag_steps),
        configuration=request.configuration,
    )
    db.add(mission_rec)

    for s in request.steps:
        db.add(
            MissionStepRecord(
                id=str(uuid.uuid4()),
                mission_id=mission_id,
                step_name=s.name,
                agent_type=s.agent_type,
                status="PENDING",
                dependencies=s.dependencies,
                max_retries=s.max_retries,
                input_payload=s.input_payload,
            )
        )

    db.commit()
    db.refresh(mission_rec)

    return {
        "mission": mission_rec.to_dict(),
        "dag_validation": "VALID_DAG",
        "instance": instance.to_dict(),
    }


@router.get("/missions")
def list_missions(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists autonomous missions for the current workspace."""
    query = db.query(MissionRecord).filter(MissionRecord.workspace_id == workspace.id)
    if status_filter:
        query = query.filter(MissionRecord.status == status_filter.upper())

    missions = query.order_by(MissionRecord.created_at.desc()).limit(100).all()
    return {"missions": [m.to_dict() for m in missions], "count": len(missions)}


@router.get("/missions/{mission_id}")
def get_mission_details(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves full mission progress, DAG node statuses, checkpoints, and reviews."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    live_instance = global_mission_engine.active_missions.get(mission_id)
    steps = db.query(MissionStepRecord).filter(MissionStepRecord.mission_id == mission_id).all()
    checkpoints = db.query(MissionCheckpoint).filter(MissionCheckpoint.mission_id == mission_id).all()
    reviews = db.query(MissionHumanReviewItem).filter(MissionHumanReviewItem.mission_id == mission_id).all()

    res = mission_rec.to_dict()
    res["steps"] = [s.to_dict() for s in steps]
    res["checkpoints_count"] = len(checkpoints)
    res["reviews_count"] = len(reviews)
    if live_instance:
        res["live_status"] = live_instance.to_dict()

    return res


@router.post("/missions/{mission_id}/start")
def start_mission(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Starts or advances an existing mission."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    if mission_id not in global_mission_engine.active_missions:
        raise HTTPException(status_code=400, detail="Mission instance not active in memory")

    instance = global_mission_engine.start_mission(mission_id)
    mission_rec.status = instance.status.value
    db.commit()

    return {"mission_id": mission_id, "status": instance.status.value, "instance": instance.to_dict()}


@router.post("/missions/{mission_id}/pause")
def pause_mission(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Pauses mission execution and creates an immediate snapshot."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    instance = global_mission_engine.pause_mission(mission_id)
    mission_rec.status = instance.status.value
    db.commit()

    return {"mission_id": mission_id, "status": instance.status.value, "instance": instance.to_dict()}


@router.post("/missions/{mission_id}/resume")
def resume_mission(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Resumes execution from paused state."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    instance = global_mission_engine.resume_mission(mission_id)
    mission_rec.status = instance.status.value
    db.commit()

    return {"mission_id": mission_id, "status": instance.status.value, "instance": instance.to_dict()}


@router.post("/missions/{mission_id}/cancel")
def cancel_mission(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Cancels mission execution."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    instance = global_mission_engine.cancel_mission(mission_id)
    mission_rec.status = instance.status.value
    db.commit()

    return {"mission_id": mission_id, "status": instance.status.value, "instance": instance.to_dict()}


@router.get("/missions/{mission_id}/checkpoints")
def get_mission_checkpoints(
    mission_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Returns chronological checkpoint history for a mission."""
    checkpoints = global_mission_engine.checkpoint_manager.get_history(mission_id)
    return {
        "mission_id": mission_id,
        "checkpoints": [c.to_dict() for c in checkpoints],
        "count": len(checkpoints),
    }


@router.post("/missions/{mission_id}/rollback")
def rollback_mission(
    mission_id: str,
    request: RollbackRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Restores mission DAG to state captured in a historical checkpoint."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    try:
        instance = global_mission_engine.rollback_to_checkpoint(mission_id, request.checkpoint_id)
        mission_rec.status = instance.status.value
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"mission_id": mission_id, "status": instance.status.value, "instance": instance.to_dict()}


@router.get("/missions/{mission_id}/reviews")
def get_pending_reviews(
    mission_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Returns pending human-in-the-loop review items for a mission."""
    instance = global_mission_engine.active_missions.get(mission_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Mission instance not found")

    return {
        "mission_id": mission_id,
        "pending_reviews": list(instance.pending_human_reviews.values()),
        "count": len(instance.pending_human_reviews),
    }


@router.post("/missions/{mission_id}/reviews/{step_id}/decide")
def submit_human_decision(
    mission_id: str,
    step_id: str,
    request: HumanDecisionRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Submits human verification or modification decision, unblocking execution."""
    mission_rec = db.query(MissionRecord).filter(
        MissionRecord.id == mission_id,
        MissionRecord.workspace_id == workspace.id,
    ).first()
    if not mission_rec:
        raise HTTPException(status_code=404, detail="Mission not found")

    try:
        instance = global_mission_engine.submit_human_decision(
            mission_id=mission_id,
            step_id=step_id,
            decision=request.decision.upper(),
            modified_data=request.modified_data,
            notes=request.notes,
        )
        mission_rec.status = instance.status.value
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "mission_id": mission_id,
        "step_id": step_id,
        "status": instance.status.value,
        "instance": instance.to_dict(),
    }

