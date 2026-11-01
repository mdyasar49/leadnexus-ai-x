"""
Token & AI Cost Tracker (Phase 40)
Calculates per-inference costs, enforces daily workspace AI budgets, and aggregates consumption metrics.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class CostLimitExceededError(Exception):
    """Raised when an inference call would exceed the configured workspace AI spend limit."""
    pass


class TokenCostTracker:
    """Manages token accounting and workspace AI cost governance."""

    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> float:
        """Computes cost in USD for a given token usage pair."""
        in_cost = (input_tokens / 1000.0) * cost_per_1k_input
        out_cost = (output_tokens / 1000.0) * cost_per_1k_output
        return round(in_cost + out_cost, 6)

    @classmethod
    def verify_budget(
        cls,
        current_daily_spend_usd: float,
        estimated_call_cost_usd: float,
        daily_limit_usd: float,
    ) -> bool:
        """Verifies that the inference call does not breach workspace daily AI spend limit."""
        projected = current_daily_spend_usd + estimated_call_cost_usd
        if daily_limit_usd > 0 and projected > daily_limit_usd:
            raise CostLimitExceededError(
                f"Workspace daily AI spend limit reached: projected ${projected:.4f} > limit ${daily_limit_usd:.2f}."
            )
        return True
