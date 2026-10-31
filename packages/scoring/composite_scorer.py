from typing import Dict, Any, List, Optional
from app.models.scoring import LeadPriorityTier


DEFAULT_WEIGHTS = {
    "icp_fit": 0.30,
    "intent": 0.30,
    "buying_readiness": 0.15,
    "evidence_confidence": 0.10,
    "data_quality": 0.05,
    "contact_quality": 0.05,
    "freshness": 0.05,
}


class CompositeScorer:
    """
    Predictive Lead Scoring & Priority Engine:
    - Calculates 8 separate independent component scores (0-100)
    - Produces explainable Lead Priority Score (0-100) and Priority Tier (P0-P4)
    - Generates positive/negative factors and supports model versioning
    """
    @classmethod
    def calculate_lead_score(
        cls,
        company: Dict[str, Any],
        icp_data: Dict[str, Any],
        intent_data: Dict[str, Any],
        readiness_data: Dict[str, Any],
        weights_override: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        weights = weights_override or DEFAULT_WEIGHTS
        positive_factors = []
        negative_factors = []

        # 1. Component Scores (0-100)
        icp_score = icp_data.get("icp_fit_score", 50.0)
        intent_score = intent_data.get("intent_score", 50.0)
        readiness_score = readiness_data.get("buying_readiness_score", 50.0)
        
        # Evidence Confidence Score (0-100)
        evidence_count = len(company.get("signals", []))
        evidence_score = min(100.0, 50.0 + (evidence_count * 15.0))

        # Data Quality Score (0-100)
        has_domain = bool(company.get("domain"))
        has_name = bool(company.get("name"))
        has_country = bool(company.get("country"))
        data_quality_score = (40.0 if has_domain else 0.0) + (35.0 if has_name else 0.0) + (25.0 if has_country else 0.0)

        # Contact Quality Score (0-100)
        contacts = company.get("contacts", [])
        has_verified_email = any(c.get("email_status") in ["PUBLICLY_LISTED", "VERIFIED"] for c in contacts)
        has_phone = any(bool(c.get("business_phone")) for c in contacts) or bool(company.get("business_phone"))
        contact_quality_score = 0.0
        if has_verified_email:
            contact_quality_score += 60.0
        elif contacts:
            contact_quality_score += 30.0
        if has_phone:
            contact_quality_score += 40.0

        # Research Completeness (0-100)
        research_completeness = round((data_quality_score + contact_quality_score) / 2.0, 2)

        # Freshness Score (0-100)
        freshness_decay = intent_data.get("temporal_decay_factor", 0.85)
        freshness_score = round(freshness_decay * 100.0, 2)

        # Build Explainable Factors
        if icp_score >= 80.0:
            positive_factors.append(f"Strong ICP target fit ({icp_score:.0f}/100)")
        elif icp_score < 50.0:
            negative_factors.append(f"Weak ICP fit ({icp_score:.0f}/100)")

        if intent_score >= 80.0:
            positive_factors.append(f"High buying intent detected ({intent_data.get('primary_intent')})")
        elif intent_data.get("is_service_provider"):
            negative_factors.append("Classified as service provider or competitor (-80)")

        if readiness_data.get("has_decision_maker_identified"):
            positive_factors.append("Executive decision maker identified in buying committee")
        else:
            negative_factors.append("No decision maker confirmed in contacts")

        if has_verified_email:
            positive_factors.append("Publicly listed business email available")
        else:
            negative_factors.append("No verified business email")

        # Weighted calculation
        raw_weighted = (
            (icp_score * weights.get("icp_fit", 0.30)) +
            (intent_score * weights.get("intent", 0.30)) +
            (readiness_score * weights.get("buying_readiness", 0.15)) +
            (evidence_score * weights.get("evidence_confidence", 0.10)) +
            (data_quality_score * weights.get("data_quality", 0.05)) +
            (contact_quality_score * weights.get("contact_quality", 0.05)) +
            (freshness_score * weights.get("freshness", 0.05))
        )

        # Deduct heavily if entity is an IT Service Provider or Competitor
        if intent_data.get("is_service_provider"):
            raw_weighted = min(15.0, raw_weighted * 0.15)

        final_priority_score = round(min(100.0, max(0.0, raw_weighted)), 2)

        # Assign Priority Tier
        if intent_data.get("is_service_provider"):
            priority_tier = LeadPriorityTier.P4_IGNORE.value
        elif final_priority_score >= 85.0:
            priority_tier = LeadPriorityTier.P0_CRITICAL.value
        elif final_priority_score >= 70.0:
            priority_tier = LeadPriorityTier.P1_HIGH.value
        elif final_priority_score >= 50.0:
            priority_tier = LeadPriorityTier.P2_MEDIUM.value
        elif final_priority_score >= 30.0:
            priority_tier = LeadPriorityTier.P3_LOW.value
        else:
            priority_tier = LeadPriorityTier.P4_IGNORE.value

        return {
            "lead_priority_score": final_priority_score,
            "priority_tier": priority_tier,
            "components": {
                "icp_fit_score": icp_score,
                "intent_score": intent_score,
                "buying_readiness_score": readiness_score,
                "evidence_confidence_score": evidence_score,
                "data_quality_score": data_quality_score,
                "contact_quality_score": contact_quality_score,
                "research_completeness_score": research_completeness,
                "freshness_score": freshness_score,
            },
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "calculation_version": "v1.0.0",
        }

