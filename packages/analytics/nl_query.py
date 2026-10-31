import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from packages.analytics.dsl import AnalyticsDSLQuery


class NaturalLanguageAnalytics:
    """
    Translates natural-language business questions into safe Analytics DSL queries.
    Provides human-readable query interpretation and grounded explanations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.dsl_engine = AnalyticsDSLQuery(db)

    def parse_to_dsl(self, prompt: str) -> Dict[str, Any]:
        """Translates natural language text into safe Analytics DSL AST."""
        p = prompt.lower().strip()

        # Defaults
        entity = "companies"
        filters: List[Dict[str, Any]] = []
        group_by: List[str] = []
        time_range = "last_30_days"
        order_by = "created_at"
        order_direction = "desc"

        # 1. Geographic intent
        if "australia" in p or "australian" in p:
            filters.append({"field": "country", "op": "CONTAINS", "val": "Australia"})

        # 2. Industry / Technology
        if "odoo" in p:
            filters.append({"field": "name", "op": "CONTAINS", "val": "Odoo"})
        if "mining" in p:
            filters.append({"field": "industry", "op": "CONTAINS", "val": "Mining"})
        elif "manufacturing" in p:
            filters.append({"field": "industry", "op": "CONTAINS", "val": "Manufacturing"})

        # 3. Intent or Signals vs Companies
        if "company" in p or "companies" in p:
            entity = "companies"
        elif "intent" in p or "signal" in p:
            entity = "intent_signals"
            order_by = "created_at"

        # 4. Sources
        if "source" in p or "sources" in p:
            entity = "sources"

        # 5. Contacts / Decision Makers
        if "decision maker" in p or "contact" in p or "role" in p:
            entity = "contacts"

        # 6. Time Range parsing
        if "today" in p:
            time_range = "today"
        elif "this week" in p or "last 7 days" in p:
            time_range = "last_7_days"
        elif "this month" in p or "last 30 days" in p:
            time_range = "last_30_days"
        elif "this quarter" in p or "last 90 days" in p:
            time_range = "last_90_days"

        # 7. Priority filtering
        if "high priority" in p or "high-priority" in p:
            entity = "lead_scores"
            filters.append({"field": "lead_priority_score", "op": ">=", "val": 80.0})
            order_by = "lead_priority_score"

        # 8. Grouping
        if "by industry" in p:
            group_by = ["industry"]
        elif "by country" in p:
            group_by = ["country"]

        dsl = {
            "entity": entity,
            "filters": filters,
            "group_by": group_by,
            "time_range": time_range,
            "order_by": order_by,
            "order_direction": order_direction,
            "limit": 50
        }

        interpretation = (
            f"Querying {entity} over {time_range} "
            f"with {len(filters)} filter(s)"
            f"{f' grouped by {group_by[0]}' if group_by else ''}."
        )

        return {
            "prompt": prompt,
            "dsl": dsl,
            "interpretation": interpretation,
            "confidence": 0.92
        }

    def execute_nl_query(self, workspace_id: str, prompt: str) -> Dict[str, Any]:
        """Translates and runs query through the safe DSL execution engine."""
        parsed = self.parse_to_dsl(prompt)
        exec_res = self.dsl_engine.execute(workspace_id=workspace_id, query_dsl=parsed["dsl"])

        return {
            "prompt": prompt,
            "interpretation": parsed["interpretation"],
            "dsl": parsed["dsl"],
            "confidence": parsed["confidence"],
            "data": exec_res
        }
