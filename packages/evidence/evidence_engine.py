import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

DEFAULT_SOURCE_RELIABILITY = {
    "company_website": 0.95,
    "github": 0.92,
    "job_boards": 0.90,
    "public_api": 0.95,
    "forum_reddit": 0.72,
    "search_engine": 0.65,
    "rss_feeds": 0.80,
    "public_directory": 0.68,
}


class EvidenceEngine:
    """
    Evidence-First Provenance Engine:
    - Calculates SHA-256 evidence hashes
    - Attaches source reliability weightings and confidence
    - Maintains immutable provenance across every claim
    """
    @classmethod
    def create_evidence_record(
        cls,
        source_url: str,
        source_type: str,
        evidence_text: str,
        claim_type: str = "INTENT_SIGNAL",
        collector_version: str = "1.0.0",
        custom_reliability: Optional[float] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        clean_evidence = " ".join(evidence_text.split()) if evidence_text else ""
        
        # SHA-256 hash
        hash_input = f"{source_url}:{claim_type}:{clean_evidence}"
        evidence_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        reliability = custom_reliability or DEFAULT_SOURCE_RELIABILITY.get(source_type.lower(), 0.70)

        return {
            "source_url": source_url,
            "source_type": source_type,
            "claim_type": claim_type,
            "evidence_text": clean_evidence,
            "evidence_hash": evidence_hash,
            "source_reliability": reliability,
            "confidence": min(1.0, max(0.1, reliability)),
            "collector_version": collector_version,
            "observed_at": now.isoformat(),
            "extracted_at": now.isoformat(),
        }

