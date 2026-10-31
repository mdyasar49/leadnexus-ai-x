import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class DataMappingEngine:
    """
    Transforms external payloads into canonical LeadNexus entity schemas
    using deterministic, safe field-level transformations.
    Strictly prohibits arbitrary code execution.
    """

    COUNTRY_CODE_MAP = {
        "AU": "Australia",
        "AUS": "Australia",
        "US": "United States",
        "USA": "United States",
        "GB": "United Kingdom",
        "UK": "United Kingdom",
        "NZ": "New Zealand",
        "CA": "Canada",
        "DE": "Germany",
        "FR": "France",
        "SG": "Singapore",
    }

    @classmethod
    def apply_transformation(
        cls,
        value: Any,
        rule: str,
        enum_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Applies a safe field transformation rule."""
        if value is None:
            return None

        val_str = str(value).strip()

        if rule == "TRIM":
            return val_str

        elif rule == "LOWERCASE":
            return val_str.lower()

        elif rule == "UPPERCASE":
            return val_str.upper()

        elif rule == "NORMALIZE_EMAIL":
            clean = val_str.lower()
            return clean if "@" in clean and "." in clean.split("@")[1] else clean

        elif rule == "NORMALIZE_PHONE":
            # Remove parentheses, spaces, hyphens
            digits = re.sub(r"[^\d+]", "", val_str)
            return digits

        elif rule == "NORMALIZE_DOMAIN":
            clean = val_str.lower()
            if "://" in clean:
                parsed = urlparse(clean)
                host = parsed.hostname or clean
            else:
                host = clean.split("/")[0]
            if host.startswith("www."):
                host = host[4:]
            return host

        elif rule == "NORMALIZE_COUNTRY":
            return cls.COUNTRY_CODE_MAP.get(val_str.upper(), val_str)

        elif rule == "DATE_CONVERSION":
            try:
                if val_str.isdigit():
                    dt = datetime.fromtimestamp(float(val_str), tz=timezone.utc)
                    return dt.isoformat()
                return val_str
            except Exception:
                return val_str

        elif rule == "ENUM_MAPPING":
            if enum_map:
                return enum_map.get(val_str, val_str)
            return val_str

        elif rule == "DIRECT":
            return value

        return val_str

    @classmethod
    def map_record(
        cls,
        raw_record: Dict[str, Any],
        field_mappings: List[Dict[str, Any]],
        target_entity: str = "COMPANY",
    ) -> Dict[str, Any]:
        """
        Maps an incoming raw record into a standardized canonical payload
        according to the provided field mapping specifications.
        """
        canonical_record: Dict[str, Any] = {}

        for mapping in field_mappings:
            src_key = mapping.get("source_field")
            tgt_key = mapping.get("target_field")
            rule = mapping.get("transformation_rule", "DIRECT")
            default_val = mapping.get("default_value")
            is_required = mapping.get("is_required", False)
            enum_map = mapping.get("enum_map")

            raw_val = raw_record.get(src_key) if src_key else None
            if raw_val is None:
                val = default_val
            else:
                val = cls.apply_transformation(raw_val, rule, enum_map)

            if is_required and (val is None or str(val).strip() == ""):
                raise ValueError(f"Required target field '{tgt_key}' missing from source '{src_key}'.")

            if tgt_key:
                canonical_record[tgt_key] = val

        return canonical_record
