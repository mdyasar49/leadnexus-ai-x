import re
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from sqlalchemy import and_, or_, not_, Column, text
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore, IntentAssessment, BuyingReadinessAssessment, AIReasoningResult
from app.models.technology import TechnologyObservation


SUPPORTED_OPERATORS = {
    "=", "==", "!=", "<>", ">", ">=", "<", "<=",
    "IN", "NOT IN", "CONTAINS", "LIKE", "ILIKE",
    "EXISTS", "IS NULL", "IS NOT NULL"
}

ALLOWED_FIELDS = {
    "country": {"model": "Company", "attr": "country", "type": "str"},
    "state": {"model": "Company", "attr": "state", "type": "str"},
    "city": {"model": "Company", "attr": "city", "type": "str"},
    "industry": {"model": "Company", "attr": "industry", "type": "str"},
    "name": {"model": "Company", "attr": "name", "type": "str"},
    "domain": {"model": "Company", "attr": "domain", "type": "str"},
    "status": {"model": "Company", "attr": "status", "type": "str"},
    "employee_count_range": {"model": "Company", "attr": "employee_count_range", "type": "str"},
    "lead_score": {"model": "Company", "attr": "lead_score", "type": "int"},
    
    # LeadScore table fields
    "lead_priority_score": {"model": "LeadScore", "attr": "lead_priority_score", "type": "float"},
    "priority_tier": {"model": "LeadScore", "attr": "priority_tier", "type": "str"},
    "icp_fit_score": {"model": "LeadScore", "attr": "icp_fit_score", "type": "float"},
    "intent_score": {"model": "LeadScore", "attr": "intent_score", "type": "float"},
    "buying_readiness_score": {"model": "LeadScore", "attr": "buying_readiness_score", "type": "float"},
    "evidence_confidence_score": {"model": "LeadScore", "attr": "evidence_confidence_score", "type": "float"},
    "data_quality_score": {"model": "LeadScore", "attr": "data_quality_score", "type": "float"},
    "contact_quality_score": {"model": "LeadScore", "attr": "contact_quality_score", "type": "float"},
    "freshness_score": {"model": "LeadScore", "attr": "freshness_score", "type": "float"},

    # Virtual & joined filters
    "technology": {"model": "TechnologyObservation", "attr": "technology", "type": "str"},
    "technology_version": {"model": "TechnologyObservation", "attr": "version", "type": "str"},
    "intent_keyword": {"model": "IntentSignal", "attr": "detected_keyword", "type": "str"},
    "signal_type": {"model": "IntentSignal", "attr": "signal_type", "type": "str"},
    "has_email": {"model": "Virtual", "type": "bool"},
    "has_phone": {"model": "Virtual", "type": "bool"},
    "has_decision_maker": {"model": "Virtual", "type": "bool"},
}


class SearchDSLError(ValueError):
    """Raised when query AST or filter validation fails."""
    pass


