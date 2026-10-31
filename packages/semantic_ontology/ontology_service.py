import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.semantic_ontology import (
    Ontology,
    OntologyVersion,
    Concept,
    ConceptVersion,
    ConceptAlias,
    ConceptSynonym,
    ConceptRelationship,
    ConceptRelationshipVersion,
    Taxonomy,
    TaxonomyVersion,
    TaxonomyNode,
    OntologyType,
    ConceptStatus,
    OntologyChangeEvent,
)


class OntologyService:
    """
    Enterprise Ontology Service:
    - Central registry for canonical concepts across all ontology layers
    - Concept canonicalization, versioning, hierarchy, aliases, and synonyms
    - Seed standard LeadNexus taxonomies (Core Entity, Tech, Odoo, Industry, Job Roles, Buying Committee, Intent, Signal)
    - Version-aware queries and reproducible historical lookups
    """

    def __init__(self, db: Session):
        self.db = db

    # --- 1. Ontology Management ---

    def get_or_create_ontology(
        self,
        workspace_id: str,
        name: str,
        display_name: str,
        ontology_type: str = OntologyType.CORE_ENTITY.value,
        description: Optional[str] = None
    ) -> Ontology:
        ont = self.db.query(Ontology).filter(
            and_(Ontology.workspace_id == workspace_id, Ontology.name == name)
        ).first()
        if not ont:
            ont = Ontology(
                workspace_id=workspace_id,
                name=name,
                display_name=display_name,
                description=description or f"Ontology for {display_name}",
                ontology_type=ontology_type,
                current_version="v1.0"
            )
            self.db.add(ont)
            self.db.commit()
            self.db.refresh(ont)

            # Record initial version
            v = OntologyVersion(
                ontology_id=ont.id,
                version="v1.0",
                change_summary="Initial ontology creation",
                status=ConceptStatus.PUBLISHED.value
            )
            self.db.add(v)
            self.db.commit()

        return ont

    # --- 2. Concept Canonicalization & Upsert ---

    def upsert_concept(
        self,
        workspace_id: str,
        ontology_id: str,
        canonical_name: str,
        display_name: str,
        ontology_type: str,
        parent_concept_id: Optional[str] = None,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        changed_by: str = "system"
    ) -> Concept:
        """
        Creates or updates a canonical concept.
        Records an immutable ConceptVersion on significant modifications.
        """
        norm_name = canonical_name.strip().upper()
        concept = self.db.query(Concept).filter(
            and_(
                Concept.workspace_id == workspace_id,
                Concept.ontology_type == ontology_type,
                Concept.canonical_name == norm_name
            )
        ).first()

        now = datetime.now(timezone.utc)
        if not concept:
            concept = Concept(
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                canonical_name=norm_name,
                display_name=display_name,
                description=description,
                ontology_type=ontology_type,
                parent_concept_id=parent_concept_id,
                status=ConceptStatus.PUBLISHED.value,
                version="v1.0",
                confidence=confidence,
                properties=properties or {}
            )
            self.db.add(concept)
            self.db.commit()
            self.db.refresh(concept)

            # Log initial version
            cv = ConceptVersion(
                concept_id=concept.id,
                version="v1.0",
                canonical_name=norm_name,
                display_name=display_name,
                description=description,
                parent_concept_id=parent_concept_id,
                properties=properties or {},
                changed_by=changed_by,
                change_reason="Initial creation"
            )
            self.db.add(cv)

            ce = OntologyChangeEvent(
                workspace_id=workspace_id,
                event_type="CONCEPT_CREATED",
                target_type="CONCEPT",
                target_id=concept.id,
                change_summary=f"Created concept '{concept.canonical_name}'",
                actor=changed_by
            )
            self.db.add(ce)
            self.db.commit()
        else:
            # Check if updated
            updated = False
            diff: Dict[str, Any] = {}
            if concept.display_name != display_name:
                diff["display_name"] = {"old": concept.display_name, "new": display_name}
                concept.display_name = display_name
                updated = True
            if parent_concept_id and concept.parent_concept_id != parent_concept_id:
                diff["parent_concept_id"] = {"old": concept.parent_concept_id, "new": parent_concept_id}
                concept.parent_concept_id = parent_concept_id
                updated = True
            if properties:
                merged = dict(concept.properties or {})
                merged.update(properties)
                concept.properties = merged
                updated = True

            if updated:
                # Increment minor version
                parts = concept.version.lstrip("v").split(".")
                major = int(parts[0]) if len(parts) > 0 else 1
                minor = int(parts[1]) + 1 if len(parts) > 1 else 1
                concept.version = f"v{major}.{minor}"
                concept.updated_at = now

                cv = ConceptVersion(
                    concept_id=concept.id,
                    version=concept.version,
                    canonical_name=concept.canonical_name,
                    display_name=concept.display_name,
                    description=concept.description,
                    parent_concept_id=concept.parent_concept_id,
                    properties=concept.properties,
                    changed_by=changed_by,
                    change_reason="Updated properties"
                )
                self.db.add(cv)

                ce = OntologyChangeEvent(
                    workspace_id=workspace_id,
                    event_type="CONCEPT_UPDATED",
                    target_type="CONCEPT",
                    target_id=concept.id,
                    change_summary=f"Updated concept '{concept.canonical_name}' to {concept.version}",
                    diff=diff,
                    actor=changed_by
                )
                self.db.add(ce)
                self.db.commit()
                self.db.refresh(concept)

        return concept

    # --- 3. Aliases & Synonyms ---

    def add_alias(
        self,
        concept_id: str,
        alias: str,
        source: str = "curated",
        confidence: float = 1.0
    ) -> ConceptAlias:
        norm_alias = re.sub(r"\s+", " ", alias.strip().lower())
        existing = self.db.query(ConceptAlias).filter(
            and_(ConceptAlias.concept_id == concept_id, ConceptAlias.normalized_alias == norm_alias)
        ).first()
        if existing:
            return existing

        ca = ConceptAlias(
            concept_id=concept_id,
            alias=alias.strip(),
            normalized_alias=norm_alias,
            source=source,
            confidence=confidence
        )
        self.db.add(ca)
        self.db.commit()
        self.db.refresh(ca)
        return ca

    def add_synonym(
        self,
        concept_id: str,
        synonym: str,
        similarity_score: float = 0.95
    ) -> ConceptSynonym:
        norm_syn = re.sub(r"\s+", " ", synonym.strip().lower())
        existing = self.db.query(ConceptSynonym).filter(
            and_(ConceptSynonym.concept_id == concept_id, ConceptSynonym.normalized_synonym == norm_syn)
        ).first()
        if existing:
            return existing

        cs = ConceptSynonym(
            concept_id=concept_id,
            synonym=synonym.strip(),
            normalized_synonym=norm_syn,
            similarity_score=similarity_score
        )
        self.db.add(cs)
        self.db.commit()
        self.db.refresh(cs)
        return cs

    def resolve_concept_by_name_or_alias(
        self,
        workspace_id: str,
        term: str,
        ontology_type: Optional[str] = None
    ) -> Optional[Concept]:
        """Resolves raw term via canonical name, alias, or synonym lookup."""
        if not term:
            return None
        clean_term = term.strip()
        norm_term = re.sub(r"\s+", " ", clean_term.lower())
        norm_upper = clean_term.upper()

        # 1. Exact canonical name match
        q = self.db.query(Concept).filter(
            and_(
                Concept.workspace_id == workspace_id,
                Concept.canonical_name == norm_upper
            )
        )
        if ontology_type:
            q = q.filter(Concept.ontology_type == ontology_type)
        res = q.first()
        if res:
            return res

        # 2. Exact alias match
        alias_q = self.db.query(Concept).join(ConceptAlias).filter(
            and_(
                Concept.workspace_id == workspace_id,
                ConceptAlias.normalized_alias == norm_term
            )
        )
        if ontology_type:
            alias_q = alias_q.filter(Concept.ontology_type == ontology_type)
        res = alias_q.first()
        if res:
            return res

        # 3. Synonym match
        syn_q = self.db.query(Concept).join(ConceptSynonym).filter(
            and_(
                Concept.workspace_id == workspace_id,
                ConceptSynonym.normalized_synonym == norm_term
            )
        )
        if ontology_type:
            syn_q = syn_q.filter(Concept.ontology_type == ontology_type)
        return syn_q.first()

    # --- 4. Concept Relationships ---

    def add_relationship(
        self,
        workspace_id: str,
        source_concept_id: str,
        target_concept_id: str,
        relationship_type: str,
        confidence: float = 1.0,
        is_bidirectional: bool = False
    ) -> ConceptRelationship:
        rel_type = relationship_type.strip().upper()
        existing = self.db.query(ConceptRelationship).filter(
            and_(
                ConceptRelationship.workspace_id == workspace_id,
                ConceptRelationship.source_concept_id == source_concept_id,
                ConceptRelationship.target_concept_id == target_concept_id,
                ConceptRelationship.relationship_type == rel_type
            )
        ).first()
        if existing:
            return existing

        rel = ConceptRelationship(
            workspace_id=workspace_id,
            source_concept_id=source_concept_id,
            target_concept_id=target_concept_id,
            relationship_type=rel_type,
            confidence=confidence,
            is_bidirectional=is_bidirectional,
            status=ConceptStatus.PUBLISHED.value
        )
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    # --- 5. Built-in Core Taxonomies Seeder ---

    def seed_core_taxonomies(self, workspace_id: str) -> Dict[str, int]:
        """
        Seeds standard LeadNexus ontologies and taxonomies for:
        - Technologies (ERP -> Odoo, SAP, NetSuite, Dynamics, React, Python, AWS, Azure, etc.)
        - Odoo Specialized Ontology (Versions, Modules, OCA, Ecosystem classes)
        - Industries (Retail, Manufacturing, Professional Services, Healthcare, Tech)
        - Job Roles (Executive, Technology, Finance, Operations)
        - Buying Committee (Economic Buyer, Technical Evaluator, Champion, etc.)
        - Intent Hierarchy (High, Medium, Low, Negative/Service Provider)
        - Signal Hierarchy (Hiring, Tech, GitHub, Website, Change)
        """
        counts = {"ontologies": 0, "concepts": 0, "aliases": 0, "nodes": 0}

        # 1. Tech & ERP Ontology
        tech_ont = self.get_or_create_ontology(
            workspace_id, "technology_taxonomy", "Technology Taxonomy", OntologyType.TECHNOLOGY.value
        )
        counts["ontologies"] += 1

        erp_root = self.upsert_concept(
            workspace_id, tech_ont.id, "ERP", "Enterprise Resource Planning", OntologyType.TECHNOLOGY.value
        )
        counts["concepts"] += 1

        # Odoo and Versions
        odoo_concept = self.upsert_concept(
            workspace_id, tech_ont.id, "ODOO", "Odoo ERP", OntologyType.TECHNOLOGY.value, parent_concept_id=erp_root.id
        )
        self.add_alias(odoo_concept.id, "Odoo")
        self.add_alias(odoo_concept.id, "Odoo ERP")
        self.add_alias(odoo_concept.id, "OpenERP")
        self.add_alias(odoo_concept.id, "Odoo.sh")
        self.add_alias(odoo_concept.id, "Odoo Online")
        counts["concepts"] += 1
        counts["aliases"] += 5

        for v_num in ["14", "15", "16", "17", "18", "19", "COMMUNITY", "ENTERPRISE"]:
            c = self.upsert_concept(
                workspace_id, tech_ont.id, f"ODOO_{v_num}", f"Odoo {v_num.capitalize()}",
                OntologyType.TECHNOLOGY.value, parent_concept_id=odoo_concept.id
            )
            self.add_alias(c.id, f"Odoo {v_num}")
            self.add_alias(c.id, f"Odoo v{v_num}")
            self.add_alias(c.id, f"Odoo{v_num}")
            counts["concepts"] += 1
            counts["aliases"] += 3

        # Other ERPs
        for competitor in ["SAP", "NETSUITE", "MICROSOFT_DYNAMICS", "ORACLE_ERP"]:
            c = self.upsert_concept(
                workspace_id, tech_ont.id, competitor, competitor.replace("_", " ").title(),
                OntologyType.TECHNOLOGY.value, parent_concept_id=erp_root.id
            )
            counts["concepts"] += 1

        # Frameworks & Languages
        react_concept = self.upsert_concept(
            workspace_id, tech_ont.id, "REACT", "React", OntologyType.TECHNOLOGY.value
        )
        self.add_alias(react_concept.id, "ReactJS")
        self.add_alias(react_concept.id, "React.js")
        self.add_alias(react_concept.id, "React JS")
        counts["concepts"] += 1
        counts["aliases"] += 3

        python_concept = self.upsert_concept(
            workspace_id, tech_ont.id, "PYTHON", "Python", OntologyType.TECHNOLOGY.value
        )
        self.add_alias(python_concept.id, "Python 3")
        counts["concepts"] += 1
        counts["aliases"] += 1

        # 2. Industry Ontology
        ind_ont = self.get_or_create_ontology(
            workspace_id, "industry_taxonomy", "Industry Taxonomy", OntologyType.INDUSTRY.value
        )
        counts["ontologies"] += 1

        retail_root = self.upsert_concept(
            workspace_id, ind_ont.id, "RETAIL", "Retail & Commerce", OntologyType.INDUSTRY.value
        )
        counts["concepts"] += 1

        ecom = self.upsert_concept(
            workspace_id, ind_ont.id, "ECOMMERCE", "E-Commerce", OntologyType.INDUSTRY.value, parent_concept_id=retail_root.id
        )
        self.add_alias(ecom.id, "eCommerce")
        self.add_alias(ecom.id, "online retail")
        counts["concepts"] += 1
        counts["aliases"] += 2

        mfg_root = self.upsert_concept(
            workspace_id, ind_ont.id, "MANUFACTURING", "Manufacturing & Industrial", OntologyType.INDUSTRY.value
        )
        counts["concepts"] += 1

        prof_root = self.upsert_concept(
            workspace_id, ind_ont.id, "PROFESSIONAL_SERVICES", "Professional Services", OntologyType.INDUSTRY.value
        )
        it_serv = self.upsert_concept(
            workspace_id, ind_ont.id, "IT_SERVICES", "IT Services & Consulting", OntologyType.INDUSTRY.value, parent_concept_id=prof_root.id
        )
        self.add_alias(it_serv.id, "IT Consulting")
        self.add_alias(it_serv.id, "Software Services")
        counts["concepts"] += 2
        counts["aliases"] += 2

        # 3. Job Roles & Seniority
        role_ont = self.get_or_create_ontology(
            workspace_id, "job_role_taxonomy", "Job Role Taxonomy", OntologyType.JOB_ROLE.value
        )
        counts["ontologies"] += 1

        cto = self.upsert_concept(
            workspace_id, role_ont.id, "CHIEF_TECHNOLOGY_OFFICER", "Chief Technology Officer", OntologyType.JOB_ROLE.value,
            properties={"role_family": "TECHNOLOGY", "seniority": "C_LEVEL", "department": "Engineering"}
        )
        self.add_alias(cto.id, "CTO")
        self.add_alias(cto.id, "Chief Tech Officer")
        self.add_alias(cto.id, "Chief Technical Officer")
        counts["concepts"] += 1
        counts["aliases"] += 3

        ceo = self.upsert_concept(
            workspace_id, role_ont.id, "CHIEF_EXECUTIVE_OFFICER", "Chief Executive Officer", OntologyType.JOB_ROLE.value,
            properties={"role_family": "EXECUTIVE", "seniority": "C_LEVEL", "department": "Executive"}
        )
        self.add_alias(ceo.id, "CEO")
        self.add_alias(ceo.id, "Managing Director")
        self.add_alias(ceo.id, "MD")
        self.add_alias(ceo.id, "Founder & CEO")
        counts["concepts"] += 1
        counts["aliases"] += 4

        erp_mgr = self.upsert_concept(
            workspace_id, role_ont.id, "ERP_MANAGER", "ERP Manager", OntologyType.JOB_ROLE.value,
            properties={"role_family": "TECHNOLOGY", "seniority": "MANAGER", "department": "Business Systems"}
        )
        self.add_alias(erp_mgr.id, "Odoo Manager")
        self.add_alias(erp_mgr.id, "Odoo Specialist")
        self.add_alias(erp_mgr.id, "Business Systems Manager")
        counts["concepts"] += 1
        counts["aliases"] += 3

        # 4. Buying Committee Ontology
        bc_ont = self.get_or_create_ontology(
            workspace_id, "buying_committee_ontology", "Buying Committee Ontology", OntologyType.BUYING_COMMITTEE.value
        )
        counts["ontologies"] += 1

        for role_code, title in [
            ("ECONOMIC_BUYER", "Economic Buyer"),
            ("TECHNICAL_EVALUATOR", "Technical Evaluator"),
            ("CHAMPION", "Champion"),
            ("BUSINESS_OWNER", "Business Owner"),
            ("INFLUENCER", "Influencer"),
            ("PROCUREMENT", "Procurement"),
            ("IMPLEMENTER", "Implementer"),
            ("ADMINISTRATOR", "System Administrator"),
            ("END_USER", "End User"),
            ("EXECUTIVE_SPONSOR", "Executive Sponsor"),
        ]:
            self.upsert_concept(
                workspace_id, bc_ont.id, role_code, title, OntologyType.BUYING_COMMITTEE.value
            )
            counts["concepts"] += 1

        # 5. Intent Ontology (Distinguishing High Intent from Service Provider Negative Intent)
        intent_ont = self.get_or_create_ontology(
            workspace_id, "intent_hierarchy", "Intent Hierarchy", OntologyType.INTENT.value
        )
        counts["ontologies"] += 1

        # High Intent
        for intent_code, title in [
            ("PARTNER_SEARCH_INTENT", "Partner Search Intent"),
            ("IMPLEMENTATION_INTENT", "Implementation Intent"),
            ("MIGRATION_INTENT", "Migration Intent"),
            ("UPGRADE_INTENT", "Upgrade Intent"),
            ("INTEGRATION_INTENT", "Integration Intent"),
            ("CUSTOMIZATION_INTENT", "Customization Intent"),
            ("CONSULTING_INTENT", "Consulting Intent"),
            ("SUPPORT_INTENT", "Support Intent"),
        ]:
            self.upsert_concept(
                workspace_id, intent_ont.id, intent_code, title, OntologyType.INTENT.value,
                properties={"tier": "HIGH_INTENT", "buying_readiness": 90.0}
            )
            counts["concepts"] += 1

        # Medium Intent
        for intent_code, title in [
            ("HIRING_INTENT", "Hiring Intent"),
            ("TECHNOLOGY_EVALUATION", "Technology Evaluation"),
            ("PROBLEM_RESEARCH", "Problem Research")
        ]:
            self.upsert_concept(
                workspace_id, intent_ont.id, intent_code, title, OntologyType.INTENT.value,
                properties={"tier": "MEDIUM_INTENT", "buying_readiness": 60.0}
            )
            counts["concepts"] += 1

        # Negative Intent (Crucial: SERVICE_PROVIDER)
        service_prov = self.upsert_concept(
            workspace_id, intent_ont.id, "SERVICE_PROVIDER", "Service Provider (Non-Buyer)", OntologyType.INTENT.value,
            properties={"tier": "NEGATIVE_INTENT", "buying_readiness": 0.0, "is_seller": True}
        )
        self.add_alias(service_prov.id, "Implementation Partner")
        self.add_alias(service_prov.id, "Official Partner")
        self.add_alias(service_prov.id, "Odoo Agency")
        counts["concepts"] += 1
        counts["aliases"] += 3

        # 6. Build Standard Taxonomy Nodes for ERP/Odoo
        tax = self.db.query(Taxonomy).filter(
            and_(Taxonomy.workspace_id == workspace_id, Taxonomy.name == "enterprise_technologies")
        ).first()
        if not tax:
            tax = Taxonomy(
                workspace_id=workspace_id,
                name="enterprise_technologies",
                display_name="Enterprise Technologies & Systems",
                domain="TECHNOLOGY",
                current_version="v1.0"
            )
            self.db.add(tax)
            self.db.commit()
            self.db.refresh(tax)

            # Root Node: ERP
            erp_node = TaxonomyNode(
                taxonomy_id=tax.id,
                concept_id=erp_root.id,
                code="ERP",
                name="Enterprise Resource Planning",
                level=1,
                path="/ERP",
                sort_order=1
            )
            self.db.add(erp_node)
            self.db.commit()
            self.db.refresh(erp_node)

            # Node: Odoo
            odoo_node = TaxonomyNode(
                taxonomy_id=tax.id,
                parent_node_id=erp_node.id,
                concept_id=odoo_concept.id,
                code="ODOO",
                name="Odoo ERP",
                level=2,
                path="/ERP/ODOO",
                sort_order=1
            )
            self.db.add(odoo_node)
            self.db.commit()
            self.db.refresh(odoo_node)

            # Node: Odoo 17
            odoo17 = self.db.query(Concept).filter(
                and_(Concept.workspace_id == workspace_id, Concept.canonical_name == "ODOO_17")
            ).first()
            if odoo17:
                o17_node = TaxonomyNode(
                    taxonomy_id=tax.id,
                    parent_node_id=odoo_node.id,
                    concept_id=odoo17.id,
                    code="ODOO_17",
                    name="Odoo 17",
                    level=3,
                    path="/ERP/ODOO/ODOO_17",
                    sort_order=1
                )
                self.db.add(o17_node)
                self.db.commit()

            counts["nodes"] += 3

        return counts

