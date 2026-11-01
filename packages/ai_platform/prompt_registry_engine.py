"""
Prompt Registry & Versioning Engine (Phase 40)
Handles semantic template management, input variable interpolation, and immutable version hashing.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import re
import hashlib


class PromptVariableMissingError(Exception):
    """Raised when mandatory input variables for a prompt template are omitted."""
    pass


class PromptRegistryEngine:
    """Manages prompt template compilation, versioning, and variable substitution."""

    @classmethod
    def extract_variables(cls, template_text: str) -> List[str]:
        """Extracts variable names formatted as {variable_name}."""
        matches = re.findall(r"\{([a-zA-Z0-9_]+)\}", template_text)
        # Deduplicate preserving order
        seen = set()
        variables = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                variables.append(m)
        return variables

    @classmethod
    def render_prompt(
        cls,
        template_text: str,
        variables: Dict[str, Any],
        strict: bool = True,
    ) -> str:
        """Interpolates variables into template text. In strict mode, verifies all required vars are present."""
        required = cls.extract_variables(template_text)
        missing = [v for v in required if v not in variables or variables[v] is None]

        if strict and missing:
            raise PromptVariableMissingError(f"Missing required prompt variables: {missing}")

        rendered = template_text
        for k, v in variables.items():
            rendered = rendered.replace(f"{{{k}}}", str(v))

        return rendered

    @classmethod
    def compute_fingerprint(cls, template_text: str, system_instructions: Optional[str] = None) -> str:
        """Computes deterministic SHA-256 fingerprint for prompt text."""
        content = f"{system_instructions or ''}::{template_text}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
