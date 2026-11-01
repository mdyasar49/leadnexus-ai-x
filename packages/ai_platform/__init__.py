"""
Enterprise AI Model Platform Package (Phase 40)
Multi-Provider Model Gateway, Registry, Routing, Fallback, Prompt Versioning & Safety Guardrails
"""

from packages.ai_platform.provider_abstraction import (
    BaseAIProvider,
    InferenceResponse,
    ProviderInferenceError,
    get_ai_provider,
    MockAIProvider,
)
from packages.ai_platform.model_router import EnterpriseModelRouter, ModelRoutingError
from packages.ai_platform.prompt_registry_engine import PromptRegistryEngine, PromptVariableMissingError
from packages.ai_platform.token_cost_tracker import TokenCostTracker, CostLimitExceededError
from packages.ai_platform.model_safety_guard import ModelSafetyGuard, SafetyViolationError

__all__ = [
    "BaseAIProvider",
    "InferenceResponse",
    "ProviderInferenceError",
    "get_ai_provider",
    "MockAIProvider",
    "EnterpriseModelRouter",
    "ModelRoutingError",
    "PromptRegistryEngine",
    "PromptVariableMissingError",
    "TokenCostTracker",
    "CostLimitExceededError",
    "ModelSafetyGuard",
    "SafetyViolationError",
]
