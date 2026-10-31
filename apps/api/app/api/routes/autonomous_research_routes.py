import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.autonomous_research import (
    AutonomyPolicy,
    AutonomyPolicyVersion,
    ResearchPlan,
    ResearchPlanStep,
    AutonomousResearchRun,
    ResearchRunCheckpoint,
    ResearchReport,
    ResearchDeadLetter,
    ResearchEscalation,
    ResearchSimulation,
    ResearchMode,
    RunStatus,
    ToolRiskLevel,
    TaskType,
)

from packages.autonomous_research.policy_and_tool_registry import (
    AutonomyPolicyValidator,
    ToolRegistry,
)
from packages.autonomous_research.research_task_graph_engine import (
    ResearchTaskGraphEngine,
    CyclicDependencyError,
)
from packages.autonomous_research.source_selection_engine import (
    SourceSelectionEngine,
)
from packages.autonomous_research.simulation_and_sandbox_engine import (
    SimulationAndSandboxEngine,
)
from packages.autonomous_research.checkpoint_and_dlq_service import (
    CheckpointAndDLQService,
)
from packages.autonomous_research.research_report_engine import (
    ResearchReportEngine,
)
from packages.autonomous_research.autonomous_research_loop import (
    AutonomousResearchLoop,
)


autonomous_research_router = APIRouter(
    prefix="/autonomy",
    tags=["Enterprise Autonomous Research & Adaptive Automation Engine"]
)

_tool_registry = ToolRegistry()


# --- Request & Response Schemas ---

class PolicyCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    risk_level: str = ToolRiskLevel.LOW.value
    max_iterations: int = 10
    max_runtime_seconds: int = 300
    max_tool_calls: int = 50
    max_parallel_tasks: int = 5
    max_cost_budget: float = 10.0
    allowed_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)
    blocked_domains: List[str] = Field(default_factory=list)
    require_human_approval: bool = False
    is_active: bool = True


class PlanCreateRequest(BaseModel):
    title: str
    objective: str
    target_type: str = "COMPANY"
    target_name: str
    target_domain: Optional[str] = None
    mode: str = ResearchMode.STANDARD.value
    max_depth: int = 3
    policy_id: Optional[str] = None
    custom_steps: Optional[List[Dict[str, Any]]] = None


class RunStartRequest(BaseModel):
    company_name: str
    domain: Optional[str] = None
    mode: str = ResearchMode.STANDARD.value
    plan_id: Optional[str] = None
    policy_id: Optional[str] = None
    max_iterations: Optional[int] = 10


class DAGValidationRequest(BaseModel):
    steps: List[Dict[str, Any]]


class SimulationRequest(BaseModel):
    plan_id: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    policy_id: Optional[str] = None


class EscalationResolveRequest(BaseModel):
    decision: str  # "APPROVED", "REJECTED", "RESOLVED"
    notes: str


# --- Policy Endpoints ---

