"""
LeadNexus AI X — Phase 37: Enterprise API Gateway Execution Pipeline
Orchestrates Trace Header Injection, Abuse Inspection, Rate Limiting,
Edge Caching, Circuit Breaker Protection, and Route Telemetry Logging.
"""

import time
import uuid
from typing import Dict, Any, Optional, Callable, List
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from packages.gateway.abuse_guard import EdgeAbuseGuard, EdgeAbuseDetectedError
from packages.gateway.token_bucket_limiter import TenantTokenBucketLimiter, RateLimitExceededError
from packages.gateway.edge_cache_manager import EdgeCacheManager
from packages.gateway.gateway_circuit_breaker import get_circuit_breaker, GatewayCircuitOpenError
from app.models.api_gateway import GatewayRouteMetric


class GatewayResponse:
    def __init__(
        self,
        status_code: int,
        data: Any,
        headers: Dict[str, str],
        latency_ms: float,
        cache_hit: bool,
        trace_id: str
    ):
        self.status_code = status_code
        self.data = data
        self.headers = headers
        self.latency_ms = latency_ms
        self.cache_hit = cache_hit
        self.trace_id = trace_id


class EnterpriseGatewayPipeline:
    """Universal gateway pipeline wrapping API route handlers."""

    @classmethod
    def execute(
        cls,
        db: Session,
        tenant_id: str,
        method: str,
        route_pattern: str,
        handler: Callable[[], Any],
        client_ip: Optional[str] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cache_ttl: int = 60,
        cache_tags: Optional[List[str]] = None,
        fallback_fn: Optional[Callable[[], Any]] = None,
    ) -> GatewayResponse:
        """Executes request through full gateway pipeline."""
        start_time = time.time()
        trace_id = f"trace_{uuid.uuid4().hex}"
        req_headers = headers or {}

        # 1. Edge Abuse Inspection
        if query_params:
            EdgeAbuseGuard.inspect_dict(query_params, context="query")
        if body:
            EdgeAbuseGuard.inspect_dict(body, context="body")

        # 2. Token-Bucket Rate Limiting
        rate_headers = TenantTokenBucketLimiter.check_and_consume(db, tenant_id=tenant_id)

        # 3. Edge Cache Evaluation (for idempotent GET requests)
        cache_key = f"{tenant_id}:{method}:{route_pattern}"
        if query_params:
            cache_key += f":{sorted(query_params.items())}"

        if_none_match = req_headers.get("if-none-match") or req_headers.get("If-None-Match")

        if method == "GET":
            cached_data, is_not_modified, etag = EdgeCacheManager.get(cache_key, if_none_match=if_none_match)
            if is_not_modified:
                latency_ms = (time.time() - start_time) * 1000
                res_headers = {
                    **rate_headers,
                    "ETag": etag,
                    "X-Trace-ID": trace_id,
                    "X-Cache": "HIT_NOT_MODIFIED",
                    "X-Latency-MS": f"{latency_ms:.2f}",
                }
                return GatewayResponse(status_code=304, data=None, headers=res_headers, latency_ms=latency_ms, cache_hit=True, trace_id=trace_id)

            if cached_data is not None:
                latency_ms = (time.time() - start_time) * 1000
                res_headers = {
                    **rate_headers,
                    "ETag": etag,
                    "X-Trace-ID": trace_id,
                    "X-Cache": "HIT",
                    "X-Latency-MS": f"{latency_ms:.2f}",
                }
                return GatewayResponse(status_code=200, data=cached_data, headers=res_headers, latency_ms=latency_ms, cache_hit=True, trace_id=trace_id)

        # 4. Circuit Breaker Protected Upstream Execution
        breaker = get_circuit_breaker(service_name=route_pattern)
        data = breaker.execute(upstream_fn=handler, fallback_fn=fallback_fn)

        # 5. Store Cache on GET
        etag_val = None
        if method == "GET" and data is not None:
            etag_val = EdgeCacheManager.set(
                cache_key=cache_key,
                data=data,
                ttl_seconds=cache_ttl,
                tags=cache_tags or [f"tenant:{tenant_id}"]
            )

        latency_ms = (time.time() - start_time) * 1000

        # 6. Log Route Metric
        metric = GatewayRouteMetric(
            tenant_id=tenant_id,
            method=method,
            route_pattern=route_pattern,
            status_code=200,
            latency_ms=latency_ms,
            cache_hit=False,
            client_ip=client_ip,
            trace_id=trace_id,
        )
        db.add(metric)
        db.commit()

        # 7. Package Response
        res_headers = {
            **rate_headers,
            "X-Trace-ID": trace_id,
            "X-Cache": "MISS",
            "X-Latency-MS": f"{latency_ms:.2f}",
        }
        if etag_val:
            res_headers["ETag"] = etag_val

        return GatewayResponse(
            status_code=200,
            data=data,
            headers=res_headers,
            latency_ms=latency_ms,
            cache_hit=False,
            trace_id=trace_id
        )
