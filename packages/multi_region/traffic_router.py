"""
LeadNexus AI X — Global Traffic Management & Data Residency Router
Phase 35 (ChatGPT Master Roadmap): Read/Write Splitting & Strict Sovereignty Enforcement
"""

import logging
from typing import Dict, Any, Tuple, Optional
from packages.multi_region.split_brain_guard import SplitBrainGuard

logger = logging.getLogger("leadnexus.multi_region.traffic_router")


class DataSovereigntyViolationError(Exception):
    """Raised when tenant data residency policy is violated."""
    pass


class GlobalTrafficRouter:
    """
    Routes global requests based on HTTP method, tenant residency policies,
    and regional health metrics.
    """

    AUSTRALIA_REGIONS = {"ap-southeast-2", "ap-southeast-4"}

    def __init__(self, split_brain_guard: SplitBrainGuard):
        self.split_brain_guard = split_brain_guard

    def resolve_target_region(
        self,
        method: str,
        tenant_affinity: Dict[str, Any],
        client_country: Optional[str] = "AU",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Determines the destination regional endpoint and policy compliance.
        Returns: (target_region_id, routing_metadata)
        """
        method = method.upper()
        is_write = method in ["POST", "PUT", "DELETE", "PATCH"]
        residency = tenant_affinity.get("data_residency_requirement", "AU_ONLY")
        strict_sovereignty = tenant_affinity.get("strict_sovereignty_enforced", True)
        primary_region = tenant_affinity.get("primary_region_id", "ap-southeast-2")
        failover_region = tenant_affinity.get("failover_region_id", "ap-southeast-1")

        # 1. Enforce Data Sovereignty for AU_ONLY tenants
        if residency == "AU_ONLY" and strict_sovereignty:
            if primary_region not in self.AUSTRALIA_REGIONS:
                raise DataSovereigntyViolationError(
                    f"Data Residency Breach: Tenant policy strictly requires Australian storage (AU_ONLY). "
                    f"Configured primary region '{primary_region}' is outside Australia."
                )

        # 2. Write Routing: STRICTLY ONE AUTHORIZED WRITE REGION
        if is_write:
            authorized_primary = self.split_brain_guard.authorized_write_region
            
            # Check sovereignty compliance on write target
            if residency == "AU_ONLY" and strict_sovereignty and authorized_primary not in self.AUSTRALIA_REGIONS:
                raise DataSovereigntyViolationError(
                    f"Data Sovereignty Policy Conflict: Active write cluster '{authorized_primary}' violates "
                    f"tenant AU_ONLY residency constraint."
                )

            return authorized_primary, {
                "route_type": "PRIMARY_WRITE",
                "is_write": True,
                "fencing_token": self.split_brain_guard.current_fence_token,
                "sovereignty_checked": True,
            }

        # 3. Read Routing: Nearest healthy replica respecting residency
        if residency == "AU_ONLY" and strict_sovereignty:
            target_read = primary_region  # Stays inside AU
        else:
            # Latency optimized for non-AU
            target_read = failover_region if client_country not in ["AU", "NZ"] else primary_region

        return target_read, {
            "route_type": "READ_REPLICA",
            "is_write": False,
            "fencing_token": None,
            "sovereignty_checked": True,
        }
