"""
Agent Arbitration & Conflict Resolution Engine (Phase 41)
Detects and arbitrates factual, structural, or scoring disagreements between specialized agents.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid
from app.models.multi_agent_platform import ArbitrationStrategy


class ArbitrationConflict:
    def __init__(
        self,
        task_id: str,
        conflict_field: str,
        claims: Dict[str, Dict[str, Any]],  # agent_type -> {"value": ..., "confidence": ...}
    ):
        self.task_id = task_id
        self.conflict_field = conflict_field
        self.claims = claims


class AgentArbitrator:
    """Arbitrates conflicting outputs between cooperating specialized agents."""

    @classmethod
    def detect_conflict(
        cls,
        field: str,
        agent_a: str,
        value_a: Any,
        confidence_a: float,
        agent_b: str,
        value_b: Any,
        confidence_b: float,
        task_id: str = "task-default",
    ) -> Optional[ArbitrationConflict]:
        """Detects if two agents report conflicting non-equivalent values for the same attribute."""
        if value_a != value_b:
            return ArbitrationConflict(
                task_id=task_id,
                conflict_field=field,
                claims={
                    agent_a: {"value": value_a, "confidence": confidence_a},
                    agent_b: {"value": value_b, "confidence": confidence_b},
                },
            )
        return None

    @classmethod
    def resolve_conflict(
        cls,
        conflict: ArbitrationConflict,
        strategy: str = ArbitrationStrategy.CONFIDENCE_WEIGHTED,
    ) -> Dict[str, Any]:
        """Resolves conflict using selected arbitration strategy."""
        claims = conflict.claims
        now = datetime.now(timezone.utc)

        if strategy == ArbitrationStrategy.CONFIDENCE_WEIGHTED:
            # Pick highest confidence
            best_agent = max(claims.keys(), key=lambda a: claims[a].get("confidence", 0.0))
            resolved_value = claims[best_agent]["value"]
            winning_confidence = claims[best_agent]["confidence"]

            return {
                "id": str(uuid.uuid4()),
                "task_id": conflict.task_id,
                "conflict_field": conflict.conflict_field,
                "strategy": ArbitrationStrategy.CONFIDENCE_WEIGHTED,
                "winner_agent": best_agent,
                "resolved_value": resolved_value,
                "winning_confidence": winning_confidence,
                "resolution_notes": f"Selected {best_agent} based on highest confidence score ({winning_confidence:.2f}).",
                "resolved_at": now.isoformat(),
            }
        elif strategy == ArbitrationStrategy.SUPERVISOR_CONSENSUS:
            # Default to PlanningAgent or ReviewAgent if present, else highest confidence
            supervisor = next((a for a in claims if a in ("PlanningAgent", "ReviewAgent")), None)
            if supervisor:
                return {
                    "id": str(uuid.uuid4()),
                    "task_id": conflict.task_id,
                    "conflict_field": conflict.conflict_field,
                    "strategy": ArbitrationStrategy.SUPERVISOR_CONSENSUS,
                    "winner_agent": supervisor,
                    "resolved_value": claims[supervisor]["value"],
                    "resolution_notes": f"Overridden by supervisor agent: {supervisor}.",
                    "resolved_at": now.isoformat(),
                }
            else:
                return cls.resolve_conflict(conflict, strategy=ArbitrationStrategy.CONFIDENCE_WEIGHTED)
        else:
            # HUMAN_REVIEW required
            return {
                "id": str(uuid.uuid4()),
                "task_id": conflict.task_id,
                "conflict_field": conflict.conflict_field,
                "strategy": ArbitrationStrategy.HUMAN_REVIEW,
                "winner_agent": None,
                "resolved_value": None,
                "resolution_notes": "Dispute escalated to Human-in-the-Loop review queue.",
                "resolved_at": None,
            }

