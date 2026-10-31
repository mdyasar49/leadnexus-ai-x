"""
LeadNexus AI X - Phase 29: Enterprise Governance, Policy Engine, Data Contracts & Compliance Tests
Verifies declarative policy DSL, field-level PII masking, data producer contracts,
global suppressions, legal holds, and tenant quota controls.
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
from app.models.governance import (
    ContractEnforcementMode,
    DataContract,
    GovernancePolicy,
    LegalHold,
    PolicyEffect,
    PolicyType,
    SuppressionRecord,
    SuppressionType,
    TenantQuota,
)
from packages.governance.data_contract_engine import DataContractEngine
from packages.governance.field_masking_service import FieldMaskingService
from packages.governance.policy_engine import (
    PolicyContext,
    PolicyEngine,
    PolicyEvaluationResult,
)
from packages.governance.suppression_and_legal_hold_service import (
    SuppressionAndLegalHoldService,
)
from packages.governance.tenant_quota_service import TenantQuotaService


class TestPhase29Governance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Governance Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Governance Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="compliance_officer@leadnexus.test",
                name="Compliance Officer",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. Policy Engine & DSL ---

    def test_01_policy_dsl_single_condition_equals(self):
        cond = {"field": "action", "operator": "equals", "value": "companies:export"}
        ctx = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ANALYST"],
            action="companies:export",
            resource_type="COMPANY",
        )
        self.assertTrue(PolicyEngine.evaluate_condition(cond, ctx))

    def test_02_policy_dsl_in_and_not_in_operators(self):
        cond_in = {"field": "actor_roles", "operator": "in", "value": ["ADMIN", "ANALYST"]}
        cond_not_in = {"field": "actor_roles", "operator": "not_in", "value": ["VIEWER"]}
        ctx = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ANALYST"],
            action="companies:read",
            resource_type="COMPANY",
        )
        self.assertTrue(PolicyEngine.evaluate_condition(cond_in, ctx))
        self.assertTrue(PolicyEngine.evaluate_condition(cond_not_in, ctx))

    def test_03_policy_dsl_and_block_evaluation(self):
        rules = {
            "all": [
                {"field": "action", "operator": "equals", "value": "contacts:view_pii"},
                {"field": "actor_roles", "operator": "not_in", "value": ["ADMIN"]},
            ]
        }
        ctx_analyst = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ANALYST"],
            action="contacts:view_pii",
            resource_type="CONTACT",
        )
        # Analyst is not admin, so rule matches
        self.assertTrue(PolicyEngine.evaluate_policy_rules(rules, ctx_analyst))

        ctx_admin = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ADMIN"],
            action="contacts:view_pii",
            resource_type="CONTACT",
        )
        # Admin is in ["ADMIN"], so rule fails
        self.assertFalse(PolicyEngine.evaluate_policy_rules(rules, ctx_admin))

    def test_04_policy_dsl_or_block_evaluation(self):
        rules = {
            "any": [
                {"field": "actor_roles", "operator": "contains", "value": "ADMIN"},
                {"field": "action", "operator": "equals", "value": "companies:read"},
            ]
        }
        ctx = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["VIEWER"],
            action="companies:read",
            resource_type="COMPANY",
        )
        self.assertTrue(PolicyEngine.evaluate_policy_rules(rules, ctx))

    def test_05_policy_engine_priority_ordering(self):
        policies = [
            {
                "id": "pol_10",
                "name": "General Allow",
                "priority": 100,
                "effect": "ALLOW",
                "rules_dsl": {"field": "action", "operator": "equals", "value": "companies:export"},
                "is_active": True,
            },
            {
                "id": "pol_01",
                "name": "Strict Export Guard",
                "priority": 10,
                "effect": "REQUIRE_APPROVAL",
                "rules_dsl": {"field": "action", "operator": "equals", "value": "companies:export"},
                "is_active": True,
            },
        ]
        ctx = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ANALYST"],
            action="companies:export",
            resource_type="COMPANY",
        )
        res = PolicyEngine.evaluate(policies, ctx)
        # Priority 10 rule should be evaluated first
        self.assertEqual(res.decision, PolicyEffect.REQUIRE_APPROVAL)
        self.assertEqual(res.matched_policy_id, "pol_01")

    def test_06_policy_engine_default_fallback(self):
        ctx = PolicyContext(
            workspace_id=self.workspace.id,
            actor_id=self.user.id,
            actor_roles=["ANALYST"],
            action="unrecognized:action",
            resource_type="SYSTEM",
        )
        res = PolicyEngine.evaluate([], ctx, default_effect=PolicyEffect.DENY)
        self.assertEqual(res.decision, PolicyEffect.DENY)

    # --- 2. Field-Level Masking & PII Protection ---

    def test_07_field_masking_email(self):
        self.assertEqual(FieldMaskingService.mask_email("sarah.jenkins@acme.com"), "s***s@acme.com")
        self.assertEqual(FieldMaskingService.mask_email("ed@tech.co"), "e***@tech.co")
        self.assertEqual(FieldMaskingService.mask_email(None), "***@***.com")

    def test_08_field_masking_phone(self):
        self.assertEqual(FieldMaskingService.mask_phone("+1 415-555-2671"), "+1 ***-***-2671")
        self.assertEqual(FieldMaskingService.mask_phone("555-8912"), "***-***-8912")

    def test_09_field_masking_name(self):
        self.assertEqual(FieldMaskingService.mask_name("Sarah Jenkins"), "S**** J******")

    def test_10_field_masking_financial(self):
        self.assertEqual(FieldMaskingService.mask_financial(125000), "$50k - $250k (Confidential)")
        self.assertEqual(FieldMaskingService.mask_financial(2500000), "$1M - $10M (Confidential)")

    def test_11_field_masking_record_clone(self):
        raw = {
            "company_name": "Apex Manufacturing Ltd",
            "contact_email": "sarah.jenkins@acme.com",
            "contact_phone": "+1 415-555-2671",
            "estimated_revenue": 500000,
        }
        masked = FieldMaskingService.mask_record(raw)
        # Company name is not masked
        self.assertEqual(masked["company_name"], "Apex Manufacturing Ltd")
        # Contact PII and financials are masked
        self.assertTrue(masked["contact_email"].startswith("s***"))
        self.assertTrue(masked["contact_phone"].endswith("2671"))
        self.assertIn("Confidential", masked["estimated_revenue"])

    # --- 3. Data Contract Engine ---

    def test_12_data_contract_completeness_calculation(self):
        payload = {"name": "Apex", "domain": "apex.com", "city": "Dallas"}
        req = ["name", "domain"]
        opt = ["city", "country"]
        score = DataContractEngine.calculate_completeness(payload, req, opt)
        # 3 out of 4 fields filled
        self.assertEqual(score, 0.75)

    def test_13_data_contract_valid_payload(self):
        contract = {
            "schema_definition": {
                "required_fields": ["name", "domain"],
                "optional_fields": ["industry"],
                "field_types": {"name": "string", "domain": "string"},
            },
            "sla_freshness_hours": 72,
            "min_completeness_score": 0.60,
            "enforcement_mode": "STRICT_REJECT",
        }
        payload = {
            "name": "Apex Manufacturing Ltd",
            "domain": "apexmanufacturing.com",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        res = DataContractEngine.validate_payload(payload, contract)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.is_accepted)
        self.assertEqual(len(res.violations), 0)

    def test_14_data_contract_missing_required_fields(self):
        contract = {
            "schema_definition": {
                "required_fields": ["name", "domain", "technologies"],
            },
            "min_completeness_score": 0.70,
            "enforcement_mode": "STRICT_REJECT",
        }
        payload = {"name": "Apex Manufacturing Ltd"}  # Missing domain and technologies
        res = DataContractEngine.validate_payload(payload, contract)
        self.assertFalse(res.is_valid)
        self.assertFalse(res.is_accepted)
        self.assertTrue(any("domain" in v for v in res.violations))

    def test_15_data_contract_type_mismatch(self):
        contract = {
            "schema_definition": {
                "required_fields": ["name"],
                "field_types": {"technologies": "list"},
            },
            "min_completeness_score": 0.50,
            "enforcement_mode": "STRICT_REJECT",
        }
        payload = {"name": "Apex", "technologies": "Odoo 17"}  # String instead of list
        res = DataContractEngine.validate_payload(payload, contract)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("type list" in v for v in res.violations))

    def test_16_data_contract_freshness_sla_breach(self):
        contract = {
            "schema_definition": {"required_fields": ["name"]},
            "sla_freshness_hours": 24,
            "min_completeness_score": 0.50,
            "enforcement_mode": "STRICT_REJECT",
        }
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        payload = {"name": "Apex", "observed_at": old_time.isoformat()}
        res = DataContractEngine.validate_payload(payload, contract)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Freshness SLA breach" in v for v in res.violations))

    def test_17_data_contract_warn_and_log_mode(self):
        contract = {
            "schema_definition": {"required_fields": ["name", "domain"]},
            "min_completeness_score": 0.70,
            "enforcement_mode": "WARN_AND_LOG",
        }
        payload = {"name": "Apex"}  # Missing domain
        res = DataContractEngine.validate_payload(payload, contract)
        self.assertFalse(res.is_valid)
        # Accepted despite violation because mode is WARN_AND_LOG
        self.assertTrue(res.is_accepted)

    # --- 4. Suppression & Legal Hold Service ---

    def test_18_suppression_exact_match(self):
        service = SuppressionAndLegalHoldService(self.db)
        service.add_suppression(
            workspace_id=self.workspace.id,
            suppression_type=SuppressionType.DOMAIN,
            pattern="competitor-systems.com",
            reason="Direct enterprise competitor",
        )
        is_sup, reason = service.is_suppressed(
            self.workspace.id, SuppressionType.DOMAIN.value, "competitor-systems.com"
        )
        self.assertTrue(is_sup)
        self.assertIn("Direct enterprise competitor", reason)

    def test_19_suppression_wildcard_match(self):
        service = SuppressionAndLegalHoldService(self.db)
        service.add_suppression(
            workspace_id=self.workspace.id,
            suppression_type=SuppressionType.DOMAIN,
            pattern="*.internal.corp",
            reason="Internal employee test domain",
        )
        is_sup, _ = service.is_suppressed(
            self.workspace.id, SuppressionType.DOMAIN.value, "dev.internal.corp"
        )
        self.assertTrue(is_sup)

    def test_20_suppression_clean_target(self):
        service = SuppressionAndLegalHoldService(self.db)
        is_sup, reason = service.is_suppressed(
            self.workspace.id, SuppressionType.DOMAIN.value, "allowed-lead-corp.com"
        )
        self.assertFalse(is_sup)
        self.assertIsNone(reason)

    def test_21_legal_hold_placement_and_checking(self):
        service = SuppressionAndLegalHoldService(self.db)
        company_id = str(uuid.uuid4())
        hold = service.place_legal_hold(
            workspace_id=self.workspace.id,
            name="Patent Litigation Hold",
            target_entity_type="COMPANY",
            target_entity_id=company_id,
            case_reference="CASE-2026-X99",
            placed_by=self.user.id,
        )
        self.assertTrue(hold.is_active)
        self.assertTrue(service.is_under_legal_hold(self.workspace.id, "COMPANY", company_id))

    def test_22_legal_hold_release(self):
        service = SuppressionAndLegalHoldService(self.db)
        contact_id = str(uuid.uuid4())
        hold = service.place_legal_hold(
            workspace_id=self.workspace.id,
            name="Temporary Audit Hold",
            target_entity_type="CONTACT",
            target_entity_id=contact_id,
            case_reference="AUDIT-2026-01",
        )
        self.assertTrue(service.is_under_legal_hold(self.workspace.id, "CONTACT", contact_id))

        service.release_legal_hold(hold.id)
        self.assertFalse(service.is_under_legal_hold(self.workspace.id, "CONTACT", contact_id))

    # --- 5. Tenant Quota Service ---

    def test_23_tenant_quota_budget_check_and_spend(self):
        service = TenantQuotaService(self.db)
        quota = service.get_or_create_quota(self.workspace.id)
        quota.max_daily_research_budget_usd = 50.0
        quota.current_daily_spend_usd = 45.0
        self.db.commit()

        # $10 request would exceed $50 limit ($45 + $10 = $55)
        ok, msg = service.check_research_budget(self.workspace.id, estimated_cost_usd=10.0)
        self.assertFalse(ok)
        self.assertIn("budget exceeded", msg)

        # $3 request is within limit ($45 + $3 = $48)
        ok_within, _ = service.check_research_budget(self.workspace.id, estimated_cost_usd=3.0)
        self.assertTrue(ok_within)

        # Record spend
        service.record_spend(self.workspace.id, 3.0)
        updated = service.get_or_create_quota(self.workspace.id)
        self.assertEqual(updated.current_daily_spend_usd, 48.0)

    def test_24_tenant_quota_concurrent_runs_limit(self):
        service = TenantQuotaService(self.db)
        quota = service.get_or_create_quota(self.workspace.id)
        quota.max_concurrent_runs = 5
        self.db.commit()

        ok_1, _ = service.check_concurrent_runs(self.workspace.id, active_runs_count=3)
        self.assertTrue(ok_1)

        ok_2, msg_2 = service.check_concurrent_runs(self.workspace.id, active_runs_count=5)
        self.assertFalse(ok_2)
        self.assertIn("Concurrent runs limit reached", msg_2)


if __name__ == "__main__":
    unittest.main()

