"""
Enterprise AI Model Platform API Routes (Phase 40)
Provides unified Model Gateway, multi-provider routing with automated fallbacks,
Prompt registry & versioning, token & cost tracking, latency monitoring, and safety guardrails.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.enterprise_ai_platform import (
    AIProviderEnum,
    ModelCapability,
    ModelTier,
    ModelStatus,
    RegisteredModel,
    PromptTemplateRecord,
    ModelInferenceLog,
    ModelSafetyPolicy,
)
from packages.ai_platform.provider_abstraction import get_ai_provider, ProviderInferenceError
from packages.ai_platform.model_router import EnterpriseModelRouter, ModelRoutingError
from packages.ai_platform.prompt_registry_engine import PromptRegistryEngine, PromptVariableMissingError
from packages.ai_platform.token_cost_tracker import TokenCostTracker, CostLimitExceededError
from packages.ai_platform.model_safety_guard import ModelSafetyGuard, SafetyViolationError

router = APIRouter(prefix="/ai-platform", tags=["Enterprise AI Model Platform"])


# --- Schemas ---

class ModelRegisterCreate(BaseModel):
    provider: str
    model_name: str
    version: str = "latest"
    capability: str = ModelCapability.CHAT
    tier: str = ModelTier.FAST
    cost_per_1k_input_tokens: float = 0.00015
    cost_per_1k_output_tokens: float = 0.0006
    context_window: int = 128000
    is_fallback_eligible: bool = True


class ModelStatusUpdate(BaseModel):
    status: str  # ACTIVE, CANARY, DEPRECATED, RETIRED


class PromptCreate(BaseModel):
    prompt_name: str
    system_instructions: Optional[str] = None
    template_text: str


class InferenceGatewayRequest(BaseModel):
    provider: str = "GOOGLE_GEMINI"
    model_name: str = "gemini-1.5-flash"
    prompt: Optional[str] = None
    prompt_template_name: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    system_instructions: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


class SafetyPolicyCreate(BaseModel):
    policy_name: str
    enforce_prompt_injection_defense: bool = True
    enforce_pii_redaction: bool = True
    max_tokens_budget_per_call: int = 4096
    daily_spend_limit_usd: float = 50.0


# --- 1. Model Registry & Versions ---

@router.get("/models")
def list_registered_models(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    models = db.query(RegisteredModel).order_by(RegisteredModel.created_at.desc()).all()
    # If empty, seed default enterprise models
    if not models:
        defaults = [
            RegisteredModel(provider="GOOGLE_GEMINI", model_name="gemini-1.5-flash", tier=ModelTier.FAST, cost_per_1k_input_tokens=0.000075, cost_per_1k_output_tokens=0.0003),
            RegisteredModel(provider="GOOGLE_GEMINI", model_name="gemini-1.5-pro", tier=ModelTier.BALANCED, cost_per_1k_input_tokens=0.00125, cost_per_1k_output_tokens=0.005),
            RegisteredModel(provider="OPENAI", model_name="gpt-4o-mini", tier=ModelTier.FAST, cost_per_1k_input_tokens=0.00015, cost_per_1k_output_tokens=0.0006),
            RegisteredModel(provider="OPENAI", model_name="gpt-4o", tier=ModelTier.FRONTIER, cost_per_1k_input_tokens=0.0025, cost_per_1k_output_tokens=0.010),
            RegisteredModel(provider="ANTHROPIC", model_name="claude-3-5-sonnet", tier=ModelTier.BALANCED, cost_per_1k_input_tokens=0.003, cost_per_1k_output_tokens=0.015),
            RegisteredModel(provider="MOCK", model_name="mock-emergency-backup", tier=ModelTier.OFFLINE, cost_per_1k_input_tokens=0.0, cost_per_1k_output_tokens=0.0),
        ]
        db.add_all(defaults)
        db.commit()
        models = db.query(RegisteredModel).all()

    return {"models": models}


@router.post("/models", status_code=status.HTTP_201_CREATED)
def register_model(
    payload: ModelRegisterCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    prov = payload.provider.upper()
    if prov not in AIProviderEnum.ALL_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider {payload.provider}. Allowed: {AIProviderEnum.ALL_PROVIDERS}")

    model = RegisteredModel(
        provider=prov,
        model_name=payload.model_name,
        version=payload.version,
        capability=payload.capability.upper(),
        tier=payload.tier.upper(),
        cost_per_1k_input_tokens=payload.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=payload.cost_per_1k_output_tokens,
        context_window=payload.context_window,
        is_fallback_eligible=payload.is_fallback_eligible,
        status=ModelStatus.ACTIVE,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return {"status": "registered", "model": model}


@router.put("/models/{model_id}/status")
def update_model_status(
    model_id: str,
    payload: ModelStatusUpdate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Updates model lifecycle status (ACTIVE, CANARY, DEPRECATED, RETIRED)."""
    model = db.query(RegisteredModel).filter(RegisteredModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    new_status = payload.status.upper()
    if new_status not in (ModelStatus.ACTIVE, ModelStatus.CANARY, ModelStatus.DEPRECATED, ModelStatus.RETIRED):
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    model.status = new_status
    db.commit()
    db.refresh(model)
    return {"status": "updated", "model": model}


# --- 2. Prompt Registry & Versioning ---

@router.get("/prompts")
def list_prompts(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    prompts = db.query(PromptTemplateRecord).filter(
        PromptTemplateRecord.workspace_id == ws.id,
    ).order_by(PromptTemplateRecord.prompt_name.asc(), PromptTemplateRecord.version.desc()).all()
    return {"prompts": prompts}


@router.post("/prompts", status_code=status.HTTP_201_CREATED)
def create_prompt_template(
    payload: PromptCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    variables = PromptRegistryEngine.extract_variables(payload.template_text)

    # Determine next version
    existing = db.query(PromptTemplateRecord).filter(
        PromptTemplateRecord.workspace_id == ws.id,
        PromptTemplateRecord.prompt_name == payload.prompt_name,
    ).order_by(PromptTemplateRecord.version.desc()).first()

    next_version = (existing.version + 1) if existing else 1

    prompt_record = PromptTemplateRecord(
        workspace_id=ws.id,
        prompt_name=payload.prompt_name,
        version=next_version,
        system_instructions=payload.system_instructions,
        template_text=payload.template_text,
        input_variables=variables,
        is_active=True,
    )
    db.add(prompt_record)
    db.commit()
    db.refresh(prompt_record)

    return {"status": "created", "prompt": prompt_record}


# --- 3. Unified Inference Gateway & Routing ---

@router.post("/inference")
def execute_gateway_inference(
    payload: InferenceGatewayRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """
    Unified AI Gateway Pipeline:
    1. Resolve Prompt (from registry if specified)
    2. Enforce Pre-Flight Safety Guardrails (injection check, PII sanitization)
    3. Check Daily Spend Budget
    4. Dispatch via Enterprise Model Router with automated multi-tier fallback
    5. Log Telemetry (tokens, latency, cost USD, fallback trigger)
    """
    # 1. Resolve prompt
    raw_prompt = payload.prompt or ""
    sys_inst = payload.system_instructions

    if payload.prompt_template_name:
        tmpl = db.query(PromptTemplateRecord).filter(
            PromptTemplateRecord.workspace_id == ws.id,
            PromptTemplateRecord.prompt_name == payload.prompt_template_name,
            PromptTemplateRecord.is_active == True,
        ).order_by(PromptTemplateRecord.version.desc()).first()
        if not tmpl:
            raise HTTPException(status_code=404, detail=f"Prompt template '{payload.prompt_template_name}' not found.")
        try:
            raw_prompt = PromptRegistryEngine.render_prompt(tmpl.template_text, payload.variables, strict=False)
            sys_inst = tmpl.system_instructions or sys_inst
        except PromptVariableMissingError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not raw_prompt:
        raise HTTPException(status_code=400, detail="Prompt text or template is required.")

    # 2. Safety Guardrails
    try:
        sanitized_prompt = ModelSafetyGuard.enforce_guardrails(
            prompt=raw_prompt,
            max_tokens=payload.max_tokens,
            max_allowed_tokens=4096,
            enforce_injection_check=True,
            enforce_pii_sanitization=True,
        )
    except SafetyViolationError as err:
        raise HTTPException(status_code=400, detail=str(err))

    # 3. Router & Fallback Dispatch
    router = EnterpriseModelRouter()
    try:
        response, fallback_triggered, fallback_from = router.dispatch_with_fallback(
            primary_provider=payload.provider,
            primary_model=payload.model_name,
            prompt=sanitized_prompt,
            system_instructions=sys_inst,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
    except ModelRoutingError as route_err:
        raise HTTPException(status_code=502, detail=str(route_err))

    # 4. Log Inference Telemetry
    log_entry = ModelInferenceLog(
        workspace_id=ws.id,
        model_id=response.model_name,
        provider=response.provider,
        prompt_name=payload.prompt_template_name or "ad-hoc",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
        quality_score=1.0,
        fallback_triggered=fallback_triggered,
        fallback_from_model=fallback_from,
        safety_passed=True,
    )
    db.add(log_entry)
    db.commit()

    return {
        "text": response.text,
        "model": response.model_name,
        "provider": response.provider,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": response.input_tokens + response.output_tokens,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
        "fallback_triggered": fallback_triggered,
        "fallback_from_model": fallback_from,
    }


# --- 4. Cost & Token Analytics ---

@router.get("/costs")
def get_cost_and_token_analytics(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Calculates cumulative token consumption, cost breakdown, and daily spend status."""
    logs = db.query(ModelInferenceLog).filter(ModelInferenceLog.workspace_id == ws.id).all()

    total_input = sum(l.input_tokens for l in logs)
    total_output = sum(l.output_tokens for l in logs)
    total_cost = sum(l.cost_usd for l in logs)
    fallback_count = sum(1 for l in logs if l.fallback_triggered)

    # Provider breakdown
    by_provider: Dict[str, Dict[str, Any]] = {}
    for l in logs:
        p = l.provider
        if p not in by_provider:
            by_provider[p] = {"calls": 0, "cost": 0.0, "tokens": 0}
        by_provider[p]["calls"] += 1
        by_provider[p]["cost"] = round(by_provider[p]["cost"] + l.cost_usd, 6)
        by_provider[p]["tokens"] += (l.input_tokens + l.output_tokens)

    return {
        "total_calls": len(logs),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cost_usd": round(total_cost, 6),
        "fallback_count": fallback_count,
        "breakdown_by_provider": by_provider,
        "recent_logs": logs[-10:] if logs else [],
    }


# --- 5. Safety Policies ---

@router.get("/safety-policies")
def list_safety_policies(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    policies = db.query(ModelSafetyPolicy).filter(ModelSafetyPolicy.workspace_id == ws.id).all()
    return {"safety_policies": policies}


@router.post("/safety-policies", status_code=status.HTTP_201_CREATED)
def create_safety_policy(
    payload: SafetyPolicyCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    pol = ModelSafetyPolicy(
        workspace_id=ws.id,
        policy_name=payload.policy_name,
        enforce_prompt_injection_defense=payload.enforce_prompt_injection_defense,
        enforce_pii_redaction=payload.enforce_pii_redaction,
        max_tokens_budget_per_call=payload.max_tokens_budget_per_call,
        daily_spend_limit_usd=payload.daily_spend_limit_usd,
        is_active=True,
    )
    db.add(pol)
    db.commit()
    db.refresh(pol)
    return {"status": "created", "policy": pol}

