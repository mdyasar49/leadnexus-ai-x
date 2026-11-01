"""
LeadNexus AI X — Phase 36 Test Suite (ChatGPT Master Roadmap)
Enterprise Event-Driven Architecture, CQRS, Selective Event Sourcing,
Schema Registry & Compatibility, and Dead Letter Queue (DLQ) Management.
"""

import sys
import os
import uuid
import unittest
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
from app.models.cqrs_event_sourcing import (
    EventSchemaRecord,
    AggregateEvent,
    AggregateSnapshot,
    CommandIdempotencyRecord,
    DeadLetterEvent,
    SchemaCompatibility,
    CommandStatus,
    DLQReason,
    DLQStatus,
)
from app.security.tokens import create_access_token
from packages.events import (
    EventSchemaRegistry,
    BreakingSchemaEvolutionError,
    SchemaValidationError,
    EventSourcingEngine,
    ConcurrencyConflictError,
    CQRSCommandBus,
    CommandExecutionError,
    DeadLetterManager,
    EventLoopDetectedError,
)


class TestPhase36EventDrivenCQRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Event Org", slug="event-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.ws = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.ws:
            cls.ws = Workspace(id=str(uuid.uuid4()), organization_id=cls.org.id, name="Event Workspace", slug="event-ws")
            cls.db.add(cls.ws)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="event-architect@leadnexus.io",
                hashed_password="hash",
                full_name="Event Architect",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}", "X-Workspace-ID": cls.ws.id}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_schema_registry_and_validation(self):
        """Test registering a schema, computing fingerprint, and validating payloads."""
        schema = {
            "type": "object",
            "required": ["company_id", "company_name", "lead_score"],
            "properties": {
                "company_id": {"type": "string"},
                "company_name": {"type": "string"},
                "lead_score": {"type": "integer"},
            }
        }
        record = EventSchemaRegistry.register_schema(
            db=self.db,
            event_type="lead.qualified",
            version="1.0.0",
            schema_definition=schema,
        )
        self.assertEqual(record.version, "1.0.0")
        self.assertTrue(len(record.fingerprint) == 64)

        # Valid payload
        valid_payload = {"company_id": "c1", "company_name": "Acme", "lead_score": 85}
        self.assertTrue(EventSchemaRegistry.validate_payload(self.db, "lead.qualified", "1.0.0", valid_payload))

        # Missing required field
        invalid_payload = {"company_id": "c1", "lead_score": 85}
        with self.assertRaises(SchemaValidationError):
            EventSchemaRegistry.validate_payload(self.db, "lead.qualified", "1.0.0", invalid_payload)

    def test_02_breaking_schema_change_detection(self):
        """Test that removing a required field without BREAKING compatibility is rejected."""
        # Initial schema with required 'industry'
        schema_v1 = {
            "type": "object",
            "required": ["company_id", "industry"],
            "properties": {"company_id": {"type": "string"}, "industry": {"type": "string"}}
        }
        EventSchemaRegistry.register_schema(self.db, "company.profile.updated", "1.0.0", schema_v1)

        # Attempt to register v1.1.0 which drops 'industry' under BACKWARD_COMPATIBLE
        schema_v2 = {
            "type": "object",
            "required": ["company_id"],
            "properties": {"company_id": {"type": "string"}}
        }
        with self.assertRaises(BreakingSchemaEvolutionError):
            EventSchemaRegistry.register_schema(
                self.db,
                "company.profile.updated",
                "1.1.0",
                schema_v2,
                compatibility=SchemaCompatibility.BACKWARD_COMPATIBLE
            )

    def test_03_cqrs_command_bus_and_idempotency(self):
        """Test CQRS command execution and idempotent replay avoidance."""
        idempotency_key = f"cmd_key_{uuid.uuid4().hex}"
        call_count = {"count": 0}

        def handler(payload):
            call_count["count"] += 1
            return {"status": "SUCCESS", "allocated_credits": payload["amount"] * 10}

        # First execution
        res1, is_cached1 = CQRSCommandBus.dispatch(
            db=self.db,
            tenant_id=self.ws.id,
            actor_id=self.user.id,
            idempotency_key=idempotency_key,
            command_name="AllocateResearchCredits",
            payload={"amount": 50},
            handler=handler,
        )
        self.assertFalse(is_cached1)
        self.assertEqual(res1["allocated_credits"], 500)
        self.assertEqual(call_count["count"], 1)

        # Duplicate command dispatch with same idempotency key
        res2, is_cached2 = CQRSCommandBus.dispatch(
            db=self.db,
            tenant_id=self.ws.id,
            actor_id=self.user.id,
            idempotency_key=idempotency_key,
            command_name="AllocateResearchCredits",
            payload={"amount": 50},
            handler=handler,
        )
        self.assertTrue(is_cached2)
        self.assertEqual(res2["allocated_credits"], 500)
        # Handler was NOT called a second time!
        self.assertEqual(call_count["count"], 1)

    def test_04_event_sourcing_state_reconstruction_and_snapshots(self):
        """Test event append, snapshot creation, and state reconstruction."""
        agg_id = f"lead_{uuid.uuid4().hex[:8]}"

        # 1. Append Event 1: LeadCreated
        EventSourcingEngine.append_event(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="Lead",
            aggregate_id=agg_id,
            event_type="LeadCreated",
            payload={"name": "CloudCorp Pty Ltd", "status": "NEW", "score": 10},
            correlation_id="corr-1",
        )

        # 2. Append Event 2: LeadScored
        EventSourcingEngine.append_event(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="Lead",
            aggregate_id=agg_id,
            event_type="LeadScored",
            payload={"score": 85, "priority": "P1_HIGH"},
            correlation_id="corr-2",
        )

        # 3. Create snapshot at sequence 2
        snapshot_state = {"name": "CloudCorp Pty Ltd", "status": "NEW", "score": 85, "priority": "P1_HIGH"}
        EventSourcingEngine.create_snapshot(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="Lead",
            aggregate_id=agg_id,
            state=snapshot_state,
            last_sequence_number=2,
        )

        # 4. Append Event 3: LeadQualified
        EventSourcingEngine.append_event(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="Lead",
            aggregate_id=agg_id,
            event_type="LeadQualified",
            payload={"status": "QUALIFIED"},
            correlation_id="corr-3",
        )

        # 5. Rebuild state: should read snapshot (seq 2) + apply Event 3 (seq 3)
        reconstructed, latest_seq = EventSourcingEngine.rebuild_aggregate_state(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="Lead",
            aggregate_id=agg_id,
        )

        self.assertEqual(latest_seq, 3)
        self.assertEqual(reconstructed["name"], "CloudCorp Pty Ltd")
        self.assertEqual(reconstructed["score"], 85)
        self.assertEqual(reconstructed["status"], "QUALIFIED")

    def test_05_optimistic_concurrency_control(self):
        """Test that appending with mismatched expected version raises ConcurrencyConflictError."""
        agg_id = f"research_{uuid.uuid4().hex[:8]}"
        EventSourcingEngine.append_event(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="ResearchRun",
            aggregate_id=agg_id,
            event_type="RunStarted",
            payload={"status": "RUNNING"},
            correlation_id="corr-c1",
        )

        # Current version is 1, expect version 0 should fail
        with self.assertRaises(ConcurrencyConflictError):
            EventSourcingEngine.append_event(
                db=self.db,
                tenant_id=self.ws.id,
                aggregate_type="ResearchRun",
                aggregate_id=agg_id,
                event_type="RunPaused",
                payload={"status": "PAUSED"},
                correlation_id="corr-c2",
                expected_version=0,
            )

    def test_06_dlq_quarantine_redrive_and_discard(self):
        """Test DLQ quarantine, redrive, and discard lifecycle."""
        ev_id = f"ev_{uuid.uuid4().hex}"
        dlq_entry = DeadLetterManager.quarantine(
            db=self.db,
            tenant_id=self.ws.id,
            original_event_id=ev_id,
            event_type="contact.verification.failed",
            consumer_name="contact_verification_worker",
            reason=DLQReason.TIMEOUT,
            error_details="SMTP connection socket timeout after 10000ms",
            payload={"email": "cxo@targetcorp.com", "contact_id": "cont-1"},
        )
        self.assertEqual(dlq_entry.status, DLQStatus.UNRESOLVED)
        self.assertEqual(dlq_entry.retry_count, 0)

        # Redrive successfully
        success = DeadLetterManager.redrive_event(
            db=self.db,
            dlq_id=dlq_entry.id,
            consumer_fn=lambda p: True
        )
        self.assertTrue(success)
        self.assertEqual(dlq_entry.status, DLQStatus.RETRIED)

        # Discard another poison pill
        dlq_pill = DeadLetterManager.quarantine(
            db=self.db,
            tenant_id=self.ws.id,
            original_event_id=f"ev_pill_{uuid.uuid4().hex}",
            event_type="malformed.data",
            consumer_name="parser_worker",
            reason=DLQReason.SCHEMA_ERROR,
            error_details="Unrecoverable null pointer in body",
            payload={"bad": None},
        )
        discarded = DeadLetterManager.discard(self.db, dlq_pill.id, "Permanent bad format")
        self.assertEqual(discarded.status, DLQStatus.DISCARDED)

    def test_07_loop_prevention_depth_limit(self):
        """Test that event propagation exceeding max_depth (5) raises EventLoopDetectedError."""
        with self.assertRaises(EventLoopDetectedError):
            DeadLetterManager.verify_propagation_depth(current_depth=6)

        # Cycle in causation chain raises error
        with self.assertRaises(EventLoopDetectedError):
            DeadLetterManager.verify_propagation_depth(
                current_depth=3,
                causation_ids=["ev-1", "ev-2", "ev-1"]  # ev-1 appears twice!
            )

    def test_08_api_schemas_and_commands(self):
        """Test FastAPI endpoints for schema management and CQRS commands."""
        # 1. Register Schema API
        schema_def = {
            "type": "object",
            "required": ["run_id", "status"],
            "properties": {"run_id": {"type": "string"}, "status": {"type": "string"}}
        }
        res_schema = self.client.post(
            "/api/v1/events/schemas",
            json={
                "event_type": "workflow.execution.completed",
                "version": "1.0.0",
                "schema_definition": schema_def,
                "compatibility": "BACKWARD_COMPATIBLE"
            },
            headers=self.headers,
        )
        self.assertEqual(res_schema.status_code, 201)
        self.assertIn("fingerprint", res_schema.json())

        # 2. Dispatch Command API
        cmd_key = f"api_cmd_{uuid.uuid4().hex}"
        res_cmd = self.client.post(
            "/api/v1/events/commands",
            json={
                "idempotency_key": cmd_key,
                "command_name": "TriggerWorkflowAction",
                "payload": {"workflow_id": "wf-101", "action": "NOTIFY_SALES"}
            },
            headers=self.headers,
        )
        self.assertEqual(res_cmd.status_code, 200)
        self.assertFalse(res_cmd.json()["is_cached"])

        # Re-dispatch with same key
        res_cmd_replay = self.client.post(
            "/api/v1/events/commands",
            json={
                "idempotency_key": cmd_key,
                "command_name": "TriggerWorkflowAction",
                "payload": {"workflow_id": "wf-101", "action": "NOTIFY_SALES"}
            },
            headers=self.headers,
        )
        self.assertEqual(res_cmd_replay.status_code, 200)
        self.assertTrue(res_cmd_replay.json()["is_cached"])

    def test_09_api_aggregate_history_and_simulation(self):
        """Test API endpoints for aggregate event history and simulation sandbox."""
        agg_id = f"comp_{uuid.uuid4().hex[:8]}"

        # Record an event
        EventSourcingEngine.append_event(
            db=self.db,
            tenant_id=self.ws.id,
            aggregate_type="CompanyProfile",
            aggregate_id=agg_id,
            event_type="DomainObserved",
            payload={"domain": "sydneycloud.com.au", "tier": "ENTERPRISE"},
            correlation_id="corr-sim",
        )

        res_hist = self.client.get(
            f"/api/v1/events/aggregates/CompanyProfile/{agg_id}/history",
            headers=self.headers,
        )
        self.assertEqual(res_hist.status_code, 200)
        hist_data = res_hist.json()
        self.assertEqual(hist_data["current_version"], 1)
        self.assertEqual(len(hist_data["events"]), 1)

        # Simulation endpoint
        res_sim = self.client.post(
            "/api/v1/events/simulate",
            json={
                "event_type": "lead.intent.detected",
                "payload": {"intent_score": 92, "category": "Odoo Migration"}
            },
            headers=self.headers,
        )
        self.assertEqual(res_sim.status_code, 200)
        sim_data = res_sim.json()
        self.assertEqual(sim_data["simulation_status"], "SUCCESS")
        self.assertTrue(sim_data["zero_production_mutation"])
        self.assertGreater(len(sim_data["predicted_side_effects"]), 0)


if __name__ == "__main__":
    unittest.main()
