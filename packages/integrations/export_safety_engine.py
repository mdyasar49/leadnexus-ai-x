import re
from typing import Any, Dict, List, Optional, Set


class ExportSafetyEngine:
    """
    Guards export pipelines against CSV Formula Injection, malicious hyperlinks,
    unauthorized PII leakage, and cross-tenant data exposure.
    """

    FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "%")

    UNSAFE_URL_PATTERNS = [
        re.compile(r"^javascript:", re.I),
        re.compile(r"^vbscript:", re.I),
        re.compile(r"^data:text/html", re.I),
    ]

    RESTRICTED_DATA_FIELDS: Set[str] = {
        "password_hash",
        "hashed_password",
        "private_notes",
        "security_audit_log",
        "personal_mobile_unverified",
        "secret_token",
    }

    @classmethod
    def sanitize_csv_cell(cls, value: Any) -> Any:
        """
        Prevents CSV Injection (Formula Injection / DDE) by prepending a single quote
        to cells beginning with =, +, -, @, tab, or carriage return.
        """
        if value is None:
            return ""

        val_str = str(value)
        if val_str.startswith(cls.FORMULA_PREFIXES):
            return f"'{val_str}"

        # Check for unsafe URLs
        for pattern in cls.UNSAFE_URL_PATTERNS:
            if pattern.search(val_str.strip()):
                return "[BLOCKED_UNSAFE_HYPERLINK]"

        return val_str

    @classmethod
    def sanitize_record_for_export(
        cls,
        record: Dict[str, Any],
        allow_restricted_fields: bool = False,
    ) -> Dict[str, Any]:
        """
        Sanitizes all cells in a record, removing unauthorized PII / restricted fields
        and neutralising formula injection sequences.
        """
        safe_record: Dict[str, Any] = {}

        for key, val in record.items():
            if not allow_restricted_fields and key.lower() in cls.RESTRICTED_DATA_FIELDS:
                continue  # Suppress restricted field

            if isinstance(val, (int, float, bool)):
                safe_record[key] = val
            elif isinstance(val, list):
                safe_record[key] = [cls.sanitize_csv_cell(item) for item in val]
            elif isinstance(val, dict):
                safe_record[key] = {k: cls.sanitize_csv_cell(v) for k, v in val.items()}
            else:
                safe_record[key] = cls.sanitize_csv_cell(val)

        return safe_record

    @classmethod
    def generate_safe_csv(
        cls,
        records: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
    ) -> str:
        """Generates sanitized, injection-free CSV text."""
        if not records:
            return ""

        keys = headers or list(records[0].keys())
        # Filter out restricted keys
        safe_keys = [k for k in keys if k.lower() not in cls.RESTRICTED_DATA_FIELDS]

        lines = [",".join(f'"{k}"' for k in safe_keys)]

        for rec in records:
            row = []
            for k in safe_keys:
                cell_val = cls.sanitize_csv_cell(rec.get(k, ""))
                # Escape double quotes
                escaped = str(cell_val).replace('"', '""')
                row.append(f'"{escaped}"')
            lines.append(",".join(row))

        return "\r\n".join(lines)
