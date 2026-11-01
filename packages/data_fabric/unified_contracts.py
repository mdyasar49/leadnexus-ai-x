"""
Unified Data Contracts Engine (Phase 39)
Validates domain entity payloads against contracted JSON schemas, quality rules, and freshness SLAs.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re


class ContractValidationError(Exception):
    """Raised when an asset fails schema conformity, freshness SLA, or quality constraints."""
    def __init__(self, message: str, violations: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.message = message
        self.violations = violations or []


class UnifiedDataContractEngine:
    """Validates records across all 13 enterprise data fabric domains against formal contracts."""

    @classmethod
    def validate_payload(
        cls,
        payload: Dict[str, Any],
        schema_definition: Dict[str, Any],
        quality_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validates payload against schema definition and optional quality rules.
        Returns (is_valid, list_of_violations).
        """
        violations: List[Dict[str, Any]] = []

        # 1. Required Fields Validation
        required_fields = schema_definition.get("required", [])
        for field in required_fields:
            if field not in payload or payload[field] is None or payload[field] == "":
                violations.append({
                    "rule": "REQUIRED_FIELD",
                    "field": field,
                    "message": f"Mandatory contracted field '{field}' is missing or empty.",
                })

        # 2. Type Checking
        properties = schema_definition.get("properties", {})
        for field, prop in properties.items():
            if field in payload and payload[field] is not None:
                expected_type = prop.get("type")
                val = payload[field]

                if expected_type == "string" and not isinstance(val, str):
                    violations.append({
                        "rule": "TYPE_MISMATCH",
                        "field": field,
                        "message": f"Field '{field}' expected string, got {type(val).__name__}.",
                    })
                elif expected_type == "number" and not isinstance(val, (int, float)):
                    violations.append({
                        "rule": "TYPE_MISMATCH",
                        "field": field,
                        "message": f"Field '{field}' expected number, got {type(val).__name__}.",
                    })
                elif expected_type == "boolean" and not isinstance(val, bool):
                    violations.append({
                        "rule": "TYPE_MISMATCH",
                        "field": field,
                        "message": f"Field '{field}' expected boolean, got {type(val).__name__}.",
                    })
                elif expected_type == "array" and not isinstance(val, list):
                    violations.append({
                        "rule": "TYPE_MISMATCH",
                        "field": field,
                        "message": f"Field '{field}' expected list/array, got {type(val).__name__}.",
                    })

        # 3. Quality Rules Validation
        if quality_rules:
            for rule in quality_rules:
                field = rule.get("field")
                rule_type = rule.get("type")  # REGEX, RANGE, ENUM
                if field in payload and payload[field] is not None:
                    val = payload[field]
                    if rule_type == "REGEX":
                        pattern = rule.get("pattern", "")
                        if pattern and isinstance(val, str) and not re.search(pattern, val):
                            violations.append({
                                "rule": "REGEX_VIOLATION",
                                "field": field,
                                "message": rule.get("message", f"Value '{val}' fails regex pattern '{pattern}'."),
                            })
                    elif rule_type == "RANGE":
                        min_val = rule.get("min")
                        max_val = rule.get("max")
                        if isinstance(val, (int, float)):
                            if min_val is not None and val < min_val:
                                violations.append({
                                    "rule": "RANGE_UNDERFLOW",
                                    "field": field,
                                    "message": f"Field '{field}' value {val} < minimum {min_val}.",
                                })
                            if max_val is not None and val > max_val:
                                violations.append({
                                    "rule": "RANGE_OVERFLOW",
                                    "field": field,
                                    "message": f"Field '{field}' value {val} > maximum {max_val}.",
                                })
                    elif rule_type == "ENUM":
                        allowed = rule.get("allowed", [])
                        if val not in allowed:
                            violations.append({
                                "rule": "ENUM_VIOLATION",
                                "field": field,
                                "message": f"Field '{field}' value '{val}' not in allowed set: {allowed}.",
                            })

        is_valid = len(violations) == 0
        return is_valid, violations

    @classmethod
    def check_freshness_sla(
        cls,
        last_updated_at: datetime,
        sla_freshness_seconds: int = 3600,
    ) -> Tuple[bool, float]:
        """
        Calculates age delta and evaluates compliance against SLA freshness threshold.
        Returns (is_compliant, age_seconds).
        """
        now = datetime.now(timezone.utc)
        if last_updated_at.tzinfo is None:
            last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)

        age_seconds = (now - last_updated_at).total_seconds()
        is_compliant = age_seconds <= sla_freshness_seconds
        return is_compliant, round(age_seconds, 2)
