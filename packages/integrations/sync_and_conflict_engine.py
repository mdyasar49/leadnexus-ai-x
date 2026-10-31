import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.integration import ConflictResolution


class SyncAndConflictEngine:
    """
    Manages synchronization between external integration records and canonical LeadNexus data.
    Enforces the 'Database Wins' rule: external systems cannot silently overwrite canonical data.
    """

    @classmethod
    def reconcile_field(
        cls,
        field_name: str,
        canonical_value: Any,
        external_value: Any,
        policy_resolution: str = ConflictResolution.KEEP_CANONICAL.value,
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """
        Reconciles a field between canonical and external source.
        Returns (reconciled_value, conflict_record_or_None).
        """
        # If external value is None, preserve canonical
        if external_value is None or external_value == "":
            return canonical_value, None

        # If canonical value was empty/null, safely accept external value (enrichment fill)
        if canonical_value is None or canonical_value == "":
            return external_value, None

        # If values match, no conflict
        if str(canonical_value).strip().lower() == str(external_value).strip().lower():
            return canonical_value, None

        # Values conflict!
        conflict_record = {
            "id": f"cnf_{uuid.uuid4().hex[:12]}",
            "field_name": field_name,
            "canonical_value": canonical_value,
            "external_value": external_value,
            "resolution": policy_resolution,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

        if policy_resolution == ConflictResolution.ACCEPT_EXTERNAL.value:
            return external_value, conflict_record
        elif policy_resolution == ConflictResolution.MERGE.value:
            # Merge if string or list
            if isinstance(canonical_value, list) and isinstance(external_value, list):
                merged = list(set(canonical_value + external_value))
                return merged, conflict_record
            return canonical_value, conflict_record
        else:
            # Default: KEEP_CANONICAL
            return canonical_value, conflict_record

    @classmethod
    def evaluate_sync_batch(
        cls,
        canonical_records_by_key: Dict[str, Dict[str, Any]],
        external_records_by_key: Dict[str, Dict[str, Any]],
        match_key: str = "domain",
        default_policy: str = ConflictResolution.KEEP_CANONICAL.value,
    ) -> Dict[str, Any]:
        """
        Evaluates a batch of external records against existing canonical records.
        Produces sync preview counts, changes, and detected conflicts.
        """
        new_records = []
        updated_records = []
        unchanged_records = []
        all_conflicts = []

        for ext_key, ext_rec in external_records_by_key.items():
            if ext_key not in canonical_records_by_key:
                # Brand new record
                new_records.append(ext_rec)
                continue

            canon_rec = canonical_records_by_key[ext_key]
            record_has_changes = False
            reconciled_rec = dict(canon_rec)

            for field, ext_val in ext_rec.items():
                canon_val = canon_rec.get(field)
                final_val, conflict = cls.reconcile_field(
                    field_name=field,
                    canonical_value=canon_val,
                    external_value=ext_val,
                    policy_resolution=default_policy,
                )
                if conflict:
                    all_conflicts.append(conflict)
                if final_val != canon_val:
                    reconciled_rec[field] = final_val
                    record_has_changes = True

            if record_has_changes:
                updated_records.append(reconciled_rec)
            else:
                unchanged_records.append(canon_rec)

        return {
            "records_found": len(external_records_by_key),
            "new_records_count": len(new_records),
            "updated_records_count": len(updated_records),
            "unchanged_records_count": len(unchanged_records),
            "conflicts_count": len(all_conflicts),
            "new_records": new_records,
            "updated_records": updated_records,
            "conflicts": all_conflicts,
        }
