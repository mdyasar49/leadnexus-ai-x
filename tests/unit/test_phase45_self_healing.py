"""
LeadNexus AI X - Phase 45 Test Suite (ChatGPT Master Roadmap)
Self-Healing, Automated Remediation & Reliability Engineering
Tests: Playbook registry, safety cooldowns, hourly rate quotas, blast radius caps,
post-remediation verification, rollback logic, incident lifecycle, and workflow invariants.
"""

import sys
import os
import uuid
import unittest
import time
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.main import app
from app.db.session import SessionLocal, sync_engine
from app.db.base import Base
from app.models.tenant import Organization, Workspace
from app.models.user import User
from app.models.saved_lead import SavedLead
from app.models.self_healing_remediation import (
    RemediationPlaybook,
    RemediationIncident,
    RemediationActionExecution,
    RemediationRateLimitLog,
)
from app.security.tokens import create_access_token
from packages.self_healing import (
    PlaybookRegistry,
    PlaybookDefinition,
    RemediationSafetyGuard,
    SafetyViolationError,
    RemediationExecutor,
    RemediationResult,
    IncidentCoordinator,
    IncidentRecord,
    IncidentStatus,
    SelfHealingEngine,
)


class TestPhase45SelfHealing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Self-Healing Org", slug="self-healing-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                name="Self-Healing Workspace",
                slug="self-healing-workspace",
                organization_id=cls.org.id,
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="sre_lead@leadnexus.internal",
                first_name="SRE",
                last_name="Lead",
                password_hash="hashed_pw_test",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        token = create_access_token(user_id=cls.user.id)
        cls.headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": cls.workspace.id,
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_playbook_registry_defaults_and_lookup(self):
        """Validates standard playbooks presence and lookup by action and subsystem."""
        reg = PlaybookRegistry()
        playbooks = reg.list_playbooks()
        self.assertGreaterEqual(len(playbooks), 5)

        pb_restart = reg.get_playbook("pb-restart-worker")
        self.assertIsNotNone(pb_restart)
        self.assertEqual(pb_restart.action_type, "RESTART_WORKER")
        self.assertEqual(pb_restart.target_subsystem, "worker_pool")

        pb_found = reg.find_playbook_by_action("FAILOVER_PROVIDER", "model_router")
        self.assertIsNotNone(pb_found)
        self.assertEqual(pb_found.playbook_id, "pb-failover-provider")

    def test_02_safety_guard_cooldown_enforcement(self):
        """Validates that rapid repeated executions trigger cooldown violation."""
        guard = RemediationSafetyGuard(default_cooldown_seconds=60)
        subsystem = "test_subsystem_cooldown"

        # First check allowed
        ok1, _ = guard.check_safety(subsystem, "RESTART_WORKER")
        self.assertTrue(ok1)
        guard.record_execution(subsystem)

        # Immediate second check blocked by cooldown
        ok2, reason = guard.check_safety(subsystem, "RESTART_WORKER")
        self.assertFalse(ok2)
        self.assertIn("Cooldown active", reason)

    def test_03_safety_guard_hourly_quota_enforcement(self):
        """Validates that exceeding max actions per hour is blocked."""
        guard = RemediationSafetyGuard(default_cooldown_seconds=0, default_max_per_hour=2)
        subsystem = "test_subsystem_quota"

        # Execution 1
        ok1, _ = guard.check_safety(subsystem, "ACTION")
        self.assertTrue(ok1)
        guard.record_execution(subsystem)

        # Execution 2
        ok2, _ = guard.check_safety(subsystem, "ACTION")
        self.assertTrue(ok2)
        guard.record_execution(subsystem)

        # Execution 3 exceeds quota
        ok3, reason = guard.check_safety(subsystem, "ACTION")
        self.assertFalse(ok3)
        self.assertIn("Hourly remediation quota", reason)

    def test_04_safety_guard_blast_radius_cap(self):
        """Validates that actions affecting >25% of instances are rejected."""
        guard = RemediationSafetyGuard(default_cooldown_seconds=0, max_blast_radius_fraction=0.25)
        ok, reason = guard.check_safety("workers", "RESTART_WORKER", affected_fraction=0.40)
        self.assertFalse(ok)
        self.assertIn("Blast radius", reason)

    def test_05_remediation_executor_success_outcome(self):
        """Validates successful remediation execution and metric improvement."""
        guard = RemediationSafetyGuard(default_cooldown_seconds=0)
        executor = RemediationExecutor(safety_guard=guard)
        playbook = PlaybookDefinition(
            playbook_id="pb-test-success",
            name="Test Success",
            action_type="RESTART_WORKER",
            target_subsystem="worker_pool",
            description="Test",
        )

        # Pre-metric=2200, threshold=1500 -> healthy post-metric=975 (threshold*0.65)
        result = executor.execute_playbook(
            playbook=playbook,
            incident_id="inc-1",
            pre_metric_value=2200.0,
            threshold=1500.0,
        )
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertLessEqual(result.post_metric_value, 1500.0)

    def test_06_remediation_executor_rollback_on_degradation(self):
        """Validates rollback trigger if post-remediation metric worsens."""
        guard = RemediationSafetyGuard(default_cooldown_seconds=0)
        executor = RemediationExecutor(safety_guard=guard)
        playbook = PlaybookDefinition(
            playbook_id="pb-test-degraded",
            name="Test Degraded",
            action_type="THROTTLE_INGRESS",
            target_subsystem="api_gateway",
            description="Test",
        )

        # Metric evaluator simulating worse performance
        def degraded_metric():
            return 3500.0  # worse than pre_metric=2000

        result = executor.execute_playbook(
            playbook=playbook,
            incident_id="inc-degraded",
            pre_metric_value=2000.0,
            threshold=1000.0,
            metric_evaluator=degraded_metric,
        )
        self.assertEqual(result.outcome, "ROLLED_BACK")
        self.assertIn("rollback_reason", result.details)

    def test_07_incident_coordinator_auto_remediate_flow(self):
        """Validates full automated incident response: detect -> match -> execute -> RESOLVED."""
        coord = IncidentCoordinator()
        # Trigger incident matching 'api.request.latency' -> 'pb-throttle-ingress'
        incident = coord.trigger_incident(
            metric_name="api.request.latency",
            trigger_value=2200.0,
            threshold=1500.0,
            severity="WARNING",
            auto_remediate=True,
        )
        self.assertEqual(incident.status, IncidentStatus.RESOLVED)
        self.assertIsNotNone(incident.resolved_at)
        self.assertEqual(incident.assigned_playbook_id, "pb-throttle-ingress")

    def test_08_incident_coordinator_escalation(self):
        """Validates manual or failure escalation to human SRE."""
        coord = IncidentCoordinator()
        incident = coord.trigger_incident(
            metric_name="unknown.critical.failure",
            trigger_value=1.0,
            threshold=0.0,
            auto_remediate=False,
        )
        self.assertEqual(incident.status, IncidentStatus.DETECTED)

        # Escalate to human
        escalated = coord.escalate_to_human(incident.incident_id, reason="Complex cascading failure")
        self.assertEqual(escalated.status, IncidentStatus.ESCALATED)
        self.assertEqual(escalated.details["escalation_reason"], "Complex cascading failure")

    def test_09_api_self_healing_endpoints(self):
        """Validates /playbooks, /incidents, /incidents/{id}/escalate, and /health via TestClient."""
        # 1. Playbooks
        res_pb = self.client.get("/api/v1/self-healing/playbooks")
        self.assertEqual(res_pb.status_code, 200)
        self.assertGreaterEqual(res_pb.json()["count"], 5)

        # 2. Trigger incident
        payload = {
            "metric_name": "worker.pool.stalled",
            "trigger_value": 1.0,
            "threshold": 0.0,
            "severity": "CRITICAL",
            "auto_remediate": False,
        }
        res_inc = self.client.post("/api/v1/self-healing/incidents", json=payload, headers=self.headers)
        self.assertEqual(res_inc.status_code, 200)
        inc_id = res_inc.json()["incident_id"]

        # 3. Escalate incident
        esc_payload = {"reason": "Worker node unresponsive"}
        res_esc = self.client.post(f"/api/v1/self-healing/incidents/{inc_id}/escalate", json=esc_payload, headers=self.headers)
        self.assertEqual(res_esc.status_code, 200)
        self.assertEqual(res_esc.json()["status"], "ESCALATED")

        # 4. Health
        res_h = self.client.get("/api/v1/self-healing/health")
        self.assertEqual(res_h.status_code, 200)
        self.assertEqual(res_h.json()["status"], "HEALTHY")

    def test_10_primary_workflow_invariant_preservation(self):
        """
        PRIMARY WORKFLOW INVARIANT:
        Self-healing automated remediations, worker restarts, and provider failovers
        must NEVER delete, alter, or pollute canonical PostgreSQL SavedLead records.
        """
        initial_saved_count = self.db.query(SavedLead).count()

        engine = SelfHealingEngine()
        # Trigger and execute multiple playbooks
        engine.coordinator.trigger_incident("api.request.latency", 2500.0, 1500.0, auto_remediate=True)
        engine.coordinator.trigger_incident("cache.memory.high", 92.0, 85.0, auto_remediate=True)

        current_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(
            current_saved_count,
            initial_saved_count,
            "CRITICAL INVARIANT VIOLATION: Self-healing operations altered canonical SavedLead table!"
        )


if __name__ == "__main__":
    unittest.main()
