"""
Multi-Agent AI Platform API Routes (Phase 41)
Provides orchestration, task dispatch, memory inspector, inter-agent message bus,
and conflict arbitration across the 12 specialized agents.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.multi_agent_platform import (
    AgentTypeEnum,
    AgentStatus,
    AgentTaskPriority,
    ArbitrationStrategy,
    AgentTaskRecord,
    AgentMemoryEntry,
    AgentMessageBusRecord,
    AgentArbitrationRecord,
    AgentEvaluationMetric,
)
from packages.agents.agent_registry import AgentRegistry
from packages.agents.agent_runtime import AutonomousAgent, AgentExecutionResult
from packages.agents.agent_bus import InterAgentMessageBus
from packages.agents.arbitration_engine import AgentArbitrator, ArbitrationConflict
from packages.agents.specialized_agents import get_specialized_agent

router = APIRouter(prefix="/agents", tags=["Multi-Agent AI Platform"])

# Global bus instance for task communication
_bus = InterAgentMessageBus()


# --- Schemas ---

class TaskDispatchCreate(BaseModel):
    agent_type: str  # AgentTypeEnum
    goal_description: str
    input_context: Dict[str, Any] = Field(default_factory=dict)
    priority: str = AgentTaskPriority.NORMAL
    max_steps: int = 10
    token_budget: int = 16384


class MemoryWriteRequest(BaseModel):
    agent_type: str
    memory_key: str
    memory_value: Dict[str, Any]
    memory_scope: str = "TASK"
    ttl_seconds: int = 86400


class ArbitrationResolveRequest(BaseModel):
    conflict_field: str
    agent_a: str
    value_a: Any
    confidence_a: float
    agent_b: str
    value_b: Any
    confidence_b: float
    strategy: str = ArbitrationStrategy.CONFIDENCE_WEIGHTED


# --- 1. Agent Registry ---

@router.get("/registry")
def list_agent_roster(
    current_user: User = Depends(get_current_user),
):
    """Lists all 12 specialized agents with defined capabilities and tool allowances."""
    roster = [agent.to_dict() for agent in AgentRegistry.list_all()]
    return {"agents": roster, "total_specialists": len(roster)}


# --- 2. Autonomous Task Orchestration ---

@router.get("/tasks")
def list_agent_tasks(
    status_filter: Optional[str] = Query(None),
    agent_filter: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AgentTaskRecord).filter(AgentTaskRecord.workspace_id == ws.id)
    if status_filter:
        query = query.filter(AgentTaskRecord.status == status_filter.upper())
    if agent_filter:
        query = query.filter(AgentTaskRecord.assigned_agent == agent_filter)
    tasks = query.order_by(AgentTaskRecord.created_at.desc()).limit(50).all()
    return {"tasks": tasks}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def dispatch_agent_task(
    payload: TaskDispatchCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Dispatches a bounded autonomous task to one of the 12 specialized agents."""
    if payload.agent_type not in AgentTypeEnum.ALL_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type '{payload.agent_type}'. Must be one of: {AgentTypeEnum.ALL_AGENTS}",
        )

    task_record = AgentTaskRecord(
        workspace_id=ws.id,
        assigned_agent=payload.agent_type,
        status=AgentStatus.RUNNING,
        priority=payload.priority.upper(),
        goal_description=payload.goal_description,
        input_context=payload.input_context,
        max_steps=payload.max_steps,
        token_budget=payload.token_budget,
    )
    db.add(task_record)
    db.commit()
    db.refresh(task_record)

    # Instantiate specialized agent and execute
    agent_instance = get_specialized_agent(payload.agent_type)
    agent_instance.max_steps = payload.max_steps

    exec_result = agent_instance.execute_bounded(
        task_id=task_record.id,
        goal=payload.goal_description,
        context=payload.input_context,
    )

    task_record.status = exec_result.status
    task_record.output_result = exec_result.result_data
    task_record.current_steps = exec_result.steps_taken
    task_record.tokens_used = exec_result.tokens_consumed
    task_record.cost_usd = exec_result.cost_usd
    task_record.error_message = exec_result.error
    task_record.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task_record)

    # Record message on bus
    _bus.send_message(
        sender_agent="UserOrchestrator",
        recipient_agent=payload.agent_type,
        message_type="RESPONSE",
        payload={"task_id": task_record.id, "status": exec_result.status, "steps": exec_result.steps_taken},
        task_id=task_record.id,
    )

    return {
        "status": "completed" if exec_result.status == AgentStatus.COMPLETED else "failed",
        "task": task_record,
        "execution_steps": exec_result.steps_log,
        "latency_ms": exec_result.latency_ms,
    }


