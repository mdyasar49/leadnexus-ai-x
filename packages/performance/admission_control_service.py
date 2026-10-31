"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering
Admission Control Service: Priority tiers, concurrency bounding, and load shedding.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.models.performance import AdmissionControlPolicy, PriorityTier


class AdmissionControlService:
    """Regulates incoming concurrency and sheds lower-priority load during peak latency."""

    DEFAULT_CAPACITIES = {
        PriorityTier.P0_CRITICAL.value: 200,
        PriorityTier.P1_HIGH.value: 100,
        PriorityTier.P2_BACKGROUND.value: 50,
    }

    def __init__(self, db_session: Any):
        self.db = db_session

    def get_or_create_policy(self, tier: PriorityTier) -> AdmissionControlPolicy:
        tier_val = tier.value if isinstance(tier, PriorityTier) else tier
        policy = self.db.query(AdmissionControlPolicy).filter(
            AdmissionControlPolicy.priority_tier == tier_val
        ).first()

        if not policy:
            policy = AdmissionControlPolicy(
                id=tier_val,
                priority_tier=tier_val,
                max_concurrency=self.DEFAULT_CAPACITIES.get(tier_val, 100),
                current_active=0,
                shedding_active=False,
                rejected_requests_count=0,
            )
            self.db.add(policy)
            self.db.commit()
            self.db.refresh(policy)
        return policy

    def request_admission(self, tier: PriorityTier) -> Tuple[bool, Optional[str]]:
        """
        Determines whether to admit a request based on active load and shedding state.
        Returns: (admitted, rejection_reason)
        """
        policy = self.get_or_create_policy(tier)
        tier_val = tier.value if isinstance(tier, PriorityTier) else tier

        # Load Shedding Policy
        if policy.shedding_active:
            if tier_val == PriorityTier.P2_BACKGROUND.value:
                policy.rejected_requests_count += 1
                self.db.commit()
                return False, "Request rejected by Admission Control: Load shedding active for P2_BACKGROUND"

            elif tier_val == PriorityTier.P1_HIGH.value:
                # Throttle P1 to half capacity during shedding
                effective_cap = policy.max_concurrency // 2
                if policy.current_active >= effective_cap:
                    policy.rejected_requests_count += 1
                    self.db.commit()
                    return False, "Request throttled: P1 capacity reduced by active load shedding"

        # Concurrency Limit Check
        if policy.current_active >= policy.max_concurrency:
            policy.rejected_requests_count += 1
            self.db.commit()
            return False, f"Concurrency limit reached for tier {tier_val} ({policy.current_active}/{policy.max_concurrency})"

        policy.current_active += 1
        self.db.commit()
        return True, None

    def release_admission(self, tier: PriorityTier) -> None:
        policy = self.get_or_create_policy(tier)
        policy.current_active = max(0, policy.current_active - 1)
        self.db.commit()

    def set_load_shedding(self, tier: PriorityTier, active: bool) -> AdmissionControlPolicy:
        policy = self.get_or_create_policy(tier)
        policy.shedding_active = active
        self.db.commit()
        self.db.refresh(policy)
        return policy