class SearchDSLParser:
    """Safe, controlled Query DSL Parser that transforms JSON AST filters into SQLAlchemy expressions."""

    @staticmethod
    def parse_condition(cond: Dict[str, Any]) -> Any:
        """Parses a single leaf condition or nested logical branch."""
        if not isinstance(cond, dict):
            raise SearchDSLError("Each condition must be a dictionary.")

        # Check for logical compound operator
        if "operator" in cond and cond["operator"].upper() in {"AND", "OR", "NOT"}:
            op = cond["operator"].upper()
            conditions = cond.get("conditions", [])
            if not isinstance(conditions, list):
                raise SearchDSLError(f"Conditions for '{op}' must be a list.")
            
            sub_clauses = [SearchDSLParser.parse_condition(c) for c in conditions if c]
            if not sub_clauses:
                return and_()

            if op == "AND":
                return and_(*sub_clauses)
            elif op == "OR":
                return or_(*sub_clauses)
            elif op == "NOT":
                return not_(sub_clauses[0])

        field = cond.get("field")
        op = str(cond.get("operator", "=")).upper()
        value = cond.get("value")

        if not field:
            raise SearchDSLError("Leaf condition missing required 'field' property.")

        if field not in ALLOWED_FIELDS:
            raise SearchDSLError(f"Field '{field}' is not in the allowed searchable fields whitelist.")

        if op not in SUPPORTED_OPERATORS:
            raise SearchDSLError(f"Operator '{op}' is not supported. Must be one of {SUPPORTED_OPERATORS}")

        meta = ALLOWED_FIELDS[field]
        model_name = meta.get("model")

        # Map to SQLAlchemy entity
        if model_name == "Company":
            col = getattr(Company, meta["attr"])
            return SearchDSLParser._apply_column_operator(col, op, value)
        elif model_name == "LeadScore":
            col = getattr(LeadScore, meta["attr"])
            return SearchDSLParser._apply_column_operator(col, op, value)
        elif model_name == "Virtual":
            # Handled at query level via joins / subqueries
            return None
        elif model_name in {"TechnologyObservation", "IntentSignal"}:
            # Special joined expressions
            return None
        
        return and_()

    @staticmethod
    def _apply_column_operator(col: Column, op: str, value: Any):
        if op in {"=", "=="}:
            return col == value
        elif op in {"!=", "<>"}:
            return col != value
        elif op == ">":
            return col > value
        elif op == ">=":
            return col >= value
        elif op == "<":
            return col < value
        elif op == "<=":
            return col <= value
        elif op == "IN":
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            return col.in_(value)
        elif op == "NOT IN":
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            return ~col.in_(value)
        elif op in {"CONTAINS", "LIKE", "ILIKE"}:
            return col.ilike(f"%{value}%")
        elif op == "IS NULL":
            return col.is_(None)
        elif op in {"EXISTS", "IS NOT NULL"}:
            return col.is_not(None)
        
        return col == value

    @staticmethod
    def parse_filters(filters: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Tuple[List[Any], Dict[str, Any]]:
        """Parses a filter payload into SQL expressions and extracted virtual criteria."""
        clauses = []
        virtual_criteria = {}

        if not filters:
            return clauses, virtual_criteria

        if isinstance(filters, dict):
            # Check if root is a logical operator
            if "operator" in filters and filters["operator"].upper() in {"AND", "OR", "NOT"}:
                parsed = SearchDSLParser.parse_condition(filters)
                if parsed is not None:
                    clauses.append(parsed)
                return clauses, virtual_criteria
            elif "conditions" in filters and isinstance(filters["conditions"], list):
                items = filters["conditions"]
            else:
                # Key-value shorthand format: {"country": "Australia", "lead_score": 75}
                items = []
                for k, v in filters.items():
                    if k in ALLOWED_FIELDS:
                        if isinstance(v, dict) and "operator" in v:
                            items.append({"field": k, "operator": v["operator"], "value": v.get("value")})
                        elif isinstance(v, list):
                            items.append({"field": k, "operator": "IN", "value": v})
                        else:
                            items.append({"field": k, "operator": "=", "value": v})
        elif isinstance(filters, list):
            items = filters
        else:
            raise SearchDSLError("Filters must be a dict or list of conditions.")

        for item in items:
            field = item.get("field")
            if field in ALLOWED_FIELDS and ALLOWED_FIELDS[field].get("model") in {"Virtual", "TechnologyObservation", "IntentSignal"}:
                virtual_criteria[field] = item
            else:
                expr = SearchDSLParser.parse_condition(item)
                if expr is not None:
                    clauses.append(expr)

        return clauses, virtual_criteria


class NaturalLanguageQueryBuilder:
    """Safely converts human natural language queries into verified Search DSL schemas with a human-readable explanation."""

    COUNTRY_KEYWORDS = {
        "australia": "Australia", "australian": "Australia",
        "united states": "United States", "usa": "United States", "us": "United States",
        "united kingdom": "United Kingdom", "uk": "United Kingdom",
        "india": "India", "indian": "India",
        "canada": "Canada", "canadian": "Canada",
        "germany": "Germany", "german": "Germany",
        "france": "France", "french": "France",
        "singapore": "Singapore",
    }

    TECH_KEYWORDS = [
        "odoo", "zoho", "salesforce", "hubspot", "sap", "netsuite",
        "shopify", "woocommerce", "magento", "wordpress", "react", "vue",
        "django", "flask", "fastapi", "postgres", "aws", "gcp", "azure"
    ]

    INTENT_KEYWORDS = [
        "migration", "migrating", "upgrade", "integration", "integrating",
        "implementation", "developer", "partner", "consultant", "support"
    ]

    @classmethod
    def parse_nl_query(cls, query: str) -> Dict[str, Any]:
        """Converts free-text search prompt to a safe structured AST and preview description."""
        if not query or not query.strip():
            return {
                "parsed_dsl": {"operator": "AND", "conditions": []},
                "explanation": "No filters applied (matches all leads)",
                "detected_criteria": {}
            }

        text = query.lower()
        conditions = []
        criteria_summary = []
        detected = {}

        # 1. Detect Country
        for key, country_name in cls.COUNTRY_KEYWORDS.items():
            pattern = r'\b' + re.escape(key) + r'\b'
            if re.search(pattern, text):
                conditions.append({"field": "country", "operator": "=", "value": country_name})
                criteria_summary.append(f"Country is '{country_name}'")
                detected["country"] = country_name
                break

        # 2. Detect Technology
        for tech in cls.TECH_KEYWORDS:
            pattern = r'\b' + re.escape(tech) + r'\b'
            if re.search(pattern, text):
                conditions.append({"field": "technology", "operator": "CONTAINS", "value": tech})
                criteria_summary.append(f"Uses technology '{tech.title()}'")
                detected["technology"] = tech
                break

        # 3. Detect Intent Keywords
        for intent in cls.INTENT_KEYWORDS:
            pattern = r'\b' + re.escape(intent) + r'\b'
            if re.search(pattern, text):
                conditions.append({"field": "intent_keyword", "operator": "CONTAINS", "value": intent})
                criteria_summary.append(f"Signal intent mentions '{intent}'")
                detected["intent_keyword"] = intent
                break

        # 4. Detect Score Thresholds e.g. "score > 80", "score >= 70", "lead score over 60"
        score_match = re.search(r'(?:score|priority|rating)\s*(?:>=|>|over|above|at least)\s*(\d{1,3})', text)
        if score_match:
            min_score = float(score_match.group(1))
            conditions.append({"field": "lead_priority_score", "operator": ">=", "value": min_score})
            criteria_summary.append(f"Lead priority score >= {min_score}")
            detected["min_score"] = min_score

        # 5. Detect Priority Tiers (P0, P1, P2, high priority, critical)
        if "critical" in text or "p0" in text:
            conditions.append({"field": "priority_tier", "operator": "=", "value": "P0_CRITICAL"})
            criteria_summary.append("Priority tier is P0 (Critical)")
            detected["priority_tier"] = "P0_CRITICAL"
        elif "high priority" in text or "p1" in text:
            conditions.append({"field": "priority_tier", "operator": "IN", "value": ["P0_CRITICAL", "P1_HIGH"]})
            criteria_summary.append("Priority tier is P0 or P1 (High/Critical)")
            detected["priority_tier"] = "HIGH"

        # 6. Detect Contact availability e.g. "with email", "verified email", "has email", "decision maker"
        if any(k in text for k in ["with email", "has email", "verified email", "email"]):
            conditions.append({"field": "has_email", "operator": "=", "value": True})
            criteria_summary.append("Must have verified/public email")
            detected["has_email"] = True
        if any(k in text for k in ["decision maker", "decision makers", "decision-maker"]):
            conditions.append({"field": "has_decision_maker", "operator": "=", "value": True})
            criteria_summary.append("Must have identified decision maker")
            detected["has_decision_maker"] = True

        parsed_dsl = {
            "operator": "AND",
            "conditions": conditions
        }

        explanation = "; ".join(criteria_summary) if criteria_summary else f"Full-text search for '{query.strip()}'"

        return {
            "query": query,
            "parsed_dsl": parsed_dsl,
            "explanation": explanation,
            "detected_criteria": detected
        }
