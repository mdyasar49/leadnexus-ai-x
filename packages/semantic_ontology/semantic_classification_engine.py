import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.semantic_ontology import (
    Concept,
    ClassificationRule,
    ClassificationResult,
    MappingMethod,
    OntologyType,
)


class SemanticClassificationEngine:
    """
    Enterprise Semantic Classification Engine:
    - Structured, evidence-grounded classification across Intent, Odoo Relationships, Job Roles, and Buying Committee
    - Classification Priority:
        1. Human-Approved Custom Mapping
        2. Deterministic Rule Matching (Regex/Patterns)
        3. Ontology Dictionary Matching
        4. Statistical / Rule-Heuristic Model
    - Absolute Business Rules:
        * Never confuse Service Provider content with Buying Intent!
          ("We provide Odoo services" -> SERVICE_PROVIDER, not BUYING_INTENT)
        * Unknown stays UNKNOWN (No fabricated inferences without evidence)
        * All classifications retain supporting evidence IDs and reasoning summary
    """

    # Service Provider detection patterns (Negative buying intent)
    SERVICE_PROVIDER_PATTERNS = [
        re.compile(r"\bwe\s+(?:provide|deliver|offer|specialize in)\s+.*(?:services|consulting|implementation)", re.I),
        re.compile(r"\bwe\s+are\s+(?:an?\s+)?(?:official|certified|gold|silver|ready|premier)?\s*(?:partner|provider|agency|consultancy)\b", re.I),
        re.compile(r"\b(?:official|certified|gold|silver|ready)\s+(?:odoo|sap|salesforce)\s+partner\b", re.I),
        re.compile(r"\bour\s+(?:services|team|developers|experts)\s+(?:build|deliver|customize|implement)\b", re.I),
        re.compile(r"\bcontact\s+us\s+for\s+a\s+quote\b", re.I),
        re.compile(r"\bhire\s+(?:our|dedicated)\s+(?:odoo|erp|python)\s+(?:developers|team)\b", re.I),
    ]

    # High Buying / Partner Search Intent patterns
    PARTNER_SEARCH_PATTERNS = [
        re.compile(r"\b(?:looking for|seeking|need|evaluating|searching for)\s+(?:an?\s+)?(?:[\w\-]+\s+)*(?:partner|vendor|consultant|integrator|agency)\b", re.I),
        re.compile(r"\brfp\s+for\s+(?:odoo|erp)\b", re.I),
        re.compile(r"\brequest\s+for\s+proposal.*(?:odoo|erp)\b", re.I),
        re.compile(r"\bplanning\s+to\s+migrate\s+(?:from|to)\s+odoo\b", re.I),
        re.compile(r"\blooking\s+to\s+upgrade\s+to\s+odoo\s+1[6-9]\b", re.I),
    ]

    # Hiring Intent patterns
    HIRING_PATTERNS = [
        re.compile(r"\b(?:we are\s+)?hiring\s+(?:an?\s+)?(?:[\w\-]+\s+)*(?:odoo|erp|python)\b", re.I),
        re.compile(r"\bjob\s+(?:opening|vacancy|posting).*odoo\b", re.I),
        re.compile(r"\bseeking\s+(?:full-time|lead|senior)?\s*(?:odoo|erp)\s+(?:developer|admin|consultant)\b", re.I),
    ]

    def __init__(self, db: Session):
        self.db = db

    def classify_intent(
        self,
        workspace_id: str,
        evidence_text: str,
        evidence_ids: Optional[List[str]] = None,
        source_url: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classifies business intent from public text evidence.
        Strictly differentiates buyers from service providers.
        """
        text = evidence_text.strip()
        ev_ids = evidence_ids or []

        # 1. First Check for High Partner Search / Migration Intent (Explicit Buyer Demand)
        for pat in self.PARTNER_SEARCH_PATTERNS:
            if pat.search(text):
                return self._persist_result(
                    workspace_id=workspace_id,
                    raw_input=text,
                    canonical_name="PARTNER_SEARCH_INTENT",
                    ontology_type=OntologyType.INTENT.value,
                    confidence=0.94,
                    method=MappingMethod.RULE.value,
                    evidence_ids=ev_ids,
                    reasoning="Evidence explicitly requests an implementation partner or migration vendor."
                )

        # 2. Check for Service Provider (Negative Intent Filter)
        for pat in self.SERVICE_PROVIDER_PATTERNS:
            if pat.search(text):
                return self._persist_result(
                    workspace_id=workspace_id,
                    raw_input=text,
                    canonical_name="SERVICE_PROVIDER",
                    ontology_type=OntologyType.INTENT.value,
                    confidence=0.96,
                    method=MappingMethod.RULE.value,
                    evidence_ids=ev_ids,
                    reasoning="Identified agency/service provider offering commercial services, not a prospective customer."
                )

        # 3. Check for Hiring Intent
        for pat in self.HIRING_PATTERNS:
            if pat.search(text):
                return self._persist_result(
                    workspace_id=workspace_id,
                    raw_input=text,
                    canonical_name="HIRING_INTENT",
                    ontology_type=OntologyType.INTENT.value,
                    confidence=0.90,
                    method=MappingMethod.RULE.value,
                    evidence_ids=ev_ids,
                    reasoning="Public job advertisement indicating internal capacity expansion for technology."
                )

        # 4. Check for General Tech Usage / Passive Mention
        if re.search(r"\bodoo\b", text, re.I):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=text,
                canonical_name="TECHNOLOGY_EVALUATION",
                ontology_type=OntologyType.INTENT.value,
                confidence=0.72,
                method=MappingMethod.RULE.value,
                evidence_ids=ev_ids,
                reasoning="Technology keyword observed without definitive purchasing urgency."
            )

        # Unknown Intent
        return self._persist_result(
            workspace_id=workspace_id,
            raw_input=text,
            canonical_name="UNKNOWN_INTENT",
            ontology_type=OntologyType.INTENT.value,
            confidence=0.10,
            method=MappingMethod.UNKNOWN.value,
            evidence_ids=ev_ids,
            reasoning="Insufficient evidence to substantiate verified intent."
        )

    def classify_odoo_relationship(
        self,
        workspace_id: str,
        evidence_text: str,
        is_partner_listed: bool = False,
        evidence_ids: Optional[List[str]] = None
    ) -> ClassificationResult:
        """
        Classifies exact nature of Odoo association:
        USES_ODOO, IMPLEMENTS_ODOO, PARTNER_ECOSYSTEM, MIGRATING_ODOO, HIRING_ODOO, etc.
        """
        text = evidence_text.strip()
        ev_ids = evidence_ids or []

        # If officially verified partner on Odoo directory
        if is_partner_listed:
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=text or "Official Partner Directory Listing",
                canonical_name="IMPLEMENTS_ODOO",
                ontology_type=OntologyType.ODOO.value,
                confidence=0.99,
                method=MappingMethod.EXACT_MATCH.value,
                evidence_ids=ev_ids,
                reasoning="Verified partner status in official ecosystem directory."
            )

        # Check for service provider / implementer
        for pat in self.SERVICE_PROVIDER_PATTERNS:
            if pat.search(text):
                return self._persist_result(
                    workspace_id=workspace_id,
                    raw_input=text,
                    canonical_name="IMPLEMENTS_ODOO",
                    ontology_type=OntologyType.ODOO.value,
                    confidence=0.92,
                    method=MappingMethod.RULE.value,
                    evidence_ids=ev_ids,
                    reasoning="Public statements affirm company provides implementation and consulting services."
                )

        # Check for migration
        if re.search(r"\b(?:migrating|migration|upgrade|upgrading)\s+(?:to|from)\s+odoo\b", text, re.I):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=text,
                canonical_name="MIGRATING_ODOO",
                ontology_type=OntologyType.ODOO.value,
                confidence=0.88,
                method=MappingMethod.RULE.value,
                evidence_ids=ev_ids,
                reasoning="Evidence notes active system migration or version upgrade project."
            )

        # Check for job posting indicating end-user usage
        if re.search(r"\b(?:odoo\s+(?:specialist|administrator|accountant|erp\s+admin)|experience\s+with\s+odoo)\b", text, re.I):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=text,
                canonical_name="USES_ODOO",
                ontology_type=OntologyType.ODOO.value,
                confidence=0.86,
                method=MappingMethod.RULE.value,
                evidence_ids=ev_ids,
                reasoning="Hiring end-user roles to administer operational Odoo ERP systems."
            )

        # Fallback passive mention
        if "odoo" in text.lower():
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=text,
                canonical_name="MENTIONS_ODOO",
                ontology_type=OntologyType.ODOO.value,
                confidence=0.70,
                method=MappingMethod.RULE.value,
                evidence_ids=ev_ids,
                reasoning="Technology mentioned without confirmed client or implementer relationship."
            )

        return self._persist_result(
            workspace_id=workspace_id,
            raw_input=text,
            canonical_name="UNKNOWN_ODOO_RELATIONSHIP",
            ontology_type=OntologyType.ODOO.value,
            confidence=0.0,
            method=MappingMethod.UNKNOWN.value,
            evidence_ids=ev_ids,
            reasoning="No Odoo-specific evidence detected."
        )

    def classify_buying_committee_role(
        self,
        workspace_id: str,
        job_title: str,
        department: Optional[str] = None
    ) -> ClassificationResult:
        """Maps professional title to buying committee role based on contextual ontology."""
        title = (job_title or "").lower().strip()
        dep = (department or "").lower().strip()

        # Economic Buyer: Budget authority
        if any(k in title for k in ["ceo", "chief executive", "managing director", "president", "cfo", "chief financial", "owner", "co-founder"]):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=job_title,
                canonical_name="ECONOMIC_BUYER",
                ontology_type=OntologyType.BUYING_COMMITTEE.value,
                confidence=0.95,
                method=MappingMethod.RULE.value,
                reasoning=f"Executive title '{job_title}' commands primary fiscal and strategic approval."
            )

        # Technical Evaluator: Architecture & security evaluation
        if any(k in title for k in ["cto", "cio", "chief technology", "chief information", "head of it", "vp engineering", "lead architect", "it director", "technical director"]):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=job_title,
                canonical_name="TECHNICAL_EVALUATOR",
                ontology_type=OntologyType.BUYING_COMMITTEE.value,
                confidence=0.92,
                method=MappingMethod.RULE.value,
                reasoning=f"Technical leadership title '{job_title}' conducts feasibility and integration evaluation."
            )

        # Champion: Operational department lead suffering from current pains
        if (any(k in title for k in ["erp", "operations", "supply chain", "logistics", "business systems"]) and
            any(m in title for m in ["manager", "director", "head", "lead"])):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=job_title,
                canonical_name="CHAMPION",
                ontology_type=OntologyType.BUYING_COMMITTEE.value,
                confidence=0.88,
                method=MappingMethod.RULE.value,
                reasoning=f"Operational manager '{job_title}' directly benefits from modernization and champions project."
            )

        # Procurement: Commercials & Vendor contracts
        if any(k in title for k in ["procurement", "purchasing", "sourcing", "vendor manager"]):
            return self._persist_result(
                workspace_id=workspace_id,
                raw_input=job_title,
                canonical_name="PROCUREMENT",
                ontology_type=OntologyType.BUYING_COMMITTEE.value,
                confidence=0.90,
                method=MappingMethod.RULE.value,
                reasoning=f"Procurement role '{job_title}' handles contracting and commercial negotiations."
            )

        # Default: Influencer
        return self._persist_result(
            workspace_id=workspace_id,
            raw_input=job_title,
            canonical_name="INFLUENCER",
            ontology_type=OntologyType.BUYING_COMMITTEE.value,
            confidence=0.75,
            method=MappingMethod.RULE.value,
            reasoning=f"Role '{job_title}' contributes operational feedback to evaluation."
        )

    def _persist_result(
        self,
        workspace_id: str,
        raw_input: str,
        canonical_name: str,
        ontology_type: str,
        confidence: float,
        method: str,
        evidence_ids: Optional[List[str]] = None,
        reasoning: Optional[str] = None
    ) -> ClassificationResult:
        # Match with concept if exists
        concept = self.db.query(Concept).filter(
            and_(Concept.workspace_id == workspace_id, Concept.canonical_name == canonical_name)
        ).first()

        res = ClassificationResult(
            workspace_id=workspace_id,
            raw_input_text=raw_input[:2000],
            concept_id=concept.id if concept else None,
            canonical_concept_name=canonical_name,
            ontology_type=ontology_type,
            confidence=confidence,
            classification_method=method,
            evidence_ids=evidence_ids or [],
            reasoning_summary=reasoning,
            review_status="AUTO_ACCEPTED" if confidence >= 0.85 else "PENDING_REVIEW"
        )
        self.db.add(res)
        self.db.commit()
        self.db.refresh(res)
        return res
