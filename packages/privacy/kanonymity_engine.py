"""
LeadNexus AI X - Phase 48: k-Anonymity & Differential Privacy Engine
Audits analytical export datasets to prevent individual re-identification across quasi-identifiers.
"""

from collections import defaultdict
from typing import Any, Dict, List, Tuple


class KAnonymityEngine:
    def evaluate(
        self,
        records: List[Dict[str, Any]],
        quasi_identifiers: List[str],
        k_threshold: int = 5,
    ) -> Dict[str, Any]:
        """
        Evaluates k-anonymity across records by grouping on quasi_identifiers.
        Returns evaluation metrics, minimum k found, and remediation advice.
        """
        if not records:
            return {
                "is_k_anonymous": True,
                "min_k": 0,
                "violating_cohorts_count": 0,
                "total_cohorts": 0,
                "recommendations": ["Dataset is empty."],
            }

        cohorts: Dict[Tuple[Any, ...], int] = defaultdict(int)
        for r in records:
            cohort_key = tuple(r.get(qi, "NULL") for qi in quasi_identifiers)
            cohorts[cohort_key] += 1

        total_cohorts = len(cohorts)
        cohort_sizes = list(cohorts.values())
        min_k = min(cohort_sizes) if cohort_sizes else 0

        violating_cohorts = [k for k, size in cohorts.items() if size < k_threshold]
        is_k_anonymous = len(violating_cohorts) == 0

        recommendations = []
        if not is_k_anonymous:
            recommendations.append(
                f"{len(violating_cohorts)} out of {total_cohorts} cohorts have fewer than {k_threshold} records."
            )
            recommendations.append(
                "Apply hierarchical generalization (e.g., aggregate 'City' to 'State/Country' or group 'Company Size' into broader brackets)."
            )
            recommendations.append(
                "Consider suppressing rare outlier cohorts to satisfy differential privacy standards."
            )
        else:
            recommendations.append(
                f"Dataset satisfies {k_threshold}-anonymity with lowest cohort size = {min_k}."
            )

        return {
            "is_k_anonymous": is_k_anonymous,
            "min_k": min_k,
            "violating_cohorts_count": len(violating_cohorts),
            "total_cohorts": total_cohorts,
            "recommendations": recommendations,
        }
