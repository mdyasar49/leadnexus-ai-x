"""
Unit Test Suite for Phase 34: Enterprise Event-Driven Architecture.
Verifies Transactional Outbox, Event Envelope Checksum, Idempotent Consumers,
Pattern Pub/Sub, DLQ routing, Audited Replay, and Tenant Isolation.
"""

import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.db.session import SessionLocal
from app.models.events import (
    OutboxEvent,
    OutboxStatus,
    EventSubscription,
    ConsumerOffset,
    EventReplayJob,
    ReplayStatus,
)
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.security.tokens import create_access_token
from packages.events.event_envelope import EventEnvelope
from packages.events.event_bus import EnterpriseEventBus
from packages.events.outbox_publisher import TransactionalOutboxService
from packages.events.idempotent_consumer import IdempotentConsumerManager
from packages.events.event_replay_engine import EventReplayService
from fastapi.testclient import TestClient
from app.main import app


class TestPhase34EnterpriseEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Events Test Org", slug=f"evt-org-{uuid.uuid4().hex[:6]}")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Events Test Workspace",
                slug=f"evt-ws-{uuid.uuid4().hex[:6]}",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.tenant_id = cls.workspace.id
        cls.tenant_b_id = f"tenant_b_{uuid.uuid4().hex[:8]}"

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email=f"event_admin_{uuid.uuid4().hex[:6]}@leadnexus.io",
                first_name="Event",
                last_name="Architect",
                password_hash="test_argon2_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.client = TestClient(app)
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.db.query(OutboxEvent).filter(OutboxEvent.tenant_id.in_([cls.tenant_id, cls.tenant_b_id])).delete(synchronize_session=False)
        cls.db.query(EventReplayJob).filter(EventReplayJob.tenant_id.in_([cls.tenant_id, cls.tenant_b_id])).delete(synchronize_session=False)
        cls.db.query(EventSubscription).filter(EventSubscription.tenant_id.in_([cls.tenant_id, cls.tenant_b_id])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_01_event_envelope_checksum_verification(self):
        envelope = EventEnvelope(
            event_type="company.resolved",
            tenant_id=self.tenant_id,
            aggregate_type="COMPANY",
            aggregate_id="comp_001",
            payload={"name": "Pacific Retail Pty Ltd", "odoo_detected": True},
        )
        self.assertIsNotNone(envelope.checksum)
        self.assertTrue(envelope.verify_checksum())

        # Tamper with payload
        envelope.payload["odoo_detected"] = False
        self.assertFalse(envelope.verify_checksum())

    def test_02_transactional_outbox_staging(self):
        event = TransactionalOutboxService.stage_event(
            db=self.db,
            tenant_id=self.tenant_id,
            event_type="lead.scored",
            aggregate_type="LEAD",
            aggregate_id="lead_001",
            payload={"score": 88.5, "priority": "HIGH"},
            correlation_id="corr_test_02",
        )
        self.db.commit()
        self.db.refresh(event)

        self.assertEqual(event.status, OutboxStatus.PENDING)
        self.assertEqual(event.aggregate_id, "lead_001")
        self.assertIsNotNone(event.checksum)

    def test_03_outbox_publisher_delivery(self):
        event = TransactionalOutboxService.stage_event(
            db=self.db,
            tenant_id=self.tenant_id,
            event_type="signal.detected",
            aggregate_type="SIGNAL",
            aggregate_id="sig_001",
            payload={"source": "github", "confidence": 0.95},
            correlation_id="corr_test_03",
        )
        self.db.commit()

        publish_res = TransactionalOutboxService.publish_pending(self.db, batch_size=10)
        self.assertGreaterEqual(publish_res["published"], 1)

        self.db.refresh(event)
        self.assertEqual(event.status, OutboxStatus.PUBLISHED)
        self.assertIsNotNone(event.published_at)

    def test_04_pattern_based_event_bus_dispatch(self):
        bus = EnterpriseEventBus()
        received_events = []

        bus.subscribe("test-consumer", "company.*", lambda env: received_events.append(env.event_type))

        env1 = EventEnvelope(
            event_type="company.created",
            tenant_id=self.tenant_id,
            aggregate_type="COMPANY",
            aggregate_id="c1",
            payload={"name": "Test"},
        )
        env2 = EventEnvelope(
            event_type="lead.created",
            tenant_id=self.tenant_id,
            aggregate_type="LEAD",
            aggregate_id="l1",
            payload={"lead": "Test"},
        )

        bus.publish(env1)
        bus.publish(env2)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0], "company.created")

    def test_05_idempotent_consumer_offset_tracking(self):
        consumer_name = f"worker_{uuid.uuid4().hex[:6]}"
        event_id = str(uuid.uuid4())

        self.assertFalse(IdempotentConsumerManager.is_duplicate(self.db, consumer_name, event_id))

        offset = IdempotentConsumerManager.record_processed(self.db, consumer_name, event_id)
        self.assertEqual(offset.last_processed_event_id, event_id)
        self.assertEqual(offset.processed_count, 1)

        # Immediate re-check must indicate duplicate
        self.assertTrue(IdempotentConsumerManager.is_duplicate(self.db, consumer_name, event_id))

    def test_06_dead_letter_queue_routing(self):
        bus = EnterpriseEventBus()

        def failing_handler(env):
            raise RuntimeError("Database connection timed out during event processing")

        bus.subscribe("failing-consumer", "error.*", failing_handler, max_retries=2)

        envelope = EventEnvelope(
            event_type="error.simulation",
            tenant_id=self.tenant_id,
            aggregate_type="TEST",
            aggregate_id="t1",
            payload={"status": "fail"},
        )

        res = bus.publish(envelope)
        self.assertEqual(res["failed_count"], 1)

        dlq = bus.get_dlq_records()
        self.assertGreaterEqual(len(dlq), 1)
        self.assertEqual(dlq[-1]["consumer_name"], "failing-consumer")

    def test_07_audited_event_replay_dry_run(self):
        now = datetime.now(timezone.utc)
        job = EventReplayService.create_replay_job(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user.id,
            target_consumer="analytics-indexer",
            from_timestamp=now - timedelta(hours=1),
            to_timestamp=now + timedelta(hours=1),
            dry_run=True,
        )

        res = EventReplayService.execute_replay_job(self.db, job.id)
        self.assertEqual(res["status"], ReplayStatus.COMPLETED.value)
        self.assertTrue(res["dry_run"])

    def test_08_audited_event_replay_execution(self):
        now = datetime.now(timezone.utc)
        job = EventReplayService.create_replay_job(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user.id,
            target_consumer="graph-projector",
            from_timestamp=now - timedelta(hours=1),
            to_timestamp=now + timedelta(hours=1),
            dry_run=False,
        )

        res = EventReplayService.execute_replay_job(self.db, job.id)
        self.assertEqual(res["status"], ReplayStatus.COMPLETED.value)
        self.assertFalse(res["dry_run"])

    def test_09_tenant_isolation_on_event_streams(self):
        # Tenant B event
        event_b = TransactionalOutboxService.stage_event(
            db=self.db,
            tenant_id=self.tenant_b_id,
            event_type="secret.event",
            aggregate_type="CONFIDENTIAL",
            aggregate_id="conf_001",
            payload={"secret": "value"},
            correlation_id="corr_b_01",
        )
        self.db.commit()

        # Query outbox for Tenant A
        tenant_a_events = (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.tenant_id == self.tenant_id)
            .all()
        )
        tenant_a_ids = [e.event_id for e in tenant_a_events]
        self.assertNotIn(event_b.event_id, tenant_a_ids)

    def test_10_api_publish_and_outbox_query(self):
        payload = {
            "event_type": "api.test.event",
            "aggregate_type": "TEST",
            "aggregate_id": "test_api_001",
            "payload": {"message": "Hello Event Bus"},
            "flush_immediately": True,
        }
        res_post = self.client.post("/api/v1/events/publish", json=payload, headers=self.headers)
        self.assertEqual(res_post.status_code, 201)
        event_id = res_post.json()["event_id"]

        res_get = self.client.get(f"/api/v1/events/outbox/{event_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["event_type"], "api.test.event")


if __name__ == "__main__":
    unittest.main()
