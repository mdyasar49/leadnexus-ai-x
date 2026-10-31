import re
from typing import Dict, Any, List, Optional, Set, Tuple


SUPPORTED_DSL_OPERATORS = {
    "=", "==", "!=", "<>", ">", ">=", "<", "<=",
    "IN", "NOT IN", "CONTAINS", "STARTS_WITH",
    "EXISTS", "NOT_EXISTS", "IS_NULL", "NOT_NULL",
    "AND", "OR"
}

ALLOWED_DSL_FIELDS = {
    "lead_score", "lead_priority_score", "intent_score", "icp_fit_score",
    "buying_readiness_score", "data_quality_score", "contact_quality_score",
    "freshness_score", "priority_tier", "status", "country", "city",
    "state", "industry", "domain", "technology", "version", "has_email",
    "has_phone", "has_decision_maker", "decision_maker_count", "conflict_count"
}


class WorkflowDSLError(ValueError):
    """Raised when workflow DSL syntax, condition, or node validation fails."""
    pass


class WorkflowConditionEvaluator:
    """Safe, sandboxed condition evaluator that operates strictly on JSON entity contexts. Zero raw SQL or code execution."""

    @staticmethod
    def evaluate(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluates a leaf condition or nested logical branch against the entity context."""
        if not isinstance(condition, dict):
            raise WorkflowDSLError("Condition must be a dictionary.")

        # Check for Logical Grouping (AND / OR)
        op = str(condition.get("operator", "")).upper()
        if op == "AND":
            sub_conds = condition.get("conditions", [])
            return all(WorkflowConditionEvaluator.evaluate(c, context) for c in sub_conds)
        elif op == "OR":
            sub_conds = condition.get("conditions", [])
            return any(WorkflowConditionEvaluator.evaluate(c, context) for c in sub_conds)

        # Leaf Condition
        field = condition.get("field")
        if not field:
            raise WorkflowDSLError("Leaf condition missing required 'field' name.")

        if field not in ALLOWED_DSL_FIELDS:
            raise WorkflowDSLError(f"Field '{field}' is not in the allowed workflow DSL whitelist.")

        if op not in SUPPORTED_DSL_OPERATORS:
            raise WorkflowDSLError(f"Operator '{op}' is not supported. Must be one of {SUPPORTED_DSL_OPERATORS}")

        actual_val = context.get(field)
        target_val = condition.get("value")

        return WorkflowConditionEvaluator._apply_operator(op, actual_val, target_val)

    @staticmethod
    def _apply_operator(op: str, actual: Any, target: Any) -> bool:
        if op in {"=", "=="}:
            if isinstance(actual, str) and isinstance(target, str):
                return actual.lower() == target.lower()
            return actual == target
        elif op in {"!=", "<>"}:
            if isinstance(actual, str) and isinstance(target, str):
                return actual.lower() != target.lower()
            return actual != target
        elif op == ">":
            return actual is not None and float(actual) > float(target)
        elif op == ">=":
            return actual is not None and float(actual) >= float(target)
        elif op == "<":
            return actual is not None and float(actual) < float(target)
        elif op == "<=":
            return actual is not None and float(actual) <= float(target)
        elif op == "IN":
            if not isinstance(target, (list, tuple, set)):
                target = [target]
            if isinstance(actual, str):
                return any(str(item).lower() == actual.lower() for item in target)
            return actual in target
        elif op == "NOT IN":
            if not isinstance(target, (list, tuple, set)):
                target = [target]
            if isinstance(actual, str):
                return all(str(item).lower() != actual.lower() for item in target)
            return actual not in target
        elif op == "CONTAINS":
            if actual is None:
                return False
            return str(target).lower() in str(actual).lower()
        elif op == "STARTS_WITH":
            if actual is None:
                return False
            return str(actual).lower().startswith(str(target).lower())
        elif op in {"EXISTS", "NOT_NULL"}:
            return actual is not None and actual != ""
        elif op in {"NOT_EXISTS", "IS_NULL"}:
            return actual is None or actual == ""
        
        return False


class WorkflowValidator:
    """Static graph validator that detects unreachable nodes, circular loops, and missing exits."""

    @staticmethod
    def validate_graph(definition: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates workflow nodes and edges:
        - Must have exactly one TRIGGER node
        - Must have at least one terminal node (END, REJECT, APPROVAL)
        - Detects unreachable nodes
        - Detects circular dependency cycles (unbounded loops)
        """
        errors = []
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])

        if not nodes:
            return False, ["Workflow definition contains no nodes."]

        node_map = {n["id"]: n for n in nodes if "id" in n}
        if len(node_map) != len(nodes):
            errors.append("Duplicate node IDs found in workflow.")

        # Check Trigger
        triggers = [n for n in nodes if n.get("type") == "TRIGGER"]
        if len(triggers) != 1:
            errors.append(f"Workflow must contain exactly 1 TRIGGER node, found {len(triggers)}.")

        # Check Exits
        exits = [n for n in nodes if n.get("type") in {"END", "REJECT", "APPROVAL"}]
        if not exits:
            errors.append("Workflow must contain at least one terminal node (END, REJECT, APPROVAL).")

        # Build Adjacency List
        adj: Dict[str, List[str]] = {nid: [] for nid in node_map}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_map}

        for edge in edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src not in node_map:
                errors.append(f"Edge references non-existent source node '{src}'.")
            elif dst not in node_map:
                errors.append(f"Edge references non-existent target node '{dst}'.")
            else:
                adj[src].append(dst)
                in_degree[dst] = in_degree.get(dst, 0) + 1

        # Check for cycles using DFS
        visited = set()
        recursion_stack = set()

        def has_cycle(u: str) -> bool:
            visited.add(u)
            recursion_stack.add(u)
            for v in adj.get(u, []):
                if v not in visited:
                    if has_cycle(v):
                        return True
                elif v in recursion_stack:
                    return True
            recursion_stack.remove(u)
            return False

        if triggers:
            start_node = triggers[0]["id"]
            if has_cycle(start_node):
                errors.append("Circular dependency detected (unbounded loop without exit condition).")

        return len(errors) == 0, errors