@autonomous_research_router.get("/policies")
def list_policies(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists autonomy policies configured for the workspace."""
    policies = (
        db.query(AutonomyPolicy)
        .filter(AutonomyPolicy.workspace_id == workspace.id)
        .order_by(desc(AutonomyPolicy.created_at))
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "risk_level": p.risk_level,
            "max_iterations": p.max_iterations,
            "max_runtime_seconds": p.max_runtime_seconds,
            "max_tool_calls": p.max_tool_calls,
            "max_cost_budget": p.max_cost_budget,
            "allowed_tools": p.allowed_tools or [],
            "forbidden_tools": p.forbidden_tools or [],
            "allowed_domains": p.allowed_domains or [],
            "blocked_domains": p.blocked_domains or [],
            "require_human_approval": p.require_human_approval,
            "is_active": p.is_active,
            "version": p.version,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]


@autonomous_research_router.post("/policies")
def create_policy(
    req: PolicyCreateRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Creates a new autonomy policy for the workspace."""
    policy = AutonomyPolicy(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name=req.name,
        description=req.description,
        risk_level=req.risk_level,
        max_iterations=req.max_iterations,
        max_runtime_seconds=req.max_runtime_seconds,
        max_tool_calls=req.max_tool_calls,
        max_parallel_tasks=req.max_parallel_tasks,
        max_cost_budget=req.max_cost_budget,
        allowed_tools=req.allowed_tools,
        forbidden_tools=req.forbidden_tools,
        allowed_domains=req.allowed_domains,
        blocked_domains=req.blocked_domains,
        require_human_approval=req.require_human_approval,
        is_active=req.is_active,
        version=1,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {"message": "Policy created successfully", "policy_id": policy.id, "name": policy.name}


@autonomous_research_router.get("/policies/active")
def get_active_policy(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Returns the currently active default policy for the workspace."""
    policy = (
        db.query(AutonomyPolicy)
        .filter(AutonomyPolicy.workspace_id == workspace.id, AutonomyPolicy.is_active == True)
        .order_by(desc(AutonomyPolicy.created_at))
        .first()
    )
    if not policy:
        return {
            "is_default": True,
            "name": "Default Platform Safe Policy",
            "risk_level": ToolRiskLevel.LOW.value,
            "max_iterations": 10,
            "max_runtime_seconds": 300,
            "max_tool_calls": 50,
            "max_cost_budget": 10.0,
            "require_human_approval": False,
        }
    return {
        "id": policy.id,
        "name": policy.name,
        "risk_level": policy.risk_level,
        "max_iterations": policy.max_iterations,
        "max_runtime_seconds": policy.max_runtime_seconds,
        "max_tool_calls": policy.max_tool_calls,
        "max_cost_budget": policy.max_cost_budget,
        "is_active": policy.is_active,
    }


# --- Tools & Registry Endpoints ---

@autonomous_research_router.get("/tools")
def list_registered_tools(
    max_risk_level: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Lists all tools registered in the platform ToolRegistry."""
    return _tool_registry.list_tools(max_risk_level=max_risk_level)


# --- Plans & DAG Endpoints ---

@autonomous_research_router.post("/plans")
def create_research_plan(
    req: PlanCreateRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Generates and persists a structured research plan graph."""
    steps_data = req.custom_steps or ResearchTaskGraphEngine.generate_default_plan(
        company_name=req.target_name,
        domain=req.target_domain,
        mode=req.mode,
    )

    is_valid, err = ResearchTaskGraphEngine.validate_dag(steps_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid DAG: {err}")

    plan_id = str(uuid.uuid4())
    plan = ResearchPlan(
        id=plan_id,
        workspace_id=workspace.id,
        title=req.title,
        objective=req.objective,
        mode=req.mode,
        target_type=req.target_type,
        target_name=req.target_name,
        policy_id=req.policy_id,
        max_depth=req.max_depth,
        status="READY",
        version=1,
    )
    db.add(plan)

    # Persist steps
    for s in steps_data:
        step_rec = ResearchPlanStep(
            id=s["id"],
            plan_id=plan_id,
            step_order=s.get("step_order", 1),
            title=s.get("title", "Research Step"),
            task_type=s.get("task_type", TaskType.COMPANY_PROFILING.value),
            agent_name=s.get("agent_name", "CompanyResearchAgent"),
            tool_name=s.get("tool_name"),
            parameters=s.get("parameters", {}),
            status="PENDING",
            depends_on=s.get("depends_on", []),
        )
        db.add(step_rec)

    db.commit()
    db.refresh(plan)
    return {
        "message": "Research plan created successfully",
        "plan_id": plan.id,
        "title": plan.title,
        "step_count": len(steps_data),
        "steps": steps_data,
    }


@autonomous_research_router.get("/plans")
def list_research_plans(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists research plans for the workspace."""
    plans = (
        db.query(ResearchPlan)
        .filter(ResearchPlan.workspace_id == workspace.id)
        .order_by(desc(ResearchPlan.created_at))
        .all()
    )
    return [
        {
            "id": p.id,
            "title": p.title,
            "objective": p.objective,
            "mode": p.mode,
            "target_name": p.target_name,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in plans
    ]


@autonomous_research_router.post("/plans/validate-dag")
def validate_dag(req: DAGValidationRequest):
    """Validates that a step collection forms a valid Directed Acyclic Graph."""
    is_valid, err = ResearchTaskGraphEngine.validate_dag(req.steps)
    if not is_valid:
        return {"is_valid": False, "error": err}
    topological = ResearchTaskGraphEngine.get_topological_order(req.steps)
    return {
        "is_valid": True,
        "error": None,
        "step_count": len(req.steps),
        "execution_order": [s["id"] for s in topological],
    }


@autonomous_research_router.post("/simulations")
def simulate_plan(
    req: SimulationRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Runs a dry-run simulation of a plan or steps to predict cost, duration, and safety."""
    steps = req.steps
    if not steps and req.plan_id:
        steps_recs = db.query(ResearchPlanStep).filter(ResearchPlanStep.plan_id == req.plan_id).all()
        steps = [
            {
                "id": s.id,
                "step_order": s.step_order,
                "title": s.title,
                "task_type": s.task_type,
                "agent_name": s.agent_name,
                "tool_name": s.tool_name,
                "parameters": s.parameters or {},
                "depends_on": s.depends_on or [],
            }
            for s in steps_recs
        ]

    if not steps:
        raise HTTPException(status_code=400, detail="Either steps or valid plan_id with steps must be provided.")

    sim_result = SimulationAndSandboxEngine.simulate_plan_execution(
        workspace_id=workspace.id,
        plan_id=req.plan_id or "adhoc_plan",
        steps=steps,
    )
    return sim_result


# --- Autonomous Research Runs ---

@autonomous_research_router.post("/runs")
def start_research_run(
    req: RunStartRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Starts and executes an autonomous research run."""
    policy = None
    if req.policy_id:
        policy = db.query(AutonomyPolicy).filter(AutonomyPolicy.id == req.policy_id).first()

    loop = AutonomousResearchLoop(
        workspace_id=workspace.id,
        company_name=req.company_name,
        domain=req.domain,
        mode=req.mode,
        policy=policy,
        max_iterations=req.max_iterations or 10,
    )
    run_output = loop.execute()

    # Persist run record
    run_rec = AutonomousResearchRun(
        id=loop.run_id,
        workspace_id=workspace.id,
        plan_id=req.plan_id,
        objective=f"Autonomous research on {req.company_name}",
        mode=req.mode,
        status=loop.status,
        current_iteration=loop.current_iteration,
        total_iterations=loop.current_iteration,
        tool_call_count=loop.tool_calls_count,
        total_cost=loop.total_cost,
        stop_condition=loop.stop_condition,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if loop.status in (RunStatus.COMPLETED.value, RunStatus.BUDGET_EXCEEDED.value) else None,
    )
    db.add(run_rec)

    # Persist checkpoints
    for chk in loop.checkpoints:
        chk_rec = ResearchRunCheckpoint(
            id=chk["id"],
            run_id=loop.run_id,
            iteration=chk["iteration"],
            state_snapshot=chk.get("state_snapshot", {}),
            completed_tasks=chk.get("completed_tasks", []),
            pending_tasks=chk.get("pending_tasks", []),
            discovered_entities=chk.get("discovered_entities", []),
            cost_accrued=chk.get("cost_accrued", 0.0),
        )
        db.add(chk_rec)

    # Persist report
    rep = run_output.get("report")
    if rep:
        rep_rec = ResearchReport(
            id=rep["id"],
            workspace_id=workspace.id,
            run_id=loop.run_id,
            title=rep["title"],
            summary=rep["summary"],
            findings_summary=rep.get("findings_summary", {}),
            completeness_score=rep.get("completeness_score", 0.0),
            confidence_score=rep.get("confidence_score", 0.0),
            gaps_unresolved=rep.get("gaps_unresolved", []),
            report_version=1,
        )
        db.add(rep_rec)

    db.commit()
    return run_output


@autonomous_research_router.get("/runs")
def list_research_runs(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists research runs for the workspace."""
    runs = (
        db.query(AutonomousResearchRun)
        .filter(AutonomousResearchRun.workspace_id == workspace.id)
        .order_by(desc(AutonomousResearchRun.created_at))
        .all()
    )
    return [
        {
            "id": r.id,
            "objective": r.objective,
            "mode": r.mode,
            "status": r.status,
            "iterations": r.total_iterations,
            "tool_calls": r.tool_call_count,
            "cost": r.total_cost,
            "stop_condition": r.stop_condition,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]


@autonomous_research_router.get("/runs/{run_id}")
def get_research_run(
    run_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves full details of a specific research run."""
    run = (
        db.query(AutonomousResearchRun)
        .filter(AutonomousResearchRun.id == run_id, AutonomousResearchRun.workspace_id == workspace.id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    checkpoints = db.query(ResearchRunCheckpoint).filter(ResearchRunCheckpoint.run_id == run_id).all()
    report = db.query(ResearchReport).filter(ResearchReport.run_id == run_id).first()

    return {
        "id": run.id,
        "objective": run.objective,
        "mode": run.mode,
        "status": run.status,
        "current_iteration": run.current_iteration,
        "tool_call_count": run.tool_call_count,
        "total_cost": run.total_cost,
        "stop_condition": run.stop_condition,
        "checkpoints_count": len(checkpoints),
        "has_report": report is not None,
        "report_id": report.id if report else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


# --- Checkpoints, DLQ & Escalations Endpoints ---

@autonomous_research_router.get("/runs/{run_id}/checkpoints")
def list_run_checkpoints(
    run_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists snapshots and checkpoints saved for a run."""
    checkpoints = (
        db.query(ResearchRunCheckpoint)
        .filter(ResearchRunCheckpoint.run_id == run_id)
        .order_by(ResearchRunCheckpoint.iteration)
        .all()
    )
    return [
        {
            "id": c.id,
            "iteration": c.iteration,
            "completed_tasks_count": len(c.completed_tasks or []),
            "pending_tasks_count": len(c.pending_tasks or []),
            "cost_accrued": c.cost_accrued,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in checkpoints
    ]


@autonomous_research_router.get("/runs/{run_id}/dead-letter")
def list_run_dead_letters(
    run_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists tasks routed to the Dead Letter Queue for a run."""
    dlqs = db.query(ResearchDeadLetter).filter(ResearchDeadLetter.run_id == run_id).all()
    return [
        {
            "id": d.id,
            "task_id": d.task_id,
            "failure_reason": d.failure_reason,
            "retry_count": d.retry_count,
            "resolution_status": d.resolution_status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in dlqs
    ]


@autonomous_research_router.get("/runs/{run_id}/escalations")
def list_run_escalations(
    run_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists human-in-the-loop escalations triggered during a run."""
    escs = db.query(ResearchEscalation).filter(ResearchEscalation.run_id == run_id).all()
    return [
        {
            "id": e.id,
            "task_id": e.task_id,
            "escalation_type": e.escalation_type,
            "reason": e.reason,
            "status": e.status,
            "reviewer_id": e.reviewer_id,
            "reviewer_notes": e.reviewer_notes,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in escs
    ]


@autonomous_research_router.post("/runs/{run_id}/escalations/{esc_id}/resolve")
def resolve_run_escalation(
    run_id: str,
    esc_id: str,
    req: EscalationResolveRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Resolves an open human escalation with approval or rejection."""
    esc = db.query(ResearchEscalation).filter(ResearchEscalation.id == esc_id, ResearchEscalation.run_id == run_id).first()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    esc.status = req.decision.upper()
    esc.reviewer_id = user.id
    esc.reviewer_notes = req.notes
    esc.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(esc)
    return {
        "message": f"Escalation resolved as {esc.status}",
        "escalation_id": esc.id,
        "status": esc.status,
    }


# --- Reports Endpoints ---

@autonomous_research_router.get("/reports")
def list_reports(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists research reports generated in the workspace."""
    reports = (
        db.query(ResearchReport)
        .filter(ResearchReport.workspace_id == workspace.id)
        .order_by(desc(ResearchReport.created_at))
        .all()
    )
    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "title": r.title,
            "summary": r.summary,
            "completeness_score": r.completeness_score,
            "confidence_score": r.confidence_score,
            "version": r.report_version,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@autonomous_research_router.get("/reports/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves full details of a specific research report."""
    report = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.workspace_id == workspace.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    return {
        "id": report.id,
        "run_id": report.run_id,
        "title": report.title,
        "summary": report.summary,
        "findings_summary": report.findings_summary or {},
        "completeness_score": report.completeness_score,
        "confidence_score": report.confidence_score,
        "gaps_unresolved": report.gaps_unresolved or [],
        "version": report.report_version,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }

