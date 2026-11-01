"""
Model Safety & Guardrails (Phase 40)
Protects against prompt injection attacks, jailbreaks, PII leakage, and runaway token requests.
"""

from typing import Any, Dict, List, Optional, Tuple
import re


class SafetyViolationError(Exception):
    """Raised when an inference input or output breaches enterprise safety guardrails."""
    pass


class ModelSafetyGuard:
    """Pre-flight and post-flight guardrails for enterprise LLM execution."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts|rules)",
        r"system\s+(prompt\s+)?override",
        r"dan\s+mode",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"jailbreak",
        r"disregard\s+all\s+guidelines",
    ]

    PII_PATTERNS = [
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),
        (r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]"),
    ]

    @classmethod
    def check_prompt_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """Scans for adversarial prompt injection phrases."""
        text_lower = text.lower()
        for pat in cls.INJECTION_PATTERNS:
            if re.search(pat, text_lower):
                return True, pat
        return False, None

    @classmethod
    def sanitize_pii(cls, text: str) -> str:
        """Sanitizes PII (emails, phones) from text before passing to external LLMs."""
        sanitized = text
        for pat, repl in cls.PII_PATTERNS:
            sanitized = re.sub(pat, repl, sanitized)
        return sanitized

    @classmethod
    def enforce_guardrails(
        cls,
        prompt: str,
        max_tokens: int,
        max_allowed_tokens: int = 4096,
        enforce_injection_check: bool = True,
        enforce_pii_sanitization: bool = True,
    ) -> str:
        """
        Executes pre-flight safety policies.
        Returns sanitized prompt string or raises SafetyViolationError.
        """
        if max_tokens > max_allowed_tokens:
            raise SafetyViolationError(
                f"Requested token budget {max_tokens} exceeds safety maximum {max_allowed_tokens}."
            )

        if enforce_injection_check:
            is_injection, pattern = cls.check_prompt_injection(prompt)
            if is_injection:
                raise SafetyViolationError(
                    f"Prompt blocked by safety guard: potential prompt injection / jailbreak detected."
                )

        if enforce_pii_sanitization:
            return cls.sanitize_pii(prompt)

        return prompt
