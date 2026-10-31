import re
from typing import Dict, Any, List


class NaturalLanguageQueryBuilder:
    """
    Natural Language to Safe Parameterized Query Converter:
    - Parses researcher questions into structured, parameterized filter schemas
    - Strict Security Rule: NEVER generates or executes raw dynamic SQL queries.
    """
    @classmethod
    def parse_query(cls, text: str) -> Dict[str, Any]:
        filters: Dict[str, Any] = {
            "country": None,
            "technology": None,
            "intent_min": None,
            "priority": None,
            "has_decision_maker": None,
        }

        lower = text.lower()

        # Geography
        if "australia" in lower or "australian" in lower:
            filters["country"] = "Australia"
        elif "india" in lower or "indian" in lower:
            filters["country"] = "India"
        elif "united states" in lower or "usa" in lower:
            filters["country"] = "United States"

        # Technology
        if "odoo" in lower:
            filters["technology"] = "Odoo"
        elif "zoho" in lower:
            filters["technology"] = "Zoho"
        elif "salesforce" in lower:
            filters["technology"] = "Salesforce"
        elif "sap" in lower:
            filters["technology"] = "SAP"
        elif "shopify" in lower:
            filters["technology"] = "Shopify"

        # Intent Strength
        if "high intent" in lower or "strong intent" in lower or "migration" in lower:
            filters["intent_min"] = 70.0
            filters["priority"] = ["P0_CRITICAL", "P1_HIGH"]
        elif "buying ready" in lower or "urgent" in lower:
            filters["intent_min"] = 80.0
            filters["priority"] = ["P0_CRITICAL"]

        # Decision Maker
        if "decision maker" in lower or "cto" in lower or "it manager" in lower:
            filters["has_decision_maker"] = True

        return {
            "raw_query": text,
            "structured_filters": filters,
            "is_safe": True,
            "execution_mode": "PARAMETERIZED_FILTER"
        }

