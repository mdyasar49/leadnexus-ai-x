"""
LeadNexus AI X - Phase 43 Test Suite (ChatGPT Master Roadmap)
Autonomous Orchestration & Long-Running Mission Engine
Tests: DAG topological sorting, cycle detection, worker pool priority dispatch,
state checkpointing, mission lifecycle, human-in-the-loop review, and workflow invariants.
"""

import sys
import os
import uuid
import unittest
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
from app.models.autonomous_orchestration import (
    MissionRecord,
    MissionStepRecord,
    MissionCheckpoint,
    MissionHumanReviewItem,
)
from app.security.tokens import create_access_token
from packages.orchestration import (
    DAGScheduler,
    DAGStep,
    CycleDetectedError,
    CheckpointManager,
    MissionStateSnapshot,
    WorkerPool,
    TaskPriority,
    MissionEngine,
    MissionStatus,
    StepStatus,
)


class TestPhase43AutonomousOrchestration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Orchestration Org", slug="orch-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                name="Orchestration Workspace",
                slug="orch-workspace",
                organization_id=cls.org.id,
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="mission_commander@leadnexus.internal",
                first_name="Mission",
                last_name="Commander",
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

    def test_01_dag_validation_and_topological_sort(self):
        """Validates that a linear/branching DAG correctly resolves in topological order."""
        steps = [
            DAGStep("step_c", "Analyze Tech Stack", "TechnologyAgent", dependencies=["step_a"]),
            DAGStep("step_a", "Discover Companies", "ResearchAgent", dependencies=[]),
            DAGStep("step_b", "Enrich Contacts", "ContactAgent", dependencies=["step_a"]),
            DAGStep("step_d", "Final Quality Review", "ReviewAgent", dependencies=["step_b", "step_c"]),
        ]
        sorted_order = DAGScheduler.validate_and_sort(steps)
        self.assertEqual(sorted_order[0], "step_a")
        self.assertEqual(sorted_order[-1], "step_d")
        self.assertTrue(sorted_order.index("step_a") < sorted_order.index("step_b"))
        self.assertTrue(sorted_order.index("step_a") < sorted_order.index("step_c"))
        self.assertTrue(sorted_order.index("step_b") < sorted_order.index("step_d"))

    def test_02_dag_cycle_detection(self):
        """Validates that circular dependencies raise CycleDetectedError."""
        cyclic_steps = [
            DAGStep("node_1", "Task 1", "ResearchAgent", dependencies=["node_3"]),
            DAGStep("node_2", "Task 2", "CompanyAgent", dependencies=["node_1"]),
            DAGStep("node_3", "Task 3", "ReviewAgent", dependencies=["node_2"]),
        ]
        with self.assertRaises(CycleDetectedError):
            DAGScheduler.validate_and_sort(cyclic_steps)

    def test_03_dag_ready_steps_and_dependency_resolution(self):
        """Validates that steps only become ready when all dependencies are COMPLETED."""
        steps = [
            DAGStep("step_1", "Ingest", "ResearchAgent"),
            DAGStep("step_2", "Extract", "CompanyAgent", dependencies=["step_1"]),
            DAGStep("step_3", "Score", "ScoringAgent", dependencies=["step_2"]),
        ]
        # Initially only step_1 is ready
        statuses = {"step_1": "PENDING", "step_2": "PENDING", "step_3": "PENDING"}
        ready = DAGScheduler.get_ready_steps(steps, statuses)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].step_id, "step_1")

        # Once step_1 is COMPLETED, step_2 becomes ready
        statuses["step_1"] = "COMPLETED"
        statuses["step_2"] = "PENDING"
        ready = DAGScheduler.get_ready_steps(steps, statuses)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].step_id, "step_2")

    def test_04_worker_pool_priority_queuing(self):
        """Validates that worker pool dispatches tasks strictly according to priority weight."""
        pool = WorkerPool(max_concurrency=2)
        pool.enqueue("s_low", "m1", "Agent", priority=TaskPriority.LOW)
        pool.enqueue("s_crit", "m1", "Agent", priority=TaskPriority.CRITICAL)
        pool.enqueue("s_norm", "m1", "Agent", priority=TaskPriority.NORMAL)
        pool.enqueue("s_high", "m1", "Agent", priority=TaskPriority.HIGH)

        # First dispatch must be CRITICAL
        w1, t1 = pool.poll_and_dispatch()
        self.assertEqual(t1.step_id, "s_crit")

        # Second dispatch must be HIGH
        w2, t2 = pool.poll_and_dispatch()
        self.assertEqual(t2.step_id, "s_high")

        # Concurrency limit reached
        self.assertEqual(pool.available_slots, 0)
        self.assertIsNone(pool.poll_and_dispatch())

        # Complete w1, next should be NORMAL
        pool.complete_task(w1, status="COMPLETED")
        w3, t3 = pool.poll_and_dispatch()
        self.assertEqual(t3.step_id, "s_norm")

    def test_05_checkpoint_manager_save_and_restore(self):
        """Validates sequential snapshot saving, hash computation, and restoration."""
        mgr = CheckpointManager()
        s1 = mgr.save_checkpoint(
            mission_id="m-test-1",
            status="RUNNING",
            step_statuses={"step_1": "COMPLETED", "step_2": "RUNNING"},
            step_outputs={"step_1": {"leads_found": 15}},
            context_variables={"region": "EMEA"},
            reason="STEP_COMPLETED",
        )
        self.assertEqual(s1.checkpoint_number, 1)
        self.assertEqual(len(s1.compute_hash()), 64)

        s2 = mgr.save_checkpoint(
            mission_id="m-test-1",
            status="PAUSED",
            step_statuses={"step_1": "COMPLETED", "step_2": "PAUSED"},
            step_outputs={"step_1": {"leads_found": 15}},
            context_variables={"region": "EMEA"},
            reason="USER_PAUSE",
        )
        self.assertEqual(s2.checkpoint_number, 2)

        # Restore from checkpoint 1
        restored = mgr.restore_from_checkpoint("m-test-1", s1.checkpoint_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.checkpoint_number, 1)
        self.assertEqual(restored.status, "RUNNING")

    def test_06_mission_engine_lifecycle_execution(self):
        """Validates end-to-end execution lifecycle of a mission."""
        engine = MissionEngine(max_concurrency=4)
        steps = [
            DAGStep("step_1", "Search Companies", "ResearchAgent"),
            DAGStep("step_2", "Extract Key People", "PersonAgent", dependencies=["step_1"]),
        ]
        mission = engine.create_mission("APAC Expansion", "Identify top tech firms", steps)
        self.assertEqual(mission.status, MissionStatus.CREATED)

        engine.start_mission(mission.mission_id)
        self.assertEqual(mission.status, MissionStatus.RUNNING)
        self.assertEqual(mission.step_statuses["step_1"], StepStatus.RUNNING)

        # Complete step 1
        engine.complete_step(mission.mission_id, "step_1", {"companies": ["Apex Corp"]})
        self.assertEqual(mission.step_statuses["step_1"], StepStatus.COMPLETED)
        self.assertEqual(mission.step_statuses["step_2"], StepStatus.RUNNING)

        # Complete step 2
        engine.complete_step(mission.mission_id, "step_2", {"people": ["CEO Alice"]})
        self.assertEqual(mission.status, MissionStatus.COMPLETED)

    def test_07_mission_engine_pause_and_resume(self):
        """Validates pausing an active mission and safely resuming it."""
        engine = MissionEngine(max_concurrency=4)
        steps = [
            DAGStep("step_a", "Scan Registry", "ResearchAgent"),
            DAGStep("step_b", "Enrich Data", "CompanyAgent", dependencies=["step_a"]),
        ]
        mission = engine.create_mission("Pause Test Mission", "Testing pause/resume", steps)
        engine.start_mission(mission.mission_id)
        self.assertEqual(mission.status, MissionStatus.RUNNING)

        # Pause
        engine.pause_mission(mission.mission_id)
        self.assertEqual(mission.status, MissionStatus.PAUSED)

        # Resume
        engine.resume_mission(mission.mission_id)
        self.assertEqual(mission.status, MissionStatus.RUNNING)

    def test_08_human_in_the_loop_checkpoint(self):
        """Validates that steps requiring human review halt execution until explicit decision."""
        engine = MissionEngine(max_concurrency=4)
        steps = [
            DAGStep("step_1", "Gather Candidates", "ResearchAgent"),
            DAGStep("step_review", "Human Approval", "ReviewAgent", dependencies=["step_1"], requires_human_review=True),
            DAGStep("step_final", "Final Outreach", "ContactAgent", dependencies=["step_review"]),
        ]
        mission = engine.create_mission("HITL Mission", "Human in loop test", steps)
        engine.start_mission(mission.mission_id)

        # Complete step_1
        engine.complete_step(mission.mission_id, "step_1", {"candidates": 5})

        # Mission must halt at AWAITING_HUMAN_REVIEW
        self.assertEqual(mission.status, MissionStatus.AWAITING_HUMAN_REVIEW)
        self.assertEqual(mission.step_statuses["step_review"], StepStatus.AWAITING_REVIEW)
        self.assertIn("step_review", mission.pending_human_reviews)

        # Submit approval
        engine.submit_human_decision(mission.mission_id, "step_review", "APPROVED")

        # Step 2 complete, step 3 now running
        self.assertEqual(mission.step_statuses["step_review"], StepStatus.COMPLETED)
        self.assertEqual(mission.step_statuses["step_final"], StepStatus.RUNNING)
        self.assertEqual(mission.status, MissionStatus.RUNNING)

    def test_09_api_mission_creation_and_details(self):
        """Validates POST /api/v1/orchestration/missions and GET /missions/{id} endpoints."""
        payload = {
            "name": "API Autonomous Mission",
            "goal": "Verify API mission dispatch",
            "priority": "HIGH",
            "steps": [
                {
                    "step_id": "api_s1",
                    "name": "Query Search",
                    "agent_type": "ResearchAgent",
                    "dependencies": [],
                    "input_payload": {"query": "SaaS CTOs"},
                },
                {
                    "step_id": "api_s2",
                    "name": "Verify Emails",
                    "agent_type": "ContactAgent",
                    "dependencies": ["api_s1"],
                    "input_payload": {"domain": "saas.io"},
                },
            ],
            "configuration": {"max_retries": 2},
        }
        res = self.client.post("/api/v1/orchestration/missions", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        mission_id = data["mission"]["id"]
        self.assertEqual(data["dag_validation"], "VALID_DAG")
        self.assertEqual(data["mission"]["priority"], "HIGH")

        # Fetch detail
        det_res = self.client.get(f"/api/v1/orchestration/missions/{mission_id}", headers=self.headers)
        self.assertEqual(det_res.status_code, 200)
        det_data = det_res.json()
        self.assertEqual(det_data["name"], "API Autonomous Mission")
        self.assertEqual(len(det_data["steps"]), 2)

    def test_10_primary_workflow_invariant_preservation(self):
        """
        PRIMARY WORKFLOW INVARIANT:
        Autonomous mission execution and DAG task exploration must NEVER pollute
        canonical PostgreSQL SavedLead records without explicit user addition.
        """
        initial_saved_count = self.db.query(SavedLead).count()

        # Run multi-step mission that processes rich lead data
        engine = MissionEngine(max_concurrency=4)
        steps = [
            DAGStep("s_find", "Discover Leads", "ResearchAgent"),
            DAGStep("s_enrich", "Enrich Executives", "PersonAgent", dependencies=["s_find"]),
        ]
        m = engine.create_mission("Secret Pipeline Mission", "Explore leads without polluting DB", steps)
        engine.start_mission(m.mission_id)
        engine.complete_step(m.mission_id, "s_find", {"leads": [{"name": "Lead A"}, {"name": "Lead B"}]})
        engine.complete_step(m.mission_id, "s_enrich", {"enriched": [{"name": "Lead A", "email": "a@lead.com"}]})

        current_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(
            current_saved_count,
            initial_saved_count,
            "CRITICAL INVARIANT VIOLATION: Autonomous mission polluted canonical SavedLead table!"
        )


if __name__ == "__main__":
    unittest.main()
