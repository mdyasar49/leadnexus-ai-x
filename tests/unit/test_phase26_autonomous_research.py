import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

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
from app.models.autonomous_research import (
    AutonomyPolicy,
    ResearchPlan,
    ResearchPlanStep,
    AutonomousResearchRun,
    ResearchRunCheckpoint,
    ResearchReport,
    ResearchDeadLetter,
    ResearchEscalation,
    ResearchBudget,
    ResearchMode,
    RunStatus,
    ToolRiskLevel,
    TaskType,
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.autonomous_research.policy_and_tool_registry import (
    AutonomyPolicyValidator,
    ToolRegistry,
)
from packages.autonomous_research.research_task_graph_engine import (
    ResearchTaskGraphEngine,
    CyclicDependencyError,
)
from packages.autonomous_research.source_selection_engine import (
    SourceSelectionEngine,
)
from packages.autonomous_research.specialized_agents import (
    SpecializedAgentDispatcher,
    AgentFindingResult,
)
from packages.autonomous_research.checkpoint_and_dlq_service import (
    CheckpointAndDLQService,
)
from packages.autonomous_research.research_report_engine import (
    ResearchReportEngine,
)
from packages.autonomous_research.simulation_and_sandbox_engine import (
    SimulationAndSandboxEngine,
)
from packages.autonomous_research.autonomous_research_loop import (
    AutonomousResearchLoop,
)


class TestPhase26AutonomousResearch(unittest.TestCase):
    """
    Comprehensive test suite covering Phase 26:
    Advanced Automation, Autonomous Research & Adaptive Intelligence Engine
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        # Seed Organization, Workspace, User
        cls.org_id = str(uuid.uuid4())
        cls.ws_id = str(uuid.uuid4())
        cls.user_id = str(uuid.uuid4())

        cls.org = Organization(id=cls.org_id, name="Phase26 Test Org", slug=f"p26-org-{uuid.uuid4().hex[:6]}")
        cls.ws = Workspace(id=cls.ws_id, organization_id=cls.org_id, name="Phase26 Test Workspace", slug=f"p26-ws-{uuid.uuid4().hex[:6]}")
        cls.user = User(
            id=cls.user_id,
            email=f"p26_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="hashed_pw_test",
            first_name="Autonomous",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )

        cls.db.add(cls.org)
        cls.db.add(cls.ws)
        cls.db.add(cls.user)
        cls.db.commit()

        # FastAPI test client overrides
        app.dependency_overrides[get_sync_db] = lambda: cls.db
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        app.dependency_overrides.clear()

    def test_01_autonomy_policy_forbidden_tools(self):
        """Hard invariant: forbidden tools (outreach, shell, raw sql) are rejected permanently."""
        policy = AutonomyPolicy(
            id=str(uuid.uuid4()),
            workspace_id=self.ws_id,
            name="Open Policy",
            risk_level=ToolRiskLevel.HIGH.value,
            is_active=True,
        )
        is_allowed, reason = AutonomyPolicyValidator.validate_tool_execution(
            policy=policy,
            tool_name="outreach_sender",
            tool_risk_level=ToolRiskLevel.RESTRICTED.value,
        )
        self.assertFalse(is_allowed)
        self.assertIn("forbidden", reason.lower())

        is_allowed2, reason2 = AutonomyPolicyValidator.validate_tool_execution(
            policy=policy,
            tool_name="raw_shell_command",
            tool_risk_level=ToolRiskLevel.RESTRICTED.value,
        )
        self.assertFalse(is_allowed2)

    def test_02_autonomy_policy_risk_level_enforcement(self):
        """Tool risk level exceeding policy risk level is rejected."""
        low_policy = AutonomyPolicy(
            id=str(uuid.uuid4()),
            workspace_id=self.ws_id,
            name="Strict Low Policy",
            risk_level=ToolRiskLevel.LOW.value,
            is_active=True,
        )
        # Medium risk tool against LOW policy
        is_allowed, reason = AutonomyPolicyValidator.validate_tool_execution(
            policy=low_policy,
            tool_name="smtp_handshake_verifier",
            tool_risk_level=ToolRiskLevel.MEDIUM.value,
        )
        self.assertFalse(is_allowed)
        self.assertIn("exceeds policy max risk level", reason)

        # Low risk tool against LOW policy
        is_allowed_low, _ = AutonomyPolicyValidator.validate_tool_execution(
            policy=low_policy,
            tool_name="company_website_crawler",
            tool_risk_level=ToolRiskLevel.LOW.value,
        )
        self.assertTrue(is_allowed_low)

    def test_03_ssrf_and_domain_safety(self):
        """SSRF defense blocks localhost, private IPs, and metadata services."""
        blocked_targets = [
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "10.0.0.5",
            "192.168.1.1",
            "service.internal",
        ]
        for target in blocked_targets:
            is_valid, err = AutonomyPolicyValidator.validate_domain(None, target)
            self.assertFalse(is_valid, f"Expected {target} to be blocked")
            self.assertIsNotNone(err)

        # Public target is allowed
        is_valid_pub, _ = AutonomyPolicyValidator.validate_domain(None, "omniretail.com.au")
        self.assertTrue(is_valid_pub)

    def test_04_budget_boundary_enforcement(self):
        """Exceeded budget rejects further tool calls."""
        budget = ResearchBudget(
            workspace_id=self.ws_id,
            max_tool_calls=10,
            tool_calls_used=10,
            max_cost_usd=5.0,
            cost_usd_used=5.0,
            is_exceeded=True,
        )
        is_allowed, reason = AutonomyPolicyValidator.validate_tool_execution(
            policy=None,
            tool_name="search_engine_query",
            tool_risk_level=ToolRiskLevel.LOW.value,
            budget=budget,
        )
        self.assertFalse(is_allowed)
        self.assertIn("budget", reason.lower())

    def test_05_tool_registry_management(self):
        """Tool registry catalogs tools and supports risk-level filtering."""
        reg = ToolRegistry()
        tools = reg.list_tools()
        self.assertGreaterEqual(len(tools), 10)

        # Low risk tools only
        low_tools = reg.list_tools(max_risk_level=ToolRiskLevel.LOW.value)
        self.assertTrue(all(t["risk_level"] == ToolRiskLevel.LOW.value for t in low_tools))
        self.assertIn("search_engine_query", [t["name"] for t in low_tools])

    def test_06_dag_validation_and_cycle_rejection(self):
        """Cyclic dependency graphs are detected and rejected."""
        cyclic_steps = [
            {"id": "step_a", "title": "Step A", "depends_on": ["step_b"]},
            {"id": "step_b", "title": "Step B", "depends_on": ["step_a"]},
        ]
        is_valid, err = ResearchTaskGraphEngine.validate_dag(cyclic_steps)
        self.assertFalse(is_valid)
        self.assertIn("Cycle detected", err)

        with self.assertRaises(CyclicDependencyError):
            ResearchTaskGraphEngine.get_topological_order(cyclic_steps)

    def test_07_topological_sort_order(self):
        """Topological ordering places prerequisites before dependent steps."""
        valid_steps = [
            {"id": "step_3", "title": "Audit", "depends_on": ["step_2"]},
            {"id": "step_1", "title": "Profile", "depends_on": []},
            {"id": "step_2", "title": "Detect Tech", "depends_on": ["step_1"]},
        ]
        ordered = ResearchTaskGraphEngine.get_topological_order(valid_steps)
        ordered_ids = [s["id"] for s in ordered]
        self.assertEqual(ordered_ids, ["step_1", "step_2", "step_3"])

    def test_08_get_ready_steps(self):
        """Identifies only steps whose dependencies have fully completed."""
        steps = [
            {"id": "s1", "depends_on": []},
            {"id": "s2", "depends_on": ["s1"]},
            {"id": "s3", "depends_on": ["s1"]},
            {"id": "s4", "depends_on": ["s2", "s3"]},
        ]
        # Initially, only s1 is ready
        ready1 = ResearchTaskGraphEngine.get_ready_steps(steps, set(), set())
        self.assertEqual([s["id"] for s in ready1], ["s1"])

        # After s1 completes, s2 and s3 are ready in parallel
        ready2 = ResearchTaskGraphEngine.get_ready_steps(steps, {"s1"}, set())
        self.assertEqual({s["id"] for s in ready2}, {"s2", "s3"})

        # s4 becomes ready only when both s2 and s3 complete
        ready3 = ResearchTaskGraphEngine.get_ready_steps(steps, {"s1", "s2"}, set())
        self.assertEqual([s["id"] for s in ready3], ["s3"])

        ready4 = ResearchTaskGraphEngine.get_ready_steps(steps, {"s1", "s2", "s3"}, set())
        self.assertEqual([s["id"] for s in ready4], ["s4"])

    def test_09_default_plan_generation_modes(self):
        """Generates appropriate plan graphs for QUICK, STANDARD, and DEEP modes."""
        quick_plan = ResearchTaskGraphEngine.generate_default_plan("Target Co", "target.com", mode="QUICK")
        self.assertEqual(len(quick_plan), 3)

        standard_plan = ResearchTaskGraphEngine.generate_default_plan("Target Co", "target.com", mode="STANDARD")
        self.assertEqual(len(standard_plan), 8)

        deep_plan = ResearchTaskGraphEngine.generate_default_plan("Target Co", "target.com", mode="DEEP")
        self.assertEqual(len(deep_plan), 9)

        # All generated plans must form valid DAGs
        for plan in (quick_plan, standard_plan, deep_plan):
            is_valid, err = ResearchTaskGraphEngine.validate_dag(plan)
            self.assertTrue(is_valid, f"Plan DAG validation failed: {err}")

    def test_10_gap_remediation_injection(self):
        """Injects gap remediation step into existing plan DAG without cycles."""
        standard_plan = ResearchTaskGraphEngine.generate_default_plan("Target Co", "target.com")
        updated_plan = ResearchTaskGraphEngine.inject_gap_remediation_step(
            standard_plan,
            gap_attribute="odoo_version",
            entity_name="Target Co",
        )
        self.assertEqual(len(updated_plan), len(standard_plan) + 1)
        self.assertEqual(updated_plan[-1]["task_type"], TaskType.GAP_REMEDIATION.value)

        is_valid, err = ResearchTaskGraphEngine.validate_dag(updated_plan)
        self.assertTrue(is_valid)

    def test_11_source_selection_and_expected_value(self):
        """Calculates expected information value and ranks sources."""
        sources = [
            {"domain": "github.com", "relevance": 0.9, "historical_yield_rate": 0.95, "cost_usd": 0.001, "latency_sec": 1.0},
            {"domain": "prlog.org", "relevance": 0.5, "historical_yield_rate": 0.4, "cost_usd": 0.01, "latency_sec": 2.0},
            {"domain": "odoo.com", "relevance": 0.95, "historical_yield_rate": 0.9, "cost_usd": 0.002, "latency_sec": 1.2},
        ]
        ranked = SourceSelectionEngine.rank_sources_for_task("ODOO_VERIFICATION", sources)
        self.assertGreater(ranked[0]["expected_value"], ranked[-1]["expected_value"])
        self.assertTrue(ranked[-1]["is_syndicated"])  # prlog.org is syndicated

    def test_12_source_diversity_and_anti_syndication(self):
        """Requires at least 2 independent apex domains for corroborated evidence."""
        urls_single_domain = [
            "https://omniretail.com.au/about",
            "https://omniretail.com.au/team",
            "https://omniretail.com.au/contact",
        ]
        eval1 = SourceSelectionEngine.evaluate_source_diversity(urls_single_domain)
        self.assertEqual(eval1["unique_domain_count"], 1)
        self.assertFalse(eval1["is_corroborated"])

        urls_multi_domains = [
            "https://omniretail.com.au/about",
            "https://github.com/omniretail/odoo-addons",
            "https://asic.gov.au/lookup?q=omniretail",
        ]
        eval2 = SourceSelectionEngine.evaluate_source_diversity(urls_multi_domains)
        self.assertEqual(eval2["unique_domain_count"], 3)
        self.assertTrue(eval2["is_corroborated"])

    def test_13_specialized_agents_findings(self):
        """Specialized agents produce structured findings with evidence snippets."""
        firm_finding = SpecializedAgentDispatcher.run_company_research({"company_name": "Acme Corp", "domain": "acme.com"})
        self.assertEqual(firm_finding.finding_type, "FIRMOGRAPHICS")
        self.assertIn("Sydney", firm_finding.data["headquarters"])

        odoo_finding = SpecializedAgentDispatcher.run_odoo_verification({"company_name": "Acme Corp", "domain": "acme.com"})
        self.assertEqual(odoo_finding.finding_type, "ODOO_INTELLIGENCE")
        self.assertTrue(odoo_finding.data["odoo_installed"])
        self.assertEqual(odoo_finding.data["version"], "17.0")

        dm_finding = SpecializedAgentDispatcher.run_decision_maker_search({"company_name": "Acme Corp"})
        self.assertEqual(dm_finding.finding_type, "DECISION_MAKERS")
        self.assertGreaterEqual(len(dm_finding.data["decision_makers"]), 1)

    def test_14_agent_conflict_detection(self):
        """Detects contradictory claims between specialized agents."""
        f1 = AgentFindingResult(
            agent_name="AgentA",
            finding_type="ODOO_INTELLIGENCE",
            entity_name="Test Co",
            confidence_score=0.9,
            evidence_snippet="Found Odoo Enterprise",
            data={"edition": "Enterprise"},
            source_urls=[],
        )
        f2 = AgentFindingResult(
            agent_name="AgentB",
            finding_type="ODOO_INTELLIGENCE",
            entity_name="Test Co",
            confidence_score=0.8,
            evidence_snippet="Found Odoo Community",
            data={"edition": "Community"},
            source_urls=[],
        )
        conflicts = SpecializedAgentDispatcher.detect_agent_conflicts([f1, f2])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_type"], "ODOO_EDITION_MISMATCH")

    def test_15_checkpoint_creation_and_restoration(self):
        """Checkpoint preserves state and allows worker resume."""
        chk = CheckpointAndDLQService.create_checkpoint(
            run_id="run_123",
            iteration=2,
            completed_task_ids=["step_1", "step_2"],
            pending_task_ids=["step_3"],
            discovered_entities=[{"name": "OmniRetail"}],
            cost_accrued=0.035,
        )
        self.assertEqual(chk["iteration"], 2)
        self.assertEqual(len(chk["completed_tasks"]), 2)

        restored = CheckpointAndDLQService.restore_from_checkpoint(chk)
        self.assertEqual(restored["resumed_iteration"], 3)
        self.assertIn("step_1", restored["completed_tasks"])
        self.assertIn("step_3", restored["pending_tasks"])

    def test_16_dead_letter_queue_and_exponential_backoff(self):
        """Failed tasks route to DLQ with backoff calculations."""
        delay1 = CheckpointAndDLQService.calculate_exponential_backoff(attempt_number=1)
        delay2 = CheckpointAndDLQService.calculate_exponential_backoff(attempt_number=2)
        delay3 = CheckpointAndDLQService.calculate_exponential_backoff(attempt_number=3)
        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 4.0)

        dlq_rec = CheckpointAndDLQService.route_to_dead_letter_queue(
            run_id="run_999",
            task_id="step_failed",
            failure_reason="Upstream HTTP 500 error",
            task_payload={"task": "query"},
            retry_count=3,
        )
        self.assertEqual(dlq_rec["resolution_status"], "PENDING")
        self.assertEqual(dlq_rec["task_id"], "step_failed")

    def test_17_human_escalation_lifecycle(self):
        """Creates and resolves human-in-the-loop escalation tickets."""
        esc = CheckpointAndDLQService.create_human_escalation(
            run_id="run_esc_1",
            escalation_type="AMBIGUOUS_IDENTITY",
            reason="Multiple companies named OmniRetail found.",
        )
        self.assertEqual(esc["status"], "OPEN")

        resolved = CheckpointAndDLQService.resolve_escalation(
            escalation_data=esc,
            reviewer_id=self.user_id,
            decision="APPROVED",
            notes="Confirmed OmniRetail Australia (ASIC 12345)",
        )
        self.assertEqual(resolved["status"], "APPROVED")
        self.assertEqual(resolved["reviewer_id"], self.user_id)

    def test_18_research_report_completeness_and_confidence(self):
        """Calculates completeness score and compiles final research report."""
        findings = [
            {"finding_type": "FIRMOGRAPHICS", "confidence_score": 0.95, "source_urls": ["https://co.com", "https://asic.gov.au"], "data": {}},
            {"finding_type": "TECH_STACK", "confidence_score": 0.90, "source_urls": ["https://co.com/login"], "data": {"detected_stack": ["Odoo"]}},
            {"finding_type": "ODOO_INTELLIGENCE", "confidence_score": 0.96, "source_urls": ["https://github.com/co/odoo"], "data": {"version": "17.0", "edition": "Enterprise"}},
            {"finding_type": "DECISION_MAKERS", "confidence_score": 0.88, "source_urls": ["https://co.com/team"], "data": {"decision_makers": [{"name": "Marcus"}]}},
            {"finding_type": "CONTACT_VERIFICATION", "confidence_score": 0.94, "source_urls": ["dns://co.com"], "data": {}},
        ]
        rep = ResearchReportEngine.generate_research_report(
            workspace_id=self.ws_id,
            run_id="run_rep_1",
            company_name="Test Corp",
            findings=findings,
        )
        self.assertEqual(rep["completeness_pct"], 100.0)
        self.assertGreater(rep["confidence_score"], 0.80)
        self.assertIn("Odoo", rep["summary"])
        self.assertIn("17.0", rep["summary"])

    def test_19_simulation_dry_run_engine(self):
        """Simulates plan duration, costs, tool calls, and feasibility."""
        steps = ResearchTaskGraphEngine.generate_default_plan("Simulated Co", "sim.com", mode="STANDARD")
        sim = SimulationAndSandboxEngine.simulate_plan_execution(
            workspace_id=self.ws_id,
            plan_id="plan_sim_1",
            steps=steps,
        )
        self.assertTrue(sim["is_feasible"])
        self.assertEqual(sim["estimated_tool_calls"], len(steps))
        self.assertGreater(sim["estimated_duration_sec"], 0)
        self.assertGreater(sim["estimated_cost_usd"], 0.0)

    def test_20_autonomous_research_loop_full_execution(self):
        """Executes full bounded autonomous research loop cleanly to completion."""
        loop = AutonomousResearchLoop(
            workspace_id=self.ws_id,
            company_name="OmniRetail Australia",
            domain="omniretail.com.au",
            mode="STANDARD",
            max_iterations=10,
        )
        result = loop.execute()

        self.assertEqual(result["status"], RunStatus.COMPLETED.value)
        self.assertEqual(result["completed_steps_count"], result["total_steps_count"])
        self.assertGreater(result["findings_count"], 0)
        self.assertGreater(result["checkpoints_count"], 0)
        self.assertIn("report", result)
        self.assertGreater(result["report"]["completeness_score"], 0.8)

    def test_21_fastapi_autonomy_routes(self):
        """Verifies Phase 26 REST API endpoints."""
        # 1. List tools
        tools_res = self.client.get("/api/v1/autonomy/tools")
        self.assertEqual(tools_res.status_code, 200)
        self.assertGreaterEqual(len(tools_res.json()), 10)

        # 2. Create Policy
        policy_payload = {
            "name": "Phase 26 Production Safe Policy",
            "risk_level": "LOW",
            "max_iterations": 10,
            "max_runtime_seconds": 300,
            "max_tool_calls": 50,
            "max_parallel_tasks": 5,
            "max_cost_budget": 10.0,
            "require_human_approval": False,
            "is_active": True,
        }
        pol_res = self.client.post("/api/v1/autonomy/policies", json=policy_payload)
        self.assertEqual(pol_res.status_code, 200)
        policy_id = pol_res.json()["policy_id"]

        # 3. Create Plan
        plan_payload = {
            "title": "Autonomous Profiling for OmniRetail",
            "objective": "Verify Odoo adoption and leadership team",
            "target_name": "OmniRetail Solutions Pty Ltd",
            "target_domain": "omniretail.com.au",
            "mode": "STANDARD",
            "policy_id": policy_id,
        }
        plan_res = self.client.post("/api/v1/autonomy/plans", json=plan_payload)
        self.assertEqual(plan_res.status_code, 200)
        plan_id = plan_res.json()["plan_id"]

        # 4. Simulate Plan
        sim_res = self.client.post("/api/v1/autonomy/simulations", json={"plan_id": plan_id})
        self.assertEqual(sim_res.status_code, 200)
        self.assertTrue(sim_res.json()["is_feasible"])

        # 5. Start Run
        run_res = self.client.post(
            "/api/v1/autonomy/runs",
            json={
                "company_name": "OmniRetail Solutions Pty Ltd",
                "domain": "omniretail.com.au",
                "mode": "STANDARD",
                "plan_id": plan_id,
                "policy_id": policy_id,
            },
        )
        self.assertEqual(run_res.status_code, 200)
        run_data = run_res.json()
        run_id = run_data["run_id"]

        # 6. Checkpoints endpoint
        chk_res = self.client.get(f"/api/v1/autonomy/runs/{run_id}/checkpoints")
        self.assertEqual(chk_res.status_code, 200)
        self.assertGreater(len(chk_res.json()), 0)

        # 7. List Reports endpoint
        rep_res = self.client.get("/api/v1/autonomy/reports")
        self.assertEqual(rep_res.status_code, 200)
        self.assertGreater(len(rep_res.json()), 0)


if __name__ == "__main__":
    unittest.main()
