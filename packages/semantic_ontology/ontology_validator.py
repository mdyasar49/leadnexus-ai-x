import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.semantic_ontology import (
    Concept,
    ConceptAlias,
    ConceptRelationship,
    OntologyValidationError,
    OntologyType,
)


class OntologyValidator:
    """
    Ontology Validation Engine:
    - Cycle / Loop Detection in parent-child hierarchy
    - Invalid parent relationships across mismatched ontology types
    - Semantic relationship domain/range validation (e.g. Rejecting 'TECHNOLOGY WORKS_AT COMPANY')
    - Duplicate & ambiguous concept detection
    """

    ALLOWED_PARENT_TYPES = {
        OntologyType.TECHNOLOGY.value: {OntologyType.TECHNOLOGY.value},
        OntologyType.INDUSTRY.value: {OntologyType.INDUSTRY.value},
        OntologyType.JOB_ROLE.value: {OntologyType.JOB_ROLE.value},
        OntologyType.BUYING_COMMITTEE.value: {OntologyType.BUYING_COMMITTEE.value},
        OntologyType.INTENT.value: {OntologyType.INTENT.value},
        OntologyType.SIGNAL.value: {OntologyType.SIGNAL.value},
        OntologyType.CORE_ENTITY.value: {OntologyType.CORE_ENTITY.value},
    }

    # Allowed relationship constraints: (source_type, rel_type) -> set of allowed target_types
    ALLOWED_RELATIONSHIPS = {
        ("COMPANY", "USES_TECHNOLOGY"): {"TECHNOLOGY"},
        ("COMPANY", "IMPLEMENTS_TECHNOLOGY"): {"TECHNOLOGY"},
        ("COMPANY", "INTEGRATES_WITH"): {"TECHNOLOGY", "COMPANY"},
        ("COMPANY", "PARTNER_OF"): {"COMPANY"},
        ("COMPANY", "CUSTOMER_OF"): {"COMPANY"},
        ("COMPANY", "VENDOR_OF"): {"COMPANY"},
        ("COMPANY", "OWNS"): {"COMPANY"},
        ("COMPANY", "PARENT_OF"): {"COMPANY"},
        ("COMPANY", "SUBSIDIARY_OF"): {"COMPANY"},
        ("COMPANY", "COMPETITOR_OF"): {"COMPANY"},
        ("COMPANY", "BELONGS_TO_INDUSTRY"): {"INDUSTRY"},
        ("COMPANY", "HAS_LOCATION"): {"LOCATION", "COUNTRY", "CITY"},
        ("PERSON", "WORKS_AT"): {"COMPANY"},
        ("PERSON", "FOUNDED"): {"COMPANY"},
        ("PERSON", "LEADS"): {"COMPANY"},
        ("PERSON", "MANAGES"): {"COMPANY"},
        ("PERSON", "HOLDS_ROLE"): {"JOB_ROLE"},
        ("PERSON", "BUYING_COMMITTEE_ROLE"): {"BUYING_COMMITTEE"},
        ("TECHNOLOGY", "HAS_VERSION"): {"TECHNOLOGY"},
        ("TECHNOLOGY", "INTEGRATES_WITH"): {"TECHNOLOGY"},
        ("TECHNOLOGY", "EXTENDS"): {"TECHNOLOGY"},
    }

    def __init__(self, db: Session):
        self.db = db

    def validate_workspace_ontology(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Runs full suite of validation checks and persists OntologyValidationError records."""
        errors: List[Dict[str, Any]] = []

        # 1. Circular Dependency Check
        cycle_errors = self.check_circular_dependencies(workspace_id)
        errors.extend(cycle_errors)

        # 2. Invalid Parent Type Check
        parent_errors = self.check_invalid_parent_types(workspace_id)
        errors.extend(parent_errors)

        # 3. Duplicate / Highly Ambiguous Concept Names
        dup_errors = self.check_duplicate_concepts(workspace_id)
        errors.extend(dup_errors)

        # Persist unrecorded errors
        for err in errors:
            existing = self.db.query(OntologyValidationError).filter(
                and_(
                    OntologyValidationError.workspace_id == workspace_id,
                    OntologyValidationError.error_code == err["error_code"],
                    OntologyValidationError.entity_id == err.get("entity_id"),
                    OntologyValidationError.is_resolved.is_(False)
                )
            ).first()
            if not existing:
                ove = OntologyValidationError(
                    workspace_id=workspace_id,
                    error_code=err["error_code"],
                    severity=err.get("severity", "ERROR"),
                    entity_id=err.get("entity_id"),
                    message=err["message"],
                    details=err.get("details", {})
                )
                self.db.add(ove)

        self.db.commit()
        return errors

    def check_circular_dependencies(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Detects circular parent loops (e.g. A -> parent B -> parent A)."""
        concepts = self.db.query(Concept).filter(Concept.workspace_id == workspace_id).all()
        parent_map: Dict[str, Optional[str]] = {c.id: c.parent_concept_id for c in concepts}
        name_map: Dict[str, str] = {c.id: c.canonical_name for c in concepts}

        errors = []
        for c_id in parent_map:
            visited = set()
            curr = c_id
            while curr:
                if curr in visited:
                    # Loop found!
                    loop_node_name = name_map.get(curr, curr)
                    errors.append({
                        "error_code": "CIRCULAR_DEPENDENCY",
                        "severity": "ERROR",
                        "entity_id": c_id,
                        "message": f"Circular taxonomy dependency detected involving concept '{name_map.get(c_id, c_id)}' and '{loop_node_name}'.",
                        "details": {"concept_id": c_id, "loop_start": curr}
                    })
                    break
                visited.add(curr)
                curr = parent_map.get(curr)

        return errors

    def check_invalid_parent_types(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Rejects mismatched parent types (e.g., Job Role parented by Database / Technology)."""
        concepts = self.db.query(Concept).filter(
            and_(Concept.workspace_id == workspace_id, Concept.parent_concept_id.isnot(None))
        ).all()

        errors = []
        for c in concepts:
            parent = self.db.query(Concept).filter(Concept.id == c.parent_concept_id).first()
            if not parent:
                errors.append({
                    "error_code": "MISSING_PARENT",
                    "severity": "ERROR",
                    "entity_id": c.id,
                    "message": f"Concept '{c.canonical_name}' references non-existent parent ID '{c.parent_concept_id}'.",
                    "details": {"concept_id": c.id, "parent_id": c.parent_concept_id}
                })
                continue

            allowed = self.ALLOWED_PARENT_TYPES.get(c.ontology_type, {c.ontology_type})
            if parent.ontology_type not in allowed:
                errors.append({
                    "error_code": "INVALID_PARENT_TYPE",
                    "severity": "ERROR",
                    "entity_id": c.id,
                    "message": f"Invalid parent hierarchy: '{c.canonical_name}' ({c.ontology_type}) cannot have parent '{parent.canonical_name}' of type '{parent.ontology_type}'.",
                    "details": {"concept_id": c.id, "child_type": c.ontology_type, "parent_type": parent.ontology_type}
                })

        return errors

    def check_duplicate_concepts(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Detects duplicates or collisions between canonical names and aliases across different concepts."""
        aliases = self.db.query(ConceptAlias).join(Concept).filter(Concept.workspace_id == workspace_id).all()
        alias_map: Dict[str, List[str]] = {}
        for a in aliases:
            norm = a.normalized_alias
            alias_map.setdefault(norm, []).append(a.concept_id)

        errors = []
        for norm_alias, concept_ids in alias_map.items():
            unique_ids = set(concept_ids)
            if len(unique_ids) > 1:
                errors.append({
                    "error_code": "AMBIGUOUS_ALIAS_COLLISION",
                    "severity": "WARNING",
                    "entity_id": list(unique_ids)[0],
                    "message": f"Ambiguous alias '{norm_alias}' maps to multiple distinct concepts: {list(unique_ids)}.",
                    "details": {"normalized_alias": norm_alias, "conflicting_concepts": list(unique_ids)}
                })

        return errors

    def validate_relationship_types(
        self,
        source_type: str,
        rel_type: str,
        target_type: str
    ) -> Tuple[bool, Optional[str]]:
        """Validates that a proposed relationship conforms to semantic domain/range constraints."""
        s_type = source_type.strip().upper()
        r_type = rel_type.strip().upper()
        t_type = target_type.strip().upper()

        allowed_targets = self.ALLOWED_RELATIONSHIPS.get((s_type, r_type))
        if allowed_targets is None:
            # If relationship not in strict constraint matrix, allow unless blatantly absurd
            if s_type == "TECHNOLOGY" and r_type in ("WORKS_AT", "FOUNDED", "LEADS"):
                return False, f"Semantic Error: Technology entity cannot '{r_type}' a Company."
            return True, None

        if t_type not in allowed_targets:
            return False, f"Invalid relationship: '{s_type} {r_type}' requires target type in {allowed_targets}, but got '{t_type}'."

        return True, None
