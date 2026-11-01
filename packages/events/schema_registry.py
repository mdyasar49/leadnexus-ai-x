"""
LeadNexus AI X — Phase 36: Event Schema Registry & Compatibility Engine
Maintains versioned schemas, generates cryptographic fingerprints, validates
payloads, and blocks breaking schema evolution without explicit version increments.
"""

import hashlib
import json
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.models.cqrs_event_sourcing import EventSchemaRecord, SchemaCompatibility


class BreakingSchemaEvolutionError(Exception):
    """Raised when an unregistered breaking schema change is submitted."""
    pass


class SchemaValidationError(Exception):
    """Raised when an event payload violates its registered schema definition."""
    pass


class EventSchemaRegistry:
    """Manages event contracts, SemVer versioning, and compatibility rules."""

    @staticmethod
    def compute_fingerprint(schema_definition: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 fingerprint for canonical JSON schema."""
        canonical_json = json.dumps(schema_definition, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    @classmethod
    def register_schema(
        cls,
        db: Session,
        event_type: str,
        version: str,
        schema_definition: Dict[str, Any],
        compatibility: SchemaCompatibility = SchemaCompatibility.BACKWARD_COMPATIBLE
    ) -> EventSchemaRecord:
        """
        Registers a new schema version. Validates that backwards-compatibility
        rules are respected relative to previous versions.
        """
        fingerprint = cls.compute_fingerprint(schema_definition)

        # Check existing version
        existing = db.query(EventSchemaRecord).filter(
            EventSchemaRecord.event_type == event_type,
            EventSchemaRecord.version == version
        ).first()

        if existing:
            if existing.fingerprint != fingerprint:
                raise BreakingSchemaEvolutionError(
                    f"Version {version} for event '{event_type}' already registered with different schema definition. "
                    "In-place breaking changes are prohibited. Bump SemVer version."
                )
            return existing

        # Check latest previous version for breaking field removals
        latest = (
            db.query(EventSchemaRecord)
            .filter(EventSchemaRecord.event_type == event_type)
            .order_by(EventSchemaRecord.created_at.desc())
            .first()
        )

        if latest:
            # If compatibility is backward compatible, required fields in previous must exist in new
            old_req = set(latest.schema_definition.get("required", []))
            new_props = set(schema_definition.get("properties", {}).keys())
            missing = old_req - new_props
            if missing and compatibility == SchemaCompatibility.BACKWARD_COMPATIBLE:
                raise BreakingSchemaEvolutionError(
                    f"Breaking change detected: Required fields {list(missing)} from version {latest.version} "
                    f"missing in new version {version}. Mark as BREAKING or maintain deprecated fields."
                )

        record = EventSchemaRecord(
            event_type=event_type,
            version=version,
            schema_definition=schema_definition,
            fingerprint=fingerprint,
            compatibility=compatibility,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def validate_payload(
        cls,
        db: Session,
        event_type: str,
        version: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Validates payload against registered schema properties and required fields."""
        schema_record = db.query(EventSchemaRecord).filter(
            EventSchemaRecord.event_type == event_type,
            EventSchemaRecord.version == version
        ).first()

        if not schema_record:
            # Fallback permissive if schema not explicitly enrolled yet
            return True

        definition = schema_record.schema_definition
        required = definition.get("required", [])
        for field in required:
            if field not in payload or payload[field] is None:
                raise SchemaValidationError(
                    f"Payload missing required field '{field}' for event '{event_type}' (v{version})"
                )

        # Basic type checking if specified
        properties = definition.get("properties", {})
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }

        for prop, prop_def in properties.items():
            if prop in payload and payload[prop] is not None:
                expected_type = prop_def.get("type")
                if expected_type in type_map:
                    if not isinstance(payload[prop], type_map[expected_type]):
                        raise SchemaValidationError(
                            f"Field '{prop}' has invalid type. Expected {expected_type}, got {type(payload[prop]).__name__}"
                        )

        return True
