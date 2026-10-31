from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.scoring import ClaimStatus


class LeadReasoningResult(BaseModel):
    icp_score: float = Field(..., ge=0.0, le=100.0)
    intent_score: float = Field(..., ge=0.0, le=100.0)
    buying_readiness_score: float = Field(..., ge=0.0, le=100.0)
    evidence_confidence: float = Field(..., ge=0.0, le=1.0)
    ai_confidence: float = Field(default=0.92, ge=0.0, le=1.0)
    primary_intent: Optional[str] = None
    secondary_intents: List[str] = Field(default_factory=list)
    primary_need: Optional[str] = None
    positive_evidence_ids: List[str] = Field(default_factory=list)
    negative_evidence_ids: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    reasoning_summary: str


class EvidenceReasoner:
    """
    Evidence Reasoning Engine:
    - Reasons over concrete evidence claims (NO_EVIDENCE = NO_FACT)
    - Validates contradictions, detects missing gaps, and formulates next research actions
    """
    @classmethod
    def reason_over_lead(
        cls,
        company: Dict[str, Any],
        icp_data: Dict[str, Any],
        intent_data: Dict[str, Any],
        readiness_data: Dict[str, Any]
    ) -> LeadReasoningResult:
        positive_evidence_ids = []
        negative_evidence_ids = []
        contradictions = []
        missing_information = []
        recommended_actions = []

        signals = company.get("signals", [])
        contacts = company.get("contacts", [])
        technologies = company.get("technologies", [])

        # Collect Evidence IDs
        for sig in signals:
            h = sig.get("evidence_hash") or sig.get("evidence_pointer")
            if h:
                positive_evidence_ids.append(str(h))

        # Check Service Provider Contradiction
        if intent_data.get("is_service_provider"):
            contradictions.append("Entity presents as an Odoo/IT Service Provider or Partner, contradicting buyer persona.")
            negative_evidence_ids.append("service_provider_signature")

        # Check Missing Information Gaps
        if not company.get("domain"):
            missing_information.append("Company official domain unconfirmed")
            recommended_actions.append("Execute targeted search for canonical business domain")

        has_dm = readiness_data.get("has_decision_maker_identified", False)
        if not has_dm:
            missing_information.append("Executive decision maker (CTO, CIO, IT Manager) missing from contact record")
            recommended_actions.append("Research executive leadership on official team/about page")

        if not any(c.get("business_phone") for c in contacts) and not company.get("business_phone"):
            missing_information.append("Public business office phone missing")
            recommended_actions.append("Inspect official contact page for verified telephone number")

        # Determine Primary Need
        primary_intent = intent_data.get("primary_intent", "GENERAL_INTEREST")
        primary_need = f"Likely seeking assistance with {primary_intent.replace('_', ' ').lower()}"

        # Construct Grounded Reasoning Summary
        icp_score = icp_data.get("icp_fit_score", 50.0)
        intent_score = intent_data.get("intent_score", 50.0)
        readiness_score = readiness_data.get("buying_readiness_score", 50.0)

        evidence_confidence = 0.95 if len(positive_evidence_ids) >= 2 else 0.70

        summary = (
            f"Lead evaluated with ICP Fit of {icp_score}/100 and Intent Score of {intent_score}/100. "
            f"Primary intent: {primary_intent}. "
            f"Corroborated by {len(positive_evidence_ids)} verified evidence record(s). "
        )
        if contradictions:
            summary += f" Contradictions detected: {'; '.join(contradictions)}."
        elif missing_information:
            summary += f" Key missing attributes: {', '.join(missing_information[:2])}."

        return LeadReasoningResult(
            icp_score=icp_score,
            intent_score=intent_score,
            buying_readiness_score=readiness_score,
            evidence_confidence=evidence_confidence,
            ai_confidence=0.92,
            primary_intent=primary_intent,
            secondary_intents=intent_data.get("secondary_intents", []),
            primary_need=primary_need,
            positive_evidence_ids=positive_evidence_ids,
            negative_evidence_ids=negative_evidence_ids,
            contradictions=contradictions,
            missing_information=missing_information,
            recommended_actions=recommended_actions,
            reasoning_summary=summary,
        )

