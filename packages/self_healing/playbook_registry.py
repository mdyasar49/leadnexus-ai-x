"""
LeadNexus AI X - Phase 45: Remediation Playbook Catalog
Maintains the registry of approved self-healing playbooks across workers,
model providers, caches, and rate-limiting ingress.
"""

from typing import Any, Callable, Dict, List, Optional
import uuid


class PlaybookDefinition:
    def __init__(
        self,
        playbook_id: str,
        name: str,
        action_type: str,
        target_subsystem: str,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        cooldown_seconds: int = 300,
        max_per_hour: int = 5,
        is_enabled: bool = True,
    ):
        self.playbook_id = playbook_id
        self.name = name
        self.action_type = action_type
        self.target_subsystem = target_subsystem
        self.description = description
        self.parameters = parameters or {}
        self.cooldown_seconds = cooldown_seconds
        self.max_per_hour = max_per_hour
        self.is_enabled = is_enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "name": self.name,
            "action_type": self.action_type,
            "target_subsystem": self.target_subsystem,
            "description": self.description,
            "parameters": self.parameters,
            "cooldown_seconds": self.cooldown_seconds,
            "max_per_hour": self.max_per_hour,
            "is_enabled": self.is_enabled,
        }


class PlaybookRegistry:
    """Catalog of approved self-healing remediation playbooks."""

    def __init__(self):
        self._playbooks: Dict[str, PlaybookDefinition] = {}
        self._seed_default_playbooks()

    def _seed_default_playbooks(self):
        defaults = [
            PlaybookDefinition(
                playbook_id="pb-restart-worker",
                name="Worker Pool Slot Recycling",
                action_type="RESTART_WORKER",
                target_subsystem="worker_pool",
                description="Recycles stalled worker execution slots without dropping queued tasks.",
                parameters={"graceful_timeout_seconds": 15},
                cooldown_seconds=180,
                max_per_hour=6,
            ),
            PlaybookDefinition(
                playbook_id="pb-flush-cache",
                name="Redis Transient Key Purge",
                action_type="FLUSH_CACHE",
                target_subsystem="cache_redis",
                description="Evicts volatile cached query responses when memory usage crosses 85%.",
                parameters={"namespace": "transient_search:*"},
                cooldown_seconds=300,
                max_per_hour=4,
            ),
            PlaybookDefinition(
                playbook_id="pb-failover-provider",
                name="Cascading AI Provider Failover",
                action_type="FAILOVER_PROVIDER",
                target_subsystem="model_router",
                description="Reroutes inference requests to secondary fallback AI models during upstream 5xx errors.",
                parameters={"fallback_model": "gemini-1.5-flash"},
                cooldown_seconds=120,
                max_per_hour=10,
            ),
            PlaybookDefinition(
                playbook_id="pb-throttle-ingress",
                name="Adaptive Ingress Concurrency Shedding",
                action_type="THROTTLE_INGRESS",
                target_subsystem="api_gateway",
                description="Temporarily reduces non-critical background traffic during latency spikes.",
                parameters={"shed_percentage": 20},
                cooldown_seconds=240,
                max_per_hour=5,
            ),
            PlaybookDefinition(
                playbook_id="pb-reset-circuit",
                name="Circuit Breaker Probe Reset",
                action_type="RESET_CIRCUIT",
                target_subsystem="circuit_breaker",
                description="Transitions open circuit breakers to HALF_OPEN to test downstream dependency recovery.",
                parameters={"probe_requests": 3},
                cooldown_seconds=120,
                max_per_hour=8,
            ),
        ]
        for pb in defaults:
            self._playbooks[pb.playbook_id] = pb

    def get_playbook(self, playbook_id: str) -> Optional[PlaybookDefinition]:
        return self._playbooks.get(playbook_id)

    def find_playbook_by_action(self, action_type: str, target_subsystem: str) -> Optional[PlaybookDefinition]:
        for pb in self._playbooks.values():
            if pb.is_enabled and pb.action_type == action_type and pb.target_subsystem == target_subsystem:
                return pb
        return None

    def list_playbooks(self) -> List[PlaybookDefinition]:
        return list(self._playbooks.values())
