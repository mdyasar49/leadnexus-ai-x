"""
LeadNexus AI X - Phase 29: Enterprise Governance & Policy Engine
Policy Engine: Declarative rule evaluation, DSL interpreter, and access/export enforcement.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    MASK = "MASK"


@dataclass
class PolicyContext:
    workspace_id: str
    actor_id: str
    actor_roles: List[str]
    action: str  # e.g. "companies:export", "contacts:view_pii", "research:autonomous_run"
    resource_type: str  # e.g. "COMPANY", "CONTACT", "RUN"
    resource_data: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyEvaluationResult:
    decision: PolicyEffect
    matched_policy_id: Optional[str] = None
    matched_rule_name: Optional[str] = None
    reason: Optional[str] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PolicyEngine:
    """Evaluates declarative governance policies against incoming operational requests."""

    @classmethod
    def evaluate_condition(cls, condition: Dict[str, Any], context: PolicyContext) -> bool:
        """
        Evaluates a single DSL condition:
        e.g. {"field": "actor_roles", "operator": "contains", "value": "ADMIN"}
        """
        field_name = condition.get("field", "")
        op = condition.get("operator", "equals")
        target_value = condition.get("value")

        # Resolve field value from context
        if field_name == "actor_roles":
            actual_value = context.actor_roles
        elif field_name == "action":
            actual_value = context.action
        elif field_name == "actor_id":
            actual_value = context.actor_id
        elif field_name == "resource_type":
            actual_value = context.resource_type
        else:
            actual_value = context.resource_data.get(field_name)

        if op == "equals":
            return actual_value == target_value
        elif op == "not_equals":
            return actual_value != target_value
        elif op == "contains":
            if isinstance(actual_value, list):
                return target_value in actual_value
            elif isinstance(actual_value, str):
                return str(target_value).lower() in actual_value.lower()
            return False
        elif op == "in":
            if isinstance(target_value, list):
                if isinstance(actual_value, list):
                    return any(item in target_value for item in actual_value)
                return actual_value in target_value
            return False
        elif op == "not_in":
            if isinstance(target_value, list):
                if isinstance(actual_value, list):
                    return not any(item in target_value for item in actual_value)
                return actual_value not in target_value
            return True
        elif op == "greater_than":
            try:
                return float(actual_value) > float(target_value)
            except (ValueError, TypeError):
                return False
        elif op == "less_than":
            try:
                return float(actual_value) < float(target_value)
            except (ValueError, TypeError):
                return False

        return False

    @classmethod
    def evaluate_policy_rules(cls, rules_dsl: Dict[str, Any], context: PolicyContext) -> bool:
        """
        Evaluates rules DSL with support for 'all' (AND) and 'any' (OR) logic blocks.
        """
        if not rules_dsl:
            return True

        # AND block
        if "all" in rules_dsl:
            for cond in rules_dsl["all"]:
                if not cls.evaluate_condition(cond, context):
                    return False
            return True

        # OR block
        if "any" in rules_dsl:
            for cond in rules_dsl["any"]:
                if cls.evaluate_condition(cond, context):
                    return True
            return False

        # Single condition
        return cls.evaluate_condition(rules_dsl, context)

    @classmethod
    def evaluate(
        cls,
        policies: List[Dict[str, Any]],
        context: PolicyContext,
        default_effect: PolicyEffect = PolicyEffect.ALLOW,
    ) -> PolicyEvaluationResult:
        """
        Evaluates ordered active policies by priority (ascending order: priority 1 > priority 10).
        """
        sorted_policies = sorted(policies, key=lambda p: p.get("priority", 100))

        for policy in sorted_policies:
            if not policy.get("is_active", True):
                continue

            rules = policy.get("rules_dsl", {})
            if cls.evaluate_policy_rules(rules, context):
                effect_str = policy.get("effect", PolicyEffect.DENY.value)
                decision = PolicyEffect(effect_str) if effect_str in [e.value for e in PolicyEffect] else PolicyEffect.DENY

                return PolicyEvaluationResult(
                    decision=decision,
                    matched_policy_id=policy.get("id"),
                    matched_rule_name=policy.get("name"),
                    reason=f"Matched policy '{policy.get('name')}' with effect {decision.value}",
                )

        return PolicyEvaluationResult(
            decision=default_effect,
            reason=f"No matching policy. Defaulting to {default_effect.value}",
        )
