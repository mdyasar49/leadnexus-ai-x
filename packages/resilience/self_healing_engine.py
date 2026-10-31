"""
LeadNexus AI X - Phase 30: Enterprise Reliability & Resilience
Self-Healing Engine: Automated remediation triggers, zombie task recovery, and incident orchestration.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.resilience import (
    IncidentSeverity,
    IncidentStatus,
    PlatformIncident,
    SelfHealingAction,
)
from packages.resilience.circuit_breaker_service import CircuitBreakerService
from packages.resilience.distributed_lease_manager import DistributedLeaseManager


class SelfHealingEngine:
    """Detects operational degradation and executes automated remediation policies."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def execute_zombie_task_remediation(self) -> List[SelfHealingAction]:
        """Identifies tasks with expired leases and safely reaps them."""
        lease_mgr = DistributedLeaseManager(self.db)
        reaped_tasks = lease_mgr.reap_stale_leases()

        actions = []
        for task_id in reaped_tasks:
            act = SelfHealingAction(
                id=str(uuid.uuid4()),
                rule_name="REAP_ZOMBIE_TASK_LEASE",
                trigger_event="LEASE_HEARTBEAT_EXPIRED",
                target_resource=f"task:{task_id}",
                action_taken="RELEASED_EXPIRED_LEASE_FOR_REDRIVE",
                remediation_status="SUCCESS",
                details={"task_id": task_id},
                executed_at=datetime.now(timezone.utc),
            )
            self.db.add(act)
            actions.append(act)

        if actions:
            self.db.commit()

        return actions

    # --- Platform Incidents ---

    def create_incident(
        self,
        title: str,
        severity: IncidentSeverity = IncidentSeverity.MAJOR,
        affected_components: Optional[List[str]] = None,
        root_cause: Optional[str] = None,
    ) -> PlatformIncident:
        inc = PlatformIncident(
            id=str(uuid.uuid4()),
            title=title,
            severity=severity.value if isinstance(severity, IncidentSeverity) else severity,
            status=IncidentStatus.INVESTIGATING.value,
            affected_components=affected_components or [],
            root_cause=root_cause,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(inc)
        self.db.commit()
        self.db.refresh(inc)
        return inc

    def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        root_cause: Optional[str] = None,
    ) -> Optional[PlatformIncident]:
        inc = self.db.query(PlatformIncident).filter(PlatformIncident.id == incident_id).first()
        if not inc:
            return None

        inc.status = status.value if isinstance(status, IncidentStatus) else status
        if root_cause:
            inc.root_cause = root_cause
        if status == IncidentStatus.RESOLVED:
            inc.resolved_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(inc)
        return inc
