from typing import Dict, Any, List


class BuyingReadinessEngine:
    """
    Buying Readiness Assessment Engine:
    - Calculates probability of active procurement
    - Signals: Vendor search, timeline urgency, hiring, decision makers
    """
    @classmethod
    def evaluate_readiness(
        cls,
        company: Dict[str, Any],
        intent_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        score = 0.0
        factors = []
        timeline = "EXPLORATORY"

        # 1. Direct Vendor / Partner Search
        primary_intent = intent_data.get("primary_intent", "")
        if primary_intent in ["BUYING_INTENT", "PARTNER_SEARCH_INTENT", "VENDOR_SEARCH_INTENT"]:
            score += 35.0
            factors.append("Active search for an external partner/vendor (+35)")
            timeline = "IMMEDIATE"
        elif primary_intent in ["MIGRATION_INTENT", "UPGRADE_INTENT", "IMPLEMENTATION_INTENT"]:
            score += 25.0
            factors.append("Undergoing active ERP migration/upgrade/implementation (+25)")
            timeline = "1-3_MONTHS"

        # 2. Hiring Signal
        has_hiring = any(
            "HIRING" in s.get("signal_type", "") or "developer" in s.get("detected_keyword", "").lower()
            for s in company.get("signals", [])
        )
        if has_hiring:
            score += 25.0
            factors.append("Active technical hiring for ERP/software team (+25)")
            if timeline == "EXPLORATORY":
                timeline = "1-3_MONTHS"

        # 3. Decision Maker Identified
        contacts = company.get("contacts", [])
        target_roles = ["cto", "cio", "it manager", "erp manager", "head of it", "managing director", "ceo", "founder"]
        has_dm = any(any(r in c.get("job_title", "").lower() for r in target_roles) for c in contacts)

        if has_dm:
            score += 25.0
            factors.append("Verified executive decision maker identified in buying committee (+25)")
        elif contacts:
            score += 10.0
            factors.append("General contacts identified (+10)")

        # 4. Multi-Source Corroboration
        if intent_data.get("corroboration_count", 0) >= 2:
            score += 15.0
            factors.append("Corroborated across multiple independent sources (+15)")

        final_readiness = min(100.0, max(0.0, score))

        return {
            "buying_readiness_score": round(final_readiness, 2),
            "timeline_indicator": timeline,
            "has_active_hiring": has_hiring,
            "has_decision_maker_identified": has_dm,
            "readiness_factors": factors,
            "is_buying_ready": final_readiness >= 60.0
        }

