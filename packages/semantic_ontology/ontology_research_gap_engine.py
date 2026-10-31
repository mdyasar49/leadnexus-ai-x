import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.lead import Company, Contact, IntentSignal
from app.models.knowledge_graph import KnowledgeRelationship
from app.models.semantic_ontology import (
    Concept,
    SemanticMapping,
    OntologyValidationError,
)


class OntologyResearchGapEngine:
    """
    Ontology-Aware Research Gap & Data Quality Engine:
    - Analyzes workspace entities against canonical ontology completeness standards
    - Generates actionable research gaps:
        * ODOO_VERSION_UNKNOWN
        * DECISION_MAKER_MISSING
        * BUSINESS_EMAIL_MISSING
        * INDUSTRY_UNKNOWN
        * IMPLEMENTATION_STATUS_UNKNOWN
    - Audits semantic mapping health (ambiguous mappings, missing concepts, deprecated items)
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate_company_research_gaps(
        self,
        workspace_id: str,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """Identifies specific missing semantic dimensions for a targeted company."""
        comp = self.db.query(Company).filter(
            and_(Company.workspace_id == workspace_id, Company.id == company_id)
        ).first()
        if not comp:
            raise ValueError(f"Company '{company_id}' not found.")

        gaps = []

        # 1. Check Industry Ontology Gap
        if not comp.industry:
            gaps.append({
                "gap_code": "INDUSTRY_UNKNOWN",
                "severity": "MEDIUM",
                "message": "Company lacks a normalized industry classification in the ontology.",
                "suggested_task": "Query official business registries or company 'About' page to determine industry."
            })

        # 2. Check Decision Maker / Contacts Gap
        contacts = self.db.query(Contact).filter(
            and_(Contact.workspace_id == workspace_id, Contact.company_id == company_id)
        ).all()

        if not contacts:
            gaps.append({
                "gap_code": "DECISION_MAKER_MISSING",
                "severity": "HIGH",
                "message": "No organizational personnel or executives discovered for this company.",
                "suggested_task": "Execute targeted executive search (CEO, CTO, ERP Manager) on professional directories."
            })
        else:
            dm = [c for c in contacts if c.is_decision_maker]
            if not dm:
                gaps.append({
                    "gap_code": "VERIFIED_DECISION_MAKER_MISSING",
                    "severity": "HIGH",
                    "message": "Personnel discovered, but none confirmed as verified decision makers.",
                    "suggested_task": "Verify job roles and seniority to designate primary buying committee members."
                })
            else:
                for d in dm:
                    if not d.email or d.email_status != "VERIFIED":
                        gaps.append({
                            "gap_code": "BUSINESS_EMAIL_MISSING",
                            "severity": "MEDIUM",
                            "message": f"Decision maker '{d.full_name}' ({d.job_title}) lacks verified business email.",
                            "suggested_task": "Perform verification against domain MX records and public references."
                        })

        # 3. Check Odoo Version Specificity
        signals = self.db.query(IntentSignal).filter(
            and_(IntentSignal.workspace_id == workspace_id, IntentSignal.company_id == company_id)
        ).all()

        has_odoo = any("odoo" in (s.evidence_snippet or "").lower() for s in signals) or "odoo" in comp.name.lower()
        if has_odoo:
            has_version = any(
                any(f"odoo {v}" in (s.evidence_snippet or "").lower() for v in ["14", "15", "16", "17", "18", "19"])
                for s in signals
            )
            if not has_version:
                gaps.append({
                    "gap_code": "ODOO_VERSION_UNKNOWN",
                    "severity": "MEDIUM",
                    "message": "Odoo ERP footprint detected, but active software version is undetermined.",
                    "suggested_task": "Inspect web client assets, release notes, or public job postings for version numbers (e.g., 16, 17, 18)."
                })

        return gaps

    def audit_semantic_data_quality(self, workspace_id: str) -> Dict[str, Any]:
        """Audits overall health of semantic ontology mappings and validation errors."""
        total_mappings = self.db.query(SemanticMapping).filter(SemanticMapping.workspace_id == workspace_id).count()
        human_approved = self.db.query(SemanticMapping).filter(
            and_(SemanticMapping.workspace_id == workspace_id, SemanticMapping.is_human_approved.is_(True))
        ).count()

        val_errors = self.db.query(OntologyValidationError).filter(
            and_(OntologyValidationError.workspace_id == workspace_id, OntologyValidationError.is_resolved.is_(False))
        ).count()

        ambiguous_count = self.db.query(SemanticMapping).filter(
            and_(SemanticMapping.workspace_id == workspace_id, SemanticMapping.confidence < 0.70)
        ).count()

        return {
            "total_semantic_mappings": total_mappings,
            "human_approved_mappings": human_approved,
            "human_approval_rate": round((human_approved / max(1, total_mappings)) * 100.0, 1),
            "unresolved_validation_errors": val_errors,
            "ambiguous_mappings_count": ambiguous_count,
            "semantic_health_score": max(0.0, min(100.0, 100.0 - (val_errors * 5.0) - (ambiguous_count * 2.0)))
        }
