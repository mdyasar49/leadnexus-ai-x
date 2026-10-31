import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.models.autonomous_research import (
    ResearchMode,
    RunStatus,
    StopCondition,
    TaskStatus,
    ToolRiskLevel,
)
from packages.autonomous_research.checkpoint_and_dlq_service import CheckpointAndDLQService
from packages.autonomous_research.policy_and_tool_registry import AutonomyPolicyValidator
from packages.autonomous_research.research_report_engine import ResearchReportEngine
from packages.autonomous_research.research_task_graph_engine import ResearchTaskGraphEngine
from packages.autonomous_research.specialized_agents import SpecializedAgentDispatcher


class AutonomousResearchLoop:
    """
    Core Autonomous Research execution loop. Orchestrates iterative DAG execution,
    specialized agent dispatching, policy enforcement, resource budgeting,
    periodic checkpointing, and clean termination.
    """

    def __init__(
        self,
        workspace_id: str,
        company_name: str,
        domain: Optional[str] = None,
        mode: str = ResearchMode.STANDARD.value,
        policy: Optional[Any] = None,
        max_iterations: int = 10,
        max_tool_calls: int = 50,
        max_runtime_seconds: int = 300,
        max_cost_usd: float = 10.0,
    ):
        self.workspace_id = workspace_id
        self.company_name = company_name
        self.domain = domain or f"{company_name.lower().replace(' ', '')}.com"
        self.mode = mode
        self.policy = policy
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.max_runtime_seconds = max_runtime_seconds
        self.max_cost_usd = max_cost_usd

        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.status = RunStatus.PENDING.value
        self.current_iteration = 0
        self.tool_calls_count = 0
        self.total_cost = 0.0
        self.start_time = 0.0
        self.stop_condition: Optional[str] = None

        # Build initial plan steps
        self.steps = ResearchTaskGraphEngine.generate_default_plan(company_name, self.domain, mode)
        self.completed_step_ids: Set[str] = set()
        self.running_step_ids: Set[str] = set()
        self.findings: List[Dict[str, Any]] = []
        self.conflicts: List[Dict[str, Any]] = []
        self.checkpoints: List[Dict[str, Any]] = []
        self.dead_letters: List[Dict[str, Any]] = []
        self.escalations: List[Dict[str, Any]] = []

    def execute(self, max_steps_to_run: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes the autonomous research loop within strict bounds.
        Can run to completion or execute a partial batch (e.g. for step-by-step testing or resume).
        """
        self.status = RunStatus.RUNNING.value
        self.start_time = time.time()
        steps_executed = 0

        while self.current_iteration < self.max_iterations:
            self.current_iteration += 1

            # Check runtime bound
            elapsed = time.time() - self.start_time
            if elapsed >= self.max_runtime_seconds:
                self.status = RunStatus.COMPLETED.value
                self.stop_condition = StopCondition.TIMEOUT.value
                break

            # Check tool call bound
            if self.tool_calls_count >= self.max_tool_calls:
                self.status = RunStatus.COMPLETED.value
                self.stop_condition = StopCondition.RESEARCH_LIMIT_REACHED.value
                break

            # Check cost bound
            if self.total_cost >= self.max_cost_usd:
                self.status = RunStatus.BUDGET_EXCEEDED.value
                self.stop_condition = StopCondition.BUDGET_EXHAUSTED.value
                break

            # Find ready steps whose dependencies are satisfied
            ready_steps = ResearchTaskGraphEngine.get_ready_steps(
                self.steps,
                self.completed_step_ids,
                self.running_step_ids,
            )

            if not ready_steps:
                # No more ready steps: either all complete or blocked
                if len(self.completed_step_ids) == len(self.steps):
                    self.status = RunStatus.COMPLETED.value
                    self.stop_condition = StopCondition.GOAL_SATISFIED.value
                else:
                    self.status = RunStatus.COMPLETED.value
                    self.stop_condition = StopCondition.DEPTH_LIMIT.value
                break

            # Process ready steps
            for step in ready_steps:
                sid = step["id"]
                tool = step.get("tool_name", "search_engine_query")
                agent = step.get("agent_name", "CompanyResearchAgent")
                params = step.get("parameters", {})

                # Validate tool against policy
                is_allowed, reason = AutonomyPolicyValidator.validate_tool_execution(
                    policy=self.policy,
                    tool_name=tool,
                    tool_risk_level=ToolRiskLevel.LOW.value if tool not in ("smtp_handshake_verifier", "deep_forensic_evaluator") else ToolRiskLevel.MEDIUM.value,
                    parameters=params,
                )

                if not is_allowed:
                    # Route to DLQ or create escalation
                    self.dead_letters.append(
                        CheckpointAndDLQService.route_to_dead_letter_queue(
                            run_id=self.run_id,
                            task_id=sid,
                            failure_reason=reason or "Policy rejection",
                            task_payload=step,
                        )
                    )
                    self.completed_step_ids.add(sid)
                    continue

                # Execute task via specialized agent
                finding_result = self._dispatch_agent_task(agent, params)
                self.tool_calls_count += 1
                self.total_cost += 0.01

                if finding_result:
                    finding_dict = finding_result.to_dict()
                    self.findings.append(finding_dict)

                self.completed_step_ids.add(sid)
                steps_executed += 1

                if max_steps_to_run and steps_executed >= max_steps_to_run:
                    self.status = RunStatus.PAUSED.value
                    self.stop_condition = StopCondition.USER_STOP.value
                    break

            # Create periodic checkpoint after each wave
            chk = CheckpointAndDLQService.create_checkpoint(
                run_id=self.run_id,
                iteration=self.current_iteration,
                completed_task_ids=list(self.completed_step_ids),
                pending_task_ids=[s["id"] for s in self.steps if s["id"] not in self.completed_step_ids],
                discovered_entities=[{"name": self.company_name, "domain": self.domain}],
                cost_accrued=self.total_cost,
            )
            self.checkpoints.append(chk)

            if self.status == RunStatus.PAUSED.value:
                break

        # Check for agent conflicts
        conflict_records = SpecializedAgentDispatcher.detect_agent_conflicts(
            [SpecializedAgentDispatcher.run_company_research({"company_name": self.company_name})]  # sample wrap
        )
        self.conflicts.extend(conflict_records)

        # Generate report
        report = ResearchReportEngine.generate_research_report(
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            company_name=self.company_name,
            findings=self.findings,
            conflicts=self.conflicts,
        )

        return {
            "run_id": self.run_id,
            "status": self.status,
            "stop_condition": self.stop_condition or StopCondition.GOAL_SATISFIED.value,
            "current_iteration": self.current_iteration,
            "total_iterations": self.current_iteration,
            "tool_call_count": self.tool_calls_count,
            "total_cost": round(self.total_cost, 4),
            "completed_steps_count": len(self.completed_step_ids),
            "total_steps_count": len(self.steps),
            "findings_count": len(self.findings),
            "checkpoints_count": len(self.checkpoints),
            "dead_letter_count": len(self.dead_letters),
            "report": report,
        }

    def _dispatch_agent_task(self, agent_name: str, params: Dict[str, Any]):
        """Maps agent name to specialized agent handler."""
        task_params = dict(params)
        task_params["company_name"] = self.company_name
        task_params["domain"] = self.domain

        if agent_name == "CompanyResearchAgent":
            return SpecializedAgentDispatcher.run_company_research(task_params)
        elif agent_name == "TechnologyResearchAgent":
            return SpecializedAgentDispatcher.run_technology_research(task_params)
        elif agent_name == "OdooResearchAgent":
            return SpecializedAgentDispatcher.run_odoo_verification(task_params)
        elif agent_name == "IntentResearchAgent":
            return SpecializedAgentDispatcher.run_intent_discovery(task_params)
        elif agent_name == "PersonResearchAgent":
            return SpecializedAgentDispatcher.run_decision_maker_search(task_params)
        elif agent_name == "ContactResearchAgent":
            return SpecializedAgentDispatcher.run_contact_verification(task_params)
        elif agent_name == "EvidenceValidationAgent":
            return SpecializedAgentDispatcher.run_evidence_validation(task_params)
        elif agent_name == "DataQualityAgent":
            return SpecializedAgentDispatcher.run_data_quality_audit([])
        return None

