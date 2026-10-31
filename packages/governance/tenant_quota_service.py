"""
LeadNexus AI X - Phase 29: Enterprise Governance & Resource Limits
Tenant Quota Service: Resource consumption bounds, daily research budgets, and concurrency enforcement.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.governance import TenantQuota


class TenantQuotaService:
    """Monitors and enforces workspace-level operational resource boundaries."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def get_or_create_quota(self, workspace_id: str) -> TenantQuota:
        quota = self.db.query(TenantQuota).filter(TenantQuota.workspace_id == workspace_id).first()
        if not quota:
            quota = TenantQuota(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                max_daily_research_budget_usd=100.0,
                max_concurrent_runs=5,
                max_monthly_exports=10000,
                current_daily_spend_usd=0.0,
                is_enforced=True,
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(quota)
            self.db.commit()
            self.db.refresh(quota)
        return quota

    def check_research_budget(
        self,
        workspace_id: str,
        estimated_cost_usd: float,
    ) -> Tuple[bool, Optional[str]]:
        quota = self.get_or_create_quota(workspace_id)
        if not quota.is_enforced:
            return True, None

        projected = quota.current_daily_spend_usd + estimated_cost_usd
        if projected > quota.max_daily_research_budget_usd:
            return False, f"Daily research budget exceeded: projected ${projected:.2f} > limit ${quota.max_daily_research_budget_usd:.2f}"

        return True, None

    def record_spend(self, workspace_id: str, amount_usd: float) -> TenantQuota:
        quota = self.get_or_create_quota(workspace_id)
        quota.current_daily_spend_usd = round(quota.current_daily_spend_usd + amount_usd, 4)
        quota.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(quota)
        return quota

    def check_concurrent_runs(
        self,
        workspace_id: str,
        active_runs_count: int,
    ) -> Tuple[bool, Optional[str]]:
        quota = self.get_or_create_quota(workspace_id)
        if not quota.is_enforced:
            return True, None

        if active_runs_count >= quota.max_concurrent_runs:
            return False, f"Concurrent runs limit reached ({active_runs_count}/{quota.max_concurrent_runs})"

        return True, None
