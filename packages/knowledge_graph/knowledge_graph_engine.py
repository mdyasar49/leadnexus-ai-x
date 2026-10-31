import math
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeEntityVersion,
    KnowledgeRelationship,
    KnowledgeRelationshipVersion,
    RelationshipEvidence,
    RelationshipConflict,
    GraphSnapshot,
    GraphSnapshotEntity,
    GraphSnapshotRelationship,
    GraphChangeEvent,
    InferenceStatus,
    RelationshipStatus,
    ConflictStatus,
    KnowledgeEntityType
)
from app.models.lead import Company, Contact, IntentSignal
from app.models.technology import TechnologyObservation, OdooSignalObservation


class KnowledgeGraphEngine:
    """
    Enterprise Knowledge Graph Engine:
    - Canonical entity and relationship registry backed by PostgreSQL
    - Controlled taxonomy enforcement (Company, Tech, People, Odoo, Evidence)
    - Multi-source corroboration with source-independence validation (no duplicate/syndicated counting)
    - Non-destructive relationship conflict tracking
    - Temporal validity and 'As-Of' time-travel query support
    - Snapshot and change event recording
    """

    CONTRADICTORY_PAIRS = {
        ("USES_ODOO", "DOES_NOT_USE_ODOO"),
        ("IMPLEMENTS_ODOO", "DOES_NOT_USE_ODOO"),
        ("IMPLEMENTS_ODOO", "DOES_NOT_IMPLEMENT_ODOO"),
        ("USES_TECHNOLOGY", "DOES_NOT_USE_TECHNOLOGY"),
        ("WORKS_AT", "RESIGNED_FROM"),
        ("PARTNER_OF", "TERMINATED_PARTNER_OF")
    }

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def extract_source_independence_key(url: str) -> str:
        """Extracts apex domain/hostname as source independence key to prevent syndicated counting."""
        if not url:
            return "unknown_source"
        try:
            parsed = urlparse(url.strip())
            netloc = parsed.netloc or parsed.path
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc.lower() if netloc else "unknown_source"
        except Exception:
            return "unknown_source"

    # --- 1. Entity Management ---

    def upsert_entity(
        self,
        workspace_id: str,
        entity_type: str,
        canonical_name: str,
        normalized_identifier: str,
        properties: Optional[Dict[str, Any]] = None,
        changed_by: str = "system"
    ) -> KnowledgeEntity:
        """Finds or creates a knowledge entity with version snapshotting."""
        norm_id = normalized_identifier.strip().lower()
        entity = self.db.query(KnowledgeEntity).filter(
            and_(
                KnowledgeEntity.workspace_id == workspace_id,
                KnowledgeEntity.entity_type == entity_type.upper(),
                KnowledgeEntity.normalized_identifier == norm_id
            )
        ).first()

        props = properties or {}
        if entity:
            # Update properties if changed
            if entity.properties != props:
                entity.properties = {**entity.properties, **props}
                entity.canonical_name = canonical_name
                self.db.commit()
                self.db.refresh(entity)

                # Store version
                current_ver_count = self.db.query(KnowledgeEntityVersion).filter(
                    KnowledgeEntityVersion.entity_id == entity.id
                ).count()
                v = KnowledgeEntityVersion(
                    entity_id=entity.id,
                    version=current_ver_count + 1,
                    properties_snapshot=entity.properties,
                    changed_by=changed_by,
                    change_reason="Properties update"
                )
                self.db.add(v)
                self.db.commit()
        else:
            entity = KnowledgeEntity(
                workspace_id=workspace_id,
                entity_type=entity_type.upper(),
                canonical_name=canonical_name,
                normalized_identifier=norm_id,
                properties=props,
                is_canonical=True
            )
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)

            v = KnowledgeEntityVersion(
                entity_id=entity.id,
                version=1,
                properties_snapshot=props,
                changed_by=changed_by,
                change_reason="Initial creation"
            )
            self.db.add(v)
            self.db.commit()

        return entity

    def get_entity_by_identifier(
        self,
        workspace_id: str,
        entity_type: str,
        normalized_identifier: str
    ) -> Optional[KnowledgeEntity]:
        norm_id = normalized_identifier.strip().lower()
        return self.db.query(KnowledgeEntity).filter(
            and_(
                KnowledgeEntity.workspace_id == workspace_id,
                KnowledgeEntity.entity_type == entity_type.upper(),
                KnowledgeEntity.normalized_identifier == norm_id
            )
        ).first()

    # --- 2. Relationship Management & Corroboration ---

    def create_or_update_relationship(
        self,
        workspace_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: str,
        inference_status: str = InferenceStatus.OBSERVED.value,
        base_confidence: float = 80.0,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
        confidence_reason: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None
    ) -> Tuple[KnowledgeRelationship, Optional[RelationshipConflict]]:
        """
        Creates or updates a knowledge relationship.
        - Applies multi-source corroboration rule across independent sources.
        - Checks for conflicting relationships and logs RelationshipConflict if detected.
        """
        rel_type = relationship_type.upper()
        now = datetime.now(timezone.utc)
        v_from = valid_from or now

        # Conflict check: Check if an opposing relationship already exists
        conflict_detected: Optional[RelationshipConflict] = None
        for r_pos, r_neg in self.CONTRADICTORY_PAIRS:
            opposing_type = None
            if rel_type == r_pos:
                opposing_type = r_neg
            elif rel_type == r_neg:
                opposing_type = r_pos

            if opposing_type:
                opposing_rel = self.db.query(KnowledgeRelationship).filter(
                    and_(
                        KnowledgeRelationship.workspace_id == workspace_id,
                        KnowledgeRelationship.source_entity_id == source_entity_id,
                        KnowledgeRelationship.target_entity_id == target_entity_id,
                        KnowledgeRelationship.relationship_type == opposing_type,
                        KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
                    )
                ).first()
                if opposing_rel:
                    # Found a contradiction!
                    conflict = RelationshipConflict(
                        workspace_id=workspace_id,
                        relationship_id_a=opposing_rel.id,
                        relationship_id_b=opposing_rel.id,  # Will update once new rel created
                        source_entity_id=source_entity_id,
                        target_entity_id=target_entity_id,
                        conflict_type=f"CONTRADICTION: {opposing_type} vs {rel_type}",
                        status=ConflictStatus.UNRESOLVED.value,
                        resolution_notes="Opposing evidence observed from multiple sources."
                    )
                    conflict_detected = conflict

        # Look for existing active edge of this type
        rel = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.source_entity_id == source_entity_id,
                KnowledgeRelationship.target_entity_id == target_entity_id,
                KnowledgeRelationship.relationship_type == rel_type
            )
        ).first()

        items = evidence_items or []
        is_new = False
        if not rel:
            is_new = True
            rel = KnowledgeRelationship(
                workspace_id=workspace_id,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                relationship_type=rel_type,
                inference_status=inference_status.upper(),
                status=RelationshipStatus.ACTIVE.value,
                confidence=base_confidence,
                confidence_reason=confidence_reason or f"Evidence observed for {rel_type}",
                confidence_version="v1.0",
                observed_at=now,
                valid_from=v_from,
                valid_to=valid_to,
                corroboration_count=max(1, len(items))
            )
            self.db.add(rel)
            self.db.commit()
            self.db.refresh(rel)

            # Record change event
            ce = GraphChangeEvent(
                workspace_id=workspace_id,
                event_type="RELATIONSHIP_CREATED",
                entity_id=source_entity_id,
                relationship_id=rel.id,
                significance_score=65.0,
                payload={"relationship_type": rel_type, "confidence": base_confidence}
            )
            self.db.add(ce)
            self.db.commit()

        # Add Evidence Links with source independence key
        existing_hashes = {e.evidence_hash for e in rel.evidence_links}
        new_evidence_added = False
        for item in items:
            snippet = item.get("evidence_snippet") or item.get("evidence_text", "")
            src_url = item.get("source_url", "https://leadnexus.internal/observation")
            src_type = item.get("source_type", "WEB")
            h_input = f"{src_url}:{rel_type}:{snippet}"
            e_hash = hashlib.sha256(h_input.encode("utf-8")).hexdigest()

            if e_hash not in existing_hashes:
                ind_key = self.extract_source_independence_key(src_url)
                re = RelationshipEvidence(
                    relationship_id=rel.id,
                    source_url=src_url,
                    source_type=src_type,
                    evidence_snippet=snippet,
                    evidence_hash=e_hash,
                    source_independence_key=ind_key,
                    weight=item.get("weight", 1.0)
                )
                self.db.add(re)
                existing_hashes.add(e_hash)
                new_evidence_added = True

        if new_evidence_added or is_new:
            self.db.commit()
            self.db.refresh(rel)

            # Recalculate corroboration and confidence:
            # Multi-source corroboration rule: Count distinct independent sources
            distinct_ind_keys = {e.source_independence_key for e in rel.evidence_links}
            ind_count = len(distinct_ind_keys)
            rel.corroboration_count = ind_count
            
            # Boost confidence logarithmically: +15 * log2(independent_count)
            boost = round(15.0 * math.log2(max(1, ind_count)), 1)
            rel.confidence = min(100.0, round(base_confidence + boost, 1))
            self.db.commit()

        if conflict_detected:
            conflict_detected.relationship_id_b = rel.id
            self.db.add(conflict_detected)
            # Mark both relationships as CONTESTED
            rel.status = RelationshipStatus.CONTESTED.value
            opposing = self.db.query(KnowledgeRelationship).filter(
                KnowledgeRelationship.id == conflict_detected.relationship_id_a
            ).first()
            if opposing:
                opposing.status = RelationshipStatus.CONTESTED.value
            self.db.commit()

        return rel, conflict_detected

    # --- 3. Conflict Resolution ---

    def resolve_conflict(
        self,
        workspace_id: str,
        conflict_id: str,
        winning_relationship_id: str,
        resolved_by: str = "operator",
        notes: Optional[str] = None
    ) -> RelationshipConflict:
        """Resolves an edge conflict, activating the winner and suppressing the loser."""
        conflict = self.db.query(RelationshipConflict).filter(
            and_(RelationshipConflict.workspace_id == workspace_id, RelationshipConflict.id == conflict_id)
        ).first()
        if not conflict:
            raise ValueError(f"Conflict '{conflict_id}' not found.")

        # Update relationships
        rel_a = self.db.query(KnowledgeRelationship).filter(KnowledgeRelationship.id == conflict.relationship_id_a).first()
        rel_b = self.db.query(KnowledgeRelationship).filter(KnowledgeRelationship.id == conflict.relationship_id_b).first()

        if winning_relationship_id == conflict.relationship_id_a:
            if rel_a: rel_a.status = RelationshipStatus.ACTIVE.value
            if rel_b: rel_b.status = RelationshipStatus.SUPPRESSED.value
        elif winning_relationship_id == conflict.relationship_id_b:
            if rel_b: rel_b.status = RelationshipStatus.ACTIVE.value
            if rel_a: rel_a.status = RelationshipStatus.SUPPRESSED.value

        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.now(timezone.utc)
        conflict.resolution_notes = notes or f"Resolved in favor of {winning_relationship_id}"

        self.db.commit()
        self.db.refresh(conflict)
        return conflict

    # --- 4. Temporal "As-Of" Time Travel ---

    def get_relationships_as_of(
        self,
        workspace_id: str,
        entity_id: str,
        as_of: datetime,
        include_inactive: bool = False
    ) -> List[KnowledgeRelationship]:
        """
        Retrieves point-in-time relationships active on a specific historical date:
        valid_from <= as_of AND (valid_to IS NULL OR valid_to >= as_of).
        """
        query = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                or_(
                    KnowledgeRelationship.source_entity_id == entity_id,
                    KnowledgeRelationship.target_entity_id == entity_id
                ),
                KnowledgeRelationship.valid_from <= as_of,
                or_(
                    KnowledgeRelationship.valid_to.is_(None),
                    KnowledgeRelationship.valid_to >= as_of
                )
            )
        )
        if not include_inactive:
            query = query.filter(KnowledgeRelationship.status.in_([RelationshipStatus.ACTIVE.value, RelationshipStatus.HISTORICAL.value]))

        return query.all()

    # --- 5. Graph Snapshotting ---

    def create_snapshot(
        self,
        workspace_id: str,
        snapshot_name: str,
        snapshot_type: str = "DAILY"
    ) -> GraphSnapshot:
        """Takes an immutable point-in-time snapshot of the graph."""
        now = datetime.now(timezone.utc)
        entities = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.workspace_id == workspace_id).all()
        relationships = self.db.query(KnowledgeRelationship).filter(
            and_(
                KnowledgeRelationship.workspace_id == workspace_id,
                KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
            )
        ).all()

        snapshot = GraphSnapshot(
            workspace_id=workspace_id,
            snapshot_name=snapshot_name,
            snapshot_type=snapshot_type.upper(),
            entity_count=len(entities),
            relationship_count=len(relationships),
            graph_version="v23.1",
            snapshot_date=now
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        # Snapshot entities
        for ent in entities:
            se = GraphSnapshotEntity(
                snapshot_id=snapshot.id,
                entity_id=ent.id,
                entity_type=ent.entity_type,
                canonical_name=ent.canonical_name,
                properties_snapshot=ent.properties or {}
            )
            self.db.add(se)

        # Snapshot relationships
        for rel in relationships:
            sr = GraphSnapshotRelationship(
                snapshot_id=snapshot.id,
                relationship_id=rel.id,
                source_entity_id=rel.source_entity_id,
                target_entity_id=rel.target_entity_id,
                relationship_type=rel.relationship_type,
                status=rel.status,
                confidence=rel.confidence
            )
            self.db.add(sr)

        self.db.commit()
        return snapshot

    # --- 6. Synchronization from Phase 1-22 Records ---

    def sync_company_node(self, company: Company) -> KnowledgeEntity:
        """Syncs or creates a KnowledgeEntity from a Company record."""
        return self.upsert_entity(
            workspace_id=company.workspace_id,
            entity_type=KnowledgeEntityType.COMPANY.value,
            canonical_name=company.name,
            normalized_identifier=f"domain:{company.domain}" if company.domain else f"company:{company.normalized_name}",
            properties={
                "company_id": company.id,
                "domain": company.domain,
                "country": company.country,
                "industry": company.industry,
                "lead_score": getattr(company, "lead_score", None),
                "status": company.status
            }
        )

    def sync_technology_node(self, workspace_id: str, tech_name: str, category: str = "ERP") -> KnowledgeEntity:
        """Syncs or creates a KnowledgeEntity for a Technology."""
        return self.upsert_entity(
            workspace_id=workspace_id,
            entity_type=KnowledgeEntityType.TECHNOLOGY.value,
            canonical_name=tech_name,
            normalized_identifier=f"tech:{tech_name.strip().lower()}",
            properties={"category": category}
        )

    def sync_person_node(self, contact: Contact) -> KnowledgeEntity:
        """Syncs or creates a KnowledgeEntity for a Person/Contact."""
        ident = f"email:{contact.email.lower()}" if contact.email else f"person:{contact.full_name.lower()}:{contact.company_id}"
        return self.upsert_entity(
            workspace_id=contact.workspace_id,
            entity_type=KnowledgeEntityType.PERSON.value,
            canonical_name=contact.full_name,
            normalized_identifier=ident,
            properties={
                "contact_id": contact.id,
                "job_title": contact.job_title,
                "email": contact.email,
                "is_decision_maker": contact.is_decision_maker,
                "confidence_score": contact.confidence_score
            }
        )
