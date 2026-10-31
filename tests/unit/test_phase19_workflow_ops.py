import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, SessionLocal, get_sync_db
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore, FieldConflict
from app.models.technology import TechnologyObservation
from app.models.workflow_ops import (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowExecution,
    WorkflowTask,
    ReviewItem,
    ReviewComment,
    HumanFeedback,
    ConflictWorkflow,
    ReviewStatus,
    ReviewPriority,
    ExecutionStatus
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.workflows.workflow_dsl import (
    WorkflowConditionEvaluator,
    WorkflowValidator,
    WorkflowDSLError
)
from packages.workflows.workflow_engine import (
    WorkflowEngine
)
from packages.workflows.review_service import (
    ReviewService
)
from packages.workflows.template_library import (
    TemplateLibraryService,
    WORKFLOW_TEMPLATES
)


class TestPhase19WorkflowOps(unittest.TestCase):
    """Test suite covering Phase 19 Enterprise Workflow Automation, Human-in-the-Loop Review & Ops."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"workflow_admin_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Workflow",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Workflow Ops Workspace",
            slug=f"wf-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed Companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Horizon Manufacturing Australia",
            normalized_name="horizon manufacturing australia",
            domain="horizonmfg.com.au",
            country="Australia",
            industry="Manufacturing",
            lead_score=85,
            status="NEW"
        )
        cls.db.add(cls.comp_1)

        # Seed LeadScore
        cls.score_1 = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            lead_priority_score=88.0,
            priority_tier="P1_HIGH",
            intent_score=82.0,
            icp_fit_score=90.0
        )
        cls.db.add(cls.score_1)

        # Seed Contact
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            full_name="Liam Foster",
            job_title="Head of Operations & ERP",
            email="liam.foster@horizonmfg.com.au",
            email_status="VERIFIED",
            is_decision_maker=True,
            source_url="https://horizonmfg.com.au/team"
        )
        cls.db.add(cls.contact_1)

        # Seed Conflict
        cls.conflict_1 = FieldConflict(
            id=str(uuid.uuid4()),
            company_id=cls.comp_1.id,
            workspace_id=cls.ws_id,
            field_name="phone",
            value_a="+61 3 9999 1111",
            source_a="Company Website",
            value_b="+61 3 8888 2222",
            source_b="Directory Listing",
            resolution_status="UNRESOLVED"
        )
        cls.db.add(cls.conflict_1)
        cls.db.commit()

        # Dependency Overrides
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        app.dependency_overrides[get_sync_db] = lambda: cls.db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # 1. WorkflowConditionEvaluator Unit Tests
    def test_condition_evaluator_operators(self):
        """Test safe condition operators against entity context."""
        context = {
            "country": "Australia",
            "lead_score": 85,
            "intent_score": 82.0,
            "has_email": True,
            "priority_tier": "P1_HIGH"
        }

        # Equals & GTE
        self.assertTrue(WorkflowConditionEvaluator.evaluate({"field": "country", "operator": "=", "value": "Australia"}, context))
        self.assertTrue(WorkflowConditionEvaluator.evaluate({"field": "lead_score", "operator": ">=", "value": 80}, context))
        self.assertFalse(WorkflowConditionEvaluator.evaluate({"field": "lead_score", "operator": ">", "value": 90}, context))

        # IN operator
        self.assertTrue(WorkflowConditionEvaluator.evaluate({"field": "priority_tier", "operator": "IN", "value": ["P0_CRITICAL", "P1_HIGH"]}, context))

        # Compound AND / OR
        tree = {
            "operator": "AND",
            "conditions": [
                {"field": "country", "operator": "=", "value": "Australia"},
                {"field": "has_email", "operator": "=", "value": True}
            ]
        }
        self.assertTrue(WorkflowConditionEvaluator.evaluate(tree, context))

    def test_condition_evaluator_rejects_unwhitelisted_field(self):
        """Verify unwhitelisted attributes or raw SQL attempts raise WorkflowDSLError."""
        with self.assertRaises(WorkflowDSLError):
            WorkflowConditionEvaluator.evaluate({"field": "system_password", "operator": "=", "value": "123"}, {})

    # 2. WorkflowValidator Unit Tests
    def test_workflow_validator_valid_and_cycles(self):
        """Test cycle detection (preventing unbounded loops) and missing triggers."""
        # Valid graph
        valid_def = {
            "nodes": [
                {"id": "n1", "type": "TRIGGER"},
                {"id": "n2", "type": "RESEARCH"},
                {"id": "n3", "type": "END"}
            ],
            "edges": [
                {"from": "n1", "to": "n2"},
                {"from": "n2", "to": "n3"}
            ]
        }
        is_valid, errs = WorkflowValidator.validate_graph(valid_def)
        self.assertTrue(is_valid)

        # Unbounded loop: n1 -> n2 -> n1
        cycle_def = {
            "nodes": [
                {"id": "n1", "type": "TRIGGER"},
                {"id": "n2", "type": "RESEARCH"},
                {"id": "n3", "type": "END"}
            ],
            "edges": [
                {"from": "n1", "to": "n2"},
                {"from": "n2", "to": "n1"},
                {"from": "n2", "to": "n3"}
            ]
        }
        is_cycle_valid, cycle_errs = WorkflowValidator.validate_graph(cycle_def)
        self.assertFalse(is_cycle_valid)
        self.assertTrue(any("circular" in e.lower() for e in cycle_errs))

    # 3. Workflow Simulation (Dry-Run) Unit Tests
    def test_simulate_workflow_dry_run(self):
        """Verify dry-run simulation evaluates branches without mutating database."""
        template = WORKFLOW_TEMPLATES["HIGH_INTENT_ODOO_LEAD"]
        context = {
            "intent_score": 85,
            "country": "Australia",
            "has_email": True,
            "has_decision_maker": True
        }
        sim_res = WorkflowEngine.simulate_workflow(template["definition_payload"], context)
        self.assertTrue(sim_res["is_valid"])
        self.assertGreaterEqual(len(sim_res["traversed_path"]), 3)
        self.assertIn("node_approval", sim_res["traversed_path"])

    # 4. Workflow Execution & Bounded Loop Unit Tests
    def test_execute_workflow_and_idempotency(self):
        """Test end-to-end workflow execution with idempotency protection."""
        wf = WorkflowDefinition(
            workspace_id=self.ws_id,
            name="Test Qualification Workflow",
            workflow_type="RESEARCH_WORKFLOW",
            is_active=True
        )
        self.db.add(wf)
        self.db.commit()

        v = WorkflowVersion(
            workspace_id=self.ws_id,
            workflow_id=wf.id,
            version_number=1,
            status="ACTIVE",
            definition_payload=WORKFLOW_TEMPLATES["HIGH_INTENT_ODOO_LEAD"]["definition_payload"],
            published_at=datetime.now(timezone.utc),
            created_by=self.user_id
        )
        self.db.add(v)
        self.db.commit()

        exec1 = WorkflowEngine.execute_workflow(
            db=self.db,
            workspace_id=self.ws_id,
            workflow_id=wf.id,
            entity_id=self.comp_1.id,
            trigger_type="MANUAL"
        )
        # Note: The template contains a HUMAN_REVIEW node, so execution correctly enters PAUSED status waiting for human decision!
        self.assertEqual(exec1.status, ExecutionStatus.PAUSED.value)

        # Idempotency: Repeating with same trigger returns existing execution
        exec2 = WorkflowEngine.execute_workflow(
            db=self.db,
            workspace_id=self.ws_id,
            workflow_id=wf.id,
            entity_id=self.comp_1.id,
            trigger_type="MANUAL"
        )
        self.assertEqual(exec1.id, exec2.id)

    # 5. Human-in-the-Loop Review System Unit Tests
    def test_review_item_lifecycle_and_bounded_research_loop(self):
        """Test human review decisions, feedback recording, and research loop limit governor."""
        item = ReviewService.create_review_item(
            db=self.db,
            workspace_id=self.ws_id,
            entity_id=self.comp_1.id,
            priority="HIGH",
            ai_recommendation={"action": "QUALIFY", "confidence": 0.89}
        )
        self.assertEqual(item.status, ReviewStatus.PENDING.value)
        self.assertIsNotNone(item.due_at)

        # Retrieve review dossier
        dossier = ReviewService.get_review_dossier(self.db, self.ws_id, item.id)
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier["company"]["name"], "Horizon Manufacturing Australia")
        self.assertEqual(len(dossier["people"]), 1)

        # Test Bounded Research Loop:
        # Loop attempt 1
        res1 = ReviewService.process_decision(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            review_id=item.id,
            decision="REQUEST_MORE_RESEARCH",
            reason="Need additional confirmation on ERP version"
        )
        self.assertFalse(res1["loop_halted"])

        # Loop attempt 2
        ReviewService.process_decision(self.db, self.ws_id, self.user_id, item.id, "REQUEST_MORE_RESEARCH", "Still inconclusive")
        # Loop attempt 3
        ReviewService.process_decision(self.db, self.ws_id, self.user_id, item.id, "REQUEST_MORE_RESEARCH", "Checking external forums")

        # Loop attempt 4 -> Must exceed max attempts and halt automatic loop!
        res_halt = ReviewService.process_decision(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            review_id=item.id,
            decision="REQUEST_MORE_RESEARCH",
            reason="Trying fourth time"
        )
        self.assertTrue(res_halt["loop_halted"])
        self.assertEqual(res_halt["decision"], "HUMAN_RESEARCH_REQUIRED")
        self.assertEqual(res_halt["status"], "ESCALATED")

    def test_conflict_resolution(self):
        """Test human field conflict resolution."""
        res = ReviewService.resolve_field_conflict(
            db=self.db,
            workspace_id=self.ws_id,
            user_id=self.user_id,
            conflict_id=self.conflict_1.id,
            resolved_value="+61 3 9999 1111"
        )
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["chosen_value"], "+61 3 9999 1111")

    # 6. Template Library Unit Tests
    def test_template_library_listing(self):
        """Verify built-in templates listing."""
        templates = TemplateLibraryService.list_templates()
        self.assertGreaterEqual(len(templates), 4)
        keys = [t["key"] for t in templates]
        self.assertIn("HIGH_INTENT_ODOO_LEAD", keys)
        self.assertIn("STALE_LEAD_REFRESH", keys)

    # 7. End-to-End API Routes Tests
    def test_api_list_templates(self):
        """Test GET /api/v1/workflows/templates."""
        resp = self.client.get("/api/v1/workflows/templates")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_api_create_and_validate_workflow(self):
        """Test POST /api/v1/workflows and validation endpoint."""
        payload = {
            "name": "API Test Workflow",
            "workflow_type": "RESEARCH_WORKFLOW",
            "definition_payload": WORKFLOW_TEMPLATES["CONTACT_VERIFICATION_WORKFLOW"]["definition_payload"]
        }
        create_resp = self.client.post("/api/v1/workflows", json=payload)
        self.assertEqual(create_resp.status_code, 201)
        wf_id = create_resp.json()["id"]

        val_resp = self.client.post(f"/api/v1/workflows/{wf_id}/validate")
        self.assertEqual(val_resp.status_code, 200)
        self.assertTrue(val_resp.json()["is_valid"])

    def test_api_simulate_workflow(self):
        """Test POST /api/v1/workflows/{id}/simulate dry-run."""
        wf = WorkflowDefinition(workspace_id=self.ws_id, name="Sim Workflow", workflow_type="RESEARCH_WORKFLOW")
        self.db.add(wf)
        self.db.commit()
        v = WorkflowVersion(
            workspace_id=self.ws_id,
            workflow_id=wf.id,
            version_number=1,
            status="ACTIVE",
            definition_payload=WORKFLOW_TEMPLATES["HIGH_INTENT_ODOO_LEAD"]["definition_payload"],
            created_by=self.user_id
        )
        self.db.add(v)
        self.db.commit()

        resp = self.client.post(f"/api/v1/workflows/{wf.id}/simulate", json={"entity_id": self.comp_1.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_valid"])
        self.assertIn("traversed_path", data)

    def test_api_reviews_dossier_and_decision(self):
        """Test GET /api/v1/reviews/{id} and POST /api/v1/reviews/{id}/decision."""
        item = ReviewService.create_review_item(
            db=self.db,
            workspace_id=self.ws_id,
            entity_id=self.comp_1.id,
            priority="CRITICAL"
        )
        dossier_resp = self.client.get(f"/api/v1/reviews/{item.id}")
        self.assertEqual(dossier_resp.status_code, 200)
        self.assertEqual(dossier_resp.json()["priority"], "CRITICAL")

        decision_resp = self.client.post(
            f"/api/v1/reviews/{item.id}/decision",
            json={"decision": "CONFIRM", "reason": "Verified executive decision maker on LinkedIn", "feedback_category": "AI_CORRECT"}
        )
        self.assertEqual(decision_resp.status_code, 200)
        self.assertEqual(decision_resp.json()["status"], "APPROVED")

    def test_api_resolve_conflict(self):
        """Test POST /api/v1/conflicts/{id}/resolve."""
        cf = FieldConflict(
            id=str(uuid.uuid4()),
            company_id=self.comp_1.id,
            workspace_id=self.ws_id,
            field_name="city",
            value_a="Sydney",
            source_a="Website",
            value_b="Melbourne",
            source_b="Registry",
            resolution_status="UNRESOLVED"
        )
        self.db.add(cf)
        self.db.commit()

        resp = self.client.post(f"/api/v1/conflicts/{cf.id}/resolve", json={"resolved_value": "Sydney"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
