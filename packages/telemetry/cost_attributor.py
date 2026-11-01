"""
LeadNexus AI X - Phase 44: Multi-Dimensional Cost Allocation Engine
Calculates micro-USD cost attribution across AI model inferences, worker compute time,
document parsing, and external API requests.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional
import uuid


# Default unit pricing rates in micro-USD (1,000,000 micros = $1.00 USD)
DEFAULT_RATES: Dict[str, int] = {
    "AI_TOKEN_PRO_INPUT": 3,      # $3.00 / 1M input tokens = 3 micros per 1K
    "AI_TOKEN_PRO_OUTPUT": 15,    # $15.00 / 1M output tokens = 15 micros per 1K
    "AI_TOKEN_FLASH_INPUT": 1,    # $0.35 / 1M -> ~1 micro per 1K
    "AI_TOKEN_FLASH_OUTPUT": 2,   # $1.05 / 1M -> ~2 micros per 1K
    "COMPUTE_MS_WORKER": 5,       # 5 micros per second of worker compute
    "DOCUMENT_PAGE_OCR": 1500,    # $0.0015 per page OCR = 1500 micros
    "SEARCH_API_QUERY": 5000,     # $0.005 per web search API call = 5000 micros
}


class CostAttributor:
    """Calculates and aggregates granular operational costs in micro-USD."""

    def __init__(self, rates: Optional[Dict[str, int]] = None):
        self.rates = rates or DEFAULT_RATES
        self._records: List[Dict[str, Any]] = []

    def record_ai_inference_cost(
        self,
        workspace_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Calculates and records AI token consumption cost in micro-USD."""
        is_flash = "flash" in model_name.lower()
        in_rate = self.rates["AI_TOKEN_FLASH_INPUT"] if is_flash else self.rates["AI_TOKEN_PRO_INPUT"]
        out_rate = self.rates["AI_TOKEN_FLASH_OUTPUT"] if is_flash else self.rates["AI_TOKEN_PRO_OUTPUT"]

        in_cost = int((input_tokens / 1000.0) * in_rate)
        out_cost = int((output_tokens / 1000.0) * out_rate)
        total_micros = max(1, in_cost + out_cost)

        record = {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "billing_entity": "AI_INFERENCE",
            "subsystem": model_name,
            "cost_micros": total_micros,
            "cost_usd": total_micros / 1_000_000.0,
            "units_consumed": input_tokens + output_tokens,
            "unit_type": "TOKENS",
            "metadata": metadata or {},
        }
        self._records.append(record)
        return total_micros

    def record_compute_cost(
        self,
        workspace_id: str,
        subsystem: str,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Records compute execution cost based on elapsed runtime."""
        duration_seconds = max(0.001, duration_ms / 1000.0)
        total_micros = max(1, int(duration_seconds * self.rates["COMPUTE_MS_WORKER"]))

        record = {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "billing_entity": "WORKER_COMPUTE",
            "subsystem": subsystem,
            "cost_micros": total_micros,
            "cost_usd": total_micros / 1_000_000.0,
            "units_consumed": duration_ms,
            "unit_type": "MILLISECONDS",
            "metadata": metadata or {},
        }
        self._records.append(record)
        return total_micros

    def get_workspace_cost_summary(self, workspace_id: str) -> Dict[str, Any]:
        """Summarizes total spend and breakdown by billing category for a workspace."""
        filtered = [r for r in self._records if r["workspace_id"] == workspace_id]
        by_category: Dict[str, int] = defaultdict(int)
        by_subsystem: Dict[str, int] = defaultdict(int)
        total_micros = 0

        for r in filtered:
            c = r["cost_micros"]
            total_micros += c
            by_category[r["billing_entity"]] += c
            by_subsystem[r["subsystem"]] += c

        return {
            "workspace_id": workspace_id,
            "total_micros": total_micros,
            "total_usd": round(total_micros / 1_000_000.0, 6),
            "record_count": len(filtered),
            "by_category_usd": {k: round(v / 1_000_000.0, 6) for k, v in by_category.items()},
            "by_subsystem_usd": {k: round(v / 1_000_000.0, 6) for k, v in by_subsystem.items()},
        }
