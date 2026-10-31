import re
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
DISPOSABLE_DOMAINS = {"mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com"}


class EntityResolver:
    """
    Enterprise Entity & Person Resolution Engine:
    - Multi-tier company deduplication and resolution hierarchy
    - Resolves public professionals and decision makers with confidence weighting
    - Enforces strict verification semantics (NEVER fabricates or guesses deliverability)
    """
    @classmethod
    def normalize_domain(cls, domain_or_url: str) -> Optional[str]:
        if not domain_or_url:
            return None
        raw = domain_or_url.strip().lower()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = f"http://{raw}"
        try:
            parsed = urlparse(raw)
            netloc = parsed.netloc
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc if netloc and "." in netloc else None
        except Exception:
            return None

    @classmethod
    def normalize_company_name(cls, name: str) -> str:
        if not name:
            return ""
        clean = " ".join(name.split()).lower()
        # Strip common legal suffixes
        suffixes = [
            r"\bpte\.?\s*ltd\.?\b",
            r"\bpty\.?\s*ltd\.?\b",
            r"\bpvt\.?\s*ltd\.?\b",
            r"\bltd\.?\b",
            r"\bllc\.?\b",
            r"\binc\.?\b",
            r"\bcorp\.?\b",
            r"\bgmbh\.?\b",
            r"\bco\.?\b"
        ]
        for s in suffixes:
            clean = re.sub(s, "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"[^\w\s]", "", clean)
        return clean.strip()

    @classmethod
    def resolve_company(
        cls,
        candidate_name: str,
        domain_hint: Optional[str] = None,
        existing_companies: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """
        Resolves candidate against existing company records using hierarchy:
        1. Exact canonical domain (Highest confidence)
        2. Normalized name + domain match
        3. Never merges solely on weak name similarity without domain/location corroboration.
        """
        norm_domain = cls.normalize_domain(domain_hint)
        norm_name = cls.normalize_company_name(candidate_name)

        if not existing_companies:
            return None, 1.0, "NEW_COMPANY"

        # Tier 1: Exact Domain Match
        if norm_domain:
            for comp in existing_companies:
                if comp.get("domain") and comp.get("domain").lower() == norm_domain:
                    return comp, 0.98, "EXACT_DOMAIN_MATCH"

        # Tier 2: Normalized Name + Matching Country/Website
        for comp in existing_companies:
            if comp.get("normalized_name") and comp.get("normalized_name") == norm_name:
                if comp.get("domain") and norm_domain and comp.get("domain").lower() == norm_domain:
                    return comp, 0.95, "NAME_AND_DOMAIN_MATCH"

        return None, 0.90, "NO_MATCH_CONFIRMED"

    @classmethod
    def verify_email(cls, email: str, is_publicly_listed: bool = True) -> Tuple[str, float]:
        """
        Validates email syntax, disposable domains, and assigns verification tier.
        Rule: An email is never marked VERIFIED_DELIVERABLE merely by syntax.
        """
        if not email or not EMAIL_REGEX.match(email.strip()):
            return "INVALID", 0.0

        clean_email = email.strip().lower()
        domain = clean_email.split("@")[1]

        if domain in DISPOSABLE_DOMAINS:
            return "INVALID", 0.0

        if is_publicly_listed:
            return "PUBLICLY_LISTED", 0.95

        return "PREDICTED", 0.50

    @classmethod
    def verify_phone(cls, phone: str, is_publicly_listed: bool = True) -> Tuple[str, float]:
        if not phone:
            return "INVALID", 0.0

        digits = re.sub(r"\D", "", phone)
        if len(digits) < 8 or len(digits) > 15:
            return "INVALID", 0.0

        if is_publicly_listed:
            return "PUBLICLY_LISTED", 0.90

        return "POSSIBLE_NUMBER", 0.60

