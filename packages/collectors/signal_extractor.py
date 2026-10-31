import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class RawSignal:
    source_name: str
    source_url: str
    detected_keyword: str
    evidence_snippet: str
    signal_type: str = "INTENT_SIGNAL"
    signal_strength: float = 1.0
    author_or_speaker: Optional[str] = None
    company_name_hint: Optional[str] = None
    domain_hint: Optional[str] = None
    location_hint: Optional[str] = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "detected_keyword": self.detected_keyword,
            "evidence_snippet": self.evidence_snippet,
            "signal_type": self.signal_type,
            "signal_strength": self.signal_strength,
            "author_or_speaker": self.author_or_speaker,
            "company_name_hint": self.company_name_hint,
            "domain_hint": self.domain_hint,
            "location_hint": self.location_hint,
            "captured_at": self.captured_at.isoformat(),
            "raw_payload": self.raw_payload,
        }


def extract_evidence_snippet(text: str, keyword: str, window: int = 140) -> str:
    """
    Extracts an evidence window around a detected intent keyword with ellipses.
    """
    if not text or not keyword:
        return ""
    
    clean_text = " ".join(text.split())
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    match = pattern.search(clean_text)
    
    if not match:
        return clean_text[:250] + ("..." if len(clean_text) > 250 else "")
    
    start = max(0, match.start() - window)
    end = min(len(clean_text), match.end() + window)
    
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean_text) else ""
    return f"{prefix}{clean_text[start:end]}{suffix}"
