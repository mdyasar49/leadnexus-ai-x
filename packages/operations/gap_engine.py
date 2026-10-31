from typing import Dict, Any, List
from app.models.operations import ResearchGapType


class GapEngine:
    """
    Research Gap Engine:
    - Identifies missing critical data attributes for discovered companies
    - Formulates targeted follow-up research queries
    """
    @classmethod
    def identify_gaps(cls, company: Dict[str, Any], has_odoo_signal: bool = False) -> List[Dict[str, Any]]:
        gaps = []

        domain = company.get("domain")
        name = company.get("name", "Company")

        if not domain:
            gaps.append({
                "gap_type": ResearchGapType.DOMAIN_MISSING.value,
                "priority": "CRITICAL",
                "suggested_query": f'"{name}" official website domain',
            })

        if not company.get("contacts"):
            gaps.append({
                "gap_type": ResearchGapType.DECISION_MAKER_MISSING.value,
                "priority": "HIGH",
                "suggested_query": f'"{name}" (CEO OR CTO OR Founder OR "IT Manager")',
            })

        if not company.get("business_phone") and not any(c.get("business_phone") for c in company.get("contacts", [])):
            gaps.append({
                "gap_type": ResearchGapType.PHONE_MISSING.value,
                "priority": "NORMAL",
                "suggested_query": f'"{name}" contact phone number office',
            })

        if not has_odoo_signal:
            gaps.append({
                "gap_type": ResearchGapType.ODOO_EVIDENCE_WEAK.value,
                "priority": "HIGH",
                "suggested_query": f'"{name}" ("Odoo" OR "ERP migration")',
            })

        return gaps

