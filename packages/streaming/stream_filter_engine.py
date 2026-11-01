"""
LeadNexus AI X - Phase 47: Stream Filter Engine
Real-time predicate matching for live signal routing and subscription delivery.
"""

from typing import Any, Dict


class StreamFilterEngine:
    def matches(self, signal: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """
        Evaluates whether signal satisfies all criteria rules.
        Empty criteria matches everything.
        """
        if not criteria:
            return True

        for key, expected_val in criteria.items():
            actual_val = self._resolve_field(signal, key)

            if actual_val is None:
                return False

            # Numeric threshold prefix matching
            if key.startswith("min_") and isinstance(expected_val, (int, float)):
                if not isinstance(actual_val, (int, float)) or actual_val < expected_val:
                    return False
            elif key.startswith("max_") and isinstance(expected_val, (int, float)):
                if not isinstance(actual_val, (int, float)) or actual_val > expected_val:
                    return False
            elif isinstance(expected_val, str):
                if expected_val.lower() not in str(actual_val).lower():
                    return False
            elif isinstance(expected_val, list):
                if actual_val not in expected_val:
                    return False
            elif actual_val != expected_val:
                return False

        return True

    def _resolve_field(self, signal: Dict[str, Any], key: str) -> Any:
        # Check direct signal fields
        if key in signal:
            return signal[key]

        # Check payload
        payload = signal.get("payload", {})
        if key in payload:
            return payload[key]

        # Normalize special keys
        if key == "min_confidence":
            return signal.get("confidence", 1.0)
        if key == "company":
            return signal.get("company_name")

        return None
