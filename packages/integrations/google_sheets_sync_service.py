import uuid
from typing import Any, Dict, List, Optional, Tuple

from packages.integrations.export_safety_engine import ExportSafetyEngine
from packages.integrations.sync_and_conflict_engine import SyncAndConflictEngine


class GoogleSheetsSyncService:
    """
    Manages bidirectional synchronization between LeadNexus canonical database
    and authorized external Google Sheets workbooks.
    Maintains stable row identity via `leadnexus_id`.
    """

    DEFAULT_HEADERS = [
        "leadnexus_id",
        "company_name",
        "primary_domain",
        "industry",
        "odoo_version",
        "odoo_edition",
        "decision_maker_name",
        "decision_maker_title",
        "lead_score",
        "last_synced_at",
    ]

    @classmethod
    def detect_headers(cls, raw_sheet_rows: List[List[Any]]) -> List[str]:
        """Detects and extracts column headers from the first row of sheet data."""
        if not raw_sheet_rows or not raw_sheet_rows[0]:
            return []
        return [str(cell).strip() for cell in raw_sheet_rows[0] if str(cell).strip()]

    @classmethod
    def parse_sheet_rows(
        cls,
        raw_rows: List[List[Any]],
        headers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Parses sheet row 2D arrays into structured dictionaries keyed by header names."""
        if len(raw_rows) <= 1:
            return []

        col_headers = headers or cls.detect_headers(raw_rows)
        parsed_records = []

        for row_idx, row in enumerate(raw_rows[1:], start=2):
            rec: Dict[str, Any] = {"_sheet_row_num": row_idx}
            for col_idx, col_name in enumerate(col_headers):
                val = row[col_idx] if col_idx < len(row) else ""
                rec[col_name] = str(val).strip()
            parsed_records.append(rec)

        return parsed_records

    @classmethod
    def format_records_for_sheet(
        cls,
        records: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
    ) -> List[List[Any]]:
        """
        Formats canonical records into a sanitized 2D array suitable for Google Sheets API.
        Guarantees CSV/Formula injection safety and stable leadnexus_id.
        """
        cols = headers or cls.DEFAULT_HEADERS
        sheet_rows: List[List[Any]] = [cols]

        for rec in records:
            safe_rec = ExportSafetyEngine.sanitize_record_for_export(rec)
            row = []
            for col in cols:
                val = safe_rec.get(col, "")
                row.append(val)
            sheet_rows.append(row)

        return sheet_rows

    @classmethod
    def compute_sync_preview(
        cls,
        sheet_records: List[Dict[str, Any]],
        canonical_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates changes between Google Sheet and Canonical Database.
        Identifies new rows, modified rows, and conflicts.
        """
        canon_by_id = {str(r.get("id") or r.get("leadnexus_id")): r for r in canonical_records if r.get("id") or r.get("leadnexus_id")}
        sheet_by_id = {str(r.get("leadnexus_id")): r for r in sheet_records if r.get("leadnexus_id")}

        preview = SyncAndConflictEngine.evaluate_sync_batch(
            canonical_records_by_key=canon_by_id,
            external_records_by_key=sheet_by_id,
            match_key="leadnexus_id",
        )

        return {
            "sheet_total_rows": len(sheet_records),
            "canonical_total_records": len(canonical_records),
            "records_to_insert_into_db": preview["new_records_count"],
            "records_to_update_in_db": preview["updated_records_count"],
            "conflicts_count": preview["conflicts_count"],
            "conflicts": preview["conflicts"],
            "is_ready_to_sync": True,
        }
