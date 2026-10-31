import re
import hashlib
from typing import Dict, Any, List, Optional
from app.models.technology import OdooSignalType

VERSION_PATTERNS = [
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?19(?:\.0)?\b', re.IGNORECASE), "Odoo 19"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?18(?:\.0)?\b', re.IGNORECASE), "Odoo 18"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?17(?:\.0)?\b', re.IGNORECASE), "Odoo 17"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?16(?:\.0)?\b', re.IGNORECASE), "Odoo 16"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?15(?:\.0)?\b', re.IGNORECASE), "Odoo 15"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?14(?:\.0)?\b', re.IGNORECASE), "Odoo 14"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?13(?:\.0)?\b', re.IGNORECASE), "Odoo 13"),
    (re.compile(r'\bodoo\s*(?:v(?:ersion)?\s*)?12(?:\.0)?\b', re.IGNORECASE), "Odoo 12"),
]

SIGNAL_PATTERNS = [
    (re.compile(r'\b(?:hiring|looking for|seeking)\s+(?:an?\s+)?odoo\s+(?:developer|consultant|specialist|expert)\b', re.IGNORECASE), OdooSignalType.ODOO_DEVELOPER_HIRING),
    (re.compile(r'\b(?:migrat(?:ing|ion))\s+(?:to|from)\s+odoo\b', re.IGNORECASE), OdooSignalType.ODOO_MIGRATION),
    (re.compile(r'\b(?:upgrad(?:ing|e))\s+(?:from|to|our|\w+\s+)*?odoo\b', re.IGNORECASE), OdooSignalType.ODOO_UPGRADE),
    (re.compile(r'\bodoo\s+(?:implementation|rollout)\b', re.IGNORECASE), OdooSignalType.IMPLEMENTS_ODOO),
    (re.compile(r'\bodoo\s+integration\b', re.IGNORECASE), OdooSignalType.ODOO_INTEGRATION),
    (re.compile(r'\bodoo\s+(?:custom(?:ization| module)|partner)\b', re.IGNORECASE), OdooSignalType.ODOO_CUSTOMIZATION),
    (re.compile(r'\b(?:official|certified|gold|silver|ready)\s+odoo\s+partner\b', re.IGNORECASE), OdooSignalType.PARTNER_ECOSYSTEM),
    (re.compile(r'\bodoo\s+(?:support|troubleshooting|helpdesk)\b', re.IGNORECASE), OdooSignalType.ODOO_SUPPORT),
    (re.compile(r'\b(?:uses|running\s+on|powered\s+by)\s+odoo\b', re.IGNORECASE), OdooSignalType.USES_ODOO),
]


class OdooIntelligence:
    """
    Dedicated Odoo Enterprise Intelligence Engine:
    - Extracts grounded Odoo versions (Odoo 12-19). Never infers without evidence.
    - Classifies commercial intent and adoption stage.
    """
    @classmethod
    def analyze_text(cls, text: str, source_url: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        clean_text = " ".join(text.split())
        observations = []

        # 1. Version Detection
        detected_version: Optional[str] = None
        for pattern, ver_name in VERSION_PATTERNS:
            match = pattern.search(clean_text)
            if match:
                detected_version = ver_name
                break  # Pick highest/most specific version match

        # 2. Signal Type Classification
        for pattern, sig_type in SIGNAL_PATTERNS:
            match = pattern.search(clean_text)
            if match:
                start = max(0, match.start() - 60)
                end = min(len(clean_text), match.end() + 60)
                evidence = clean_text[start:end]
                evidence_hash = hashlib.sha256(f"{source_url}:{evidence}".encode("utf-8")).hexdigest()

                observations.append({
                    "signal_type": sig_type.value,
                    "detected_version": detected_version,
                    "source_url": source_url,
                    "evidence_text": evidence,
                    "evidence_hash": evidence_hash,
                    "confidence": 0.95 if detected_version else 0.88,
                })

        # Fallback: General Odoo mention if nothing specific triggered
        if not observations and "odoo" in clean_text.lower():
            idx = clean_text.lower().find("odoo")
            snippet = clean_text[max(0, idx - 50):min(len(clean_text), idx + 50)]
            observations.append({
                "signal_type": OdooSignalType.USES_ODOO.value,
                "detected_version": detected_version,
                "source_url": source_url,
                "evidence_text": snippet,
                "evidence_hash": hashlib.sha256(f"{source_url}:{snippet}".encode("utf-8")).hexdigest(),
                "confidence": 0.75,
            })

        return observations
