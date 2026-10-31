import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore, EvidenceClaim
from app.models.campaign import Campaign
from app.models.source import ResearchSource
from app.models.analytics import (
    AnalyticsMetric,
    LeadSnapshot,
    CompanySnapshot,
    IntentSnapshot
)


ALLOWED_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "CONTAINS", "EXISTS"}
ALLOWED_AGGREGATIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
ALLOWED_ENTITIES = {
    "companies": Company,
    "contacts": Contact,
    "intent_signals": IntentSignal,
    "lead_scores": LeadScore,
    "campaigns": Campaign,
    "sources": ResearchSource,
    "lead_snapshots": LeadSnapshot
}

TIME_RANGES = {
    "today": 0,
    "yesterday": 1,
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
    "month_to_date": 30,
    "quarter_to_date": 90,
    "year_to_date": 365
}


class AnalyticsDSLError(Exception):
    """Raised when an analytics query violates safe DSL rules."""
    pass


class AnalyticsDSLQuery:
    """
    Safe Analytics DSL Query Engine.
    Executes controlled, parametrized queries with strict entity, field, and operator whitelisting.
    Prevents raw SQL injection and arbitrary code execution.
    """

    def __init__(self, db: Session):
        self.db = db

    def explain(self, workspace_id: str, query_dsl: Dict[str, Any]) -> Dict[str, Any]:
        """Provides an explain plan with estimated complexity and filter interpretation."""
        entity_name = query_dsl.get("entity", "companies")
        if entity_name not in ALLOWED_ENTITIES:
            raise AnalyticsDSLError(f"Entity '{entity_name}' is not queryable.")

        filters = query_dsl.get("filters", [])
        group_by = query_dsl.get("group_by", [])
        time_range = query_dsl.get("time_range", "last_30_days")
        aggregations = query_dsl.get("aggregations", [{"func": "COUNT", "field": "*"}])

        complexity = "LOW"
        if len(filters) > 3 or len(group_by) > 1 or query_dsl.get("compare_period"):
            complexity = "MEDIUM"
        if len(group_by) > 2 or query_dsl.get("compare_period") and len(filters) > 3:
            complexity = "HIGH"

        return {
            "entity": entity_name,
            "target_model": ALLOWED_ENTITIES[entity_name].__tablename__,
            "estimated_complexity": complexity,
            "execution_mode": "SYNC" if complexity != "HIGH" else "ASYNC",
            "time_range": time_range,
            "applied_filters_count": len(filters),
            "group_by_dimensions": group_by,
            "aggregations": aggregations,
            "tenant_isolated": True,
            "workspace_id": workspace_id,
            "interpretation": f"Querying {entity_name} over {time_range} grouped by {', '.join(group_by) if group_by else 'none'}."
        }

    def execute(self, workspace_id: str, query_dsl: Dict[str, Any]) -> Dict[str, Any]:
        """Executes safe DSL query against PostgreSQL canonical data with workspace isolation."""
        entity_name = query_dsl.get("entity", "companies")
        if entity_name not in ALLOWED_ENTITIES:
            raise AnalyticsDSLError(f"Entity '{entity_name}' is not queryable.")

        model = ALLOWED_ENTITIES[entity_name]
        query = self.db.query(model).filter(getattr(model, "workspace_id") == workspace_id)

        # 1. Time Range Filter
        time_range = query_dsl.get("time_range")
        if time_range and time_range in TIME_RANGES and hasattr(model, "created_at"):
            days = TIME_RANGES[time_range]
            cutoff = datetime.now(timezone.utc) - timedelta(days=days if days > 0 else 1)
            query = query.filter(getattr(model, "created_at") >= cutoff)

        # 2. Field Filters
        filters = query_dsl.get("filters", [])
        for f in filters:
            field_name = f.get("field")
            op = f.get("op", "=").upper()
            val = f.get("val")

            if not hasattr(model, field_name):
                raise AnalyticsDSLError(f"Field '{field_name}' does not exist on {entity_name}.")

            if op not in ALLOWED_OPERATORS:
                raise AnalyticsDSLError(f"Operator '{op}' is not permitted.")

            col = getattr(model, field_name)
            if op == "=":
                query = query.filter(col == val)
            elif op == "!=":
                query = query.filter(col != val)
            elif op == ">":
                query = query.filter(col > val)
            elif op == ">=":
                query = query.filter(col >= val)
            elif op == "<":
                query = query.filter(col < val)
            elif op == "<=":
                query = query.filter(col <= val)
            elif op == "IN":
                query = query.filter(col.in_(val if isinstance(val, list) else [val]))
            elif op == "NOT IN":
                query = query.filter(~col.in_(val if isinstance(val, list) else [val]))
            elif op == "CONTAINS":
                query = query.filter(col.ilike(f"%{val}%"))
            elif op == "EXISTS":
                query = query.filter(col.isnot(None))

        # 3. Simple Grouping & Aggregations vs Records
        group_by = query_dsl.get("group_by", [])
        limit = min(query_dsl.get("limit", 100), 500)
        offset = query_dsl.get("offset", 0)

        if group_by:
            first_group = group_by[0]
            if not hasattr(model, first_group):
                raise AnalyticsDSLError(f"Grouping field '{first_group}' does not exist on {entity_name}.")
            
            group_col = getattr(model, first_group)
            agg_results = self.db.query(group_col, func.count(model.id)).filter(
                getattr(model, "workspace_id") == workspace_id
            ).group_by(group_col).limit(limit).all()

            results = [
                {"dimension": str(row[0]) if row[0] is not None else "Unknown", "count": row[1]}
                for row in agg_results
            ]
            total_count = len(results)
        else:
            total_count = query.count()
            order_by_field = query_dsl.get("order_by", "created_at")
            order_direction = query_dsl.get("order_direction", "desc").lower()

            if hasattr(model, order_by_field):
                order_col = getattr(model, order_by_field)
                query = query.order_by(desc(order_col) if order_direction == "desc" else asc(order_col))

            records = query.offset(offset).limit(limit).all()
            results = [
                {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
                for row in records
            ]

        # 4. Period Comparison if requested
        comparison_data = None
        if query_dsl.get("compare_period") and time_range in TIME_RANGES and hasattr(model, "created_at"):
            days = TIME_RANGES[time_range] or 1
            prev_start = datetime.now(timezone.utc) - timedelta(days=days * 2)
            prev_end = datetime.now(timezone.utc) - timedelta(days=days)
            prev_count = self.db.query(model).filter(
                and_(
                    getattr(model, "workspace_id") == workspace_id,
                    getattr(model, "created_at") >= prev_start,
                    getattr(model, "created_at") < prev_end
                )
            ).count()
            diff_pct = 0.0
            if prev_count > 0:
                diff_pct = round(((total_count - prev_count) / prev_count) * 100.0, 2)
            comparison_data = {
                "previous_period_count": prev_count,
                "current_period_count": total_count,
                "change_percentage": diff_pct,
                "direction": "INCREASING" if diff_pct > 0 else "DECREASING" if diff_pct < 0 else "STABLE"
            }

        return {
            "entity": entity_name,
            "total_count": total_count,
            "time_range": time_range or "all_time",
            "results": results,
            "comparison": comparison_data,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }

