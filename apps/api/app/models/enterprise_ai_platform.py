"""
Enterprise AI Model Platform Models (Phase 40)
Supports multi-provider AI model gateway, registry, routing, fallback, prompt versioning,
token tracking, cost management, latency monitoring, and safety policies.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class AIProviderEnum:
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE_GEMINI = "GOOGLE_GEMINI"
    MISTRAL = "MISTRAL"
    LOCAL_OLLAMA = "LOCAL_OLLAMA"
    MOCK = "MOCK"

    ALL_PROVIDERS = [OPENAI, ANTHROPIC, GOOGLE_GEMINI, MISTRAL, LOCAL_OLLAMA, MOCK]


class ModelCapability:
    COMPLETION = "COMPLETION"
    CHAT = "CHAT"
    EMBEDDING = "EMBEDDING"
    EXTRACTION = "EXTRACTION"
    RESEARCH = "RESEARCH"
    REASONING = "REASONING"


class ModelTier:
    FAST = "FAST"              # High throughput, low latency (e.g. gpt-4o-mini, gemini-flash)
    BALANCED = "BALANCED"      # Mid-tier (e.g. claude-sonnet, gpt-4o)
    FRONTIER = "FRONTIER"      # Heavy reasoning (e.g. o1, claude-opus)
    OFFLINE = "OFFLINE"        # Local / on-premise (e.g. llama3-ollama)


class ModelStatus:
    ACTIVE = "ACTIVE"
    CANARY = "CANARY"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class RegisteredModel(Base):
    """Catalog of approved enterprise AI models across multiple vendors."""

    __tablename__ = "registered_ai_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(32), nullable=False, index=True)  # AIProviderEnum
    model_name = Column(String(64), nullable=False, index=True)  # e.g., "gemini-1.5-flash", "gpt-4o"
    version = Column(String(32), default="latest", nullable=False)
    capability = Column(String(32), default=ModelCapability.CHAT, nullable=False)
    tier = Column(String(16), default=ModelTier.FAST, nullable=False)
    cost_per_1k_input_tokens = Column(Float, default=0.00015, nullable=False)
    cost_per_1k_output_tokens = Column(Float, default=0.0006, nullable=False)
    context_window = Column(Integer, default=128000, nullable=False)
    status = Column(String(16), default=ModelStatus.ACTIVE, nullable=False)
    is_fallback_eligible = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PromptTemplateRecord(Base):
    """Versioned, reusable prompt templates with variable substitution."""

    __tablename__ = "prompt_template_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    prompt_name = Column(String(64), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    system_instructions = Column(Text, nullable=True)
    template_text = Column(Text, nullable=False)
    input_variables = Column(JSON, default=list, nullable=False)  # ["company_name", "industry"]
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ModelInferenceLog(Base):
    """Audit and telemetry record for each inference call executed through the gateway."""

    __tablename__ = "model_inference_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    model_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    prompt_name = Column(String(64), nullable=True)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=1.0, nullable=False)
    fallback_triggered = Column(Boolean, default=False, nullable=False)
    fallback_from_model = Column(String(64), nullable=True)
    safety_passed = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ModelSafetyPolicy(Base):
    """Input/Output guardrails, prompt injection blocks, and token budget policies."""

    __tablename__ = "model_safety_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    policy_name = Column(String(64), nullable=False)
    blocked_patterns = Column(JSON, default=list, nullable=False)  # regex or phrase filters
    enforce_prompt_injection_defense = Column(Boolean, default=True, nullable=False)
    enforce_pii_redaction = Column(Boolean, default=True, nullable=False)
    max_tokens_budget_per_call = Column(Integer, default=4096, nullable=False)
    daily_spend_limit_usd = Column(Float, default=50.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

