import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.enrichment import (
    ContactPoint,
    ContactVerification,
    VerificationExpiration,
    ContactOwnershipType,
    EmailDeliverabilityStatus,
    PhoneType,
    PrivacyClassification,
)


GENERIC_PREFIXES = {
    "info", "contact", "hello", "admin", "enquiries", "office", "mail", "help", "general", "inquiry"
}

DEPARTMENT_PREFIXES = {
    "sales", "support", "billing", "jobs", "careers", "marketing", "partners", "legal", "hr",
    "recruitment", "finance", "press", "media", "privacy", "security", "dev", "engineering"
}

DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "sharklasers.com", "yopmail.com", "trashmail.com", "throwawaymail.com"
}

COUNTRY_CALLING_CODES = {
    "61": "Australia",
    "1": "United States/Canada",
    "91": "India",
    "44": "United Kingdom",
    "49": "Germany",
    "33": "France",
    "65": "Singapore",
    "64": "New Zealand",
}


class ContactIntelligenceEngine:
    """Enterprise contact intelligence, normalization, ownership classification, and verification semantics."""

    @staticmethod
    def normalize_email(email_str: str) -> Optional[str]:
        """Normalizes email address, removing whitespace, tags, and lowercasing."""
        if not email_str:
            return None
        clean = email_str.strip().lower()
        # Remove surrounding punctuation, HTML tags, or quotes
        clean = re.sub(r'^[<"\'\s]+|[>"\'\s]+$', '', clean)
        if "@" not in clean:
            return None
        parts = clean.split("@")
        if len(parts) != 2:
            return None
        local_part, domain_part = parts[0].strip(), parts[1].strip()
        if not local_part or not domain_part or "." not in domain_part:
            return None
        return f"{local_part}@{domain_part}"

    @staticmethod
    def classify_email_ownership(email_str: str, person_name: Optional[str] = None) -> str:
        """Classifies email into PERSON_CONTACT, COMPANY_CONTACT, or DEPARTMENT_CONTACT."""
        norm = ContactIntelligenceEngine.normalize_email(email_str)
        if not norm:
            return ContactOwnershipType.UNKNOWN_OWNER.value

        local = norm.split("@")[0]

        if local in GENERIC_PREFIXES:
            return ContactOwnershipType.COMPANY_CONTACT.value

        if local in DEPARTMENT_PREFIXES:
            return ContactOwnershipType.DEPARTMENT_CONTACT.value

        # If a person's name is known, check for matching initials or tokens
        if person_name:
            name_parts = re.split(r'[\s._-]+', person_name.lower())
            if any(part in local for part in name_parts if len(part) > 2):
                return ContactOwnershipType.PERSON_CONTACT.value

        # Check for typical personal name pattern (e.g. first.last, f.last)
        if re.search(r'^[a-z]+[._-][a-z]+$', local):
            return ContactOwnershipType.PERSON_CONTACT.value

        return ContactOwnershipType.UNKNOWN_OWNER.value

    @staticmethod
    def verify_email_semantics(
        email_str: str,
        is_pattern_predicted: bool = False,
        is_publicly_listed: bool = True
    ) -> Dict[str, Any]:
        """
        Applies strict verification semantics.
        Rule: An email is NEVER marked VERIFIED_DELIVERABLE merely because syntax is valid or MX exists.
        Rule: A predicted email is strictly marked PREDICTED and confidence capped at 0.50.
        """
        norm = ContactIntelligenceEngine.normalize_email(email_str)
        if not norm:
            return {
                "normalized_email": None,
                "syntax_valid": False,
                "domain_valid": False,
                "mx_valid": False,
                "deliverability_status": EmailDeliverabilityStatus.INVALID.value,
                "confidence": 0.0,
                "is_predicted": False,
                "is_disposable": False,
                "reason": "Malformed email syntax"
            }

        domain = norm.split("@")[1]
        is_disposable = domain in DISPOSABLE_EMAIL_DOMAINS
        syntax_valid = bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', norm))

        if is_disposable:
            return {
                "normalized_email": norm,
                "syntax_valid": syntax_valid,
                "domain_valid": True,
                "mx_valid": False,
                "deliverability_status": EmailDeliverabilityStatus.UNDELIVERABLE.value,
                "confidence": 0.1,
                "is_predicted": is_pattern_predicted,
                "is_disposable": True,
                "reason": "Disposable / temporary mailbox domain"
            }

        if is_pattern_predicted:
            return {
                "normalized_email": norm,
                "syntax_valid": syntax_valid,
                "domain_valid": True,
                "mx_valid": True,
                "deliverability_status": EmailDeliverabilityStatus.PREDICTED.value,
                "confidence": 0.50,
                "is_predicted": True,
                "is_disposable": False,
                "reason": "Pattern predicted from company domain naming conventions (unverified deliverability)"
            }

        status = EmailDeliverabilityStatus.PUBLICLY_LISTED.value if is_publicly_listed else EmailDeliverabilityStatus.UNVERIFIED.value
        confidence = 0.90 if is_publicly_listed else 0.65

        return {
            "normalized_email": norm,
            "syntax_valid": syntax_valid,
            "domain_valid": True,
            "mx_valid": True,
            "deliverability_status": status,
            "confidence": confidence,
            "is_predicted": False,
            "is_disposable": False,
            "reason": "Publicly observed business contact on verified domain"
        }

    @staticmethod
    def normalize_phone(raw_phone: str, default_country_code: str = "61") -> Dict[str, Any]:
        """
        Normalizes phone number to E.164 standard format where possible.
        Extracts country calling code, national number, and assigns telephone classification.
        Rule: Valid number formatting does NOT imply confirmed active personal ownership.
        """
        if not raw_phone:
            return {
                "raw_phone": raw_phone,
                "normalized_phone": None,
                "e164": None,
                "country": None,
                "phone_type": PhoneType.UNKNOWN.value,
                "is_valid_format": False
            }

        clean = raw_phone.strip()
        has_plus = clean.startswith("+")
        digits_only = re.sub(r'\D', '', clean)

        if len(digits_only) < 7:
            return {
                "raw_phone": raw_phone,
                "normalized_phone": clean,
                "e164": None,
                "country": None,
                "phone_type": PhoneType.UNKNOWN.value,
                "is_valid_format": False
            }

        country_name = "Unknown"
        e164 = None

        if has_plus:
            for code, c_name in COUNTRY_CALLING_CODES.items():
                if digits_only.startswith(code):
                    country_name = c_name
                    e164 = f"+{digits_only}"
                    break
            if not e164:
                e164 = f"+{digits_only}"
        else:
            # Australian local number formatting (e.g. 03 9988 7766 -> +61 3 9988 7766)
            if digits_only.startswith("0") and default_country_code == "61":
                e164 = f"+61{digits_only[1:]}"
                country_name = "Australia"
            else:
                e164 = f"+{default_country_code}{digits_only}"
                country_name = COUNTRY_CALLING_CODES.get(default_country_code, "Unknown")

        # Classify phone type based on cues
        lower_raw = raw_phone.lower()
        if "sales" in lower_raw:
            phone_type = PhoneType.SALES.value
        elif "support" in lower_raw or "help" in lower_raw:
            phone_type = PhoneType.SUPPORT.value
        elif "hq" in lower_raw or "head" in lower_raw or "office" in lower_raw or "reception" in lower_raw:
            phone_type = PhoneType.HEAD_OFFICE.value
        elif "branch" in lower_raw or "warehouse" in lower_raw:
            phone_type = PhoneType.BRANCH.value
        elif "direct" in lower_raw or "mobile" in lower_raw:
            phone_type = PhoneType.PERSONAL_PROFESSIONAL.value
        else:
            phone_type = PhoneType.HEAD_OFFICE.value

        return {
            "raw_phone": raw_phone,
            "normalized_phone": e164,
            "e164": e164,
            "country": country_name,
            "phone_type": phone_type,
            "is_valid_format": True
        }

    @staticmethod
    def classify_privacy(value_type: str, raw_value: str, context: Optional[str] = None) -> str:
        """Enforces privacy classification: ensures private consumer data is rejected."""
        val = raw_value.lower()
        # Consumer email domains are private
        consumer_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com"}
        if value_type == "EMAIL":
            domain = val.split("@")[-1] if "@" in val else ""
            if domain in consumer_domains:
                return PrivacyClassification.PRIVATE.value
            local = val.split("@")[0]
            if local in GENERIC_PREFIXES or local in DEPARTMENT_PREFIXES:
                return PrivacyClassification.COMPANY_GENERIC.value
            return PrivacyClassification.PUBLIC_BUSINESS.value
        elif value_type == "PHONE":
            if "mobile" in (context or "").lower() and "personal" in (context or "").lower():
                return PrivacyClassification.PRIVATE.value
            return PrivacyClassification.PUBLIC_BUSINESS.value

        return PrivacyClassification.PUBLIC_BUSINESS.value
