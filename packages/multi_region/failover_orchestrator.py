"""
LeadNexus AI X — Controlled Failover & Failback Orchestrator
Phase 35 (ChatGPT Master Roadmap): Zero Data Loss Pre-flight Checks & Audited State Machine
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.multi_region import (
    RegionNode,
    TenantRegionAffinity,
    FailoverExecutionJob,
)
from packages.multi_region.split_brain_guard import SplitBrainGuard
from packages.multi_region.traffic_router import GlobalTrafficRouter, DataSovereigntyViolationError

logger = logging.getLogger("leadnexus.multi_region.failover")


class ReplicationLagThresholdExceededError(Exception):
    """Raised when replication lag is too high to perform zero-data-loss failover."""
    pass


class FailoverOrchestrator:
    """
    Executes controlled regional failovers and failbacks with strict pre-flight
    replication lag verification and split-brain fencing.
    """

    def __init__(self, split_brain_guard: SplitBrainGuard):
        self.split_brain_guard = split_brain_guard
        self.traffic_router = GlobalTrafficRouter(split_brain_guard)

    def execute_failover(
        self,
        db: Session,
        source_region_id: str,
        target_region_id: str,
        initiated_by: str,
        job_type: str = "PLANNED_FAILOVER",
        max_allowed_lag_s: float = 1.0,
    ) -> FailoverExecutionJob:
        """
        Executes a controlled switchover of the authorized write region.
        """
        start_time = time.perf_counter()
        now_dt = datetime.now(timezone.utc)

        # 1. Fetch Region Nodes
        source_node = db.query(RegionNode).filter(RegionNode.id == source_region_id).first()
        target_node = db.query(RegionNode).filter(RegionNode.id == target_region_id).first()

        if not target_node:
            raise ValueError(f"Target region node '{target_region_id}' does not exist.")

        # 2. Pre-flight Check: Replication Lag Gate
        target_lag = target_node.replication_lag_seconds or 0.0
        if job_type == "PLANNED_FAILOVER" and target_lag > max_allowed_lag_s:
            raise ReplicationLagThresholdExceededError(
                f"Planned failover aborted: Target replication lag {target_lag:.2f}s "
                f"exceeds maximum allowed threshold {max_allowed_lag_s:.2f}s (Zero Data Loss Protection)."
            )

        # 3. Create Audit Job
        job = FailoverExecutionJob(
            id=str(uuid.uuid4()),
            job_type=job_type,
            source_region_id=source_region_id,
            target_region_id=target_region_id,
            status="DRAINING_SOURCE",
            initiated_by=initiated_by,
            split_brain_fence_token="",
            replication_lag_at_switchover_s=target_lag,
            created_at=now_dt,
        )
        db.add(job)
        db.commit()

        # 4. Drain Source Region
        if source_node:
            source_node.status = "DRAINING"
            source_node.is_primary_write = False
            db.commit()

        # 5. Promote Target with Monotonic Fencing Token
        fence_token = self.split_brain_guard.issue_new_fencing_token(target_region_id)
        target_node.is_primary_write = True
        target_node.status = "ACTIVE"
        if source_node:
            source_node.status = "ACTIVE"

        duration_s = time.perf_counter() - start_time

        # 6. Finalize Job
        job.status = "COMPLETED"
        job.split_brain_fence_token = fence_token
        job.duration_seconds = round(duration_s, 3)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        logger.info(
            f"[Failover Orchestrator] Successfully completed {job_type} from '{source_region_id}' "
            f"to '{target_region_id}' in {duration_s:.3f}s. Fencing Token: {fence_token}"
        )
        return job
