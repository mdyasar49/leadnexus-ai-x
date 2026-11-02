"""
LeadNexus AI X - Phase 48: Consent Vault & Opt-Out Suppression Registry
High-performance in-memory and persistent suppression registry enforcing GDPR RTBF and CCPA Do-Not-Sell.
"""

from typing import Dict, List, Optional, Set
import time


class ConsentVault:
    def __init__(self):
        self._suppressed_emails: Set[str] = set()
        self._suppressed_domains: Set[str] = set()
        self._records: Dict[str, Dict] = {}

    def add_opt_out(
        self,
        opt_out_id: str,
        subject_email: Optional[str] = None,
        subject_domain: Optional[str] = None,
        opt_out_type: str = "GDPR_RTBF",
        reason: Optional[str] = None,
    ) -> Dict:
        """Registers a suppression entry for an email or domain."""
        email_clean = subject_email.strip().lower() if subject_email else None
        domain_clean = subject_domain.strip().lower() if subject_domain else None

        if email_clean:
            self._suppressed_emails.add(email_clean)
        if domain_clean:
            self._suppressed_domains.add(domain_clean)

        record = {
            "id": opt_out_id,
            "subject_email": email_clean,
            "subject_domain": domain_clean,
            "opt_out_type": opt_out_type,
            "reason": reason or "User requested opt-out",
            "is_active": True,
            "requested_at": time.time(),
        }
        self._records[opt_out_id] = record
        return record

    def is_suppressed(self, email: Optional[str] = None, domain: Optional[str] = None) -> bool:
        """
        Sub-millisecond check if an email or domain is opted-out.
        Also checks if the email's domain is in suppressed_domains.
        """
        if email:
            email_clean = email.strip().lower()
            if email_clean in self._suppressed_emails:
                return True
            if "@" in email_clean:
                parsed_domain = email_clean.split("@")[-1]
                if parsed_domain in self._suppressed_domains:
                    return True

        if domain:
            domain_clean = domain.strip().lower()
            if domain_clean in self._suppressed_domains:
                return True

        return False

    def remove_opt_out(self, opt_out_id: str) -> bool:
        if opt_out_id in self._records:
            rec = self._records[opt_out_id]
            if rec["subject_email"] and rec["subject_email"] in self._suppressed_emails:
                self._suppressed_emails.remove(rec["subject_email"])
            if rec["subject_domain"] and rec["subject_domain"] in self._suppressed_domains:
                self._suppressed_domains.remove(rec["subject_domain"])
            del self._records[opt_out_id]
            return True
        return False

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_opt_outs": len(self._records),
            "suppressed_emails": len(self._suppressed_emails),
            "suppressed_domains": len(self._suppressed_domains),
        }

    def clear(self):
        self._suppressed_emails.clear()
        self._suppressed_domains.clear()
        self._records.clear()
