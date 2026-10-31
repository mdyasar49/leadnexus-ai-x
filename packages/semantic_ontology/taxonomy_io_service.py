import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.semantic_ontology import (
    Concept,
    Taxonomy,
    TaxonomyNode,
    OntologyType,
    ConceptStatus,
    OntologyChangeEvent,
)


class TaxonomyIOService:
    """
    Taxonomy & Ontology Import/Export Service:
    - Secure export to JSON and CSV
    - Defense against CSV formula injection (OWASP sanitization)
    - Controlled multi-stage import: Validate -> Preview -> Detect Conflicts -> Human Approval -> Apply
    """

    FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def sanitize_for_csv(cls, value: Any) -> str:
        """Escapes potentially malicious spreadsheet formula triggers."""
        s_val = str(value) if value is not None else ""
        if s_val.startswith(cls.FORMULA_PREFIXES):
            # Prepend a single quote to neutralize spreadsheet execution
            return f"'{s_val}"
        return s_val

    def export_concepts_json(self, workspace_id: str, ontology_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Exports ontology concepts and aliases as structured JSON."""
        q = self.db.query(Concept).filter(Concept.workspace_id == workspace_id)
        if ontology_type:
            q = q.filter(Concept.ontology_type == ontology_type.upper())
        concepts = q.all()

        return [
            {
                "canonical_name": c.canonical_name,
                "display_name": c.display_name,
                "ontology_type": c.ontology_type,
                "description": c.description,
                "version": c.version,
                "status": c.status,
                "parent_canonical_name": c.parent.canonical_name if c.parent else None,
                "aliases": [a.alias for a in c.aliases],
                "properties": c.properties or {}
            }
            for c in concepts
        ]

    def export_concepts_csv(self, workspace_id: str, ontology_type: Optional[str] = None) -> str:
        """Exports ontology concepts to safe CSV format."""
        data = self.export_concepts_json(workspace_id, ontology_type)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "Canonical Name", "Display Name", "Ontology Type", "Description",
            "Parent Concept", "Version", "Status", "Aliases"
        ])

        for row in data:
            writer.writerow([
                self.sanitize_for_csv(row["canonical_name"]),
                self.sanitize_for_csv(row["display_name"]),
                self.sanitize_for_csv(row["ontology_type"]),
                self.sanitize_for_csv(row["description"]),
                self.sanitize_for_csv(row["parent_canonical_name"]),
                self.sanitize_for_csv(row["version"]),
                self.sanitize_for_csv(row["status"]),
                self.sanitize_for_csv("; ".join(row["aliases"]))
            ])

        return output.getvalue()

    def preview_json_import(
        self,
        workspace_id: str,
        import_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validates imported payload and flags conflicts against existing concepts without applying changes.
        """
        to_create = []
        conflicts = []
        for item in import_data:
            c_name = str(item.get("canonical_name", "")).strip().upper()
            o_type = str(item.get("ontology_type", "CORE_ENTITY")).strip().upper()
            if not c_name:
                continue

            existing = self.db.query(Concept).filter(
                and_(
                    Concept.workspace_id == workspace_id,
                    Concept.ontology_type == o_type,
                    Concept.canonical_name == c_name
                )
            ).first()

            if existing:
                conflicts.append({
                    "canonical_name": c_name,
                    "existing_id": existing.id,
                    "existing_display_name": existing.display_name,
                    "imported_display_name": item.get("display_name"),
                    "action_required": "MERGE_OR_SKIP"
                })
            else:
                to_create.append({
                    "canonical_name": c_name,
                    "display_name": item.get("display_name", c_name),
                    "ontology_type": o_type,
                    "description": item.get("description")
                })

        return {
            "total_items": len(import_data),
            "new_concepts_count": len(to_create),
            "conflict_count": len(conflicts),
            "new_concepts": to_create,
            "conflicts": conflicts
        }

