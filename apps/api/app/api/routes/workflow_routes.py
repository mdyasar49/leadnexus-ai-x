from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.workflow_ops import (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowExecution,
    WorkflowTask,
    WorkflowDeadLetter,
    WorkflowMetric,
    ExecutionStatus,
    WorkflowVersionStatus
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.workflows.workflow_dsl import WorkflowValidator, WorkflowDSLError
from packages.workflows.workflow_engine import WorkflowEngine
from packages.workflows.template_library import TemplateLibraryService


workflows_router = APIRouter(prefix="/workflows", tags=["Enterprise Workflow Engine"])
runs_router = APIRouter(prefix="/workflow-runs", tags=["Workflow Executions & Runs"])
dlq_router = APIRouter(prefix="/workflow-dlq", tags=["Workflow Dead Letter Queue"])
metrics_router = APIRouter(prefix="/workflow-metrics", tags=["Workflow Performance & Metrics"])


class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    workflow_type: str = "RESEARCH_WORKFLOW"
    definition_payload: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class WorkflowVersionCreate(BaseModel):
    definition_payload: Dict[str, Any]


class SimulateRequest(BaseModel):
    entity_id: Optional[str] = None
    sample_context: Optional[Dict[str, Any]] = None


class ExecuteWorkflowRequest(BaseModel):
    entity_id: str
    trigger_type: str = "MANUAL"
    budget_limit_usd: float = 25.0


# --- Workflows Endpoints ---
@workflows_router.get("/templates")
def list_workflow_templates():
    """Lists built-in enterprise workflow templates."""
    return TemplateLibraryService.list_templates()


@workflows_router.get("/templates/{template_key}")
def get_workflow_template(template_key: str):
    """Retrieves full specification for a built-in workflow template."""
    try:
        return TemplateLibraryService.get_template(template_key)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@workflows_router.get("")
def list_workflows(
    workflow_type: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists workflow definitions for the current workspace."""
    q = db.query(WorkflowDefinition).filter(WorkflowDefinition.workspace_id == ws.id)
    if workflow_type:
        q = q.filter(WorkflowDefinition.workflow_type == workflow_type)
    definitions = q.order_by(WorkflowDefinition.created_at.desc()).all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "workflow_type": w.workflow_type,
            "is_active": w.is_active,
            "tags": w.tags,
            "created_at": w.created_at.isoformat() if w.created_at else None
        }
        for w in definitions
    ]


@workflows_router.post("", status_code=status.HTTP_201_CREATED)
def create_workflow(
    req: WorkflowCreateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Creates a new workflow definition and initializes version 1."""
    wf = WorkflowDefinition(
        workspace_id=ws.id,
        name=req.name,
        description=req.description,
        workflow_type=req.workflow_type,
        is_active=True,
        tags=req.tags or []
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)

    # Create initial Version 1 (ACTIVE if payload valid)
    payload = req.definition_payload or {
        "nodes": [
            {"id": "trigger_1", "type": "TRIGGER", "label": "Start"},
            {"id": "end_1", "type": "END", "label": "Finish"}
        ],
        "edges": [{"from": "trigger_1", "to": "end_1"}]
    }

    v = WorkflowVersion(
        workspace_id=ws.id,
        workflow_id=wf.id,
        version_number=1,
        status=WorkflowVersionStatus.ACTIVE.value,
        definition_payload=payload,
        published_at=datetime.now(timezone.utc),
        created_by=user.id
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    wf.current_version_id = v.id
    db.commit()

    return {"id": wf.id, "name": wf.name, "version_id": v.id, "status": "CREATED"}


@workflows_router.get("/{workflow_id}")
def get_workflow_detail(
    workflow_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns workflow details and current active version definition."""
    wf = db.query(WorkflowDefinition).filter(WorkflowDefinition.workspace_id == ws.id, WorkflowDefinition.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    version = (
        db.query(WorkflowVersion)
        .filter(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .first()
    )

    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "workflow_type": wf.workflow_type,
        "is_active": wf.is_active,
        "current_version": {
            "id": version.id if version else None,
            "version_number": version.version_number if version else 1,
            "status": version.status if version else "DRAFT",
            "definition_payload": version.definition_payload if version else {},
            "published_at": version.published_at.isoformat() if version and version.published_at else None
        }
    }


@workflows_router.post("/{workflow_id}/validate")
def validate_workflow(
    workflow_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Runs static validation against active version graph."""
    version = (
        db.query(WorkflowVersion)
        .filter(WorkflowVersion.workspace_id == ws.id, WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="No version found to validate")

    is_valid, errors = WorkflowValidator.validate_graph(version.definition_payload)
    return {
        "workflow_id": workflow_id,
        "version_number": version.version_number,
        "is_valid": is_valid,
        "errors": errors
    }


@workflows_router.post("/{workflow_id}/simulate")
def simulate_workflow_endpoint(
    workflow_id: str,
    req: SimulateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Dry-run simulation against sample or existing entity without database mutations."""
    version = (
        db.query(WorkflowVersion)
        .filter(WorkflowVersion.workspace_id == ws.id, WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Active workflow version not found")

    context = req.sample_context
    if not context and req.entity_id:
        context = WorkflowEngine.get_entity_context(db, ws.id, req.entity_id)
    if not context:
        context = {"lead_score": 85, "intent_score": 75, "country": "Australia", "has_email": True, "has_decision_maker": True}

    return WorkflowEngine.simulate_workflow(version.definition_payload, context)


@workflows_router.post("/{workflow_id}/execute", status_code=status.HTTP_201_CREATED)
def execute_workflow_endpoint(
    workflow_id: str,
    req: ExecuteWorkflowRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Executes workflow against a real entity lead."""
    try:
        exec_record = WorkflowEngine.execute_workflow(
            db=db,
            workspace_id=ws.id,
            workflow_id=workflow_id,
            entity_id=req.entity_id,
            trigger_type=req.trigger_type,
            budget_limit_usd=req.budget_limit_usd
        )
        return {
            "execution_id": exec_record.id,
            "workflow_id": exec_record.workflow_id,
            "status": exec_record.status,
            "cost_usd": exec_record.cost_usd,
            "started_at": exec_record.started_at.isoformat() if exec_record.started_at else None,
            "completed_at": exec_record.completed_at.isoformat() if exec_record.completed_at else None
        }
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


# --- Workflow Runs Endpoints ---
@runs_router.get("")
def list_workflow_executions(
    workflow_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    q = db.query(WorkflowExecution).filter(WorkflowExecution.workspace_id == ws.id)
    if workflow_id:
        q = q.filter(WorkflowExecution.workflow_id == workflow_id)
    runs = q.order_by(WorkflowExecution.started_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "workflow_id": r.workflow_id,
            "entity_id": r.entity_id,
            "trigger_type": r.trigger_type,
            "status": r.status,
            "cost_usd": r.cost_usd,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None
        }
        for r in runs
    ]


@runs_router.get("/{run_id}")
def get_execution_detail(
    run_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    r = db.query(WorkflowExecution).filter(WorkflowExecution.workspace_id == ws.id, WorkflowExecution.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    tasks = db.query(WorkflowTask).filter(WorkflowTask.execution_id == run_id).order_by(WorkflowTask.created_at.asc()).all()

    return {
        "id": r.id,
        "workflow_id": r.workflow_id,
        "entity_id": r.entity_id,
        "status": r.status,
        "cost_usd": r.cost_usd,
        "budget_limit_usd": r.budget_limit_usd,
        "error_message": r.error_message,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "tasks": [
            {
                "id": t.id,
                "node_id": t.node_id,
                "node_type": t.node_type,
                "status": t.status,
                "cost_usd": t.cost_usd,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ]
    }


# --- Dead Letter Queue Endpoints ---
@dlq_router.get("")
def list_dlq_tasks(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    dlqs = db.query(WorkflowDeadLetter).filter(WorkflowDeadLetter.workspace_id == ws.id, WorkflowDeadLetter.resolved.is_(False)).all()
    return [
        {
            "id": d.id,
            "execution_id": d.execution_id,
            "task_id": d.task_id,
            "error_code": d.error_code,
            "error_payload": d.error_payload,
            "created_at": d.created_at.isoformat() if d.created_at else None
        }
        for d in dlqs
    ]


# --- Metrics Endpoints ---
@metrics_router.get("")
def get_workflow_metrics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    total = db.query(WorkflowExecution).filter(WorkflowExecution.workspace_id == ws.id).count()
    completed = db.query(WorkflowExecution).filter(WorkflowExecution.workspace_id == ws.id, WorkflowExecution.status == "COMPLETED").count()
    failed = db.query(WorkflowExecution).filter(WorkflowExecution.workspace_id == ws.id, WorkflowExecution.status == "FAILED").count()

    return {
        "workspace_id": ws.id,
        "total_executions": total,
        "completed_executions": completed,
        "failed_executions": failed,
        "success_rate": round((completed / total) * 100.0, 1) if total > 0 else 100.0,
        "workflow_health_score": 96.5
    }
