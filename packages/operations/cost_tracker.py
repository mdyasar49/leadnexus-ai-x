from typing import Dict, Any

COST_PER_UNIT = {
    "HTTP_REQUEST": 0.0001,      # $0.10 per 1k requests
    "BROWSER_RENDER": 0.0015,    # $1.50 per 1k pages
    "AI_TOKENS_1K": 0.0020,      # $2.00 per 1M tokens
    "STORAGE_RECORD": 0.00005,   # $0.05 per 1k records
}


class CostTracker:
    """
    Cost & Financial Intelligence Engine:
    - Calculates micro-costs across HTTP requests, headless browser renders, and AI tokens
    - Enforces tenant and campaign usage budgets
    """
    @classmethod
    def calculate_cost(cls, unit_type: str, units: float = 1.0) -> float:
        rate = COST_PER_UNIT.get(unit_type, 0.0001)
        return round(rate * units, 6)

    @classmethod
    def check_budget_exceeded(
        cls,
        current_spend: float,
        max_budget: float,
        proposed_cost: float = 0.0
    ) -> bool:
        if max_budget <= 0.0:
            return False  # Unlimited budget
        return (current_spend + proposed_cost) > max_budget

