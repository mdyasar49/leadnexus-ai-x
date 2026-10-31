"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform Unit & Integration Test Suite
Verifies Connector SDK, sandboxed execution, security scanner, developer apps & credentials,
integration template engine, developer sandbox, and marketplace operations.
"""

import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

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
from app.models.developer_platform import (
    ApplicationScope,
    ApplicationStatus,
    ApplicationType,
    Connector,
    ConnectorInstallation,
    DeveloperAccount,
    DeveloperApplication,
    DeveloperRole,
    DeveloperSandbox,
    MarketplaceListing,
    MarketplaceTrustLevel,
    ScopeRiskLevel,
)
from packages.developer_platform.connector_sdk import (
    BaseConnector,
    ConnectorCapability,
    ConnectorContext,
    ConnectorManifest,
    ConnectorResult,
    ConnectorSecurityScanner,
    CustomWebhookExporterConnector,
    ExecutionStatus,
    PublicJobFeedConnector,
    SandboxedConnectorRunner,
)
from packages.developer_platform.developer_app_service import (
    DeveloperAppService,
    ScopeCatalog,
)
from packages.developer_platform.developer_sandbox_service import (
    DeveloperSandboxService,
    MockProviderSimulator,
)
from packages.developer_platform.integration_template_engine import (
    IntegrationTemplateEngine,
    TemplateRegistry,
    TemplateVariable,
)
from packages.developer_platform.marketplace_engine import (
    MarketplaceEngine,
    MarketplaceSecurityReviewer,
)


class TestPhase28DeveloperPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        # Seed test organization, workspace, and user
        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Dev Platform Test Org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Dev Platform Test Workspace",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="dev_architect@leadnexus.test",
                name="Dev Platform Architect",
                password_hash="test_secret_hash",
            )
            cls.db.add(cls.user)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. Connector Manifest & Validation ---

    def test_01_manifest_parser_and_validation(self):
        data = {
            "id": "test_connector_01",
            "name": "Custom ERP Scraper",
            "version": "1.2.0",
            "category": "ERP Ingestion",
            "description": "Extracts ERP evidence",
            "author": "Acme Partners",
            "capabilities": ["FETCH", "ENRICH"],
            "required_permissions": ["companies:read"],
            "entrypoint": "run",
            "allowed_domains": ["api.acme-erp.com"],
            "max_records_per_run": 250,
        }
        manifest = ConnectorManifest.from_dict(data)
        self.assertEqual(manifest.id, "test_connector_01")
        self.assertEqual(manifest.capabilities, ["FETCH", "ENRICH"])
        self.assertEqual(manifest.max_records_per_run, 250)
        self.assertIn("api.acme-erp.com", manifest.allowed_domains)

        # Missing required fields
        with self.assertRaises(ValueError):
            ConnectorManifest.from_dict({"name": "No ID"})

    # --- 2. Connector Security Scanner (AST Analysis) ---

    def test_02_connector_security_scanner_clean_code(self):
        clean_code = """
def fetch_signals(query):
    result = []
    for item in query:
        result.append({'title': item.upper()})
    return result
"""
        is_safe, issues = ConnectorSecurityScanner.scan_code(clean_code)
        self.assertTrue(is_safe)
        self.assertEqual(len(issues), 0)

    def test_03_connector_security_scanner_forbidden_calls(self):
        malicious_code = """
def execute_exploit():
    eval("1 + 1")
    exec("print('pwned')")
"""
        is_safe, issues = ConnectorSecurityScanner.scan_code(malicious_code)
        self.assertFalse(is_safe)
        self.assertTrue(any("eval" in issue for issue in issues))
        self.assertTrue(any("exec" in issue for issue in issues))

    def test_04_connector_security_scanner_forbidden_modules(self):
        unsafe_import = """
import os
import subprocess
from socket import socket

def pwn():
    os.system("rm -rf /")
