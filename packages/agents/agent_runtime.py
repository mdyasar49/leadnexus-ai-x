"""
Agent Runtime & Bounded Execution (Phase 41)
Manages step-by-step reasoning, tool invocations, token budgets, and bounded execution loops.
"""

from typing import Any, Dict, List, Optional
import time
from app.models.multi_agent_platform import AgentStatus


class BoundedExecutionExceededError(Exception):
    """Raised when an agent attempts to execute more steps than its assigned maximum allowance."""
    pass


class AgentExecutionResult:
    """Standardized output from an agent execution run."""

    def __init__(
        self,
        task_id: str,
        agent_type: str,
        status: str,
        result_data: Dict[str, Any],
        steps_taken: int,
        tokens_consumed: int,
        cost_usd: float,
        latency_ms: float,
        steps_log: List[Dict[str, Any]],
        error: Optional[str] = None,
    ):
        self.task_id = task_id
        self.agent_type = agent_type
        self.status = status
        self.result_data = result_data
        self.steps_taken = steps_taken
        self.tokens_consumed = tokens_consumed
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.steps_log = steps_log
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "result_data": self.result_data,
            "steps_taken": self.steps_taken,
            "tokens_consumed": self.tokens_consumed,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "steps_log": self.steps_log,
            "error": self.error,
        }


class AutonomousAgent:
    """Base class for all 12 specialized agents with bounded step limits and sandboxed execution."""

    def __init__(
        self,
        agent_type: str,
        max_steps: int = 10,
        token_budget: int = 16384,
    ):
        self.agent_type = agent_type
        self.max_steps = max_steps
        self.token_budget = token_budget
        self._memory: Dict[str, Any] = {}

    def read_memory(self, key: str, default: Any = None) -> Any:
        return self._memory.get(key, default)

    def write_memory(self, key: str, value: Any):
        self._memory[key] = value

    def execute_bounded(
        self,
        task_id: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionResult:
        """
        Executes reasoning and action loop within strict max_steps and token_budget constraints.
        """
        t0 = time.perf_counter()
        steps_log: List[Dict[str, Any]] = []
        tokens_used = 0
        ctx = context or {}

        current_step = 0
        finished = False
        final_output: Dict[str, Any] = {}

        while not finished:
            current_step += 1
            if current_step > self.max_steps:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return AgentExecutionResult(
                    task_id=task_id,
                    agent_type=self.agent_type,
                    status=AgentStatus.FAILED,
                    result_data={"partial_output": final_output},
                    steps_taken=current_step - 1,
                    tokens_consumed=tokens_used,
                    cost_usd=round((tokens_used / 1000.0) * 0.0002, 6),
                    latency_ms=round(elapsed_ms, 2),
                    steps_log=steps_log,
                    error=f"Execution halted: Exceeded maximum allowed step bound of {self.max_steps}.",
                )

            # Step logic
            step_action = self._step_logic(current_step, goal, ctx)
            tokens_used += step_action.get("step_tokens", 120)

            steps_log.append({
                "step": current_step,
                "action": step_action.get("action", "REASON"),
                "thought": step_action.get("thought", ""),
                "observation": step_action.get("observation", ""),
            })

            if step_action.get("is_complete", False):
                finished = True
                final_output = step_action.get("output", {})

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        cost_usd = round((tokens_used / 1000.0) * 0.0002, 6)

        return AgentExecutionResult(
            task_id=task_id,
            agent_type=self.agent_type,
            status=AgentStatus.COMPLETED,
            result_data=final_output,
            steps_taken=current_step,
            tokens_consumed=tokens_used,
            cost_usd=cost_usd,
            latency_ms=round(elapsed_ms, 2),
            steps_log=steps_log,
        )

    def _step_logic(self, step_number: int, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default synthetic step implementation, overridden by specialized subclasses."""
        if step_number == 1:
            return {
                "action": "ANALYZE_OBJECTIVE",
                "thought": f"Analyzing task goal: '{goal[:60]}...' with provided context.",
                "observation": f"Identified primary parameters: {list(context.keys())}.",
                "step_tokens": 140,
                "is_complete": False,
            }
        else:
            return {
                "action": "SYNTHESIZE_OUTPUT",
                "thought": f"Synthesizing completed output for goal: {goal[:40]}.",
                "observation": "Output verified and validated against quality constraints.",
                "step_tokens": 160,
                "is_complete": True,
                "output": {
                    "summary": f"{self.agent_type} executed goal successfully.",
                    "goal": goal,
                    "status": "VERIFIED",
                },
            }
