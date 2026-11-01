"""
LeadNexus AI X — Phase 37: Multi-Tier Token Bucket Rate Limiter
Enforces burst capacity, sustained per-second rates, and daily tenant quotas.
Calculates RFC 6585 X-RateLimit headers.
"""

import time
from typing import Dict, Tuple, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.api_gateway import TenantAPIQuota, QuotaTier


class RateLimitExceededError(Exception):
    """Raised when tenant exceeds sustained rate, burst capacity, or daily quota."""
    def __init__(self, message: str, retry_after: int, remaining: int, limit: int):
        super().__init__(message)
        self.retry_after = retry_after
        self.remaining = remaining
        self.limit = limit


class TenantTokenBucketLimiter:
    """In-memory high-throughput token bucket with database quota synchronisation."""

    # In-memory bucket cache: tenant_id -> {"tokens": float, "last_updated": float}
    _buckets: Dict[str, Dict[str, float]] = {}

    @classmethod
    def check_and_consume(
        cls,
        db: Session,
        tenant_id: str,
        cost: float = 1.0
    ) -> Dict[str, Any]:
        """
        Consumes tokens from the tenant's bucket.
        Returns dict with rate-limit telemetry headers.
        Raises RateLimitExceededError on exhaustion.
        """
        quota = db.query(TenantAPIQuota).filter(TenantAPIQuota.tenant_id == tenant_id).first()
        if not quota:
            # Default to Professional tier if not explicitly provisioned
            quota = TenantAPIQuota(
                tenant_id=tenant_id,
                tier=QuotaTier.PROFESSIONAL,
                requests_per_second=50,
                burst_capacity=100,
                daily_quota=100000,
            )
            db.add(quota)
            db.commit()
            db.refresh(quota)

        # 1. Check daily quota
        now = datetime.now(timezone.utc)
        if quota.last_reset_at.date() < now.date():
            quota.used_today = 0
            quota.last_reset_at = now
            quota.is_throttled = False
            db.commit()

        if quota.used_today >= quota.daily_quota:
            quota.is_throttled = True
            db.commit()
            raise RateLimitExceededError(
                f"Daily API quota of {quota.daily_quota} requests exhausted for tenant '{tenant_id}'.",
                retry_after=86400 - (now.hour * 3600 + now.minute * 60 + now.second),
                remaining=0,
                limit=quota.daily_quota
            )

        # 2. Token-bucket rate limiting
        now_ts = time.time()
        bucket = cls._buckets.get(tenant_id)

        capacity = float(quota.burst_capacity)
        refill_rate = float(quota.requests_per_second)

        if not bucket:
            bucket = {"tokens": capacity, "last_updated": now_ts}
            cls._buckets[tenant_id] = bucket

        # Refill tokens based on elapsed time
        elapsed = now_ts - bucket["last_updated"]
        bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
        bucket["last_updated"] = now_ts

        if bucket["tokens"] < cost:
            # Bucket exhausted
            missing_tokens = cost - bucket["tokens"]
            retry_after = max(1, int(missing_tokens / refill_rate) + 1)
            raise RateLimitExceededError(
                f"Rate limit exceeded. Burst capacity or sustained throughput reached.",
                retry_after=retry_after,
                remaining=int(bucket["tokens"]),
                limit=int(capacity)
            )

        # Consume tokens
        bucket["tokens"] -= cost
        quota.used_today += int(cost)
        db.commit()

        return {
            "X-RateLimit-Limit": str(int(capacity)),
            "X-RateLimit-Remaining": str(int(bucket["tokens"])),
            "X-RateLimit-Reset": str(int(now_ts + 1)),
            "X-Daily-Quota-Remaining": str(quota.daily_quota - quota.used_today),
        }