@router.get("/tasks/{task_id}")
def get_task_detail(
    task_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    task = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.id == task_id,
        AgentTaskRecord.workspace_id == ws.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task": task}


# --- 3. Agent Memory ---

@router.get("/memory")
def get_agent_memory(
    agent_type: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AgentMemoryEntry).filter(AgentMemoryEntry.workspace_id == ws.id)
    if agent_type:
        query = query.filter(AgentMemoryEntry.agent_type == agent_type)
    entries = query.order_by(AgentMemoryEntry.created_at.desc()).limit(100).all()
    return {"memory_entries": entries}


@router.post("/memory", status_code=status.HTTP_201_CREATED)
def write_agent_memory(
    payload: MemoryWriteRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    entry = AgentMemoryEntry(
        workspace_id=ws.id,
        agent_type=payload.agent_type,
        memory_scope=payload.memory_scope.upper(),
        memory_key=payload.memory_key,
        memory_value=payload.memory_value,
        ttl_seconds=payload.ttl_seconds,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"status": "written", "entry": entry}


# --- 4. Inter-Agent Message Bus ---

@router.get("/messages")
def get_bus_messages(
    task_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if task_id:
        return {"messages": _bus.get_messages_for_task(task_id)}
    return {"messages": _bus._messages[-50:]}


# --- 5. Conflict Arbitration ---

@router.post("/arbitration/resolve")
def resolve_agent_dispute(
    payload: ArbitrationResolveRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Detects and resolves conflicts between two specialized agent claims."""
    conflict = AgentArbitrator.detect_conflict(
        field=payload.conflict_field,
        agent_a=payload.agent_a,
        value_a=payload.value_a,
        confidence_a=payload.confidence_a,
        agent_b=payload.agent_b,
        value_b=payload.value_b,
        confidence_b=payload.confidence_b,
    )

    if not conflict:
        return {"status": "NO_CONFLICT", "message": "Both agents agree on the same value."}

    resolution = AgentArbitrator.resolve_conflict(conflict, strategy=payload.strategy)

    # Persist in DB
    arb_record = AgentArbitrationRecord(
        task_id=f"arb-{conflict.conflict_field}",
        disputing_agents=[payload.agent_a, payload.agent_b],
        conflict_summary=f"Dispute on '{payload.conflict_field}': {payload.agent_a}={payload.value_a} vs {payload.agent_b}={payload.value_b}",
        proposed_outcomes={payload.agent_a: payload.value_a, payload.agent_b: payload.value_b},
        arbitrator_decision=resolution,
        resolution_strategy=payload.strategy,
        is_resolved=resolution["winner_agent"] is not None,
        resolved_at=datetime.now(timezone.utc) if resolution["winner_agent"] else None,
    )
    db.add(arb_record)
    db.commit()
    db.refresh(arb_record)

    return {"status": "RESOLVED", "resolution": resolution, "arbitration_record": arb_record}


# --- 6. Agent Evaluation & Health ---

@router.get("/health")
def get_agents_health(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Returns operational health, success rates, and token utilization for all 12 agents."""
    health_report = []
    for agent_def in AgentRegistry.list_all():
        tasks = db.query(AgentTaskRecord).filter(
            AgentTaskRecord.workspace_id == ws.id,
            AgentTaskRecord.assigned_agent == agent_def.agent_type,
        ).all()

        total = len(tasks)
        successful = sum(1 for t in tasks if t.status == AgentStatus.COMPLETED)
        rate = round((successful / total * 100.0), 1) if total > 0 else 100.0
        avg_tokens = round(sum(t.tokens_used for t in tasks) / total, 1) if total > 0 else 0.0

        health_report.append({
            "agent_type": agent_def.agent_type,
            "display_name": agent_def.display_name,
            "status": "HEALTHY",
            "total_tasks": total,
            "success_rate": rate,
            "avg_tokens": avg_tokens,
            "max_steps_allowed": agent_def.max_steps,
        })

    return {"agents_health": health_report}

