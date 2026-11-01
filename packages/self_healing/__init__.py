"""
LeadNexus AI X - Phase 45: Self-Healing, Automated Remediation & Reliability Engineering Package
Exposes playbook catalog, safety guard, executor, and incident coordinator.
"""

from packages.self_healing.playbook_registry import PlaybookRegistry, PlaybookDefinition
from packages.self_healing.safety_guard import RemediationSafetyGuard, SafetyViolationError
from packages.self_healing.remediation_executor import RemediationExecutor, RemediationResult
from packages.self_healing.incident_coordinator import (
    IncidentCoordinator,
    IncidentRecord,
    IncidentStatus,
    METRIC_PLAYBOOK_MAPPING,
)


class SelfHealingEngine:
    """Unified self-healing facade coordinating playbooks, safety checks, and executions."""

    def __init__(self):
        self.registry = PlaybookRegistry()
        self.safety_guard = RemediationSafetyGuard()
        self.coordinator = IncidentCoordinator(registry=self.registry, safety_guard=self.safety_guard)


__all__ = [
    "PlaybookRegistry",
    "PlaybookDefinition",
    "RemediationSafetyGuard",
    "SafetyViolationError",
    "RemediationExecutor",
    "RemediationResult",
    "IncidentCoordinator",
    "IncidentRecord",
    "IncidentStatus",
    "METRIC_PLAYBOOK_MAPPING",
    "SelfHealingEngine",
]
