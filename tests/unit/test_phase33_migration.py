"""
LeadNexus AI X - Phase 33: Enterprise Data Migration & Zero-Downtime Upgrades Unit Tests
Verifies Expand-Migrate-Contract state machine, parity gates, keyset chunked backfills,
dual-write column reconciliation, and API version contracts.
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
from app.models.migration import (
    APIVersionContract,
    BackfillJob,
    BackfillStatus,
    MigrationPhase,
    ReconciliationJob,
    ReconciliationStatus,
    SchemaMigrationPlan,
)
from packages.migration.api_versioning_manager import (
    APIVersioningManager,
)
from packages.migration.chunked_backfill_engine import (
    ChunkedBackfillEngine,
)
from packages.migration.data_reconciliation_engine import (
    DataReconciliationEngine,
)
from packages.migration.expand_contract_orchestrator import (
    ExpandContractOrchestrator,
)


class TestPhase33Migration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Migration Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Migration Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="db_architect@leadnexus.test",
                name="Database Migration Architect",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

        # Clean up any leftover test plans from previous runs to ensure test isolation
        cls.db.query(SchemaMigrationPlan).filter(
            SchemaMigrationPlan.id.in_(["plan_v32_v33_test", "plan_rollback_test"])
        ).delete(synchronize_session=False)
        cls.db.query(APIVersionContract).filter(
            APIVersionContract.id.in_(["v2", "v1_legacy", "v0_retired"])
        ).delete(synchronize_session=False)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.query(SchemaMigrationPlan).filter(
                SchemaMigrationPlan.id.in_(["plan_v32_v33_test", "plan_rollback_test"])
            ).delete(synchronize_session=False)
            cls.db.query(APIVersionContract).filter(
                APIVersionContract.id.in_(["v2", "v1_legacy", "v0_retired"])
            ).delete(synchronize_session=False)
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        cls.db.close()

    # --- 1. Expand-Contract Orchestrator ---

    def test_01_migration_plan_creation(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        plan = orchestrator.create_plan(
            plan_id="plan_v32_v33_test",
            name="Test Migration",
            source_version="v32.0.0",
            target_version="v33.0.0",
            plan_definition={"table": "contacts"},
        )
        self.assertEqual(plan.phase, MigrationPhase.PLANNED.value)

    def test_02_migration_plan_advance_to_expanding(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        ok, plan, err = orchestrator.advance_phase("plan_v32_v33_test", MigrationPhase.EXPANDING)
        self.assertTrue(ok)
        self.assertEqual(plan.phase, MigrationPhase.EXPANDING.value)

    def test_03_migration_plan_advance_to_backfilling(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        ok, plan, err = orchestrator.advance_phase("plan_v32_v33_test", MigrationPhase.BACKFILLING)
        self.assertTrue(ok)
        self.assertEqual(plan.phase, MigrationPhase.BACKFILLING.value)

    def test_04_migration_plan_advance_to_reconciling(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        ok, plan, err = orchestrator.advance_phase("plan_v32_v33_test", MigrationPhase.RECONCILING)
        self.assertTrue(ok)
        self.assertEqual(plan.phase, MigrationPhase.RECONCILING.value)

    def test_05_migration_plan_contracting_gate_blocked(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        # Parity is 98.5% (below 100%) -> MUST BE BLOCKED
        ok, plan, err = orchestrator.advance_phase(
            "plan_v32_v33_test", MigrationPhase.CONTRACTING, reconciliation_parity_pct=98.5
        )
        self.assertFalse(ok)
        self.assertIn("Contracting gate blocked", err)
        self.assertEqual(plan.phase, MigrationPhase.RECONCILING.value)

    def test_06_migration_plan_contracting_gate_allowed(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        # Parity is 100.0% -> ALLOWED
        ok, plan, err = orchestrator.advance_phase(
            "plan_v32_v33_test", MigrationPhase.CONTRACTING, reconciliation_parity_pct=100.0
        )
        self.assertTrue(ok)
        self.assertEqual(plan.phase, MigrationPhase.CONTRACTING.value)

    def test_07_migration_plan_rollback(self):
        orchestrator = ExpandContractOrchestrator(self.db)
        plan = orchestrator.create_plan(
            plan_id="plan_rollback_test",
            name="Rollback Test Plan",
            source_version="v32.0.0",
            target_version="v33.0.0",
            plan_definition={},
        )
        rolled_back = orchestrator.rollback(plan.id, reason="Simulated critical failure during backfill")
        self.assertEqual(rolled_back.phase, MigrationPhase.ROLLED_BACK.value)
        self.assertIn("rollback_reason", rolled_back.plan_definition)

    # --- 2. Chunked Backfill Engine ---

    def test_08_chunked_backfill_initialize(self):
        engine = ChunkedBackfillEngine(self.db)
        job = engine.initialize_job("plan_v32_v33_test", "contacts", total_records=100, chunk_size=50)
        self.assertEqual(job.status, BackfillStatus.PENDING.value)
        self.assertEqual(job.total_records, 100)
        self.assertEqual(job.chunk_size, 50)

    def test_09_chunked_backfill_execute_chunks(self):
        engine = ChunkedBackfillEngine(self.db)
        job = engine.initialize_job("plan_v32_v33_test", "companies", total_records=10, chunk_size=5)

        # Chunk 1
        items_c1 = [{"id": f"c_{i}", "old_name": f"Company {i}"} for i in range(5)]
        def transform(item):
            item["new_name"] = item["old_name"].upper()
            return item

        job_c1 = engine.execute_chunk(job.id, items_c1, transform, next_cursor="cursor_chunk_1")
        self.assertEqual(job_c1.processed_records, 5)
        self.assertEqual(job_c1.status, BackfillStatus.RUNNING.value)
        self.assertEqual(job_c1.current_cursor, "cursor_chunk_1")

        # Chunk 2 (Final)
        items_c2 = [{"id": f"c_{i}", "old_name": f"Company {i}"} for i in range(5, 10)]
        job_c2 = engine.execute_chunk(job.id, items_c2, transform, next_cursor=None)
        self.assertEqual(job_c2.processed_records, 10)
        self.assertEqual(job_c2.status, BackfillStatus.COMPLETED.value)
        self.assertIsNotNone(job_c2.completed_at)

    # --- 3. Data Reconciliation Engine ---

    def test_10_data_reconciliation_100_percent_parity(self):
        engine = DataReconciliationEngine(self.db)
        pairs = [
            {"id": "r1", "source_val": "DELIVERABLE", "target_val": "DELIVERABLE"},
            {"id": "r2", "source_val": "RISKY", "target_val": "RISKY"},
        ]
        job = engine.reconcile_columns("plan_v32_v33_test", "contacts", "old_status", "new_status", pairs)
        self.assertEqual(job.parity_pct, 100.0)
        self.assertEqual(job.status, ReconciliationStatus.PASSED.value)
        self.assertEqual(job.discrepancies_count, 0)

    def test_11_data_reconciliation_discrepancies_detected(self):
        engine = DataReconciliationEngine(self.db)
        pairs = [
            {"id": "r1", "source_val": "DELIVERABLE", "target_val": "DELIVERABLE"},
            {"id": "r2", "source_val": "DELIVERABLE", "target_val": "UNDELIVERABLE"},  # Mismatch!
        ]
        job = engine.reconcile_columns("plan_v32_v33_test", "contacts", "old_status", "new_status", pairs)
        self.assertEqual(job.parity_pct, 50.0)
        self.assertEqual(job.status, ReconciliationStatus.FAILED.value)
        self.assertEqual(job.discrepancies_count, 1)

    # --- 4. API Versioning Manager ---

    def test_12_api_versioning_manager_register_and_validate(self):
        mgr = APIVersioningManager(self.db)
        mgr.register_version(api_version="v2", is_deprecated=False)

        ok, warning, err = mgr.validate_request_version("v2")
        self.assertTrue(ok)
        self.assertIsNone(warning)
        self.assertIsNone(err)

    def test_13_api_versioning_manager_deprecated_warning(self):
        mgr = APIVersioningManager(self.db)
        sunset = datetime.now(timezone.utc) + timedelta(days=90)
        mgr.register_version(api_version="v1_legacy", is_deprecated=True, sunset_date=sunset)

        ok, warning, err = mgr.validate_request_version("v1_legacy")
        self.assertTrue(ok)
        self.assertIsNotNone(warning)
        self.assertIn("deprecated", warning)

    def test_14_api_versioning_manager_sunset_rejection(self):
        mgr = APIVersioningManager(self.db)
        past_sunset = datetime.now(timezone.utc) - timedelta(days=10)
        mgr.register_version(api_version="v0_retired", is_deprecated=True, sunset_date=past_sunset)

        ok, warning, err = mgr.validate_request_version("v0_retired")
        self.assertFalse(ok)
        self.assertIn("reached sunset", err)


if __name__ == "__main__":
    unittest.main()
