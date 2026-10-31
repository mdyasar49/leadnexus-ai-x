"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering
AI Model Router & Cost Engine: Task complexity routing, token metering, and tenant cost attribution.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.performance import AIModelCostRecord, ModelTier


class AIModelRouterAndCostEngine:
    """Routes AI inference requests to the optimal cost/latency tier and tracks expenditure."""

    ROUTING_TABLE: Dict[str, Dict[str, Any]] = {
        ModelTier.CHEAP_FAST.value: {
            "model_name": "gemini-1.5-flash-8b",
            "cost_per_1k_input": 0.0000375,
            "cost_per_1k_output": 0.00015,
            "suitable_tasks": ["signal_parsing", "domain_cleaning", "simple_classification"],
        },
        ModelTier.BALANCED.value: {
            "model_name": "gemini-1.5-flash",
            "cost_per_1k_input": 0.000075,
            "cost_per_1k_output": 0.00030,
            "suitable_tasks": ["company_summarization", "intent_detection", "data_extraction"],
        },
        ModelTier.PREMIUM.value: {
            "model_name": "gemini-1.5-pro",
            "cost_per_1k_input": 0.00125,
            "cost_per_1k_output": 0.00500,
            "suitable_tasks": ["multi_hop_reasoning", "evidence_synthesis", "qualification_decision"],
        },
    }

    @classmethod
    def route_task(cls, task_type: str) -> Tuple[ModelTier, str]:
        """Routes task type to the appropriate cost/latency model tier."""
        task_lower = task_type.lower()
        if "reason" in task_lower or "synthes" in task_lower or "qualif" in task_lower or "complex" in task_lower:
            tier = ModelTier.PREMIUM
        elif "pars" in task_lower or "clean" in task_lower or "classif" in task_lower or "simple" in task_lower:
            tier = ModelTier.CHEAP_FAST
        else:
            tier = ModelTier.BALANCED

        meta = cls.ROUTING_TABLE[tier.value]
        return tier, meta["model_name"]

    @classmethod
    def calculate_cost(
        cls,
        tier: ModelTier,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        meta = cls.ROUTING_TABLE[tier.value]
        input_cost = (prompt_tokens / 1000.0) * meta["cost_per_1k_input"]
        output_cost = (completion_tokens / 1000.0) * meta["cost_per_1k_output"]
        return round(input_cost + output_cost, 6)

    def __init__(self, db_session: Any):
        self.db = db_session

    def record_usage(
        self,
        workspace_id: str,
        task_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int = 150,
    ) -> AIModelCostRecord:
        tier, model_name = self.route_task(task_type)
        cost_usd = self.calculate_cost(tier, prompt_tokens, completion_tokens)

        record = AIModelCostRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            model_name=model_name,
            model_tier=tier.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            recorded_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
