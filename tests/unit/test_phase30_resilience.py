"""
LeadNexus AI X - Phase 30: Enterprise Reliability, Resilience & Disaster Recovery Unit Tests
Verifies distributed task leases, fencing tokens, zombie cleanup, DLQ classification & redrive,
circuit breaker state machine, backup cryptographic verification, and self-healing automation.
"""

import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.db.base import Base
from app.db.session import sync_engine, SessionLocal
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.resilience import (
    BackupSnapshot,
    BackupStatus,
    CircuitBreakerState,
    CircuitState,
    DeadLetterMessage,
    DLQStatus,
    IncidentSeverity,
    IncidentStatus,
    PlatformIncident,
    SelfHealingAction,
    TaskLease,
)
from packages.resilience.backup_and_disaster_recovery import (
    BackupAndDisasterRecoveryService,
)
from packages.resilience.circuit_breaker_service import CircuitBreakerService
from packages.resilience.dead_letter_queue_service import (
    DLQClassifier,
    DeadLetterQueueService,
)
from packages.resilience.distributed_lease_manager import DistributedLeaseManager
from packages.resilience.self_healing_engine import SelfHealingEngine


class TestPhase30Resilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Resilience Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Resilience Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="sre_lead@leadnexus.test",
                name="SRE Lead Engineer",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. Distributed Lease Manager ---

    def test_01_lease_manager_acquire_new_lease(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        ok, lease, err = mgr.acquire_lease(task_id, worker_id="worker_01", ttl_seconds=60)
        self.assertTrue(ok)
        self.assertEqual(lease.worker_id, "worker_01")
        self.assertEqual(lease.fencing_token, 1)
        self.assertTrue(lease.is_active)

    def test_02_lease_manager_acquire_conflict(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        ok1, _, _ = mgr.acquire_lease(task_id, worker_id="worker_01", ttl_seconds=60)
        self.assertTrue(ok1)

        # Worker 2 attempts to acquire active lease -> conflict
        ok2, lease2, err2 = mgr.acquire_lease(task_id, worker_id="worker_02", ttl_seconds=60)
        self.assertFalse(ok2)
        self.assertIsNone(lease2)
        self.assertIn("leased to worker 'worker_01'", err2)

    def test_03_lease_manager_renew_lease(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        ok, lease, _ = mgr.acquire_lease(task_id, worker_id="worker_01", ttl_seconds=30)
        initial_heartbeats = lease.heartbeat_count

        renewed = mgr.renew_lease(task_id, "worker_01", lease.fencing_token, ttl_seconds=60)
        self.assertTrue(renewed)
        self.db.refresh(lease)
        self.assertEqual(lease.heartbeat_count, initial_heartbeats + 1)

    def test_04_lease_manager_release_lease(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        ok, lease, _ = mgr.acquire_lease(task_id, worker_id="worker_01", ttl_seconds=60)
        self.assertTrue(lease.is_active)

        released = mgr.release_lease(task_id, "worker_01", lease.fencing_token)
        self.assertTrue(released)
        self.db.refresh(lease)
        self.assertFalse(lease.is_active)

    def test_05_lease_manager_stale_lease_takeover(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        # Acquire expired lease
        ok1, lease1, _ = mgr.acquire_lease(task_id, worker_id="worker_01", ttl_seconds=-10)
        self.assertTrue(ok1)
        self.assertEqual(lease1.fencing_token, 1)

        # Worker 2 takes over stale lease -> token increments to 2
        ok2, lease2, _ = mgr.acquire_lease(task_id, worker_id="worker_02", ttl_seconds=60)
        self.assertTrue(ok2)
        self.assertEqual(lease2.worker_id, "worker_02")
        self.assertEqual(lease2.fencing_token, 2)

    def test_06_lease_manager_reap_stale_leases(self):
        mgr = DistributedLeaseManager(self.db)
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        mgr.acquire_lease(task_id, worker_id="dead_worker", ttl_seconds=-5)

        reaped = mgr.reap_stale_leases()
        self.assertIn(task_id, reaped)

    # --- 2. DLQ Error Classifier & Queue Service ---

    def test_07_dlq_classifier_rate_limit(self):
        self.assertEqual(DLQClassifier.classify_error("HTTP 429 Too Many Requests"), "RATE_LIMIT")
        self.assertEqual(DLQClassifier.classify_error("Rate limit quota exceeded"), "RATE_LIMIT")

    def test_08_dlq_classifier_auth_failure(self):
        self.assertEqual(DLQClassifier.classify_error("401 Unauthorized access"), "UPSTREAM_AUTH_FAILURE")
        self.assertEqual(DLQClassifier.classify_error("403 Forbidden token"), "UPSTREAM_AUTH_FAILURE")

    def test_09_dlq_classifier_schema_corruption(self):
        self.assertEqual(DLQClassifier.classify_error("Invalid json schema received"), "SCHEMA_CORRUPTION")
        self.assertEqual(DLQClassifier.classify_error("JSON decode error"), "SCHEMA_CORRUPTION")

    def test_10_dlq_classifier_network_transient(self):
        self.assertEqual(DLQClassifier.classify_error("Gateway timeout connecting to upstream"), "NETWORK_TRANSIENT")
        self.assertEqual(DLQClassifier.classify_error("503 Service Unavailable"), "NETWORK_TRANSIENT")

    def test_11_dlq_quarantine_message(self):
        dlq_svc = DeadLetterQueueService(self.db)
        msg = dlq_svc.quarantine_message(
            queue_name="test_crawler_queue",
            task_id="crawl_task_99",
            payload={"domain": "example.com"},
            error_message="Connection timed out after 30s",
            workspace_id=self.workspace.id,
        )
        self.assertEqual(msg.status, DLQStatus.QUARANTINED.value)
        self.assertEqual(msg.error_category, "NETWORK_TRANSIENT")

    def test_12_dlq_redrive_message(self):
        dlq_svc = DeadLetterQueueService(self.db)
        msg = dlq_svc.quarantine_message(
            queue_name="test_queue",
            task_id="task_redrive_01",
            payload={},
            error_message="Temporary rate limit",
        )
        redriven = dlq_svc.redrive_message(msg.id)
        self.assertEqual(redriven.status, DLQStatus.REDRIVEN.value)

    def test_13_dlq_discard_message(self):
        dlq_svc = DeadLetterQueueService(self.db)
        msg = dlq_svc.quarantine_message(
            queue_name="test_queue",
            task_id="task_discard_01",
            payload={},
            error_message="Unrecoverable fatal syntax error",
        )
        discarded = dlq_svc.discard_message(msg.id)
        self.assertEqual(discarded.status, DLQStatus.DISCARDED.value)

    # --- 3. Circuit Breaker Service ---

    def test_14_circuit_breaker_initial_state(self):
        cb_svc = CircuitBreakerService(self.db)
        cb = cb_svc.get_or_create("service_github_test")
        self.assertEqual(cb.state, CircuitState.CLOSED.value)
        self.assertTrue(cb_svc.can_execute("service_github_test"))

    def test_15_circuit_breaker_tripping_to_open(self):
        cb_svc = CircuitBreakerService(self.db)
        svc_name = f"flaky_api_{uuid.uuid4().hex[:6]}"
        for _ in range(4):
            cb_svc.record_failure(svc_name, failure_threshold=5)
            self.assertTrue(cb_svc.can_execute(svc_name))

        # 5th failure trips circuit
        cb = cb_svc.record_failure(svc_name, failure_threshold=5)
        self.assertEqual(cb.state, CircuitState.OPEN.value)

    def test_16_circuit_breaker_blocking_execution_when_open(self):
        cb_svc = CircuitBreakerService(self.db)
        svc_name = f"open_api_{uuid.uuid4().hex[:6]}"
        cb = cb_svc.get_or_create(svc_name, cooldown_seconds=60)
        cb.state = CircuitState.OPEN.value
        cb.opened_at = datetime.now(timezone.utc)
        self.db.commit()

        # Cooldown has not expired -> execution blocked
        self.assertFalse(cb_svc.can_execute(svc_name))

    def test_17_circuit_breaker_half_open_transition(self):
        cb_svc = CircuitBreakerService(self.db)
        svc_name = f"half_open_api_{uuid.uuid4().hex[:6]}"
        cb = cb_svc.get_or_create(svc_name, cooldown_seconds=10)
        cb.state = CircuitState.OPEN.value
        # Opened 20 seconds ago -> cooldown expired
        cb.opened_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        self.db.commit()

        # can_execute transitions to HALF_OPEN to allow trial probe
        can_run = cb_svc.can_execute(svc_name)
        self.assertTrue(can_run)
        self.db.refresh(cb)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN.value)

    def test_18_circuit_breaker_recovery_on_success(self):
        cb_svc = CircuitBreakerService(self.db)
        svc_name = f"recovering_api_{uuid.uuid4().hex[:6]}"
        cb = cb_svc.get_or_create(svc_name)
        cb.state = CircuitState.HALF_OPEN.value
        self.db.commit()

        cb_recovered = cb_svc.record_success(svc_name)
        self.assertEqual(cb_recovered.state, CircuitState.CLOSED.value)
        self.assertEqual(cb_recovered.consecutive_failures, 0)

    # --- 4. Disaster Recovery & Backup Verification ---

    def test_19_backup_service_create_snapshot(self):
        dr_svc = BackupAndDisasterRecoveryService(self.db)
        data = b'{"records": [{"company": "Apex"}, {"company": "Nexus"}]}'
        snap = dr_svc.create_snapshot(
            snapshot_name="leadnexus_test_snap_01",
            storage_path="/backups/dr_test_01.json",
            records_count=2,
            data_bytes=data,
        )
        self.assertEqual(snap.records_count, 2)
        self.assertEqual(snap.size_bytes, len(data))
        self.assertEqual(len(snap.checksum_sha256), 64)
        self.assertEqual(snap.verification_status, BackupStatus.PENDING.value)

    def test_20_backup_service_verify_integrity_success(self):
        dr_svc = BackupAndDisasterRecoveryService(self.db)
        data = b'{"verified": true}'
        snap = dr_svc.create_snapshot("snap_verify_ok", "/backups/ok.json", 1, data)

        ok, updated_snap, err = dr_svc.verify_snapshot(snap.id, data)
        self.assertTrue(ok)
        self.assertEqual(updated_snap.verification_status, BackupStatus.VERIFIED.value)
        self.assertIsNone(err)

    def test_21_backup_service_verify_integrity_corrupted(self):
        dr_svc = BackupAndDisasterRecoveryService(self.db)
        clean_data = b'{"clean": true}'
        corrupted_data = b'{"clean": false, "tampered": true}'
        snap = dr_svc.create_snapshot("snap_corrupted", "/backups/corrupted.json", 1, clean_data)

        ok, updated_snap, err = dr_svc.verify_snapshot(snap.id, corrupted_data)
        self.assertFalse(ok)
        self.assertEqual(updated_snap.verification_status, BackupStatus.CORRUPTED.value)
        self.assertIn("Checksum mismatch", err)

    # --- 5. Self-Healing & Incident Management ---

    def test_22_self_healing_zombie_task_remediation(self):
        lease_mgr = DistributedLeaseManager(self.db)
        task_id = f"zombie_task_{uuid.uuid4().hex[:6]}"
        lease_mgr.acquire_lease(task_id, worker_id="crashed_worker", ttl_seconds=-10)

        healing = SelfHealingEngine(self.db)
        actions = healing.execute_zombie_task_remediation()
        self.assertTrue(any(a.details.get("task_id") == task_id for a in actions))

    def test_23_incident_lifecycle(self):
        healing = SelfHealingEngine(self.db)
        inc = healing.create_incident(
            title="External Job Feed Degraded Outage",
            severity=IncidentSeverity.MAJOR,
            affected_components=["job_feed_connector", "enrichment_service"],
            root_cause="Upstream API 503 outage",
        )
        self.assertEqual(inc.status, IncidentStatus.INVESTIGATING.value)

        # Update to IDENTIFIED
        healing.update_incident_status(inc.id, IncidentStatus.IDENTIFIED)
        self.db.refresh(inc)
        self.assertEqual(inc.status, IncidentStatus.IDENTIFIED.value)

        # Resolve
        healing.update_incident_status(inc.id, IncidentStatus.RESOLVED, root_cause="Upstream fixed routing")
        self.db.refresh(inc)
        self.assertEqual(inc.status, IncidentStatus.RESOLVED.value)
        self.assertIsNotNone(inc.resolved_at)


if __name__ == "__main__":
    unittest.main()
