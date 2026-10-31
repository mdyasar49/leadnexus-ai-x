import re
import hashlib
from typing import Dict, Any, List, Optional

TARGET_JOB_TITLES = [
    "Odoo Developer",
    "ERP Developer",
    "Odoo Consultant",
    "ERP Consultant",
    "Odoo Administrator",
    "Business Systems Manager",
    "ERP Manager",
    "IT Manager",
    "Head of IT",
    "CTO",
    "Technology Manager"
]


class JobIntelligence:
    """
    Public Job Posting Intelligence:
    - Analyzes job postings for tech stack requirements, seniority, and ERP scope
    - Strictly does NOT assume a job posting is a verified person/decision maker
    """
    @classmethod
    def analyze_job(cls, title: str, description: str, job_url: str) -> Dict[str, Any]:
        full_content = f"{title}\n{description}"
        matched_roles = []
        for role in TARGET_JOB_TITLES:
            parts = role.split()
            if len(parts) == 2:
                # E.g. "Odoo" ... "Consultant" matches "Odoo Implementation Consultant"
                flex_pattern = rf"\b{re.escape(parts[0])}\b(?:\s+\w+){{0,2}}\s+\b{re.escape(parts[1])}\b"
                if re.search(flex_pattern, full_content, re.IGNORECASE):
                    matched_roles.append(role)
            else:
                if re.search(rf"\b{re.escape(role)}\b", full_content, re.IGNORECASE):
                    matched_roles.append(role)

        is_hiring_erp = bool(re.search(r"\b(odoo|erp|zoho|salesforce)\b", full_content, re.IGNORECASE))

        evidence_hash = hashlib.sha256(f"{job_url}:{title}".encode("utf-8")).hexdigest()

        return {
            "title": title,
            "job_url": job_url,
            "matched_roles": matched_roles,
            "is_hiring_erp": is_hiring_erp,
            "evidence_snippet": f"Hiring for: {title}",
            "evidence_hash": evidence_hash,
            "confidence": 0.95 if matched_roles else 0.75,
        }
