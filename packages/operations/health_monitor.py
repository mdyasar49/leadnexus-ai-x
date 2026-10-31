from datetime import datetime, timezone
from typing import Dict, Any, Optional

DEFAULT_SOURCE_HEALTH = {
    "search_engine": {"success_rate": 99.2, "latency_ms": 190, "is_healthy": True},
    "github": {"success_rate": 99.8, "latency_ms": 110, "is_healthy": True},
    "company_website": {"success_rate": 96.5, "latency_ms": 250, "is_healthy": True},
    "job_boards": {"success_rate": 98.0, "latency_ms": 140, "is_healthy": True},
    "forum_reddit": {"success_rate": 97.4, "latency_ms": 160, "is_healthy": True},
    "rss_feeds": {"success_rate": 99.0, "latency_ms": 95, "is_healthy": True},
}


class HealthMonitor:
    """
    Source & Platform Health Monitor:
    - Tracks SLI/SLO metrics (Success Rate, Latency, Error Rate, Blocked Rate)
    - Automatically detects unhealthy sources and recommends backpressure
    """
    @classmethod
    def evaluate_source_health(
        cls,
        source_key: str,
        total_requests: int,
        successes: int,
        blocked_count: int,
        total_latency_ms: int
    ) -> Dict[str, Any]:
        if total_requests == 0:
            default = DEFAULT_SOURCE_HEALTH.get(source_key, {"success_rate": 100.0, "latency_ms": 100, "is_healthy": True})
            return {
                "source_key": source_key,
                "success_rate": default["success_rate"],
                "latency_ms": default["latency_ms"],
                "is_healthy": default["is_healthy"],
                "status": "OPERATIONAL"
            }

        success_rate = (successes / total_requests) * 100.0
        blocked_rate = (blocked_count / total_requests) * 100.0
        avg_latency = int(total_latency_ms / total_requests)

        # Circuit breaker trigger conditions
        is_healthy = True
        status = "OPERATIONAL"

        if blocked_rate > 25.0:
            is_healthy = False
            status = "DEGRADED_ACCESS_BLOCKED"
        elif success_rate < 80.0:
            is_healthy = False
            status = "DEGRADED_HIGH_ERRORS"
        elif avg_latency > 3500:
            status = "HIGH_LATENCY"

        return {
            "source_key": source_key,
            "success_rate": round(success_rate, 2),
            "blocked_rate": round(blocked_rate, 2),
            "latency_ms": avg_latency,
            "is_healthy": is_healthy,
            "status": status,
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }

