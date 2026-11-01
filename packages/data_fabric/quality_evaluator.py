"""
Data Quality & Freshness Evaluator (Phase 39)
Calculates multi-dimensional data quality scores: Completeness, Validity, Timeliness, and Uniqueness.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class DataQualityEvaluator:
    """Evaluates multi-dimensional data quality benchmarks across domain entities."""

    @classmethod
    def evaluate_records(
        cls,
        records: List[Dict[str, Any]],
        required_fields: List[str],
        unique_key: Optional[str] = None,
        sla_seconds: int = 3600,
        timestamp_field: str = "updated_at",
    ) -> Dict[str, Any]:
        """
        Computes 4-dimensional quality radar:
        - Completeness: Non-null ratio across required fields.
        - Validity: Ratio of non-corrupt / compliant records.
        - Timeliness: Ratio of records updated within SLA.
        - Uniqueness: Distinct ratio of primary key values.
        """
        total_records = len(records)
        if total_records == 0:
            return {
                "completeness": 100.0,
                "validity": 100.0,
                "timeliness": 100.0,
                "uniqueness": 100.0,
                "overall_score": 100.0,
                "violations": [],
            }

        violations: List[str] = []

        # 1. Completeness Score
        total_required_slots = total_records * len(required_fields) if required_fields else total_records
        filled_slots = 0
        for idx, rec in enumerate(records):
            for field in required_fields:
                val = rec.get(field)
                if val is not None and val != "":
                    filled_slots += 1
                else:
                    violations.append(f"Record #{idx} missing required field '{field}'.")

        completeness = round((filled_slots / total_required_slots) * 100.0, 1) if total_required_slots > 0 else 100.0

        # 2. Uniqueness Score
        if unique_key:
            keys_seen = set()
            duplicates = 0
            for idx, rec in enumerate(records):
                k = rec.get(unique_key)
                if k in keys_seen:
                    duplicates += 1
                    violations.append(f"Duplicate key '{k}' found at record #{idx}.")
                else:
                    keys_seen.add(k)
            uniqueness = round(((total_records - duplicates) / total_records) * 100.0, 1)
        else:
            uniqueness = 100.0

        # 3. Timeliness / Freshness Score
        now = datetime.now(timezone.utc)
        fresh_records = 0
        for idx, rec in enumerate(records):
            ts = rec.get(timestamp_field)
            if ts:
                if isinstance(ts, str):
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts_dt = now
                elif isinstance(ts, datetime):
                    ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                else:
                    ts_dt = now

                age = (now - ts_dt).total_seconds()
                if age <= sla_seconds:
                    fresh_records += 1
                else:
                    violations.append(f"Record #{idx} exceeds freshness SLA ({age:.0f}s > {sla_seconds}s).")
            else:
                fresh_records += 1  # Assume fresh if no timestamp provided

        timeliness = round((fresh_records / total_records) * 100.0, 1)

        # 4. Validity Score (no corrupt/malformed values)
        valid_records = total_records
        for idx, rec in enumerate(records):
            # Example validity check: email format if present
            if "email" in rec and rec["email"]:
                if "@" not in str(rec["email"]) or "." not in str(rec["email"]):
                    valid_records -= 1
                    violations.append(f"Record #{idx} contains invalid email format: '{rec['email']}'.")

        validity = round((valid_records / total_records) * 100.0, 1)

        # Weighted Overall Score: Completeness (35%), Validity (25%), Timeliness (25%), Uniqueness (15%)
        overall = round(
            (completeness * 0.35) + (validity * 0.25) + (timeliness * 0.25) + (uniqueness * 0.15),
            1,
        )

        return {
            "completeness": completeness,
            "validity": validity,
            "timeliness": timeliness,
            "uniqueness": uniqueness,
            "overall_score": overall,
            "total_evaluated": total_records,
            "violations_count": len(violations),
            "violations": violations[:20],  # Sample first 20
        }
