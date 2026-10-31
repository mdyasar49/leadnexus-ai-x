import difflib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.semantic_ontology import (
    Concept,
    ConceptAlias,
    ConceptSynonym,
    SemanticMapping,
    SemanticMappingEvidence,
    MappingMethod,
)


class SemanticNormalizationEngine:
    """
    Cross-Source Semantic Normalization & Mapping Engine:
    - Normalizes noisy, heterogeneous terms from GitHub, job boards, websites, and forums
    - Enforces mapping priority:
        1. Human-approved mapping (Never overwritten)
        2. Exact alias / canonical concept match
        3. Dictionary / regex normalization rule
        4. High-confidence fuzzy string similarity
        5. Fallback to 'NEEDS_REVIEW' (No arbitrary guessing)
    - Links supporting evidence snippets to every semantic mapping
    """

    # Static normalization dictionaries for fast pre-filtering
    PRE_NORMALIZATIONS = {
        # Tech variants
        "reactjs": "REACT",
        "react.js": "REACT",
        "react js": "REACT",
        "nodejs": "NODEJS",
        "node.js": "NODEJS",
        "python3": "PYTHON",
        "py3": "PYTHON",
        "k8s": "KUBERNETES",
        # Odoo variants
        "openerp": "ODOO",
        "open erp": "ODOO",
        "odoo erp": "ODOO",
        "odoo.sh": "ODOO",
        "odoo-sh": "ODOO",
        # Job roles
        "cto": "CHIEF_TECHNOLOGY_OFFICER",
        "chief tech officer": "CHIEF_TECHNOLOGY_OFFICER",
        "chief technology officer": "CHIEF_TECHNOLOGY_OFFICER",
        "chief technical officer": "CHIEF_TECHNOLOGY_OFFICER",
        "ceo": "CHIEF_EXECUTIVE_OFFICER",
        "chief executive officer": "CHIEF_EXECUTIVE_OFFICER",
        "managing director": "CHIEF_EXECUTIVE_OFFICER",
        "md": "CHIEF_EXECUTIVE_OFFICER",
        "cfo": "CHIEF_FINANCIAL_OFFICER",
        "chief financial officer": "CHIEF_FINANCIAL_OFFICER",
        "erp manager": "ERP_MANAGER",
        "odoo specialist": "ERP_MANAGER",
        # Industries
        "ecommerce": "ECOMMERCE",
        "e-commerce": "ECOMMERCE",
        "online retail": "ECOMMERCE",
        "it services": "IT_SERVICES",
        "it consulting": "IT_SERVICES",
    }

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def clean_term(raw_term: str) -> str:
        """Cleans whitespace, lowercase, and basic noise from raw string."""
        if not raw_term:
            return ""
        # Remove markdown/punctuation artifacts, condense whitespaces
        cleaned = re.sub(r"[^\w\s\.\-\+]", " ", raw_term)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    def normalize_term(
        self,
        workspace_id: str,
        raw_term: str,
        source_context: str = "GENERAL",
        ontology_type: Optional[str] = None,
        source_url: Optional[str] = None,
        evidence_snippet: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Normalizes a raw term to a canonical concept.
        Returns the resolved concept, mapping method, confidence, and review status.
        """
        cleaned = self.clean_term(raw_term)
        if not cleaned:
            return {
                "raw_term": raw_term,
                "canonical_name": "UNKNOWN",
                "concept_id": None,
                "mapping_method": MappingMethod.UNKNOWN.value,
                "confidence": 0.0,
                "status": "UNRESOLVED"
            }

        # Step 1: Check existing stored SemanticMapping
        existing_map = self.db.query(SemanticMapping).filter(
            and_(
                SemanticMapping.workspace_id == workspace_id,
                SemanticMapping.normalized_source_term == cleaned
            )
        ).first()

        if existing_map:
            # If human-approved, this is immutable law for this term
            if existing_map.is_human_approved:
                concept = existing_map.concept
                return {
                    "raw_term": raw_term,
                    "canonical_name": concept.canonical_name if concept else "UNKNOWN",
                    "concept_id": existing_map.concept_id,
                    "mapping_method": MappingMethod.HUMAN_APPROVED.value,
                    "confidence": existing_map.confidence,
                    "status": "APPROVED",
                    "is_human_approved": True
                }

        # Step 2: Check Pre-Normalization Dictionary Rule
        if cleaned in self.PRE_NORMALIZATIONS:
            target_canonical = self.PRE_NORMALIZATIONS[cleaned]
            concept = self.db.query(Concept).filter(
                and_(Concept.workspace_id == workspace_id, Concept.canonical_name == target_canonical)
            ).first()
            if concept:
                mapping = self._record_mapping(
                    workspace_id=workspace_id,
                    raw_term=raw_term,
                    normalized_term=cleaned,
                    concept_id=concept.id,
                    source_context=source_context,
                    method=MappingMethod.DICTIONARY.value,
                    confidence=0.98,
                    source_url=source_url,
                    snippet=evidence_snippet
                )
                return {
                    "raw_term": raw_term,
                    "canonical_name": concept.canonical_name,
                    "concept_id": concept.id,
                    "mapping_method": MappingMethod.DICTIONARY.value,
                    "confidence": 0.98,
                    "status": "RESOLVED"
                }

        # Step 3: Exact match against Canonical Concept Name
        exact_concept = self.db.query(Concept).filter(
            and_(
                Concept.workspace_id == workspace_id,
                Concept.canonical_name == raw_term.strip().upper()
            )
        )
        if ontology_type:
            exact_concept = exact_concept.filter(Concept.ontology_type == ontology_type)
        c_res = exact_concept.first()
        if c_res:
            self._record_mapping(
                workspace_id, raw_term, cleaned, c_res.id, source_context,
                MappingMethod.EXACT_MATCH.value, 1.0, source_url, evidence_snippet
            )
            return {
                "raw_term": raw_term,
                "canonical_name": c_res.canonical_name,
                "concept_id": c_res.id,
                "mapping_method": MappingMethod.EXACT_MATCH.value,
                "confidence": 1.0,
                "status": "RESOLVED"
            }

        # Step 4: Exact match against ConceptAlias
        alias_res = self.db.query(ConceptAlias).join(Concept).filter(
            and_(
                Concept.workspace_id == workspace_id,
                ConceptAlias.normalized_alias == cleaned
            )
        )
        if ontology_type:
            alias_res = alias_res.filter(Concept.ontology_type == ontology_type)
        a_row = alias_res.first()
        if a_row:
            concept = a_row.concept
            self._record_mapping(
                workspace_id, raw_term, cleaned, concept.id, source_context,
                MappingMethod.RULE.value, a_row.confidence, source_url, evidence_snippet
            )
            return {
                "raw_term": raw_term,
                "canonical_name": concept.canonical_name,
                "concept_id": concept.id,
                "mapping_method": MappingMethod.RULE.value,
                "confidence": a_row.confidence,
                "status": "RESOLVED"
            }

        # Step 5: High-Confidence Fuzzy String Similarity
        # Query candidate concepts of matching ontology_type
        c_q = self.db.query(Concept).filter(Concept.workspace_id == workspace_id)
        if ontology_type:
            c_q = c_q.filter(Concept.ontology_type == ontology_type)
        candidates = c_q.all()

        best_concept = None
        best_ratio = 0.0
        for c in candidates:
            # Check canonical name
            ratio = difflib.SequenceMatcher(None, cleaned, c.canonical_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_concept = c
            # Check display name
            d_ratio = difflib.SequenceMatcher(None, cleaned, c.display_name.lower()).ratio()
            if d_ratio > best_ratio:
                best_ratio = d_ratio
                best_concept = c

        if best_concept and best_ratio >= 0.88:
            self._record_mapping(
                workspace_id, raw_term, cleaned, best_concept.id, source_context,
                MappingMethod.FUZZY_MATCH.value, round(best_ratio, 2), source_url, evidence_snippet
            )
            return {
                "raw_term": raw_term,
                "canonical_name": best_concept.canonical_name,
                "concept_id": best_concept.id,
                "mapping_method": MappingMethod.FUZZY_MATCH.value,
                "confidence": round(best_ratio, 2),
                "status": "RESOLVED"
            }

        # Step 6: Ambiguous / Unknown -> NEEDS_REVIEW
        return {
            "raw_term": raw_term,
            "canonical_name": "UNKNOWN",
            "concept_id": None,
            "mapping_method": MappingMethod.UNKNOWN.value,
            "confidence": round(best_ratio, 2) if best_concept else 0.0,
            "status": "NEEDS_REVIEW",
            "suggested_concept": best_concept.canonical_name if (best_concept and best_ratio > 0.6) else None
        }

    def _record_mapping(
        self,
        workspace_id: str,
        raw_term: str,
        normalized_term: str,
        concept_id: str,
        source_context: str,
        method: str,
        confidence: float,
        source_url: Optional[str] = None,
        snippet: Optional[str] = None
    ) -> SemanticMapping:
        """Helper to record or update semantic mapping record and evidence link."""
        mapping = self.db.query(SemanticMapping).filter(
            and_(
                SemanticMapping.workspace_id == workspace_id,
                SemanticMapping.normalized_source_term == normalized_term
            )
        ).first()

        if not mapping:
            mapping = SemanticMapping(
                workspace_id=workspace_id,
                source_term=raw_term,
                normalized_source_term=normalized_term,
                concept_id=concept_id,
                source_context=source_context,
                mapping_method=method,
                confidence=confidence,
                is_human_approved=False
            )
            self.db.add(mapping)
            self.db.commit()
            self.db.refresh(mapping)
        elif not mapping.is_human_approved and mapping.confidence < confidence:
            mapping.concept_id = concept_id
            mapping.mapping_method = method
            mapping.confidence = confidence
            self.db.commit()

        if source_url or snippet:
            ev = SemanticMappingEvidence(
                mapping_id=mapping.id,
                source_url=source_url,
                evidence_snippet=snippet,
                source_type=source_context
            )
            self.db.add(ev)
            self.db.commit()

        return mapping

    def approve_human_mapping(
        self,
        workspace_id: str,
        mapping_id: str,
        concept_id: str,
        approved_by: str = "operator"
    ) -> SemanticMapping:
        """Explicitly approves a semantic mapping, locking it against automated overwrite."""
        mapping = self.db.query(SemanticMapping).filter(
            and_(SemanticMapping.workspace_id == workspace_id, SemanticMapping.id == mapping_id)
        ).first()
        if not mapping:
            raise ValueError(f"Mapping '{mapping_id}' not found.")

        mapping.concept_id = concept_id
        mapping.is_human_approved = True
        mapping.mapping_method = MappingMethod.HUMAN_APPROVED.value
        mapping.confidence = 1.0
        mapping.approved_by = approved_by
        mapping.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

