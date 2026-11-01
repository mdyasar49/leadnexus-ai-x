"""
Data Fabric Policy Enforcer (Phase 39)
Applies privacy masking, role-based redaction, and security policies across all 13 data domains.
"""

from typing import Any, Dict, List, Optional
from app.models.enterprise_data_fabric import PolicyEnforcementAction, DataClassification


class DataPolicyEnforcer:
    """Enforces data access policies, field-level masking, and classification checks."""

    @classmethod
    def mask_value(cls, value: Any, mask_type: str = "PARTIAL") -> str:
        """Applies privacy masking to sensitive field values."""
        if value is None:
            return ""
        s = str(value).strip()
        if not s:
            return ""

        if "@" in s:  # Email
            parts = s.split("@", 1)
            local = parts[0]
            masked_local = local[0] + "***" + (local[-1] if len(local) > 1 else "")
            return f"{masked_local}@{parts[1]}"
        elif len(s) >= 7 and any(c.isdigit() for c in s):  # Phone or ID
            return s[:2] + "****" + s[-2:]
        else:
            return s[0] + "***" if len(s) > 1 else "***"

    @classmethod
    def enforce_policies(
        cls,
        record: Dict[str, Any],
        domain: str,
        policies: List[Dict[str, Any]],
        user_role: str = "member",
    ) -> Dict[str, Any]:
        """
        Applies active policies to a domain record based on user role and domain.
        Returns transformed/masked record.
        """
        output = dict(record)

        for pol in policies:
            if not pol.get("is_active", True):
                continue

            target_dom = pol.get("target_domain", "").upper()
            if target_dom != "ALL" and target_dom != domain.upper():
                continue

            action = pol.get("enforcement_action", PolicyEnforcementAction.MASK)
            field = pol.get("field_name")

            # Admins bypass masking unless policy is strictly enforced
            if user_role == "admin" and not pol.get("enforce_on_admin", False):
                continue

            if action == PolicyEnforcementAction.MASK and field and field in output:
                output[field] = cls.mask_value(output[field])
            elif action == PolicyEnforcementAction.RESTRICT and field and field in output:
                output[field] = "[RESTRICTED]"
            elif action == PolicyEnforcementAction.BLOCK:
                # If block policy triggers, redact entire record body
                return {"_blocked": True, "reason": pol.get("policy_name", "Policy blocked access.")}

        return output

