"""
LeadNexus AI X — Phase 35 Test Suite (ChatGPT Master Roadmap)
Multi-Region Global Architecture, Tenant Region Affinity & Split-Brain Prevention
DEFAULT: ONE AUTHORIZED WRITE REGION. No uncontrolled multi-primary.
"""

import sys
import os
import uuid
import unittest
from fastapi.testclient import TestClient

# Ensure API and root are in python path
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
from app.models.multi_region import (
    RegionNode,
    TenantRegionAffinity,
    FailoverExecutionJob,
    RegionalHealthHeartbeat,
)
from app.security.tokens import create_access_token
from packages.multi_region import (
    SplitBrainGuard,
    GlobalTrafficRouter,
    FailoverOrchestrator,
    ReplicationLagThresholdExceededError,
    DataSovereigntyViolationError,
)


class TestPhase35MultiRegion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Multi-Region Org", slug="mr-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Multi-Region Workspace",
                slug="mr-ws",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="multi_region_admin@leadnexus.ai",
                hashed_password="mock_password",
                is_active=True,
                is_superuser=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        # Seed region nodes
        cls.sydney = cls.db.query(RegionNode).filter(RegionNode.id == "ap-southeast-2").first()
        if not cls.sydney:
            cls.sydney = RegionNode(
                id="ap-southeast-2",
                name="Asia Pacific (Sydney)",
                cloud_provider="AWS",
                status="ACTIVE",
                is_primary_write=True,
                latency_ms=11.2,
                replication_lag_seconds=0.0,
            )
            cls.db.add(cls.sydney)

        cls.singapore = cls.db.query(RegionNode).filter(RegionNode.id == "ap-southeast-1").first()
        if not cls.singapore:
            cls.singapore = RegionNode(
                id="ap-southeast-1",
                name="Asia Pacific (Singapore)",
                cloud_provider="AWS",
                status="ACTIVE",
                is_primary_write=False,
                latency_ms=75.0,
                replication_lag_seconds=0.08,
            )
            cls.db.add(cls.singapore)
        cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_single_authorized_write_region_default(self):
        """Invariant: Exactly one region is authorized as primary write node."""
        primaries = self.db.query(RegionNode).filter(RegionNode.is_primary_write == True).all()
        self.assertEqual(len(primaries), 1, "Exactly ONE region can hold primary write authorization.")

    def test_02_split_brain_guard_fencing_token_monotonicity(self):
        """Verifies that split brain guard increments epoch and binds token to promoted region."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2", initial_epoch=1)
        initial_token = guard.current_fence_token
        self.assertEqual(initial_token, "epoch-1-ap-southeast-2")

        new_token = guard.issue_new_fencing_token("ap-southeast-1")
        self.assertEqual(new_token, "epoch-2-ap-southeast-1")
        self.assertEqual(guard.authorized_write_region, "ap-southeast-1")
        self.assertEqual(guard.fencing_epoch, 2)

    def test_03_split_brain_write_permission_rejection(self):
        """Ensures write attempts targeting a read-only replica are rejected."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2", initial_epoch=1)
        ok, reason = guard.validate_write_permission("ap-southeast-1")
        self.assertFalse(ok)
        self.assertIn("Read-Only Replica", reason)

        ok_primary, _ = guard.validate_write_permission("ap-southeast-2")
        self.assertTrue(ok_primary)

    def test_04_data_sovereignty_au_only_enforcement(self):
        """Verifies that an AU_ONLY tenant cannot be routed outside Australia."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2")
        router = GlobalTrafficRouter(guard)

        # Illegal affinity: primary region outside Australia for AU_ONLY
        invalid_affinity = {
            "primary_region_id": "us-west-2",
            "data_residency_requirement": "AU_ONLY",
            "strict_sovereignty_enforced": True,
        }
        with self.assertRaises(DataSovereigntyViolationError):
            router.resolve_target_region("GET", invalid_affinity)

    def test_05_write_routing_to_primary_vs_read_to_replica(self):
        """Verifies read/write splitting where writes go to primary and reads go to nearest replica."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2")
        router = GlobalTrafficRouter(guard)

        affinity = {
            "primary_region_id": "ap-southeast-2",
            "failover_region_id": "ap-southeast-1",
            "data_residency_requirement": "GLOBAL",
            "strict_sovereignty_enforced": False,
        }

        # Write -> Pinned to authorized write primary
        target_w, meta_w = router.resolve_target_region("POST", affinity, client_country="SG")
        self.assertEqual(target_w, "ap-southeast-2")
        self.assertTrue(meta_w["is_write"])

        # Read -> Routed to Singapore for Singapore client
        target_r, meta_r = router.resolve_target_region("GET", affinity, client_country="SG")
        self.assertEqual(target_r, "ap-southeast-1")
        self.assertFalse(meta_r["is_write"])

    def test_06_controlled_failover_execution_and_fencing(self):
        """Tests controlled failover execution promoting standby node to write primary."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2", initial_epoch=1)
        orchestrator = FailoverOrchestrator(guard)

        job = orchestrator.execute_failover(
            db=self.db,
            source_region_id="ap-southeast-2",
            target_region_id="ap-southeast-1",
            initiated_by=str(self.user.id),
            job_type="PLANNED_FAILOVER",
            max_allowed_lag_s=1.0,
        )

        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(guard.authorized_write_region, "ap-southeast-1")
        self.assertTrue(job.split_brain_fence_token.startswith("epoch-2-ap-southeast-1"))

    def test_07_controlled_failback_execution(self):
        """Tests controlled failback returning write authority to original primary."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-1", initial_epoch=2)
        orchestrator = FailoverOrchestrator(guard)

        job = orchestrator.execute_failover(
            db=self.db,
            source_region_id="ap-southeast-1",
            target_region_id="ap-southeast-2",
            initiated_by=str(self.user.id),
            job_type="CONTROLLED_FAILBACK",
            max_allowed_lag_s=1.0,
        )

        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(guard.authorized_write_region, "ap-southeast-2")

    def test_08_failover_aborted_when_replication_lag_exceeded(self):
        """Tests that failover is aborted if replication lag exceeds threshold (Zero Data Loss Gate)."""
        guard = SplitBrainGuard(initial_write_region="ap-southeast-2")
        orchestrator = FailoverOrchestrator(guard)

        # Temporarily set high lag on target
        self.singapore.replication_lag_seconds = 2.5
        self.db.commit()

        with self.assertRaises(ReplicationLagThresholdExceededError):
            orchestrator.execute_failover(
                db=self.db,
                source_region_id="ap-southeast-2",
                target_region_id="ap-southeast-1",
                initiated_by=str(self.user.id),
                job_type="PLANNED_FAILOVER",
                max_allowed_lag_s=1.0,
            )

        # Reset lag to healthy
        self.singapore.replication_lag_seconds = 0.05
        self.db.commit()

    def test_09_regional_heartbeat_recording(self):
        """Tests ingestion of replica heartbeat telemetry."""
        hb = RegionalHealthHeartbeat(
            id=str(uuid.uuid4()),
            region_id="ap-southeast-1",
            database_replica_status="HEALTHY",
            replication_lag_bytes=1024,
            replication_lag_seconds=0.03,
            queue_depth=5,
            p99_latency_ms=28.5,
            error_rate_pct=0.0,
        )
        self.db.add(hb)
        self.db.commit()

        stored = self.db.query(RegionalHealthHeartbeat).filter(RegionalHealthHeartbeat.id == hb.id).first()
        self.assertIsNotNone(stored)
        self.assertEqual(stored.region_id, "ap-southeast-1")

    def test_10_api_endpoints_integration(self):
        """Tests REST API endpoints for nodes, tenant affinity, routing decision, and heartbeat."""
        # 1. List nodes
        nodes_res = self.client.get("/api/v1/multi-region/nodes")
        self.assertEqual(nodes_res.status_code, 200)
        self.assertTrue(len(nodes_res.json()) >= 2)

        # 2. Get tenant affinity
        aff_res = self.client.get("/api/v1/multi-region/tenant-affinity", headers=self.headers)
        self.assertEqual(aff_res.status_code, 200)
        self.assertEqual(aff_res.json()["data_residency_requirement"], "AU_ONLY")

        # 3. Routing decision
        route_res = self.client.post(
            "/api/v1/multi-region/routing-decision",
            json={"method": "POST", "client_country": "AU"},
            headers=self.headers,
        )
        self.assertEqual(route_res.status_code, 200)
        self.assertTrue(route_res.json()["is_write"])

        # 4. Ingest heartbeat
        hb_res = self.client.post(
            "/api/v1/multi-region/heartbeat",
            json={
                "region_id": "ap-southeast-2",
                "database_replica_status": "HEALTHY",
                "replication_lag_seconds": 0.01,
            },
        )
        self.assertEqual(hb_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()

