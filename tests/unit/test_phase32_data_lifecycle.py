"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle, Archival & Retention Unit Tests
Verifies tiered storage transitions, retention policy enforcement, legal hold exemption,
cryptographic archive package generation, tombstone references, staging restoration, and AI cache purging.
"""

import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.db.base import Base
from app.db.session import sync_engine, SessionLocal
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.data_lifecycle import (
    ArchivePackage,
    ArchiveStatus,
    ArchiveTombstone,
    DataRetentionPolicy,
    LifecycleTransitionEvent,
    StorageTier,
)
from app.models.knowledge_retrieval import AIConversation, AIConversationMessage, RAGDocument, RAGDocumentChunk
from packages.data_lifecycle.archival_package_service import (
    ArchivalPackageService,
)
from packages.data_lifecycle.ephemeral_ai_cache_cleaner import (
    EphemeralAICacheCleaner,
)
from packages.data_lifecycle.retention_policy_engine import (
    RetentionPolicyEngine,
)
from packages.data_lifecycle.staging_restoration_service import (
    StagingRestorationService,
)
from packages.governance.suppression_and_legal_hold_service import (
    SuppressionAndLegalHoldService,
)


class TestPhase32DataLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Lifecycle Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Lifecycle Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="data_archivist@leadnexus.test",
                name="Data Archivist Engineer",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. Retention Policy Engine ---

    def test_01_retention_policy_engine_within_window(self):
        engine = RetentionPolicyEngine(self.db)
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)
        eligible, reason = engine.is_eligible_for_transition(
            workspace_id=self.workspace.id,
            entity_type="RAW_SIGNAL",
            entity_id="sig_recent_01",
            created_at=recent_date,
            retention_days=90,
        )
        self.assertFalse(eligible)
        self.assertIn("Within retention window", reason)

    def test_02_retention_policy_engine_expired_window(self):
        engine = RetentionPolicyEngine(self.db)
        expired_date = datetime.now(timezone.utc) - timedelta(days=120)
        eligible, reason = engine.is_eligible_for_transition(
            workspace_id=self.workspace.id,
            entity_type="RAW_SIGNAL",
            entity_id="sig_expired_01",
            created_at=expired_date,
            retention_days=90,
        )
        self.assertTrue(eligible)
        self.assertIn("Retention window expired", reason)

    def test_03_retention_policy_engine_legal_hold_exemption(self):
        hold_svc = SuppressionAndLegalHoldService(self.db)
        held_entity_id = f"cont_held_{uuid.uuid4().hex[:6]}"
        hold = hold_svc.place_legal_hold(
            workspace_id=self.workspace.id,
            name="Litigation Hold on Contact",
            target_entity_type="CONTACT",
            target_entity_id=held_entity_id,
            case_reference="CASE-HOLD-099",
        )

        engine = RetentionPolicyEngine(self.db)
        very_old_date = datetime.now(timezone.utc) - timedelta(days=365)

        # Even though very old, legal hold MUST prevent transition
        eligible, reason = engine.is_eligible_for_transition(
            workspace_id=self.workspace.id,
            entity_type="CONTACT",
            entity_id=held_entity_id,
            created_at=very_old_date,
            retention_days=60,
        )
        self.assertFalse(eligible)
        self.assertIn("Legal Hold", reason)

        # Release hold
        hold_svc.release_legal_hold(hold.id)

    def test_04_retention_policy_engine_record_transition(self):
        engine = RetentionPolicyEngine(self.db)
        event = engine.record_transition(
            workspace_id=self.workspace.id,
            entity_type="RAW_SIGNAL",
            entity_id="sig_1029",
            from_tier=StorageTier.WARM,
            to_tier=StorageTier.COLD,
            reason="Age exceeded 90 days",
        )
        self.assertEqual(event.from_tier, StorageTier.WARM.value)
        self.assertEqual(event.to_tier, StorageTier.COLD.value)

    # --- 2. Archival Package Service ---

    def test_05_archival_package_service_create_package(self):
        svc = ArchivalPackageService(self.db)
        records = [
            {"id": "rec_01", "name": "Apex Test A", "domain": "a.test"},
            {"id": "rec_02", "name": "Apex Test B", "domain": "b.test"},
        ]
        pkg, tombstones = svc.create_archive_package(
            workspace_id=self.workspace.id,
            package_name="Q2 2026 Archived Signals",
            entity_type="RAW_SIGNAL",
            records=records,
        )
        self.assertEqual(pkg.records_count, 2)
        self.assertEqual(len(pkg.checksum_sha256), 64)
        self.assertEqual(len(tombstones), 2)
        self.assertEqual(pkg.status, ArchiveStatus.ACTIVE.value)

    def test_06_archival_package_service_get_tombstone(self):
        svc = ArchivalPackageService(self.db)
        unique_id = f"rec_tomb_{uuid.uuid4().hex[:6]}"
        pkg, tombstones = svc.create_archive_package(
            workspace_id=self.workspace.id,
            package_name="Tombstone Test Package",
            entity_type="CONTACT",
            records=[{"id": unique_id, "email": "test@tombstone.test"}],
        )
        ts = svc.get_tombstone(self.workspace.id, "CONTACT", unique_id)
        self.assertIsNotNone(ts)
        self.assertEqual(ts.archive_package_id, pkg.id)

    # --- 3. Staging Restoration Service ---

    def test_07_staging_restoration_service_preview(self):
        svc = ArchivalPackageService(self.db)
        records = [{"id": "item_1", "text": "Signal 1"}, {"id": "item_2", "text": "Signal 2"}]
        pkg, _ = svc.create_archive_package(
            workspace_id=self.workspace.id,
            package_name="Preview Test Package",
            entity_type="RAW_SIGNAL",
            records=records,
        )

        restore_svc = StagingRestorationService(self.db)
        preview = restore_svc.preview_archive(pkg.id)
        self.assertIsNotNone(preview)
        self.assertEqual(preview["records_count"], 2)
        self.assertEqual(len(preview["records"]), 2)

    def test_08_staging_restoration_service_restore_record(self):
        svc = ArchivalPackageService(self.db)
        target_id = f"restore_item_{uuid.uuid4().hex[:6]}"
        records = [{"id": target_id, "data": "Valuable Data to Restore"}]
        pkg, _ = svc.create_archive_package(
            workspace_id=self.workspace.id,
            package_name="Restore Test Package",
            entity_type="CONTACT",
            records=records,
        )

        restore_svc = StagingRestorationService(self.db)
        ok, restored_data, err = restore_svc.restore_record(self.workspace.id, pkg.id, target_id)
        self.assertTrue(ok)
        self.assertEqual(restored_data["data"], "Valuable Data to Restore")

        # Tombstone should now be removed
        ts_after = svc.get_tombstone(self.workspace.id, "CONTACT", target_id)
        self.assertIsNone(ts_after)

    def test_09_staging_restoration_service_restore_missing_entity(self):
        restore_svc = StagingRestorationService(self.db)
        ok, data, err = restore_svc.restore_record(self.workspace.id, "pkg_nonexistent", "item_404")
        self.assertFalse(ok)
        self.assertIn("not found", err)

    # --- 4. Ephemeral AI Cache Cleaner ---

    def test_10_ephemeral_ai_cache_cleaner_purge_turns(self):
        cleaner = EphemeralAICacheCleaner(self.db)
        # Create a conversation and stale message
        conv = AIConversation(
            id=str(uuid.uuid4()),
            workspace_id=self.workspace.id,
            user_id=self.user.id,
            title="Test Chat",
        )
        self.db.add(conv)
        self.db.commit()

        stale_msg = AIConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            role="user",
            content="Old question from 30 days ago",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        self.db.add(stale_msg)
        self.db.commit()

        purged = cleaner.purge_stale_conversation_turns(ttl_days=14)
        self.assertGreaterEqual(purged, 1)

    def test_11_ephemeral_ai_cache_cleaner_purge_rag_chunks(self):
        cleaner = EphemeralAICacheCleaner(self.db)
        doc = RAGDocument(
            id=str(uuid.uuid4()),
            workspace_id=self.workspace.id,
            document_type="EVIDENCE",
            title="Temp Doc",
            content_hash="hash_ephemeral_123",
            source_type="PUBLIC_WEB",
            content="Ephemeral text content",
        )
        self.db.add(doc)
        self.db.commit()

        stale_chunk = RAGDocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            sequence=0,
            chunk_text="Ephemeral chunk",
            chunk_hash="chunk_hash_001",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        self.db.add(stale_chunk)
        self.db.commit()

        purged_chunks = cleaner.purge_transient_rag_chunks(ttl_days=30)
        self.assertGreaterEqual(purged_chunks, 1)


if __name__ == "__main__":
    unittest.main()
