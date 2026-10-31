"""
LeadNexus AI X - Phase 33: Enterprise Data Migration & Zero-Downtime Upgrades
Expand-Migrate-Contract Orchestrator: Zero-downtime schema evolution state machine and rollback engine.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.migration import MigrationPhase, SchemaMigrationPlan


class ExpandContractOrchestrator:
    """Orchestrates zero-downtime schema evolution across Expand, Backfill, Reconcile, and Contract phases."""

    VALID_TRANSITIONS = {
        MigrationPhase.PLANNED.value: [MigrationPhase.EXPANDING.value, MigrationPhase.ROLLED_BACK.value],
        MigrationPhase.EXPANDING.value: [MigrationPhase.BACKFILLING.value, MigrationPhase.ROLLED_BACK.value],
        MigrationPhase.BACKFILLING.value: [MigrationPhase.RECONCILING.value, MigrationPhase.ROLLED_BACK.value],
        MigrationPhase.RECONCILING.value: [MigrationPhase.CONTRACTING.value, MigrationPhase.ROLLED_BACK.value],
        MigrationPhase.CONTRACTING.value: [MigrationPhase.COMPLETED.value, MigrationPhase.ROLLED_BACK.value],
    }

    def __init__(self, db_session: Any):
        self.db = db_session

    def create_plan(
        self,
        plan_id: str,
        name: str,
        source_version: str,
        target_version: str,
        plan_definition: Dict[str, Any],
    ) -> SchemaMigrationPlan:
        plan = SchemaMigrationPlan(
            id=plan_id,
            name=name,
            source_version=source_version,
            target_version=target_version,
            phase=MigrationPhase.PLANNED.value,
            plan_definition=plan_definition,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def advance_phase(
        self,
        plan_id: str,
        target_phase: MigrationPhase,
        reconciliation_parity_pct: Optional[float] = None,
    ) -> Tuple[bool, SchemaMigrationPlan, Optional[str]]:
        plan = self.db.query(SchemaMigrationPlan).filter(SchemaMigrationPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Migration plan '{plan_id}' not found.")

        target_phase_val = target_phase.value if isinstance(target_phase, MigrationPhase) else target_phase
        current_phase = plan.phase

        # Validation: Contract stage gate requires 100% parity
        if target_phase_val == MigrationPhase.CONTRACTING.value:
            if reconciliation_parity_pct is None or reconciliation_parity_pct < 100.0:
                return False, plan, f"Contracting gate blocked: Parity is {reconciliation_parity_pct}%, required 100.0%"

        # Transition validation
        allowed_next = self.VALID_TRANSITIONS.get(current_phase, [])
        if target_phase_val not in allowed_next:
            return False, plan, f"Invalid phase transition: cannot advance from {current_phase} to {target_phase_val}"

        plan.phase = target_phase_val
        plan.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(plan)
        return True, plan, None

    def rollback(self, plan_id: str, reason: str) -> SchemaMigrationPlan:
        plan = self.db.query(SchemaMigrationPlan).filter(SchemaMigrationPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Migration plan '{plan_id}' not found.")

        plan.phase = MigrationPhase.ROLLED_BACK.value
        curr_def = dict(plan.plan_definition or {})
        curr_def["rollback_reason"] = reason
        curr_def["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        plan.plan_definition = curr_def
        plan.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(plan)
        return plan

