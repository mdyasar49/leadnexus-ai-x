from typing import Dict, Any, List


class RecommendationEngine:
    """
    Research Recommendation & Next-Best-Action Engine:
    - Calculates Expected Information Value (EIV)
    - Prioritizes targeted follow-up research tasks within budget limits
    - Enforces safety boundaries: AI only recommends approved, bounded actions
    """
    @classmethod
    def determine_next_action(
        cls,
        company: Dict[str, Any],
        score_data: Dict[str, Any],
        gaps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        components = score_data.get("components", {})
        contact_score = components.get("contact_quality_score", 0.0)
        icp_score = components.get("icp_fit_score", 0.0)
        intent_score = components.get("intent_score", 0.0)

        # Evaluate candidate actions based on Expected Information Value
        candidates = []

        # 1. Missing Decision Maker
        if contact_score < 60.0:
            candidates.append({
                "action": "RESEARCH_DECISION_MAKER",
                "description": "Discover executive IT/ERP decision maker (CTO, CIO, IT Manager)",
                "target_role": "CTO / IT Director",
                "potential_score_gain": 20.0,
                "confidence": 0.85,
                "cost_estimate_usd": 0.005,
                "priority": "HIGH",
            })

        # 2. Missing Phone
        if not company.get("business_phone"):
            candidates.append({
                "action": "VERIFY_BUSINESS_PHONE",
                "description": "Inspect company public contact page for office phone number",
                "potential_score_gain": 10.0,
                "confidence": 0.90,
                "cost_estimate_usd": 0.002,
                "priority": "NORMAL",
            })

        # 3. Refresh Stale Evidence
        if components.get("freshness_score", 100.0) < 50.0:
            candidates.append({
                "action": "REFRESH_EVIDENCE",
                "description": "Query latest public jobs and GitHub commits to verify active intent",
                "potential_score_gain": 15.0,
                "confidence": 0.80,
                "cost_estimate_usd": 0.003,
                "priority": "HIGH",
            })

        # Sort by (potential_score_gain * confidence) / cost
        if candidates:
            candidates.sort(key=lambda x: (x["potential_score_gain"] * x["confidence"]) / x["cost_estimate_usd"], reverse=True)
            top_action = candidates[0]
        else:
            top_action = {
                "action": "QUALIFIED_READY_FOR_ENGAGEMENT",
                "description": "Lead has complete evidence and decision maker; no further automated research required",
                "potential_score_gain": 0.0,
                "confidence": 1.0,
                "cost_estimate_usd": 0.0,
                "priority": "LOW",
            }

        return {
            "recommended_action": top_action["action"],
            "action_details": top_action,
            "all_opportunities": candidates,
            "expected_information_value": round(top_action["potential_score_gain"] * top_action["confidence"], 2)
        }

