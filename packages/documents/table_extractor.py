"""
LeadNexus AI X - Phase 42: Table Structure Extractor
Detects, extracts, normalizes, and validates tabular structures across unstructured text,
CSV, and markdown documents.
"""

import re
from typing import Any, Dict, List, Optional


class TableExtractor:
    """Specialized engine for table identification and structure normalization."""

    @classmethod
    def extract_from_markdown(cls, text: str) -> List[Dict[str, Any]]:
        """Extracts markdown-style tables: | Col1 | Col2 | ..."""
        lines = text.strip().split("\n")
        tables: List[Dict[str, Any]] = []
        current_table_lines: List[str] = []

        for line in lines:
            if "|" in line:
                current_table_lines.append(line)
            else:
                if len(current_table_lines) >= 3:
                    parsed = cls._parse_markdown_table_lines(current_table_lines)
                    if parsed:
                        tables.append(parsed)
                current_table_lines = []

        if len(current_table_lines) >= 3:
            parsed = cls._parse_markdown_table_lines(current_table_lines)
            if parsed:
                tables.append(parsed)

        return tables

    @classmethod
    def _parse_markdown_table_lines(cls, lines: List[str]) -> Optional[Dict[str, Any]]:
        cleaned = [l.strip().strip("|") for l in lines]
        if len(cleaned) < 3:
            return None

        # Line 0 is header
        headers = [c.strip() for c in cleaned[0].split("|")]
        # Line 1 should be delimiter (|---|---|)
        if not re.match(r"^[\s\-:|]+$", cleaned[1]):
            return None

        # Remaining lines are rows
        rows: List[List[str]] = []
        for l in cleaned[2:]:
            cells = [c.strip() for c in l.split("|")]
            # Pad or trim to match header count
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            rows.append(cells[: len(headers)])

        return {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "col_count": len(headers),
            "confidence": 0.95,
        }

    @classmethod
    def to_records(cls, table: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converts a table dict (headers, rows) into a list of row dicts."""
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        records = []
        for row in rows:
            record = {}
            for idx, h in enumerate(headers):
                val = row[idx] if idx < len(row) else ""
                record[h] = val
            records.append(record)
        return records
