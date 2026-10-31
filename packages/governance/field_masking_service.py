"""
LeadNexus AI X - Phase 29: Enterprise Governance & Field-Level Privacy
Field Masking Service: Pseudonymization, PII masking, and data protection transformers.
"""

import re
from typing import Any, Dict, List, Optional


class FieldMaskingService:
    """Provides consistent enterprise data masking and pseudonymization for PII attributes."""

    @classmethod
    def mask_email(cls, email: Optional[str]) -> str:
        """
        Masks email addresses: sarah.jenkins@acme.com -> s***s@acme.com
        """
        if not email or "@" not in email:
            return "***@***.com"

        user_part, domain_part = email.split("@", 1)
        if len(user_part) <= 2:
            masked_user = user_part[0] + "***"
        else:
            masked_user = user_part[0] + "***" + user_part[-1]

        return f"{masked_user}@{domain_part}"

    @classmethod
    def mask_phone(cls, phone: Optional[str]) -> str:
        """
        Masks telephone numbers: +1-555-234-5678 -> +1 ***-***-5678
        """
        if not phone:
            return "***-***-****"

        cleaned = re.sub(r"[^\d+]", "", phone)
        if len(cleaned) < 4:
            return "***-***-****"

        last_4 = cleaned[-4:]
        prefix = cleaned[:-4]
        # Keep country code if available
        if prefix.startswith("+"):
            country_code = prefix[:2]
            return f"{country_code} ***-***-{last_4}"
        return f"***-***-{last_4}"

    @classmethod
    def mask_name(cls, name: Optional[str]) -> str:
        """
        Masks full names: Sarah Jenkins -> S**** J******
        """
        if not name:
            return "***"

        parts = name.strip().split()
        masked_parts = []
        for p in parts:
            if len(p) <= 1:
                masked_parts.append(p)
            else:
                masked_parts.append(p[0] + "*" * (len(p) - 1))
        return " ".join(masked_parts)

    @classmethod
    def mask_financial(cls, value: Any) -> str:
        """
        Masks exact financial or salary figures into generalized range brackets.
        """
        try:
            num = float(value)
            if num < 50000:
                return "< $50k (Confidential)"
            elif num < 250000:
                return "$50k - $250k (Confidential)"
            elif num < 1000000:
                return "$250k - $1M (Confidential)"
            elif num < 10000000:
                return "$1M - $10M (Confidential)"
            else:
                return "> $10M (Confidential)"
        except (ValueError, TypeError):
            return "[Confidential Financial Value]"

    @classmethod
    def mask_record(
        cls,
        record: Dict[str, Any],
        fields_to_mask: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Returns a masked copy of the record for unauthorized or restricted view contexts.
        """
        if not fields_to_mask:
            fields_to_mask = ["email", "phone", "name", "salary", "revenue", "personal_address"]

        cloned = dict(record)
        for k, val in list(cloned.items()):
            k_lower = k.lower()
            if "company" in k_lower or "organization" in k_lower:
                continue
            if any(f.lower() in k_lower for f in fields_to_mask):
                if val is not None:
                    if "email" in k_lower:
                        cloned[k] = cls.mask_email(str(val))
                    elif "phone" in k_lower:
                        cloned[k] = cls.mask_phone(str(val))
                    elif "name" in k_lower:
                        cloned[k] = cls.mask_name(str(val))
                    elif "salary" in k_lower or "revenue" in k_lower:
                        cloned[k] = cls.mask_financial(val)
                    else:
                        cloned[k] = "[MASKED]"
        return cloned
