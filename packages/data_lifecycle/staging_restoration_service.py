"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle & Restoration
Staging Restoration Service: Selective unarchival, manifest inspection, and tombstone resolution.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.models.data_lifecycle import ArchivePackage, ArchiveStatus, ArchiveTombstone


class StagingRestorationService:
    """Restores selectively unarchived records back into active or warm database tables."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def preview_archive(self, package_id: str) -> Optional[Dict[str, Any]]:
        pkg = self.db.query(ArchivePackage).filter(ArchivePackage.id == package_id).first()
        if not pkg:
            return None

        manifest = pkg.manifest or {}
        return {
            "package_id": pkg.id,
            "package_name": pkg.package_name,
            "records_count": pkg.records_count,
            "checksum_sha256": pkg.checksum_sha256,
            "records": manifest.get("records", []),
        }

    def restore_record(
        self,
        workspace_id: str,
        package_id: str,
        entity_id: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        pkg = self.db.query(ArchivePackage).filter(
            ArchivePackage.id == package_id,
            ArchivePackage.workspace_id == workspace_id,
        ).first()
        if not pkg:
            return False, None, f"Archive package '{package_id}' not found."

        manifest = pkg.manifest or {}
        records = manifest.get("records", [])

        target_rec = None
        for r in records:
            if str(r.get("id")) == str(entity_id):
                target_rec = r
                break

        if not target_rec:
            return False, None, f"Entity '{entity_id}' not found in archive package '{package_id}'."

        # Delete or inactivate tombstone
        tombstone = self.db.query(ArchiveTombstone).filter(
            ArchiveTombstone.archive_package_id == package_id,
            ArchiveTombstone.original_entity_id == entity_id,
        ).first()
        if tombstone:
            self.db.delete(tombstone)
            self.db.commit()

        return True, target_rec, None

