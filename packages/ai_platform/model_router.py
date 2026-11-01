"""
Enterprise Model Router (Phase 40)
Orchestrates primary model dispatch, canary testing, and multi-tier automated fallback.
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
from packages.ai_platform.provider_abstraction import (
    BaseAIProvider,
    InferenceResponse,
    ProviderInferenceError,
    get_ai_provider,
)

logger = logging.getLogger("leadnexus.ai_platform.router")


class ModelRoutingError(Exception):
    """Raised when all primary and fallback model candidates fail."""
    pass


class EnterpriseModelRouter:
    """Routes inference requests across multi-vendor models with automated fallback protection."""

    DEFAULT_CHAINS = {
        "gemini-1.5-flash": [
            {"provider": "OPENAI", "model_name": "gpt-4o-mini"},
            {"provider": "MOCK", "model_name": "mock-emergency-backup"},
        ],
        "gpt-4o": [
            {"provider": "GOOGLE_GEMINI", "model_name": "gemini-1.5-pro"},
            {"provider": "ANTHROPIC", "model_name": "claude-3-5-sonnet"},
            {"provider": "MOCK", "model_name": "mock-emergency-backup"},
        ],
        "default": [
            {"provider": "GOOGLE_GEMINI", "model_name": "gemini-1.5-flash"},
            {"provider": "OPENAI", "model_name": "gpt-4o-mini"},
            {"provider": "MOCK", "model_name": "mock-emergency-backup"},
        ],
    }

    def __init__(self, fallback_chains: Optional[Dict[str, List[Dict[str, str]]]] = None):
        self.fallback_chains = {**self.DEFAULT_CHAINS, **(fallback_chains or {})}

    def dispatch_with_fallback(
        self,
        primary_provider: str,
        primary_model: str,
        prompt: str,
        system_instructions: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        custom_provider_override: Optional[BaseAIProvider] = None,
    ) -> Tuple[InferenceResponse, bool, Optional[str]]:
        """
        Attempts execution on primary model. If ProviderInferenceError occurs,
        sequentially cascades through configured fallback chain until success.
        Returns: (InferenceResponse, fallback_triggered, fallback_from_model)
        """
        # 1. Attempt Primary
        try:
            provider = custom_provider_override or get_ai_provider(primary_provider, primary_model)
            response = provider.generate(
                prompt=prompt,
                system_instructions=system_instructions,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response, False, None
        except Exception as primary_err:
            logger.warning(
                f"[Model Router] Primary model '{primary_model}' ({primary_provider}) failed: {primary_err}. Initiating fallback cascade..."
            )

        # 2. Cascade Through Fallbacks
        fallback_candidates = self.fallback_chains.get(primary_model, self.fallback_chains["default"])
        fallback_errors = []

        for candidate in fallback_candidates:
            c_provider = candidate["provider"]
            c_model = candidate["model_name"]
            logger.info(f"[Model Router] Attempting fallback candidate: {c_model} ({c_provider})...")

            try:
                alt_provider = get_ai_provider(c_provider, c_model)
                response = alt_provider.generate(
                    prompt=prompt,
                    system_instructions=system_instructions,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response, True, primary_model
            except Exception as candidate_err:
                fallback_errors.append(f"{c_model}: {str(candidate_err)}")
                logger.warning(f"[Model Router] Fallback candidate '{c_model}' failed: {candidate_err}")

        # 3. All Failed
        error_summary = "; ".join(fallback_errors)
        raise ModelRoutingError(f"All model providers in fallback chain exhausted for '{primary_model}'. Details: {error_summary}")
