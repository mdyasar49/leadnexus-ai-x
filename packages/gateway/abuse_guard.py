"""
LeadNexus AI X — Phase 37: Edge Abuse & Attack Vector Defense Guard
Inspects inbound HTTP headers, query strings, and payloads at the gateway edge.
Blocks SQL injection, XSS, Path Traversal, and LLM Prompt Injection attacks.
"""

import re
from typing import Dict, Any, List, Optional


class EdgeAbuseDetectedError(Exception):
    """Raised when an inbound request violates gateway security rules."""
    def __init__(self, threat_category: str, detail: str):
        super().__init__(f"Edge Security Block: [{threat_category}] {detail}")
        self.threat_category = threat_category
        self.detail = detail


class EdgeAbuseGuard:
    """Pre-flight security inspection running before application controllers."""

    SQLI_PATTERNS = [
        re.compile(r"(\bUNION\b.*\bSELECT\b)", re.IGNORECASE),
        re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
        re.compile(r"(\bOR\b\s+['\"0-9]=\s*['\"0-9])", re.IGNORECASE),
        re.compile(r"(\bDROP\b\s+\bTABLE\b)", re.IGNORECASE),
    ]

    XSS_PATTERNS = [
        re.compile(r"(<script[^>]*>.*?</script>)", re.IGNORECASE | re.DOTALL),
        re.compile(r"(javascript\s*:)", re.IGNORECASE),
        re.compile(r"(onload\s*=|onerror\s*=)", re.IGNORECASE),
    ]

    TRAVERSAL_PATTERNS = [
        re.compile(r"(\.\./|\.\.\\)", re.IGNORECASE),
    ]

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"(ignore\s+(all\s+)?previous\s+instructions)", re.IGNORECASE),
        re.compile(r"(system\s+prompt\s*:)", re.IGNORECASE),
        re.compile(r"(you\s+are\s+now\s+an\s+unrestricted\s+ai)", re.IGNORECASE),
    ]

    @classmethod
    def inspect(cls, target_text: str, context: str = "request") -> None:
        """Inspects arbitrary string for attack signatures."""
        if not target_text:
            return

        # 1. SQL Injection
        for p in cls.SQLI_PATTERNS:
            if p.search(target_text):
                raise EdgeAbuseDetectedError("SQL_INJECTION", f"Potential SQL injection detected in {context}")

        # 2. XSS
        for p in cls.XSS_PATTERNS:
            if p.search(target_text):
                raise EdgeAbuseDetectedError("XSS_ATTACK", f"Cross-site scripting signature detected in {context}")

        # 3. Path Traversal
        for p in cls.TRAVERSAL_PATTERNS:
            if p.search(target_text):
                raise EdgeAbuseDetectedError("PATH_TRAVERSAL", f"Directory traversal pattern detected in {context}")

        # 4. Prompt Injection
        for p in cls.PROMPT_INJECTION_PATTERNS:
            if p.search(target_text):
                raise EdgeAbuseDetectedError("PROMPT_INJECTION", f"LLM prompt injection sequence blocked in {context}")

    @classmethod
    def inspect_dict(cls, data: Dict[str, Any], context: str = "body") -> None:
        """Recursively inspects dictionary values."""
        for k, v in data.items():
            if isinstance(v, str):
                cls.inspect(v, context=f"{context}.{k}")
            elif isinstance(v, dict):
                cls.inspect_dict(v, context=f"{context}.{k}")
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        cls.inspect(item, context=f"{context}.{k}[{i}]")
                    elif isinstance(item, dict):
                        cls.inspect_dict(item, context=f"{context}.{k}[{i}]")