"""
        is_safe, issues = ConnectorSecurityScanner.scan_code(unsafe_import)
        self.assertFalse(is_safe)
        self.assertTrue(any("os" in issue for issue in issues))
        self.assertTrue(any("subprocess" in issue for issue in issues))
        self.assertTrue(any("socket" in issue for issue in issues))

    def test_05_connector_security_scanner_ssrf_blocking(self):
        # Localhost / internal blocking
        safe_1, err_1 = ConnectorSecurityScanner.validate_outbound_network("http://127.0.0.1:8080", [])
        self.assertFalse(safe_1)
        self.assertIn("SSRF Security Violation", err_1)

        safe_2, err_2 = ConnectorSecurityScanner.validate_outbound_network("http://169.254.169.254/latest/meta-data", [])
        self.assertFalse(safe_2)

        # Domain allowlist
        safe_3, err_3 = ConnectorSecurityScanner.validate_outbound_network(
            "https://api.github.com/repos", ["api.github.com"]
        )
        self.assertTrue(safe_3)
        self.assertIsNone(err_3)

        safe_4, err_4 = ConnectorSecurityScanner.validate_outbound_network(
            "https://evil.unapproved.com/data", ["api.github.com"]
        )
        self.assertFalse(safe_4)
        self.assertIn("allowed_domains", err_4)

    # --- 3. Sandboxed Connector Runner ---

    def test_06_sandboxed_connector_runner_missing_permissions(self):
        runner = SandboxedConnectorRunner()
        runner.register_connector(PublicJobFeedConnector())

        # PublicJobFeedConnector requires: ["companies:read", "research:run"]
        # Context only provides ["companies:read"]
        ctx = ConnectorContext(
            workspace_id=self.workspace.id,
            installation_id="inst_1",
            configuration={},
            granted_scopes=["companies:read"],
        )
        result = runner.execute_connector("public_job_feed_connector", ctx)
        self.assertEqual(result.status, ExecutionStatus.PERMISSION_DENIED)
        self.assertIn("research:run", result.error_message)

    def test_07_sandboxed_connector_runner_successful_execution(self):
        runner = SandboxedConnectorRunner()
        runner.register_connector(PublicJobFeedConnector())

        ctx = ConnectorContext(
            workspace_id=self.workspace.id,
            installation_id="inst_1",
            configuration={"target_technology": "Odoo"},
            granted_scopes=["companies:read", "research:run"],
        )
        result = runner.execute_connector("public_job_feed_connector", ctx)
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.records_processed, 2)
        self.assertGreater(len(result.logs), 0)
        self.assertIn("Odoo", result.records[0]["job_title"])

    def test_08_sandboxed_connector_runner_max_records_cap(self):
        class OverflowConnector(BaseConnector):
            def __init__(self):
                manifest = ConnectorManifest(
                    id="overflow_conn",
                    name="Overflow",
                    version="1.0.0",
                    category="Test",
                    description="Test",
                    author="Test",
                    capabilities=["FETCH"],
                    required_permissions=[],
                    entrypoint="run",
                    max_records_per_run=5,
                )
                super().__init__(manifest)

            def execute(self, context: ConnectorContext) -> ConnectorResult:
                items = [{"id": i} for i in range(20)]
                return ConnectorResult(status=ExecutionStatus.SUCCESS, records_processed=20, records=items)

        runner = SandboxedConnectorRunner()
        runner.register_connector(OverflowConnector())

        ctx = ConnectorContext(
            workspace_id=self.workspace.id,
            installation_id="inst_2",
            configuration={},
            granted_scopes=[],
        )
        res = runner.execute_connector("overflow_conn", ctx)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(res.records), 5)  # Capped at 5
        self.assertEqual(res.records_processed, 5)

    def test_09_webhook_exporter_connector_ssrf_defense(self):
        runner = SandboxedConnectorRunner()
        runner.register_connector(CustomWebhookExporterConnector())

        ctx = ConnectorContext(
            workspace_id=self.workspace.id,
            installation_id="inst_3",
            configuration={"target_url": "http://10.0.0.1/webhook"},
            granted_scopes=["exports:create"],
        )
        res = runner.execute_connector("webhook_intelligence_exporter", ctx)
        self.assertEqual(res.status, ExecutionStatus.SECURITY_VIOLATION)
        self.assertIn("SSRF violation", res.error_message)

    def test_10_webhook_exporter_connector_success(self):
        runner = SandboxedConnectorRunner()
        runner.register_connector(CustomWebhookExporterConnector())

        ctx = ConnectorContext(
            workspace_id=self.workspace.id,
            installation_id="inst_4",
            configuration={"target_url": "https://api.externalpartner.com/leads/webhook", "batch_size": 25},
            granted_scopes=["exports:create"],
        )
        res = runner.execute_connector("webhook_intelligence_exporter", ctx)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertEqual(res.records_processed, 25)

    # --- 4. Developer App Service & Credentials ---

    def test_11_developer_app_service_credential_generation(self):
        client_id, secret, secret_hash = DeveloperAppService.generate_credentials()
        self.assertTrue(client_id.startswith("lnx_app_"))
        self.assertTrue(secret.startswith("lnx_sec_"))
        self.assertEqual(len(secret_hash), 64)

    def test_12_developer_app_service_secret_verification(self):
        client_id, secret, secret_hash = DeveloperAppService.generate_credentials()
        self.assertTrue(DeveloperAppService.verify_secret(secret, secret_hash))
        self.assertFalse(DeveloperAppService.verify_secret("wrong_secret", secret_hash))

    def test_13_developer_app_service_create_application(self):
        service = DeveloperAppService(self.db)
        app, secret, scopes = service.create_application(
            workspace_id=self.workspace.id,
            name="BI Ingestion Agent",
            description="Extracts company intelligence for BI warehouse",
            application_type=ApplicationType.INTERNAL,
            requested_scopes=["companies:read", "research:run", "exports:create"],
        )
        self.assertEqual(app.name, "BI Ingestion Agent")
        self.assertEqual(app.status, ApplicationStatus.ACTIVE.value)
        self.assertEqual(len(scopes), 3)

        # Scopes risk validation: LOW and MEDIUM auto-approved, HIGH requires approval
        approved = service.get_approved_scopes(app.id)
        self.assertIn("companies:read", approved)
        self.assertIn("research:run", approved)
        self.assertNotIn("exports:create", approved)  # HIGH risk pending approval

    def test_14_developer_app_service_secret_rotation(self):
        service = DeveloperAppService(self.db)
        app, old_secret, _ = service.create_application(
            workspace_id=self.workspace.id,
            name="Rotate App Test",
            application_type=ApplicationType.PRIVATE,
        )
        old_hash = app.client_secret_hash

        updated_app, new_secret = service.rotate_client_secret(app.id, actor_id=self.user.id)
        self.assertNotEqual(old_secret, new_secret)
        self.assertNotEqual(old_hash, updated_app.client_secret_hash)
        self.assertTrue(service.verify_secret(new_secret, updated_app.client_secret_hash))

    def test_15_scope_catalog_risk_tiers(self):
        self.assertEqual(ScopeCatalog.get_risk_level("companies:read"), ScopeRiskLevel.LOW)
        self.assertEqual(ScopeCatalog.get_risk_level("research:run"), ScopeRiskLevel.MEDIUM)
        self.assertEqual(ScopeCatalog.get_risk_level("exports:create"), ScopeRiskLevel.HIGH)
        self.assertEqual(ScopeCatalog.get_risk_level("admin:all"), ScopeRiskLevel.RESTRICTED)

    # --- 5. Integration Template Engine ---

    def test_16_integration_template_engine_list_and_get(self):
        templates = TemplateRegistry.list_templates()
        self.assertGreaterEqual(len(templates), 3)

        sheets_tpl = TemplateRegistry.get_template("template_google_sheets_sync")
        self.assertIsNotNone(sheets_tpl)
        self.assertEqual(sheets_tpl.category, "Productivity & Spreadsheets")

    def test_17_integration_template_variable_validation(self):
        sheets_tpl = TemplateRegistry.get_template("template_google_sheets_sync")

        # Missing required variable 'spreadsheet_id'
        is_valid, errors, _ = IntegrationTemplateEngine.validate_variables(sheets_tpl, {})
        self.assertFalse(is_valid)
        self.assertTrue(any("spreadsheet_id" in err for err in errors))

        # Valid with default fallback for sheet_name and frequency
        is_valid_2, errors_2, resolved = IntegrationTemplateEngine.validate_variables(
            sheets_tpl, {"spreadsheet_id": "1abcxyz_sheet_id"}
        )
        self.assertTrue(is_valid_2)
        self.assertEqual(resolved["spreadsheet_id"], "1abcxyz_sheet_id")
        self.assertEqual(resolved["sheet_name"], "LeadNexus_Intelligence")
        self.assertEqual(resolved["sync_frequency_minutes"], 60)

    def test_18_integration_template_instantiation(self):
        instance = IntegrationTemplateEngine.instantiate_template(
            template_id="template_google_sheets_sync",
            parameters={"spreadsheet_id": "test_sheet_999", "sheet_name": "Hot_Leads"},
            workspace_id=self.workspace.id,
        )
        self.assertEqual(instance["template_id"], "template_google_sheets_sync")
        steps = instance["execution_steps"]
        self.assertEqual(steps[0]["parameters"]["spreadsheet_id"], "test_sheet_999")
        self.assertEqual(steps[1]["parameters"]["sheet_name"], "Hot_Leads")

    # --- 6. Developer Sandbox Service ---

    def test_19_developer_sandbox_service_creation_and_seeding(self):
        service = DeveloperSandboxService(self.db)
        sandbox = service.create_sandbox(
            workspace_id=self.workspace.id,
            name="Testing Sandbox Alpha",
        )
        self.assertEqual(sandbox.name, "Testing Sandbox Alpha")
        self.assertTrue(sandbox.is_test_data)

        # Seed synthetic companies
        seed_result = service.seed_synthetic_data(sandbox.id, self.workspace.id, record_count=3)
        self.assertEqual(seed_result["companies_seeded"], 3)
        self.assertTrue(seed_result["data"][0]["is_test_data"])
        self.assertIn("Odoo", seed_result["data"][0]["technologies"][0])

        # Reset sandbox
        reset_ok = service.reset_sandbox(sandbox.id)
        self.assertTrue(reset_ok)

    def test_20_mock_provider_simulator_modes(self):
        # 200 OK
        resp_ok = MockProviderSimulator.simulate_call("company_enrichment", "SUCCESS")
        self.assertEqual(resp_ok["status_code"], 200)
        self.assertIn("Apex Manufacturing", resp_ok["payload"]["company_name"])

        # 429 Rate Limit
        resp_rate = MockProviderSimulator.simulate_call("company_enrichment", "RATE_LIMIT")
        self.assertEqual(resp_rate["status_code"], 429)
        self.assertEqual(resp_rate["headers"]["Retry-After"], "60")

        # 500 Server Error
        resp_500 = MockProviderSimulator.simulate_call("company_enrichment", "SERVER_ERROR")
        self.assertEqual(resp_500["status_code"], 500)

    # --- 7. Marketplace Engine & Security Review ---

    def test_21_marketplace_security_review_approval(self):
        clean_manifest = {
            "id": "clean_connector_01",
            "name": "Clean Public Scraper",
            "version": "1.0.0",
            "category": "Signal Ingestion",
            "capabilities": ["FETCH"],
            "required_permissions": ["companies:read"],
            "allowed_domains": ["api.public.org"],
        }
        is_approved, issues, status = MarketplaceSecurityReviewer.evaluate_package(
            manifest_data=clean_manifest,
            source_code="def run(): return {'status': 'ok'}",
        )
        self.assertTrue(is_approved)
        self.assertEqual(status, "APPROVED")
        self.assertEqual(len(issues), 0)

    def test_22_marketplace_security_review_rejection_forbidden_permissions(self):
        unsafe_manifest = {
            "id": "unsafe_conn_02",
            "name": "Database Dumping Connector",
            "version": "1.0.0",
            "capabilities": ["FETCH"],
            "required_permissions": ["database:raw_sql"],
        }
        is_approved, issues, status = MarketplaceSecurityReviewer.evaluate_package(manifest_data=unsafe_manifest)
        self.assertFalse(is_approved)
        self.assertEqual(status, "REJECTED")
        self.assertTrue(any("database:raw_sql" in err for err in issues))

    def test_23_marketplace_publish_install_uninstall(self):
        engine = MarketplaceEngine(self.db)
        manifest = {
            "id": "partner_odoo_scanner",
            "name": "Partner Odoo ERP Scanner",
            "version": "1.0.0",
            "category": "ERP Detection",
            "capabilities": ["FETCH", "ENRICH"],
            "required_permissions": ["companies:read", "research:run"],
            "allowed_domains": ["partner.odoo-scanner.com"],
        }

        # 1. Publish
        connector, listing, status = engine.publish_connector(
            connector_id="partner_odoo_scanner",
            name="Partner Odoo ERP Scanner",
            version="1.0.0",
            category="ERP Detection",
            description="Deep scans enterprise Odoo endpoints",
            author_name="Enterprise ERP Specialists",
            manifest=manifest,
            trust_level=MarketplaceTrustLevel.VERIFIED_PARTNER,
        )
        self.assertEqual(connector.id, "partner_odoo_scanner")
        self.assertEqual(listing.security_review_status, "APPROVED")
        self.assertTrue(connector.is_verified)

        # 2. Browse
        listings = engine.list_marketplace_connectors(category="ERP Detection")
        self.assertTrue(any(l["connector_id"] == "partner_odoo_scanner" for l in listings))

        # 3. Install
        installation = engine.install_connector(
            workspace_id=self.workspace.id,
            connector_id="partner_odoo_scanner",
            configuration={"scan_depth": 3},
        )
        self.assertEqual(installation.status, "ACTIVE")
        self.assertEqual(installation.configuration["scan_depth"], 3)

        # 4. Uninstall
        uninstalled = engine.uninstall_connector(installation.id)
        self.assertTrue(uninstalled)
        self.assertEqual(installation.status, "UNINSTALLED")


if __name__ == "__main__":
    unittest.main()
