"""
LeadNexus AI X — Phase 35 Test Suite
Enterprise Webhook Delivery Engine, Signature Verification, Replay Defense & Dead-Letter Redrive
"""

import sys
import os
import time
import uuid
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Ensure API and root are in python path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.main import app
from app.db.session import SessionLocal, sync_engine
from app.db.base import Base
from app.models.tenant import Organization, Workspace
from app.models.user import User
from app.security.tokens import create_access_token
from app.models.webhooks import (
    EnterpriseWebhookEndpoint,
    EnterpriseWebhookDelivery,
    WebhookRedriveJob,
)
from packages.webhooks import (
    WebhookSignatureSigner,
    ReplayDefenseGuard,
    WebhookCircuitBreaker,
    CircuitState,
    BackoffScheduler,
    WebhookDeliveryService,
    WebhookRedriveService,
)


class TestPhase35EnterpriseWebhooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        # Setup test organization and workspace
        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Test Org Phase 35", slug="test-org-p35")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.workspace = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.workspace:
            cls.workspace = Workspace(
                id=str(uuid.uuid4()),
                organization_id=cls.org.id,
                name="Test Workspace Phase 35",
                slug="test-ws-p35",
            )
            cls.db.add(cls.workspace)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="test_webhooks@leadnexus.ai",
                hashed_password="mock_password",
                is_active=True,
                is_superuser=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_signature_generation_and_constant_time_verification(self):
        """Verifies HMAC-SHA256 signature generation and constant-time verification."""
        secret = WebhookSignatureSigner.generate_secret_token()
        self.assertTrue(secret.startswith("whsec_"))

        payload = {"company_id": "c100", "technology": "Odoo ERP", "intent_score": 92}
        canonical_str = WebhookSignatureSigner.canonicalize_payload(payload)
        now_ts = int(time.time())
        nonce = "nonce_12345678"

        digest = WebhookSignatureSigner.compute_signature(canonical_str, secret, now_ts, nonce)
        signature_header = f"v1={digest}"

        is_valid = WebhookSignatureSigner.verify_signature(
            payload_str=canonical_str,
            secret=secret,
            signature_header=signature_header,
            timestamp=now_ts,
            nonce=nonce,
        )
        self.assertTrue(is_valid, "Valid signature must verify successfully.")

    def test_02_signature_tamper_detection(self):
        """Ensures that any single-character payload tampering invalidates the signature."""
        secret = "whsec_test_secret_for_tamper"
        payload = {"company_id": "c100", "score": 90}
        canonical_str = WebhookSignatureSigner.canonicalize_payload(payload)
        now_ts = int(time.time())
        nonce = "nonce_abc"

        headers = WebhookSignatureSigner.generate_signed_headers(payload, secret, now_ts, nonce)
        sig_header = headers[WebhookSignatureSigner.HEADER_SIGNATURE]

        # Tamper payload
        tampered_payload = {"company_id": "c100", "score": 91}
        tampered_canonical = WebhookSignatureSigner.canonicalize_payload(tampered_payload)

        is_valid = WebhookSignatureSigner.verify_signature(
            payload_str=tampered_canonical,
            secret=secret,
            signature_header=sig_header,
            timestamp=now_ts,
            nonce=nonce,
        )
        self.assertFalse(is_valid, "Tampered payload must fail HMAC signature verification.")

    def test_03_replay_defense_timestamp_window(self):
        """Tests that stale timestamps and future timestamps beyond skew tolerance are rejected."""
        guard = ReplayDefenseGuard(tolerance_seconds=300)
        current_time = 1700000000.0

        # Valid recent timestamp (2 minutes ago)
        valid_ts = int(current_time - 120)
        ok, reason = guard.validate_request(valid_ts, "nonce_recent", current_time)
        self.assertTrue(ok, f"Expected valid timestamp, got {reason}")

        # Stale timestamp (6 minutes ago > 300s)
        stale_ts = int(current_time - 360)
        ok_stale, reason_stale = guard.validate_request(stale_ts, "nonce_stale", current_time)
        self.assertFalse(ok_stale)
        self.assertIn("expired", reason_stale.lower())

        # Futuristic timestamp (2 minutes in future > 60s)
        future_ts = int(current_time + 120)
        ok_future, reason_future = guard.validate_request(future_ts, "nonce_future", current_time)
        self.assertFalse(ok_future)
        self.assertIn("futuristic", reason_future.lower())

    def test_04_replay_defense_nonce_deduplication(self):
        """Ensures duplicate nonces are rejected as replay attacks."""
        guard = ReplayDefenseGuard(tolerance_seconds=300)
        current_time = 1700000000.0
        ts = int(current_time - 10)
        nonce = "duplicate_nonce_sample"

        # First delivery: Accepted
        ok1, _ = guard.validate_request(ts, nonce, current_time)
        self.assertTrue(ok1)

        # Second delivery with identical nonce: Rejected
        ok2, reason = guard.validate_request(ts, nonce, current_time)
        self.assertFalse(ok2)
        self.assertIn("Replay attack", reason)

    def test_05_circuit_breaker_tripping_on_failures(self):
        """Tests per-endpoint circuit breaker tripping from CLOSED to OPEN after 5 failures."""
        cb = WebhookCircuitBreaker(failure_threshold=5, recovery_timeout_seconds=30.0)
        ep_id = "test-endpoint-trip"

        self.assertEqual(cb.get_state(ep_id), CircuitState.CLOSED)

        # Simulate 4 failures
        for _ in range(4):
            cb.record_failure(ep_id)
            self.assertEqual(cb.get_state(ep_id), CircuitState.CLOSED)

        # 5th failure trips to OPEN
        cb.record_failure(ep_id)
        self.assertEqual(cb.get_state(ep_id), CircuitState.OPEN)

        can_proceed, reason = cb.can_dispatch(ep_id)
        self.assertFalse(can_proceed)
        self.assertIn("OPEN", reason)

    def test_06_circuit_breaker_recovery_half_open_to_closed(self):
        """Tests circuit breaker transitioning to HALF_OPEN after timeout and resetting to CLOSED on success."""
        cb = WebhookCircuitBreaker(failure_threshold=2, recovery_timeout_seconds=10.0)
        ep_id = "test-endpoint-recover"
        t0 = 1000.0

        cb.record_failure(ep_id, current_time=t0)
        cb.record_failure(ep_id, current_time=t0)
        self.assertEqual(cb.get_state(ep_id, current_time=t0), CircuitState.OPEN)

        # Before recovery timeout: remains OPEN
        self.assertEqual(cb.get_state(ep_id, current_time=t0 + 5.0), CircuitState.OPEN)

        # After recovery timeout: transitions to HALF_OPEN
        self.assertEqual(cb.get_state(ep_id, current_time=t0 + 11.0), CircuitState.HALF_OPEN)

        # Probe succeeds: resets to CLOSED
        cb.record_success(ep_id)
        self.assertEqual(cb.get_state(ep_id), CircuitState.CLOSED)

    def test_07_exponential_backoff_with_jitter(self):
        """Verifies exponential retry intervals and bounded jitter."""
        scheduler = BackoffScheduler(base_delay_seconds=2.0, max_delay_seconds=60.0, exponential_factor=2.0)

        # Attempt 1 raw = 2.0s
        d1 = scheduler.compute_backoff(attempt=1, apply_jitter=False)
        self.assertEqual(d1, 2.0)

        # Attempt 3 raw = 2.0 * 4 = 8.0s
        d3 = scheduler.compute_backoff(attempt=3, apply_jitter=False)
        self.assertEqual(d3, 8.0)

        # Attempt 10 capped at max_delay_seconds (60.0s)
        d10 = scheduler.compute_backoff(attempt=10, apply_jitter=False)
        self.assertEqual(d10, 60.0)

        # With jitter, delay should fall between 50% and 100% of raw
        jittered = scheduler.compute_backoff(attempt=3, apply_jitter=True)
        self.assertTrue(4.0 <= jittered <= 8.0)

    def test_08_signed_delivery_dispatch_and_audit(self):
        """Tests WebhookDeliveryService dispatch with signed headers and successful audit persistence."""
        # Mock transport returning HTTP 200
        mock_transport = lambda url, headers, body, timeout: (200, '{"received": true}')
        service = WebhookDeliveryService(http_transport=mock_transport)

        endpoint = EnterpriseWebhookEndpoint(
            id=str(uuid.uuid4()),
            tenant_id=self.workspace.id,
            name="Audited Delivery Target",
            url="https://mock.enterprise.internal/webhook",
            secret_token=WebhookSignatureSigner.generate_secret_token(),
            event_patterns=["company.*"],
            is_active=True,
        )
        self.db.add(endpoint)
        self.db.commit()

        delivery = service.dispatch(
            db=self.db,
            endpoint=endpoint,
            event_id="evt-101",
            event_type="company.created",
            payload={"name": "Canberra Logistics", "country": "Australia"},
        )

        self.assertEqual(delivery.status, "SUCCESS")
        self.assertEqual(delivery.status_code, 200)
        self.assertIn(WebhookSignatureSigner.HEADER_SIGNATURE, delivery.headers)
        self.assertIn(WebhookSignatureSigner.HEADER_TIMESTAMP, delivery.headers)
        self.assertIn(WebhookSignatureSigner.HEADER_NONCE, delivery.headers)

    def test_09_dead_letter_queue_and_redrive_job(self):
        """Tests that exhausted retries route to DEAD_LETTER and can be redriven via redrive batch job."""
        # Mock transport returning HTTP 500
        mock_failing_transport = lambda url, headers, body, timeout: (500, "Internal Server Error")
        failing_service = WebhookDeliveryService(http_transport=mock_failing_transport)

        endpoint = EnterpriseWebhookEndpoint(
            id=str(uuid.uuid4()),
            tenant_id=self.workspace.id,
            name="Failing DLQ Target",
            url="https://failing.enterprise.internal/webhook",
            secret_token=WebhookSignatureSigner.generate_secret_token(),
            event_patterns=["lead.*"],
            is_active=True,
        )
        self.db.add(endpoint)
        self.db.commit()

        # Dispatch with max_retries reached (attempt 3 of 3)
        delivery = failing_service.dispatch(
            db=self.db,
            endpoint=endpoint,
            event_id="evt-dlq-1",
            event_type="lead.qualified",
            payload={"lead_id": "ld-999"},
            attempt_number=3,
            max_retries=3,
        )
        self.assertEqual(delivery.status, "DEAD_LETTER")

        # Now redrive using a recovering transport
        recovering_transport = lambda url, headers, body, timeout: (200, "OK")
        recovering_service = WebhookDeliveryService(http_transport=recovering_transport)
        redrive_engine = WebhookRedriveService(delivery_service=recovering_service)

        job = redrive_engine.create_redrive_job(
            db=self.db,
            tenant_id=self.workspace.id,
            initiated_by=str(self.user.id),
            endpoint_id=endpoint.id,
            filter_status="DEAD_LETTER",
            max_attempts=10,
        )

        self.assertEqual(job.status, "COMPLETED")
        self.assertGreaterEqual(job.total_eligible, 1)
        self.assertGreaterEqual(job.success_count, 1)

    def test_10_api_endpoints_integration(self):
        """Tests FastAPI REST endpoints for registration, listing, and signature verification."""
        # 1. Register endpoint
        create_resp = self.client.post(
            "/api/v1/webhooks/endpoints",
            json={
                "name": "API Test Endpoint",
                "url": "https://api.subscriber.com/webhook",
                "event_patterns": ["company.*", "evidence.added"],
            },
            headers=self.headers,
        )
        self.assertEqual(create_resp.status_code, 201)
        created_data = create_resp.json()
        ep_id = created_data["id"]
        secret = created_data["secret_token"]
        self.assertTrue(secret.startswith("whsec_"))

        # 2. List endpoints
        list_resp = self.client.get("/api/v1/webhooks/endpoints", headers=self.headers)
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(any(e["id"] == ep_id for e in list_resp.json()))

        # 3. Test incoming verification endpoint
        now_epoch = int(time.time())
        nonce = "nonce_api_test_123"
        payload = {"ping": True}
        headers = WebhookSignatureSigner.generate_signed_headers(payload, secret, now_epoch, nonce)
        sig_header = headers[WebhookSignatureSigner.HEADER_SIGNATURE]

        verify_resp = self.client.post(
            "/api/v1/webhooks/verify-incoming",
            json={
                "payload": payload,
                "secret_token": secret,
                "signature_header": sig_header,
                "timestamp": now_epoch,
                "nonce": nonce,
            },
        )
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(verify_resp.json()["is_valid"])

        # 4. Verify tampered payload fails
        tampered_verify_resp = self.client.post(
            "/api/v1/webhooks/verify-incoming",
            json={
                "payload": {"ping": False},  # Tampered!
                "secret_token": secret,
                "signature_header": sig_header,
                "timestamp": now_epoch,
                "nonce": "different_nonce",
            },
        )
        self.assertEqual(tampered_verify_resp.status_code, 200)
        self.assertFalse(tampered_verify_resp.json()["is_valid"])


if __name__ == "__main__":
    unittest.main()
