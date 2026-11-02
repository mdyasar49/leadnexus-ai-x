"""
LeadNexus AI X - Phase 48: PII Scrubber Engine
Sanitizes sensitive, non-business PII from unstructured research text while preserving verified business contacts.
"""

import re
from typing import Dict, List, Set, Tuple


class PIIScrubber:
    # Common consumer/personal email domains (business emails should be preserved)
    CONSUMER_EMAIL_DOMAINS = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
        "aol.com", "protonmail.com", "mail.com", "zoho.com", "yandex.com"
    }

    # SSN Pattern
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    # Credit Card Pattern (13 to 19 digits, optional dashes/spaces)
    CC_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,4}\b")
    # Generic Email Pattern
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b")
    # US/International Passport pattern
    PASSPORT_PATTERN = re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b")

    def scrub(self, text: str, preserve_business_contacts: bool = True) -> Tuple[str, int, List[str]]:
        """
        Scrubs sensitive non-business PII from text.
        Returns (scrubbed_text, redaction_count, list_of_redacted_categories).
        """
        redactions = 0
        categories: Set[str] = set()
        scrubbed = text

        # 1. Scrub SSNs
        ssn_matches = self.SSN_PATTERN.findall(scrubbed)
        if ssn_matches:
            scrubbed = self.SSN_PATTERN.sub("[REDACTED_SSN]", scrubbed)
            redactions += len(ssn_matches)
            categories.add("SSN_NATIONAL_ID")

        # 2. Scrub Credit Cards (validate with Luhn)
        for match in self.CC_PATTERN.finditer(scrubbed):
            raw_digits = re.sub(r"[ -]", "", match.group(0))
            if len(raw_digits) >= 13 and self._luhn_check(raw_digits):
                scrubbed = scrubbed.replace(match.group(0), "[REDACTED_FINANCIAL_CARD]")
                redactions += 1
                categories.add("FINANCIAL_PAYMENT_CARD")

        # 3. Scrub Personal Consumer Emails (preserve corporate business emails)
        for email_match in self.EMAIL_PATTERN.finditer(scrubbed):
            email = email_match.group(0)
            domain = email_match.group(1).lower()
            if not preserve_business_contacts or domain in self.CONSUMER_EMAIL_DOMAINS:
                scrubbed = scrubbed.replace(email, "[REDACTED_PERSONAL_EMAIL]")
                redactions += 1
                categories.add("CONSUMER_PERSONAL_EMAIL")

        return scrubbed, redactions, sorted(list(categories))

    def _luhn_check(self, card_number: str) -> bool:
        """Validates credit card checksum using the Luhn algorithm."""
        digits = [int(d) for d in card_number if d.isdigit()]
        if len(digits) < 13:
            return False
        checksum = 0
        reverse_digits = digits[::-1]
        for idx, digit in enumerate(reverse_digits):
            if idx % 2 == 1:
                doubled = digit * 2
                checksum += (doubled - 9) if doubled > 9 else doubled
            else:
                checksum += digit
        return (checksum % 10) == 0
