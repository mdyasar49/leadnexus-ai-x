"""
LeadNexus AI X - Phase 29: Enterprise Governance & Data Contracts
Data Contract Engine: Schema validation, SLA freshness checks, completeness thresholds, and contract enforcement.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ContractFieldSpec:
    name: str
    field_type: str  # "string", "number", "boolean", "list", "dict"
    required: bool = True
    description: str = ""


@dataclass
class ContractValidationResult:
    is_valid: bool
    is_accepted: bool  # Can be true if warn-and-log mode despite warnings
    completeness_score: float
    violations: List[str] = field(default_factory=list)
    freshness_hours: Optional[float] = None


class DataContractEngine:
    """Enforces data producer contracts, schema integrity, and freshness SLAs."""

    @classmethod
    def calculate_completeness(
        cls,
        payload: Dict[str, Any],
        required_fields: List[str],
        optional_fields: List[str],
    ) -> float:
        total_fields = len(required_fields) + len(optional_fields)
        if total_fields == 0:
            return 1.0

        filled_count = 0
        for f in required_fields + optional_fields:
            val = payload.get(f)
            if val is not None and val != "" and val != []:
                filled_count += 1

        return round(filled_count / total_fields, 2)

    @classmethod
    def validate_payload(
        cls,
        payload: Dict[str, Any],
        contract_def: Dict[str, Any],
    ) -> ContractValidationResult:
        """
        Validates payload against contract schema, freshness, and completeness score.
        """
        violations: List[str] = []
        schema = contract_def.get("schema_definition", {})
        required_fields = schema.get("required_fields", [])
        optional_fields = schema.get("optional_fields", [])
        sla_freshness_hours = contract_def.get("sla_freshness_hours", 72)
        min_completeness_score = contract_def.get("min_completeness_score", 0.70)
        enforcement_mode = contract_def.get("enforcement_mode", "STRICT_REJECT")

        # 1. Required field checks
        for rf in required_fields:
            if rf not in payload or payload[rf] is None or payload[rf] == "" or payload[rf] == []:
                violations.append(f"Missing required contract field: '{rf}'")

        # 2. Type checks
        type_specs = schema.get("field_types", {})
        for field_name, expected_type in type_specs.items():
            if field_name in payload and payload[field_name] is not None:
                val = payload[field_name]
                if expected_type == "string" and not isinstance(val, str):
                    violations.append(f"Field '{field_name}' must be of type string, got {type(val).__name__}")
                elif expected_type == "number" and not isinstance(val, (int, float)):
                    violations.append(f"Field '{field_name}' must be of type number, got {type(val).__name__}")
                elif expected_type == "list" and not isinstance(val, list):
                    violations.append(f"Field '{field_name}' must be of type list, got {type(val).__name__}")
                elif expected_type == "dict" and not isinstance(val, dict):
                    violations.append(f"Field '{field_name}' must be of type dict, got {type(val).__name__}")

        # 3. Completeness score
        completeness = cls.calculate_completeness(payload, required_fields, optional_fields)
        if completeness < min_completeness_score:
            violations.append(
                f"Completeness score {completeness} is below required contract minimum {min_completeness_score}"
            )

        # 4. Freshness SLA check
        observed_at_str = payload.get("observed_at") or payload.get("created_at")
        freshness_hours: Optional[float] = None
        if observed_at_str:
            try:
                if isinstance(observed_at_str, datetime):
                    obs_time = observed_at_str
                else:
                    obs_time = datetime.fromisoformat(str(observed_at_str).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = now - obs_time.replace(tzinfo=timezone.utc if obs_time.tzinfo is None else obs_time.tzinfo)
                freshness_hours = max(0.0, diff.total_seconds() / 3600.0)

                if freshness_hours > sla_freshness_hours:
                    violations.append(
                        f"Freshness SLA breach: Observation is {freshness_hours:.1f} hours old, exceeds SLA of {sla_freshness_hours} hours"
                    )
            except Exception:
                pass

        is_valid = len(violations) == 0
        if enforcement_mode == "WARN_AND_LOG":
            is_accepted = True
        else:
            is_accepted = is_valid

        return ContractValidationResult(
            is_valid=is_valid,
            is_accepted=is_accepted,
            completeness_score=completeness,
            violations=violations,
            freshness_hours=freshness_hours,
        )

