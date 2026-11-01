"""
LeadNexus AI X - Phase 45: Incident Response & Auto-Remediation Coordinator
Matches anomaly alerts to approved playbooks, manages the incident lifecycle
(DETECTED -> REMEDIATING -> VERIFYING -> RESOLVED / ESCALATED), and tracks MTTR metrics.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from packages.self_healing.playbook_registry import PlaybookRegistry, PlaybookDefinition
from packages.self_healing.safety_guard import RemediationSafetyGuard, SafetyViolationError
from packages.self_healing.remediation_executor import RemediationExecutor, RemediationResult


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


# Default heuristic mapping from metric name to approved playbook ID
METRIC_PLAYBOOK_MAPPING = {
    "api.request.latency": "pb-throttle-ingress",
    "worker.pool.stalled": "pb-restart-worker",
    "cache.memory.high": "pb-flush-cache",
    "model.upstream.error": "pb-failover-provider",
    "circuit.downstream.error": "pb-reset-circuit",
}


class IncidentRecord:
    def __init__(
        self,
        incident_id: str,
        metric_name: str,
        trigger_value: float,
        threshold: float,
        severity: str = "WARNING",
        rule_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.incident_id = incident_id
        self.metric_name = metric_name
        self.trigger_value = trigger_value
        self.threshold = threshold
        self.severity = severity
        self.rule_id = rule_id
        self.details = details or {}
        self.status = IncidentStatus.DETECTED
        self.assigned_playbook_id: Optional[str] = None
        self.started_at = datetime.now(timezone.utc)
        self.resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "metric_name": self.metric_name,
            "trigger_value": self.trigger_value,
            "threshold": self.threshold,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "status": self.status.value,
            "assigned_playbook_id": self.assigned_playbook_id,
            "details": self.details,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class IncidentCoordinator:
    """End-to-end reliability coordinator managing self-healing playbooks and incident states."""

    def __init__(
        self,
        registry: Optional[PlaybookRegistry] = None,
        safety_guard: Optional[RemediationSafetyGuard] = None,
    ):
        self.registry = registry or PlaybookRegistry()
        self.safety_guard = safety_guard or RemediationSafetyGuard()
        self.executor = RemediationExecutor(safety_guard=self.safety_guard)
        self.incidents: Dict[str, IncidentRecord] = {}

    def trigger_incident(
        self,
        metric_name: str,
        trigger_value: float,
        threshold: float,
        severity: str = "WARNING",
        rule_id: Optional[str] = None,
        auto_remediate: bool = True,
    ) -> IncidentRecord:
        """Creates an incident and optionally triggers auto-remediation."""
        inc_id = str(uuid.uuid4())
        record = IncidentRecord(
            incident_id=inc_id,
            metric_name=metric_name,
            trigger_value=trigger_value,
            threshold=threshold,
            severity=severity,
            rule_id=rule_id,
        )
        self.incidents[inc_id] = record

        # Match playbook
        matched_pb_id = METRIC_PLAYBOOK_MAPPING.get(metric_name)
        if matched_pb_id:
            record.assigned_playbook_id = matched_pb_id

        if auto_remediate and matched_pb_id:
            self.execute_remediation(inc_id)

        return record

    def execute_remediation(self, incident_id: str, custom_playbook_id: Optional[str] = None) -> RemediationResult:
        """Executes the assigned or custom playbook for an incident."""
        incident = self._get_incident(incident_id)
        pb_id = custom_playbook_id or incident.assigned_playbook_id
        if not pb_id:
            incident.status = IncidentStatus.ESCALATED
            raise ValueError(f"No playbook matched for metric '{incident.metric_name}'")

        playbook = self.registry.get_playbook(pb_id)
        if not playbook:
            incident.status = IncidentStatus.ESCALATED
            raise ValueError(f"Playbook '{pb_id}' not found")

        incident.status = IncidentStatus.REMEDIATING

        try:
            result = self.executor.execute_playbook(
                playbook=playbook,
                incident_id=incident_id,
                pre_metric_value=incident.trigger_value,
                threshold=incident.threshold,
            )
            incident.status = IncidentStatus.VERIFYING

            if result.outcome == "SUCCESS":
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = datetime.now(timezone.utc)
            elif result.outcome in ["FAILED", "ROLLED_BACK", "NO_IMPROVEMENT"]:
                # Check if failure quota reached -> escalate
                should_escalate = self.safety_guard.record_outcome(incident_id, success=False)
                incident.status = IncidentStatus.ESCALATED if should_escalate else IncidentStatus.FAILED

            return result

        except SafetyViolationError as e:
            incident.status = IncidentStatus.ESCALATED
            incident.details["escalation_reason"] = f"Safety guard rejected action: {str(e)}"
            raise

    def escalate_to_human(self, incident_id: str, reason: str = "Manual operator escalation") -> IncidentRecord:
        """Manually escalates an incident to human SRE."""
        incident = self._get_incident(incident_id)
        incident.status = IncidentStatus.ESCALATED
        incident.details["escalation_reason"] = reason
        return incident

    def get_mttr_metrics(self) -> Dict[str, Any]:
        """Calculates Mean Time to Remediation (MTTR) across resolved incidents."""
        resolved = [i for i in self.incidents.values() if i.status == IncidentStatus.RESOLVED and i.resolved_at]
        if not resolved:
            return {"resolved_count": 0, "avg_mttr_seconds": 0.0, "automated_success_rate": 1.0}

        total_seconds = sum((i.resolved_at - i.started_at).total_seconds() for i in resolved)
        avg_mttr = round(total_seconds / len(resolved), 2)
        total_incidents = len(self.incidents)
        success_rate = round(len(resolved) / max(1, total_incidents), 4)

        return {
            "resolved_count": len(resolved),
            "total_incidents": total_incidents,
            "avg_mttr_seconds": avg_mttr,
            "automated_success_rate": success_rate,
        }

    def _get_incident(self, incident_id: str) -> IncidentRecord:
        if incident_id not in self.incidents:
            raise ValueError(f"Incident '{incident_id}' not found")
        return self.incidents[incident_id]
