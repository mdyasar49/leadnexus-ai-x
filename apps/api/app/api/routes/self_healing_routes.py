"""
LeadNexus AI X - Phase 45: Self-Healing & Automated Remediation Routes
Provides endpoints for playbook inspection, incident triggering, automated remediation,
SRE human escalation, and MTTR telemetry.
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
from app.models.self_healing_remediation import (
    RemediationPlaybook,
    RemediationIncident,
    RemediationActionExecution,
    RemediationRateLimitLog,
)
from packages.self_healing import (
    SelfHealingEngine,
    SafetyViolationError,
    PlaybookDefinition,
    IncidentRecord,
    IncidentStatus,
)

router = APIRouter(prefix="/self-healing", tags=["Self-Healing & Automated Remediation"])

# Singleton engine instance
global_self_healing_engine = SelfHealingEngine()


# Pydantic Schemas
class TriggerIncidentRequest(BaseModel):
    metric_name: str = Field(..., description="Breached metric name (e.g. api.request.latency)")
    trigger_value: float = Field(..., description="Observed anomalous metric value")
    threshold: float = Field(..., description="Target threshold that was exceeded")
    severity: str = Field(default="WARNING", description="INFO, WARNING, or CRITICAL")
    rule_id: Optional[str] = None
    auto_remediate: bool = Field(default=True, description="Whether to execute matched playbook immediately")


class RemediateIncidentRequest(BaseModel):
    playbook_id: Optional[str] = Field(None, description="Optional custom playbook ID override")


class EscalateIncidentRequest(BaseModel):
    reason: str = Field(default="Manual SRE escalation requested", description="Escalation rationale")


@router.get("/health")
def get_self_healing_health():
    """Returns MTTR metrics, active incident counts, and safety guard status."""
    mttr = global_self_healing_engine.coordinator.get_mttr_metrics()
    active_count = sum(
        1 for i in global_self_healing_engine.coordinator.incidents.values()
        if i.status not in [IncidentStatus.RESOLVED, IncidentStatus.FAILED]
    )
    return {
        "status": "HEALTHY",
        "active_incidents": active_count,
        "mttr": mttr,
        "playbooks_count": len(global_self_healing_engine.registry._playbooks),
        "safety_guard": {
            "default_cooldown_seconds": global_self_healing_engine.safety_guard.default_cooldown_seconds,
            "max_per_hour": global_self_healing_engine.safety_guard.default_max_per_hour,
            "blast_radius_cap": global_self_healing_engine.safety_guard.max_blast_radius_fraction,
        },
    }


@router.get("/playbooks")
def list_playbooks():
    """Lists all approved self-healing remediation playbooks."""
    pbs = [pb.to_dict() for pb in global_self_healing_engine.registry.list_playbooks()]
    return {"playbooks": pbs, "count": len(pbs)}


@router.get("/incidents")
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Lists recent reliability incidents with status filter."""
    incidents = list(global_self_healing_engine.coordinator.incidents.values())
    if status_filter:
        incidents = [i for i in incidents if i.status.value == status_filter.upper()]

    return {
        "incidents": [i.to_dict() for i in reversed(incidents)],
        "count": len(incidents),
    }


@router.post("/incidents")
def trigger_incident(
    request: TriggerIncidentRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Triggers an incident from an anomaly alert and initiates auto-remediation."""
    try:
        record = global_self_healing_engine.coordinator.trigger_incident(
            metric_name=request.metric_name,
            trigger_value=request.trigger_value,
            threshold=request.threshold,
            severity=request.severity,
            rule_id=request.rule_id,
            auto_remediate=request.auto_remediate,
        )
    except SafetyViolationError as e:
        raise HTTPException(status_code=429, detail=f"Safety guard rejected action: {str(e)}")

    # Persist in DB
    db_incident = RemediationIncident(
        id=record.incident_id,
        rule_id=record.rule_id,
        metric_name=record.metric_name,
        trigger_value=record.trigger_value,
        threshold=record.threshold,
        status=record.status.value,
        severity=record.severity,
        assigned_playbook_id=record.assigned_playbook_id,
        details=record.details,
    )
    db.add(db_incident)
    db.commit()

    return record.to_dict()


@router.post("/incidents/{incident_id}/remediate")
def execute_remediation_action(
    incident_id: str,
    request: RemediateIncidentRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Manually dispatches an approved remediation playbook for an incident."""
    try:
        result = global_self_healing_engine.coordinator.execute_remediation(
            incident_id=incident_id,
            custom_playbook_id=request.playbook_id,
        )
    except SafetyViolationError as e:
        raise HTTPException(status_code=429, detail=f"Safety guard rejected action: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Persist execution log in DB
    db_exec = RemediationActionExecution(
        id=result.execution_id,
        incident_id=incident_id,
        playbook_id=result.playbook_id,
        action_type=result.action_type,
        target_subsystem=result.target_subsystem,
        execution_payload=result.details,
        pre_metric_value=result.pre_metric_value,
        post_metric_value=result.post_metric_value,
        outcome=result.outcome,
        error_message=result.error_message,
    )
    db.add(db_exec)

    # Update incident in DB
    db_inc = db.query(RemediationIncident).filter(RemediationIncident.id == incident_id).first()
    if db_inc:
        live_inc = global_self_healing_engine.coordinator.incidents.get(incident_id)
        if live_inc:
            db_inc.status = live_inc.status.value
            db_inc.resolved_at = live_inc.resolved_at

    db.commit()

    return result.to_dict()


@router.post("/incidents/{incident_id}/escalate")
def escalate_incident(
    incident_id: str,
    request: EscalateIncidentRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    """Escalates an incident to human SRE / Platform Admin."""
    try:
        record = global_self_healing_engine.coordinator.escalate_to_human(
            incident_id=incident_id,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    db_inc = db.query(RemediationIncident).filter(RemediationIncident.id == incident_id).first()
    if db_inc:
        db_inc.status = "ESCALATED"
        db_inc.details = record.details
        db.commit()

    return record.to_dict()


@router.get("/history")
def list_execution_history():
    """Returns chronological audit trail of all executed remediation actions."""
    executions = [r.to_dict() for r in global_self_healing_engine.executor.execution_history]
    return {"executions": list(reversed(executions)), "count": len(executions)}
