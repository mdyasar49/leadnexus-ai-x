import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

HIGH_INTENT_PATTERNS = [
    (r'\b(?:looking for|seeking|need)\s+(?:an?\s+)?(?:odoo|erp|zoho)\s+(?:partner|consultant|agency|vendor)\b', "BUYING_INTENT", 100.0),
    (r'\b(?:migrat(?:ing|ion))\s+(?:to|from)\s+(?:odoo|erp|shopify)\b', "MIGRATION_INTENT", 95.0),
    (r'\b(?:upgrad(?:ing|e))\s+(?:our\s+)?(?:odoo|erp)\b', "UPGRADE_INTENT", 90.0),
    (r'\b(?:implement(?:ing|ation))\s+partner\b', "IMPLEMENTATION_INTENT", 90.0),
    (r'\b(?:integrat(?:ing|ion))\s+between\s+(?:odoo|erp|shopify|pos)\b', "INTEGRATION_INTENT", 85.0),
    (r'\bcustom\s+module\s+(?:development|customization)\b', "CUSTOMIZATION_INTENT", 80.0),
]

MEDIUM_INTENT_PATTERNS = [
    (r'\b(?:hiring|seeking)\s+(?:an?\s+)?(?:odoo|erp)\s+(?:developer|administrator|manager)\b', "HIRING_INTENT", 75.0),
    (r'\b(?:evaluating|comparing)\s+(?:odoo|zoho|salesforce|netsuite)\b', "TECHNOLOGY_EVALUATION", 70.0),
    (r'\btechnical\s+issue\s+with\s+(?:odoo|pos|accounting)\b', "TECHNICAL_EVALUATION", 65.0),
]

# Negative Patterns that indicate the entity is a vendor/competitor, not a buyer
SERVICE_PROVIDER_PATTERNS = [
    r'\bwe\s+(?:provide|deliver|offer|specialize in)\s+odoo\s+(?:services|implementation|consulting)\b',
    r'\bour\s+(?:clients|customers|case studies)\b',
    r'\bofficial\s+odoo\s+(?:gold|silver|ready)\s+partner\b',
    r'\bhire\s+our\s+odoo\s+developers\b',
    r'\bwe\s+are\s+an?\s+odoo\s+partner\b',
    r'\btutorial\b',
    r'\bcourse\b',
]


class IntentEngine:
    """
    Advanced Intent Intelligence Engine:
    - Detailed Intent Taxonomy (High, Medium, Low, Negative)
    - Context-aware disambiguation (Buyer vs Service Provider/Competitor)
    - Temporal decay model with configurable aging windows
    - Signal corroboration and source independence analysis
    """
    @classmethod
    def calculate_temporal_decay(cls, event_date_iso: Optional[str]) -> float:
        """
        Calculates temporal weight factor based on recency.
        """
        if not event_date_iso:
            return 1.0  # Fresh by default if newly captured

        try:
            if "T" in event_date_iso:
                dt = datetime.fromisoformat(event_date_iso.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(event_date_iso[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            days_old = (now - dt).days

            if days_old <= 7:
                return 1.0     # Very fresh
            elif days_old <= 30:
                return 0.85    # Fresh
            elif days_old <= 90:
                return 0.70    # Recent
            elif days_old <= 180:
                return 0.40    # Aging
            else:
                return 0.20    # Stale
        except Exception:
            return 0.70

    @classmethod
    def classify_intent_context(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Differentiates positive buying intent from negative service provider/competitor status.
        Returns (is_service_provider, detected_pattern).
        """
        if not text:
            return False, None

        lower = text.lower()
        for pat in SERVICE_PROVIDER_PATTERNS:
            if re.search(pat, lower, re.IGNORECASE):
                return True, "SERVICE_PROVIDER"

        return False, None

    @classmethod
    def assess_company_intent(
        cls,
        signals: List[Dict[str, Any]],
        company_text_corpus: str = ""
    ) -> Dict[str, Any]:
        """
        Evaluates signals and returns structured intent assessment.
        """
        # 1. Context check: Is this entity a service provider?
        is_provider, reason = cls.classify_intent_context(company_text_corpus)
        if is_provider:
            return {
                "intent_score": 10.0,
                "primary_intent": "SERVICE_PROVIDER",
                "secondary_intents": ["COMPETITOR_ONLY"],
                "positive_signals_count": 0,
                "negative_signals_count": 1,
                "corroboration_count": 0,
                "is_service_provider": True,
                "explanation": "Entity identified as an Odoo/IT Service Provider or Partner, not an end-user buyer."
            }

        if not signals:
            return {
                "intent_score": 20.0,
                "primary_intent": "PASSIVE_MENTION",
                "secondary_intents": [],
                "positive_signals_count": 0,
                "negative_signals_count": 0,
                "corroboration_count": 0,
                "is_service_provider": False,
                "explanation": "No commercial intent signals detected."
            }

        # 2. Extract and score signals
        scored_intents = []
        distinct_sources = set()
        seen_content_hashes = set()

        for sig in signals:
            text = f"{sig.get('detected_keyword', '')} {sig.get('evidence_snippet', '')} {sig.get('raw_text', '')}"
            source_type = sig.get("source_name", sig.get("source", "web"))
            content_hash = sig.get("evidence_hash", hash(text))

            # Deduplication: do not double count identical syndicated evidence
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)
            distinct_sources.add(source_type)

            # Recency factor
            decay = cls.calculate_temporal_decay(sig.get("date_found") or sig.get("captured_at"))

            # Check High Intent
            matched = False
            for pat, intent_name, base_score in HIGH_INTENT_PATTERNS:
                if re.search(pat, text, re.IGNORECASE):
                    scored_intents.append((intent_name, base_score * decay, sig))
                    matched = True
                    break

            if not matched:
                # Check Medium Intent
                for pat, intent_name, base_score in MEDIUM_INTENT_PATTERNS:
                    if re.search(pat, text, re.IGNORECASE):
                        scored_intents.append((intent_name, base_score * decay, sig))
                        matched = True
                        break

            if not matched:
                # Default weak intent
                scored_intents.append(("GENERAL_INTEREST", 40.0 * decay, sig))

        if not scored_intents:
            return {
                "intent_score": 25.0,
                "primary_intent": "GENERAL_INTEREST",
                "secondary_intents": [],
                "positive_signals_count": 0,
                "negative_signals_count": 0,
                "corroboration_count": 1,
                "is_service_provider": False,
                "explanation": "Weak/neutral technology signals without explicit commercial intent."
            }

        # Sort by highest intent score
        scored_intents.sort(key=lambda x: x[1], reverse=True)
        top_intent = scored_intents[0]

        # Multi-source Corroboration Bonus (+10% if corroborated across distinct sources, e.g. Job + GitHub)
        corroboration_bonus = min(20.0, (len(distinct_sources) - 1) * 10.0)
        final_intent_score = min(100.0, top_intent[1] + corroboration_bonus)

        secondary = list(set([i[0] for i in scored_intents[1:4] if i[0] != top_intent[0]]))

        return {
            "intent_score": round(final_intent_score, 2),
            "primary_intent": top_intent[0],
            "secondary_intents": secondary,
            "positive_signals_count": len(scored_intents),
            "negative_signals_count": 0,
            "corroboration_count": len(distinct_sources),
            "is_service_provider": False,
            "explanation": f"Strong commercial signal: {top_intent[0]} corroborated across {len(distinct_sources)} distinct source(s)."
        }
