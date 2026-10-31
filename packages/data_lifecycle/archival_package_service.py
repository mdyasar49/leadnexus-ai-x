"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle & Archival
Archival Package Service: Cold storage manifest generation, cryptographic hashing, and tombstone creation.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.data_lifecycle import ArchivePackage, ArchiveStatus, ArchiveTombstone


class ArchivalPackageService:
    """Packages cold tier records into immutable archive bundles with tombstone tracking."""

    def __init__(self, db_session: Any):
        self.db = db_session

    @classmethod
    def compute_package_checksum(cls, serialized_records: str) -> str:
        return hashlib.sha256(serialized_records.encode("utf-8")).hexdigest()

    def create_archive_package(
        self,
        workspace_id: str,
        package_name: str,
        entity_type: str,
        records: List[Dict[str, Any]],
        storage_base_uri: str = "s3://leadnexus-cold-archives",
    ) -> Tuple[ArchivePackage, List[ArchiveTombstone]]:
        pkg_id = f"pkg_{entity_type.lower()}_{uuid.uuid4().hex[:12]}"
        serialized = json.dumps(records, sort_keys=True)
        checksum = self.compute_package_checksum(serialized)
        size_bytes = len(serialized.encode("utf-8"))
        storage_uri = f"{storage_base_uri}/{workspace_id}/{pkg_id}.json.gz"

        pkg = ArchivePackage(
            id=pkg_id,
            workspace_id=workspace_id,
            package_name=package_name,
            entity_type=entity_type,
            records_count=len(records),
            checksum_sha256=checksum,
            storage_uri=storage_uri,
            size_bytes=size_bytes,
            status=ArchiveStatus.ACTIVE.value,
            manifest={"records": records, "packed_at": datetime.now(timezone.utc).isoformat()},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(pkg)

        tombstones: List[ArchiveTombstone] = []
        for rec in records:
            rec_id = str(rec.get("id", uuid.uuid4()))
            ts = ArchiveTombstone(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                archive_package_id=pkg.id,
                entity_type=entity_type,
                original_entity_id=rec_id,
                archived_at=datetime.now(timezone.utc),
            )
            self.db.add(ts)
            tombstones.append(ts)

        self.db.commit()
        self.db.refresh(pkg)
        return pkg, tombstones

    def get_tombstone(self, workspace_id: str, entity_type: str, entity_id: str) -> Optional[ArchiveTombstone]:
        return self.db.query(ArchiveTombstone).filter(
            ArchiveTombstone.workspace_id == workspace_id,
            ArchiveTombstone.entity_type == entity_type,
            ArchiveTombstone.original_entity_id == entity_id,
        ).first()

