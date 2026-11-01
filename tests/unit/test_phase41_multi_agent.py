"""
LeadNexus AI X — Phase 41 Test Suite (ChatGPT Master Roadmap)
Multi-Agent AI Platform
Tests: 12 Specialized Agents, Agent Registry, Bounded Execution Runtime,
Inter-Agent Message Bus, Delegation, State Memory, and Conflict Arbitration.
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
from app.models.multi_agent_platform import (
    AgentTypeEnum,
    AgentStatus,
    AgentTaskPriority,
    ArbitrationStrategy,
    AgentTaskRecord,
    AgentMemoryEntry,
    AgentMessageBusRecord,
    AgentArbitrationRecord,
)
from app.security.tokens import create_access_token
from packages.agents import (
    AgentRegistry,
    AutonomousAgent,
    AgentExecutionResult,
    InterAgentMessageBus,
    AgentArbitrator,
    ArbitrationConflict,
    ResearchAgent,
    CompanyAgent,
    PersonAgent,
    ContactAgent,
    EvidenceAgent,
    ScoringAgent,
    QualityAgent,
    PlanningAgent,
    ReviewAgent,
    get_specialized_agent,
)


class TestPhase41MultiAgentPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="MultiAgent Org", slug="ma-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.ws = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.ws:
            cls.ws = Workspace(id=str(uuid.uuid4()), organization_id=cls.org.id, name="MultiAgent Workspace", slug="ma-ws")
            cls.db.add(cls.ws)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="agent_supervisor@leadnexus.io",
                hashed_password="hash",
                full_name="Agent Platform Supervisor",
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

    def test_01_agent_registry_contains_all_12_specialists(self):
        roster = AgentRegistry.list_all()
        self.assertEqual(len(roster), 12)
        agent_types = [a.agent_type for a in roster]

        for expected in AgentTypeEnum.ALL_AGENTS:
            self.assertIn(expected, agent_types)

        company_spec = AgentRegistry.get_agent(AgentTypeEnum.COMPANY_AGENT)
        self.assertEqual(company_spec.agent_type, "CompanyAgent")
        self.assertTrue(company_spec.sandbox_restricted)
        self.assertIn("firmographics_lookup", company_spec.capabilities)

    def test_02_bounded_execution_enforcement(self):
        # Create an agent with max_steps = 2 that doesn't terminate immediately
        class UnboundedAgent(AutonomousAgent):
            def _step_logic(self, step_number, goal, context):
                return {
                    "action": "LOOP",
                    "thought": "Thinking infinitely...",
                    "is_complete": False,
                    "step_tokens": 100,
                }

        agent = UnboundedAgent(agent_type="UnboundedAgent", max_steps=3)
        res = agent.execute_bounded(task_id="t-bound-1", goal="Neverending task")

        self.assertEqual(res.status, AgentStatus.FAILED)
        self.assertIn("Exceeded maximum allowed step bound", res.error)
        self.assertEqual(res.steps_taken, 3)

    def test_03_specialized_company_agent_execution(self):
        agent = CompanyAgent()
        res = agent.execute_bounded(
            task_id="t-company-1",
            goal="Identify firmographics for Infogenx Technologies",
            context={"company_name": "Infogenx Technologies"},
        )
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertEqual(res.result_data["company_name"], "Infogenx Technologies")
        self.assertGreater(res.result_data["confidence"], 0.9)
        self.assertLessEqual(res.steps_taken, agent.max_steps)

    def test_04_planning_agent_decomposition(self):
        planner = PlanningAgent()
        res = planner.execute_bounded(
            task_id="t-plan-1",
            goal="Conduct end-to-end B2B lead discovery for Cloud ERP in Australia",
        )
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertEqual(res.result_data["plan_status"], "COMPLETED")
        self.assertEqual(res.result_data["delegations_executed"], 3)
        self.assertEqual(len(res.steps_log), 2)

    def test_05_review_agent_user_explicit_add_rule(self):
        reviewer = ReviewAgent()
        res = reviewer.execute_bounded(
            task_id="t-rev-1",
            goal="Audit search session and verify Saved Leads isolation",
        )
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertTrue(res.result_data["compliance_verified"])
        self.assertTrue(res.result_data["export_allowed"])
        self.assertEqual(res.result_data["invariant_check"], "PASSED")

    def test_06_inter_agent_message_bus_and_delegation(self):
        bus = InterAgentMessageBus()
        # Direct message
        msg = bus.send_message(
            sender_agent="ResearchAgent",
            recipient_agent="CompanyAgent",
            message_type="QUERY",
            payload={"query_domain": "infogenx.com"},
            task_id="t-bus-101",
        )
        self.assertEqual(msg["sender_agent"], "ResearchAgent")

        # Delegation
        del_msg = bus.delegate_task(
            supervisor_agent="PlanningAgent",
            subordinate_agent="PersonAgent",
            subtask_goal="Find Head of Engineering",
            input_data={"company_id": "cmp-99"},
            parent_task_id="t-bus-101",
        )
        self.assertEqual(del_msg["message_type"], "DELEGATION")

        task_msgs = bus.get_messages_for_task("t-bus-101")
        self.assertEqual(len(task_msgs), 2)

    def test_07_agent_arbitration_confidence_weighted(self):
        # CompanyAgent says revenue is $50M (confidence 0.95), ResearchAgent says $20M (confidence 0.70)
        conflict = AgentArbitrator.detect_conflict(
            field="annual_revenue",
            agent_a="CompanyAgent",
            value_a="$50M",
            confidence_a=0.95,
            agent_b="ResearchAgent",
            value_b="$20M",
            confidence_b=0.70,
            task_id="t-arb-1",
        )
        self.assertIsNotNone(conflict)

        resolution = AgentArbitrator.resolve_conflict(conflict, strategy=ArbitrationStrategy.CONFIDENCE_WEIGHTED)
        self.assertEqual(resolution["winner_agent"], "CompanyAgent")
        self.assertEqual(resolution["resolved_value"], "$50M")
        self.assertEqual(resolution["winning_confidence"], 0.95)

    def test_08_agent_task_dispatch_api(self):
        payload = {
            "agent_type": "ScoringAgent",
            "goal_description": "Calculate ICP fit for Fintech enterprise",
            "input_context": {"revenue": "$100M", "headcount": 500},
            "priority": "HIGH",
            "max_steps": 6,
        }
        res = self.client.post("/api/v1/agents/tasks", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["task"]["assigned_agent"], "ScoringAgent")
        self.assertGreaterEqual(len(data["execution_steps"]), 1)

    def test_09_agent_memory_read_write_api(self):
        mem_payload = {
            "agent_type": "ResearchAgent",
            "memory_key": "last_searched_keyword",
            "memory_value": {"keyword": "Odoo ERP ERPNext Sydney"},
            "memory_scope": "WORKSPACE",
        }
        res = self.client.post("/api/v1/agents/memory", json=mem_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)

        get_res = self.client.get("/api/v1/agents/memory?agent_type=ResearchAgent", headers=self.headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertGreaterEqual(len(get_res.json()["memory_entries"]), 1)

    def test_10_agent_health_telemetry_api(self):
        res = self.client.get("/api/v1/agents/health", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        agents = res.json()["agents_health"]
        self.assertEqual(len(agents), 12)
        for a in agents:
            self.assertEqual(a["status"], "HEALTHY")


if __name__ == "__main__":
    unittest.main()
