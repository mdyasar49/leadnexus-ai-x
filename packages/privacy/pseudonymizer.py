"""
LeadNexus AI X - Phase 48: Cryptographic Pseudonymizer
Applies HMAC-SHA256 salted tokenization to transform direct identifiers into pseudonyms.
"""

import hashlib
import hmac
from typing import List, Tuple


class Pseudonymizer:
    def __init__(self, secret_key: str = "leadnexus_enterprise_master_privacy_key_2026"):
        self.secret_key = secret_key.encode("utf-8")

    def pseudonymize(self, value: str, salt: str = "leadnexus_salt") -> str:
        """Deterministically generates a secure pseudonym token for an identifier."""
        if not value:
            return ""
        norm_val = value.strip().lower()
        message = f"{salt}:{norm_val}".encode("utf-8")
        h = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return f"PSEUDO_{h[:16]}"

    def pseudonymize_batch(self, values: List[str], salt: str = "leadnexus_salt") -> Tuple[List[str], str]:
        """Pseudonymizes a list of values, returning tokens and key fingerprint."""
        tokens = [self.pseudonymize(v, salt=salt) for v in values]
        fingerprint = hashlib.sha256(self.secret_key).hexdigest()[:8]
        return tokens, fingerprint
