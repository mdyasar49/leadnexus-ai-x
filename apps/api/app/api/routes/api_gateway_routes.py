"""
LeadNexus AI X — Phase 37: Enterprise API Gateway & Edge Intelligence Routes
Endpoints for Quota configuration, Edge Cache invalidation, Circuit Breaker telemetry,
Abuse inspection, and Gateway latency metrics.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.api_gateway import (
    TenantAPIQuota,
    QuotaTier,
    GatewayRouteMetric,
    GatewayCircuitStatus,
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.gateway import (
    EdgeCacheManager,
    get_circuit_breaker,
    EdgeAbuseGuard,
    EdgeAbuseDetectedError,
    EnterpriseGatewayPipeline,
    RateLimitExceededError,
)

router = APIRouter(prefix="/gateway", tags=["Enterprise API Gateway & Edge Intelligence"])


# --- Schemas ---

class UpdateQuotaRequest(BaseModel):
    tier: QuotaTier = QuotaTier.ENTERPRISE
    requests_per_second: int = Field(100, ge=1, le=10000)
    burst_capacity: int = Field(200, ge=1, le=50000)
    daily_quota: int = Field(500000, ge=100, le=10000000)


class InvalidateCacheRequest(BaseModel):
    tags: List[str] = Field(..., example=["tenant:t1", "company:c123"])


class AbuseTestRequest(BaseModel):
    payload: Dict[str, Any]


class ProxySandboxRequest(BaseModel):
    route_pattern: str = "/api/v1/leads"
    method: str = "GET"
    payload: Optional[Dict[str, Any]] = None
    if_none_match: Optional[str] = None


# --- Endpoints ---

@router.get("/quotas")
def get_tenant_quota(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Retrieves current rate limit allocations and daily usage for the tenant."""
    quota = db.query(TenantAPIQuota).filter(TenantAPIQuota.tenant_id == workspace.id).first()
    if not quota:
        quota = TenantAPIQuota(
            tenant_id=workspace.id,
            tier=QuotaTier.PROFESSIONAL,
            requests_per_second=50,
            burst_capacity=100,
            daily_quota=100000,
        )
        db.add(quota)
        db.commit()
        db.refresh(quota)

    return {
        "tenant_id": quota.tenant_id,
        "tier": quota.tier.value,
        "requests_per_second": quota.requests_per_second,
        "burst_capacity": quota.burst_capacity,
        "daily_quota": quota.daily_quota,
        "used_today": quota.used_today,
        "is_throttled": quota.is_throttled,
        "remaining_today": max(0, quota.daily_quota - quota.used_today),
    }


@router.put("/quotas")
def update_tenant_quota(
    req: UpdateQuotaRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Updates tenant rate limits, burst thresholds, and daily allocation."""
    quota = db.query(TenantAPIQuota).filter(TenantAPIQuota.tenant_id == workspace.id).first()
    if not quota:
        quota = TenantAPIQuota(tenant_id=workspace.id)
        db.add(quota)

    quota.tier = req.tier
    quota.requests_per_second = req.requests_per_second
    quota.burst_capacity = req.burst_capacity
    quota.daily_quota = req.daily_quota
    db.commit()
    db.refresh(quota)

    return {
        "message": "Quota updated successfully",
        "tier": quota.tier.value,
        "requests_per_second": quota.requests_per_second,
        "burst_capacity": quota.burst_capacity,
        "daily_quota": quota.daily_quota,
    }


@router.post("/cache/invalidate")
def invalidate_edge_cache(
    req: InvalidateCacheRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Invalidates edge cache entries matching specified tags."""
    count = EdgeCacheManager.invalidate_tags(req.tags)
    return {"invalidated_count": count, "tags": req.tags}


@router.get("/circuits")
def list_circuit_breakers(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Inspects upstream circuit breaker states."""
    from packages.gateway.gateway_circuit_breaker import _registry
    return [
        {
            "service_name": name,
            "status": cb.state.value,
            "failure_count": cb.failure_count,
            "consecutive_successes": cb.consecutive_successes,
            "tripped_at": cb.tripped_at,
        }
        for name, cb in _registry.items()
    ]


@router.post("/circuits/{service_name}/reset")
def reset_circuit_breaker(
    service_name: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Manually resets a tripped circuit breaker back to CLOSED healthy state."""
    breaker = get_circuit_breaker(service_name)
    breaker.state = GatewayCircuitStatus.CLOSED
    breaker.failure_count = 0
    breaker.tripped_at = None
    return {"message": f"Circuit breaker for '{service_name}' reset to CLOSED", "status": "CLOSED"}


@router.post("/inspect-abuse")
def test_edge_abuse_filter(
    req: AbuseTestRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Simulates edge inspection against SQLi, XSS, and LLM prompt injection."""
    try:
        EdgeAbuseGuard.inspect_dict(req.payload)
        return {"status": "PASSED", "message": "No attack signatures detected"}
    except EdgeAbuseDetectedError as err:
        return {
            "status": "BLOCKED",
            "threat_category": err.threat_category,
            "detail": err.detail,
        }


@router.get("/metrics")
def get_gateway_metrics(
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Calculates p50, p95, p99 latency and cache hit ratios for the tenant."""
    metrics = (
        db.query(GatewayRouteMetric)
        .filter(GatewayRouteMetric.tenant_id == workspace.id)
        .order_by(GatewayRouteMetric.timestamp.desc())
        .limit(200)
        .all()
    )

    if not metrics:
        return {
            "total_requests": 0,
            "cache_hit_ratio": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
        }

    latencies = sorted([m.latency_ms for m in metrics])
    cache_hits = sum(1 for m in metrics if m.cache_hit)
    count = len(latencies)

    p50 = latencies[int(count * 0.50)]
    p95 = latencies[int(count * 0.95)]
    p99 = latencies[int(count * 0.99)]

    return {
        "total_requests": count,
        "cache_hits": cache_hits,
        "cache_hit_ratio": round(cache_hits / count, 3),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "p99_latency_ms": round(p99, 2),
    }


@router.post("/proxy-sandbox")
def run_gateway_proxy_sandbox(
    req: ProxySandboxRequest,
    response: Response,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    """Runs a simulated request through the full gateway execution pipeline."""
    try:
        def sample_upstream():
            return {
                "message": f"Processed {req.method} {req.route_pattern}",
                "tenant_id": workspace.id,
                "data": req.payload or {"mock": True},
            }

        res = EnterpriseGatewayPipeline.execute(
            db=db,
            tenant_id=workspace.id,
            method=req.method,
            route_pattern=req.route_pattern,
            handler=sample_upstream,
            body=req.payload,
            headers={"if-none-match": req.if_none_match} if req.if_none_match else {},
        )

        # Set response headers
        for k, v in res.headers.items():
            response.headers[k] = v
        response.status_code = res.status_code

        return {
            "status_code": res.status_code,
            "data": res.data,
            "latency_ms": res.latency_ms,
            "cache_hit": res.cache_hit,
            "trace_id": res.trace_id,
            "headers": res.headers,
        }
    except EdgeAbuseDetectedError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except RateLimitExceededError as err:
        raise HTTPException(status_code=429, detail=str(err))
