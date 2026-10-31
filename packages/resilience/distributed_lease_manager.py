"""
LeadNexus AI X - Phase 30: Enterprise Reliability & Resilience
Distributed Lease Manager: Task leasing, heartbeats, fencing tokens, and zombie process cleanup.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.resilience import TaskLease


class DistributedLeaseManager:
    """Manages distributed task execution leases, fencing tokens, and prevents zombie execution."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def acquire_lease(
        self,
        task_id: str,
        worker_id: str,
        ttl_seconds: int = 60,
    ) -> Tuple[bool, Optional[TaskLease], Optional[str]]:
        """
        Attempts to acquire an exclusive execution lease for a task.
        Returns: (success, TaskLease, error_message)
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        existing = self.db.query(TaskLease).filter(TaskLease.task_id == task_id).first()
        if existing:
            lease_exp = existing.lease_expires_at
            if lease_exp and lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)

            # Check if active and not expired
            if existing.is_active and lease_exp > now:
                if existing.worker_id == worker_id:
                    # Renew existing worker's lease
                    existing.lease_expires_at = expires_at
                    existing.heartbeat_count += 1
                    self.db.commit()
                    self.db.refresh(existing)
                    return True, existing, None
                return False, None, f"Task '{task_id}' is leased to worker '{existing.worker_id}' until {existing.lease_expires_at.isoformat()}"

            # Lease expired or inactive -> acquire and increment fencing token
            existing.worker_id = worker_id
            existing.fencing_token += 1
            existing.lease_acquired_at = now
            existing.lease_expires_at = expires_at
            existing.heartbeat_count = 1
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            return True, existing, None

        # Create new lease
        lease = TaskLease(
            id=str(uuid.uuid4()),
            task_id=task_id,
            worker_id=worker_id,
            fencing_token=1,
            lease_acquired_at=now,
            lease_expires_at=expires_at,
            heartbeat_count=1,
            is_active=True,
        )
        self.db.add(lease)
        self.db.commit()
        self.db.refresh(lease)
        return True, lease, None

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
        ttl_seconds: int = 60,
    ) -> bool:
        """Sends a heartbeat to renew an active lease, verifying worker and fencing token."""
        now = datetime.now(timezone.utc)
        lease = self.db.query(TaskLease).filter(
            TaskLease.task_id == task_id,
            TaskLease.worker_id == worker_id,
            TaskLease.fencing_token == fencing_token,
            TaskLease.is_active == True,
        ).first()

        if not lease:
            return False

        lease.lease_expires_at = now + timedelta(seconds=ttl_seconds)
        lease.heartbeat_count += 1
        self.db.commit()
        return True

    def release_lease(
        self,
        task_id: str,
        worker_id: str,
        fencing_token: int,
    ) -> bool:
        """Gracefully releases task lease upon job completion."""
        lease = self.db.query(TaskLease).filter(
            TaskLease.task_id == task_id,
            TaskLease.worker_id == worker_id,
            TaskLease.fencing_token == fencing_token,
        ).first()

        if not lease:
            return False

        lease.is_active = False
        self.db.commit()
        return True

    def reap_stale_leases(self) -> List[str]:
        """Detects expired active leases, inactivates them, and returns reaped task_ids."""
        now = datetime.now(timezone.utc)
        active_leases = self.db.query(TaskLease).filter(TaskLease.is_active == True).all()

        reaped_task_ids = []
        for lease in active_leases:
            lease_exp = lease.lease_expires_at
            if lease_exp and lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)
            if lease_exp and lease_exp < now:
                lease.is_active = False
                reaped_task_ids.append(lease.task_id)

        if reaped_task_ids:
            self.db.commit()

        return reaped_task_ids
