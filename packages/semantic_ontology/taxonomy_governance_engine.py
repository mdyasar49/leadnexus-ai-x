import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.semantic_ontology import (
    OntologyProposal,
    OntologyProposalReview,
    ProposalStatus,
    ReviewDecision,
    Concept,
    ConceptStatus,
    ConceptVersion,
    ConceptAlias,
    Taxonomy,
    TaxonomyVersion,
    TaxonomyNode,
    OntologyChangeEvent,
)


class TaxonomyGovernanceEngine:
    """
    Taxonomy Governance & Review Engine:
    - Implements controlled proposal lifecycle (PROPOSED -> UNDER_REVIEW -> APPROVED -> PUBLISHED -> DEPRECATED)
    - Enforces human review requirement for major ontology modifications
    - Applies approved proposals to update the ontology and creates version snapshots
    - Provides version diff comparison and rollback tracking
    """

    def __init__(self, db: Session):
        self.db = db

    def submit_proposal(
        self,
        workspace_id: str,
        proposal_type: str,
        title: str,
        payload: Dict[str, Any],
        description: Optional[str] = None,
        target_ontology_id: Optional[str] = None,
        proposed_by: str = "operator"
    ) -> OntologyProposal:
        """Submits a new ontology change proposal for human review."""
        proposal = OntologyProposal(
            workspace_id=workspace_id,
            proposal_type=proposal_type.upper(),
            title=title,
            description=description,
            target_ontology_id=target_ontology_id,
            payload=payload,
            status=ProposalStatus.PROPOSED.value,
            proposed_by=proposed_by
        )
        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def review_proposal(
        self,
        workspace_id: str,
        proposal_id: str,
        reviewer: str,
        decision: str,
        notes: Optional[str] = None
    ) -> OntologyProposal:
        """
        Records an operator review decision on a proposal.
        If APPROVED, automatically applies the changes to the canonical ontology.
        """
        proposal = self.db.query(OntologyProposal).filter(
            and_(OntologyProposal.workspace_id == workspace_id, OntologyProposal.id == proposal_id)
        ).first()
        if not proposal:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        dec_upper = decision.upper()
        review = OntologyProposalReview(
            proposal_id=proposal.id,
            reviewer=reviewer,
            decision=dec_upper,
            notes=notes
        )
        self.db.add(review)

        if dec_upper == ReviewDecision.APPROVE.value:
            proposal.status = ProposalStatus.APPROVED.value
            self._apply_proposal(proposal, applied_by=reviewer)
            proposal.status = ProposalStatus.APPLIED.value
        elif dec_upper == ReviewDecision.REJECT.value:
            proposal.status = ProposalStatus.REJECTED.value
        else:
            proposal.status = ProposalStatus.UNDER_REVIEW.value

        proposal.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def _apply_proposal(self, proposal: OntologyProposal, applied_by: str) -> None:
        """Applies the changes in an approved proposal to the database."""
        p_type = proposal.proposal_type
        payload = proposal.payload or {}
        ws_id = proposal.workspace_id

        if p_type == "NEW_CONCEPT":
            # Create the approved concept
            from packages.semantic_ontology.ontology_service import OntologyService
            svc = OntologyService(self.db)
            svc.upsert_concept(
                workspace_id=ws_id,
                ontology_id=payload.get("ontology_id") or proposal.target_ontology_id,
                canonical_name=payload["canonical_name"],
                display_name=payload["display_name"],
                ontology_type=payload["ontology_type"],
                parent_concept_id=payload.get("parent_concept_id"),
                description=payload.get("description"),
                properties=payload.get("properties"),
                changed_by=applied_by
            )
        elif p_type == "ALIAS":
            concept_id = payload.get("concept_id")
            alias = payload.get("alias")
            if concept_id and alias:
                from packages.semantic_ontology.ontology_service import OntologyService
                svc = OntologyService(self.db)
                svc.add_alias(concept_id, alias, source="human_approved", confidence=1.0)
        elif p_type == "DEPRECATE":
            concept_id = payload.get("concept_id")
            if concept_id:
                concept = self.db.query(Concept).filter(Concept.id == concept_id).first()
                if concept:
                    concept.status = ConceptStatus.DEPRECATED.value
                    concept.updated_at = datetime.now(timezone.utc)
                    ce = OntologyChangeEvent(
                        workspace_id=ws_id,
                        event_type="CONCEPT_DEPRECATED",
                        target_type="CONCEPT",
                        target_id=concept.id,
                        change_summary=f"Deprecated concept '{concept.canonical_name}' via proposal {proposal.id}",
                        actor=applied_by
                    )
                    self.db.add(ce)
        self.db.commit()

    def publish_taxonomy_version(
        self,
        workspace_id: str,
        taxonomy_id: str,
        new_version: str,
        change_summary: str,
        created_by: str = "operator"
    ) -> TaxonomyVersion:
        """Publishes a new version snapshot of a taxonomy tree."""
        tax = self.db.query(Taxonomy).filter(
            and_(Taxonomy.workspace_id == workspace_id, Taxonomy.id == taxonomy_id)
        ).first()
        if not tax:
            raise ValueError(f"Taxonomy '{taxonomy_id}' not found.")

        node_count = self.db.query(TaxonomyNode).filter(TaxonomyNode.taxonomy_id == tax.id).count()

        tv = TaxonomyVersion(
            taxonomy_id=tax.id,
            version=new_version,
            change_summary=change_summary,
            node_count=node_count,
            created_by=created_by
        )
        tax.current_version = new_version
        tax.updated_at = datetime.now(timezone.utc)

        ce = OntologyChangeEvent(
            workspace_id=workspace_id,
            event_type="TAXONOMY_PUBLISHED",
            target_type="TAXONOMY",
            target_id=tax.id,
            change_summary=f"Published taxonomy '{tax.name}' {new_version}: {change_summary}",
            actor=created_by
        )

        self.db.add(tv)
        self.db.add(ce)
        self.db.commit()
        self.db.refresh(tv)
        return tv

    def get_taxonomy_diff(
        self,
        workspace_id: str,
        taxonomy_id: str,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """Compares two historical versions of a taxonomy."""
        v_a = self.db.query(TaxonomyVersion).filter(
            and_(TaxonomyVersion.taxonomy_id == taxonomy_id, TaxonomyVersion.version == version_a)
        ).first()
        v_b = self.db.query(TaxonomyVersion).filter(
            and_(TaxonomyVersion.taxonomy_id == taxonomy_id, TaxonomyVersion.version == version_b)
        ).first()

        return {
            "taxonomy_id": taxonomy_id,
            "version_a": version_a,
            "version_b": version_b,
            "node_count_a": v_a.node_count if v_a else 0,
            "node_count_b": v_b.node_count if v_b else 0,
            "node_delta": (v_b.node_count if v_b else 0) - (v_a.node_count if v_a else 0),
            "summary_a": v_a.change_summary if v_a else None,
            "summary_b": v_b.change_summary if v_b else None
        }

