from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.knowledge_retrieval import (
    AIModel,
    AIModelRoute,
    AIBudget,
    ModelTier,
)


class AICostAndModelRouter:
    """
    AI Model Routing, Prompt Versioning & Budget Governance:
    - Routes tasks to appropriate model tiers (SMALL for extraction, MEDIUM for summarization, LARGE for deep research)
    - Tracks token consumption and costs
    - Throttles requests when monthly or daily token budget limits are exceeded
    """

    def __init__(self, db: Session):
        self.db = db

    def route_task_model(
        self,
        workspace_id: str,
        task_type: str = "SUMMARIZATION"
    ) -> Dict[str, Any]:
        """Selects the designated model and generation config for the task."""
        route = self.db.query(AIModelRoute).filter(
            and_(AIModelRoute.workspace_id == workspace_id, AIModelRoute.task_type == task_type.upper())
        ).first()

        if route and route.model:
            return {
                "model_name": route.model.name,
                "tier": route.model.tier,
                "provider": route.model.provider,
                "temperature": route.temperature,
                "max_tokens": route.max_tokens,
                "prompt_version": "v1.0"
            }

        # Default fallback config
        return {
            "model_name": "leadnexus-gemini-flash",
            "tier": ModelTier.MEDIUM.value,
            "provider": "google-deepmind",
            "temperature": 0.1,
            "max_tokens": 2048,
            "prompt_version": "v1.0"
        }

    def check_and_update_budget(
        self,
        workspace_id: str,
        tokens_used: int,
        estimated_cost_usd: float = 0.005
    ) -> bool:
        """
        Validates whether workspace has sufficient AI headroom.
        Updates running spend counters and throttles if budget is exceeded.
        """
        budget = self.db.query(AIBudget).filter(AIBudget.workspace_id == workspace_id).first()
        if not budget:
            budget = AIBudget(
                workspace_id=workspace_id,
                monthly_budget_usd=250.0,
                current_month_spent_usd=0.0,
                daily_token_limit=500000,
                current_day_tokens=0,
                is_throttled=False
            )
            self.db.add(budget)
            self.db.commit()
            self.db.refresh(budget)

        # Check if already throttled
        if budget.is_throttled:
            return False

        # Update spend
        budget.current_month_spent_usd += estimated_cost_usd
        budget.current_day_tokens += tokens_used

        if budget.current_month_spent_usd >= budget.monthly_budget_usd or budget.current_day_tokens >= budget.daily_token_limit:
            budget.is_throttled = True

        budget.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return not budget.is_throttled

