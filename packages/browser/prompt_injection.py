import re
import logging

logger = logging.getLogger("leadnexus.browser.prompt_defense")

# Common prompt injection patterns found in web honeypots
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?prior\s+(?:instructions|prompts)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:\s*", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:dan|jailbroken|unrestricted)", re.IGNORECASE),
    re.compile(r"reveal\s+(?:all\s+)?(?:secrets|api\s*keys|passwords)", re.IGNORECASE),
    re.compile(r"send\s+(?:all\s+)?data\s+to\s+http", re.IGNORECASE),
]


def sanitize_untrusted_content(text: str) -> str:
    """
    Treats all external webpage content strictly as UNTRUSTED DATA.
    Neutralizes prompt injection directives and masks malicious instructions
    so downstream models/processors only evaluate the content as descriptive text.
    """
    if not text:
        return ""

    sanitized = text
    for pattern in INJECTION_PATTERNS:
        if pattern.search(sanitized):
            logger.warning("[Security] Prompt injection sequence detected and sanitized in untrusted web text.")
            sanitized = pattern.sub("[UNTRUSTED_INSTRUCTION_REMOVED]", sanitized)

    return sanitized

