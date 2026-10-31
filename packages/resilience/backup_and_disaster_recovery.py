"""
LeadNexus AI X - Phase 30: Enterprise Reliability & Disaster Recovery
Backup & DR Service: Snapshot creation, SHA-256 checksum verification, and integrity validation.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.resilience import BackupSnapshot, BackupStatus


class BackupAndDisasterRecoveryService:
    """Manages disaster recovery snapshot manifests and automated cryptographic verification."""

    def __init__(self, db_session: Any):
        self.db = db_session

    @classmethod
    def compute_checksum(cls, data_bytes: bytes) -> str:
        return hashlib.sha256(data_bytes).hexdigest()

    def create_snapshot(
        self,
        snapshot_name: str,
        storage_path: str,
        records_count: int,
        data_bytes: bytes,
    ) -> BackupSnapshot:
        checksum = self.compute_checksum(data_bytes)
        snapshot = BackupSnapshot(
            id=str(uuid.uuid4()),
            snapshot_name=snapshot_name,
            storage_path=storage_path,
            checksum_sha256=checksum,
            records_count=records_count,
            size_bytes=len(data_bytes),
            verification_status=BackupStatus.PENDING.value,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def verify_snapshot(
        self,
        snapshot_id: str,
        validation_bytes: bytes,
    ) -> Tuple[bool, BackupSnapshot, Optional[str]]:
        """Validates snapshot payload against stored cryptographic checksum."""
        snapshot = self.db.query(BackupSnapshot).filter(BackupSnapshot.id == snapshot_id).first()
        if not snapshot:
            raise ValueError(f"Snapshot '{snapshot_id}' not found.")

        current_checksum = self.compute_checksum(validation_bytes)
        now = datetime.now(timezone.utc)

        if current_checksum == snapshot.checksum_sha256 and len(validation_bytes) == snapshot.size_bytes:
            snapshot.verification_status = BackupStatus.VERIFIED.value
            snapshot.verified_at = now
            self.db.commit()
            self.db.refresh(snapshot)
            return True, snapshot, None

        snapshot.verification_status = BackupStatus.CORRUPTED.value
        snapshot.verified_at = now
        self.db.commit()
        self.db.refresh(snapshot)
        return False, snapshot, f"Checksum mismatch: expected {snapshot.checksum_sha256}, got {current_checksum}"
