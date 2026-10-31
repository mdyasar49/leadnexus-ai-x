import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.knowledge_retrieval import (
    AIQueryExecution,
    AIClaim,
    AIClaimEvidence,
    AIAnswerValidation,
    PredictionLabel,
)


class ClaimValidationEngine:
    """
    AI Claim Extraction & Groundedness Validation Engine:
    - Extracts atomic factual claims from AI response text
    - Verifies each claim against retrieved evidence chunks
    - Detects unsupported claims and potential hallucinations
    - Computes overall groundedness score and validation verdict
    """

    def __init__(self, db: Session):
        self.db = db

    def extract_and_validate_claims(
        self,
        execution_id: str,
        response_text: str,
        retrieved_evidence: List[Dict[str, Any]]
    ) -> AIAnswerValidation:
        """
        Extracts atomic claims from generated text, matches them to evidence,
        and persists AIClaim and AIAnswerValidation records.
        """
        evidence_text_blob = " ".join([e.get("snippet", "").lower() for e in retrieved_evidence])
        
        # Extract atomic statements (lines or bullet points)
        raw_lines = [l.strip() for l in response_text.split("\n") if l.strip() and not l.startswith("#")]
        claims_data = []

        total_claims = 0
        supported_count = 0
        unsupported_count = 0

        for line in raw_lines:
            # Check for prediction markers
            pred_label = PredictionLabel.OBSERVED.value
            if "[PREDICTED]" in line or "predicted" in line.lower():
                pred_label = PredictionLabel.PREDICTED.value
            elif "[CALCULATED]" in line or "score" in line.lower():
                pred_label = PredictionLabel.CALCULATED.value
            elif "[RECOMMENDED]" in line or "recommend" in line.lower():
                pred_label = PredictionLabel.RECOMMENDED.value

            # Clean line text
            clean_stmt = re.sub(r"^[\•\-\*]\s*", "", line)
            clean_stmt = re.sub(r"\[.*?\]", "", clean_stmt).strip()
            if len(clean_stmt) < 15:
                continue

            total_claims += 1

            # Check if keywords in claim appear in evidence blob
            keywords = [w.lower() for w in re.findall(r"\w+", clean_stmt) if len(w) > 3]
            overlap = sum(1 for kw in keywords if kw in evidence_text_blob)
            overlap_ratio = overlap / max(1, len(keywords))

            # Predictions and recommendations don't require direct observational evidence
            if pred_label in (PredictionLabel.PREDICTED.value, PredictionLabel.RECOMMENDED.value):
                is_supported = True
                certainty = "ESTIMATED"
            elif overlap_ratio >= 0.40:
                is_supported = True
                certainty = "SUPPORTED"
                supported_count += 1
            else:
                is_supported = False
                certainty = "UNSUPPORTED"
                unsupported_count += 1

            claim_row = AIClaim(
                execution_id=execution_id,
                claim_type="FACTUAL_ASSERTION",
                subject=clean_stmt[:100],
                predicate="ASSERTS",
                object_value=clean_stmt[100:300] if len(clean_stmt) > 100 else clean_stmt,
                prediction_label=pred_label,
                certainty=certainty,
                evidence_count=1 if is_supported else 0
            )
            self.db.add(claim_row)
            self.db.commit()
            self.db.refresh(claim_row)

            if is_supported and retrieved_evidence:
                ev_link = AIClaimEvidence(
                    claim_id=claim_row.id,
                    evidence_id=retrieved_evidence[0].get("evidence_id") or retrieved_evidence[0].get("item_id"),
                    source_url=retrieved_evidence[0].get("source_url"),
                    snippet=retrieved_evidence[0].get("snippet")
                )
                self.db.add(ev_link)

        groundedness = round(supported_count / max(1, (supported_count + unsupported_count)), 2)
        has_hallucinations = unsupported_count > 0 and groundedness < 0.60
        status_verdict = "REJECTED" if has_hallucinations else ("PASSED" if groundedness >= 0.70 else "PARTIAL")

        val = AIAnswerValidation(
            execution_id=execution_id,
            is_grounded=not has_hallucinations,
            groundedness_score=groundedness,
            total_claims=total_claims,
            supported_claims=supported_count,
            unsupported_claims_count=unsupported_count,
            has_hallucinations=has_hallucinations,
            validation_status=status_verdict,
            details={
                "groundedness_ratio": groundedness,
                "unsupported_statements_count": unsupported_count
            }
        )
        self.db.add(val)
        self.db.commit()
        self.db.refresh(val)
        return val

