import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.autonomous_research import ToolRiskLevel
from packages.autonomous_research.policy_and_tool_registry import AutonomyPolicyValidator
from packages.autonomous_research.research_task_graph_engine import ResearchTaskGraphEngine


class SimulationAndSandboxEngine:
    """
    Dry-run simulation and sandboxed execution engine.
    Allows pre-execution inspection of plan feasibility, estimated duration,
    costs, tool call volumes, and potential policy violations.
    """

    ESTIMATED_TOOL_COSTS = {
        "search_engine_query": 0.005,
        "company_website_crawler": 0.02,
        "github_repository_analyzer": 0.005,
        "job_posting_detector": 0.01,
        "dns_mx_spf_checker": 0.001,
        "smtp_handshake_verifier": 0.01,
        "odoo_app_store_scanner": 0.005,
        "knowledge_graph_traversal": 0.002,
        "semantic_ontology_classifier": 0.01,
        "entity_resolution_matcher": 0.015,
        "deep_forensic_evaluator": 0.05,
    }

    ESTIMATED_TOOL_LATENCIES = {
        "search_engine_query": 1.2,
        "company_website_crawler": 3.5,
        "github_repository_analyzer": 1.5,
        "job_posting_detector": 2.0,
        "dns_mx_spf_checker": 0.4,
        "smtp_handshake_verifier": 1.8,
        "odoo_app_store_scanner": 1.0,
        "knowledge_graph_traversal": 0.3,
        "semantic_ontology_classifier": 0.8,
        "entity_resolution_matcher": 1.5,
        "deep_forensic_evaluator": 5.0,
    }

    @classmethod
    def simulate_plan_execution(
        cls,
        workspace_id: str,
        plan_id: str,
        steps: List[Dict[str, Any]],
        policy_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Performs a dry-run simulation of the research plan graph,
        predicting duration, cost, tool calls, and potential policy roadblocks.
        """
        # Validate graph integrity first
        is_valid, dag_err = ResearchTaskGraphEngine.validate_dag(steps)
        if not is_valid:
            return {
                "id": f"sim_{uuid.uuid4().hex[:12]}",
                "workspace_id": workspace_id,
                "plan_id": plan_id,
                "is_feasible": False,
                "error": f"Invalid DAG: {dag_err}",
                "estimated_duration_sec": 0,
                "estimated_tool_calls": 0,
                "estimated_cost_usd": 0.0,
                "risk_assessment": {"level": "CRITICAL", "reason": dag_err},
                "potential_bottlenecks": [dag_err],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        total_cost = 0.0
        total_duration = 0.0
        tool_counts: Dict[str, int] = {}
        risk_levels: Dict[str, int] = {
            ToolRiskLevel.LOW.value: 0,
            ToolRiskLevel.MEDIUM.value: 0,
            ToolRiskLevel.HIGH.value: 0,
            ToolRiskLevel.RESTRICTED.value: 0,
        }
        potential_bottlenecks = []
        policy_violations = []

        max_risk_seen = ToolRiskLevel.LOW.value

        for step in steps:
            tool = step.get("tool_name", "search_engine_query")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

            cost = cls.ESTIMATED_TOOL_COSTS.get(tool, 0.01)
            latency = cls.ESTIMATED_TOOL_LATENCIES.get(tool, 1.0)
            total_cost += cost
            total_duration += latency

            # Assess tool risk
            risk = ToolRiskLevel.LOW.value
            if tool in ("smtp_handshake_verifier", "entity_resolution_matcher"):
                risk = ToolRiskLevel.MEDIUM.value
            elif tool in ("deep_forensic_evaluator",):
                risk = ToolRiskLevel.HIGH.value
            elif tool in AutonomyPolicyValidator.FORBIDDEN_TOOLS or tool in ("outreach_sender", "raw_shell_command"):
                risk = ToolRiskLevel.RESTRICTED.value
                policy_violations.append(f"Forbidden tool '{tool}' detected in step '{step.get('title')}'")

            risk_levels[risk] += 1
            if AutonomyPolicyValidator.RISK_HIERARCHY.get(risk, 1) > AutonomyPolicyValidator.RISK_HIERARCHY.get(max_risk_seen, 1):
                max_risk_seen = risk

            if latency >= 3.0:
                potential_bottlenecks.append(f"Step '{step.get('title')}' uses slow tool '{tool}' (~{latency}s)")

        # Parallelism discount for independent steps (rough heuristic ~30% parallel efficiency)
        if len(steps) > 3:
            total_duration = total_duration * 0.7

        # Check policy budget limits if policy provided
        if policy_data:
            max_cost = policy_data.get("max_cost_budget", 10.0)
            max_runtime = policy_data.get("max_runtime_seconds", 300)
            if total_cost > max_cost:
                policy_violations.append(f"Estimated cost (${total_cost:.3f}) exceeds policy budget (${max_cost:.2f})")
            if total_duration > max_runtime:
                policy_violations.append(f"Estimated runtime ({total_duration:.1f}s) exceeds policy max runtime ({max_runtime}s)")

        is_feasible = len(policy_violations) == 0

        return {
            "id": f"sim_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "is_feasible": is_feasible,
            "policy_violations": policy_violations,
            "estimated_duration_sec": int(total_duration) + 1,
            "estimated_tool_calls": len(steps),
            "estimated_cost_usd": round(total_cost, 4),
            "tool_call_breakdown": tool_counts,
            "risk_assessment": {
                "overall_risk": max_risk_seen,
                "breakdown": risk_levels,
                "requires_human_approval": max_risk_seen in (ToolRiskLevel.HIGH.value, ToolRiskLevel.RESTRICTED.value),
            },
            "potential_bottlenecks": potential_bottlenecks,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def execute_in_sandbox(
        cls,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes a research tool in safe, isolated sandbox mode
        with mocked responses and zero external side effects.
        """
        # Block forbidden tools even in sandbox
        if tool_name in AutonomyPolicyValidator.FORBIDDEN_TOOLS:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is forbidden and cannot execute even in sandbox.",
                "data": {},
            }

        return {
            "success": True,
            "sandboxed": True,
            "tool_name": tool_name,
            "parameters": parameters,
            "mock_response": {
                "message": f"Sandbox execution of {tool_name} completed cleanly.",
                "status": "OK",
            },
        }

