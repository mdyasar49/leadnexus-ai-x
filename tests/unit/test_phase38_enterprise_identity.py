"""
LeadNexus AI X — Phase 38 Test Suite (ChatGPT Master Roadmap)
Enterprise Identity & Workforce Access Platform
Tests: SAML 2.0, OIDC, SCIM 2.0 Provisioning/Deprovisioning, JIT Ephemeral Access,
PAM Break-Glass Emergency Access, Access Certification Campaigns, Service Identities,
Session Posture & Revocation Kill-Switches, and Identity Auditing.
"""

import sys
import os
import uuid
import base64
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

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
from app.models.enterprise_identity import (
    SSOProviderConfig,
    GroupRoleMapping,
    SCIMUserRecord,
    SCIMGroupRecord,
    JITAccessGrant,
    PAMEmergencyAccess,
    AccessReviewCampaign,
    AccessReviewItem,
    ServiceIdentity,
    ActiveUserSession,
    IdentityAuditEvent,
    SSOProviderType,
    JITStatus,
    PAMStatus,
    ReviewDecision,
)
from app.security.tokens import create_access_token
from packages.identity import (
    SAMLOIDCEngine,
    SCIMEngine,
    JITPAMEngine,
    SessionPostureManager,
    AccessReviewManager,
)


class TestPhase38EnterpriseIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()

        cls.org = cls.db.query(Organization).first()
        if not cls.org:
            cls.org = Organization(id=str(uuid.uuid4()), name="Identity Org", slug="identity-org")
            cls.db.add(cls.org)
            cls.db.commit()

        cls.ws = cls.db.query(Workspace).filter(Workspace.organization_id == cls.org.id).first()
        if not cls.ws:
            cls.ws = Workspace(id=str(uuid.uuid4()), organization_id=cls.org.id, name="Identity Workspace", slug="id-ws")
            cls.db.add(cls.ws)
            cls.db.commit()

        cls.user = cls.db.query(User).first()
        if not cls.user:
            cls.user = User(
                id=str(uuid.uuid4()),
                email="identity_admin@leadnexus.io",
                hashed_password="hash",
                full_name="Identity Administrator",
                is_active=True,
            )
            cls.db.add(cls.user)
            cls.db.commit()

        cls.token = create_access_token(user_id=cls.user.id)
        cls.headers = {"Authorization": f"Bearer {cls.token}", "X-Workspace-ID": cls.ws.id}
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_saml_metadata_and_assertion_parsing(self):
        engine = SAMLOIDCEngine()
        metadata_xml = engine.generate_sp_metadata_xml()
        self.assertIn("EntityDescriptor", metadata_xml)
        self.assertIn("AssertionConsumerService", metadata_xml)

        # Mock SAML Response XML
        raw_xml = f"""<?xml version="1.0"?>
        <saml2p:Response xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion" Issuer="https://idp.okta.com">
            <saml2:Assertion>
                <saml2:Subject>
                    <saml2:NameID>saml_executive@enterprise.com</saml2:NameID>
                </saml2:Subject>
                <saml2:AttributeStatement>
                    <saml2:Attribute Name="firstName">
                        <saml2:AttributeValue>Jane</saml2:AttributeValue>
                    </saml2:Attribute>
                    <saml2:Attribute Name="lastName">
                        <saml2:AttributeValue>Doe</saml2:AttributeValue>
                    </saml2:Attribute>
                    <saml2:Attribute Name="groups">
                        <saml2:AttributeValue>LeadNexus-Admins</saml2:AttributeValue>
                        <saml2:AttributeValue>Corporate-Users</saml2:AttributeValue>
                    </saml2:Attribute>
                </saml2:AttributeStatement>
            </saml2:Assertion>
        </saml2p:Response>"""

        b64_response = base64.b64encode(raw_xml.encode("utf-8")).decode("utf-8")
        parsed = engine.parse_saml_assertion(b64_response)
        self.assertEqual(parsed["email"], "saml_executive@enterprise.com")
        self.assertEqual(parsed["first_name"], "Jane")
        self.assertEqual(parsed["last_name"], "Doe")
        self.assertIn("LeadNexus-Admins", parsed["groups"])

        # Role resolution
        mapping_rules = {"LeadNexus-Admins": "admin", "Corporate-Users": "viewer"}
        resolved = engine.resolve_mapped_role(parsed["groups"], mapping_rules, default_role="viewer")
        self.assertEqual(resolved, "admin")

    def test_02_oidc_claims_processing(self):
        engine = SAMLOIDCEngine()
        claims = {
            "sub": "auth0|987654321",
            "email": "alex.analyst@company.com",
            "name": "Alex Analyst",
            "given_name": "Alex",
            "family_name": "Analyst",
            "roles": ["Data-Analysts"],
        }
        identity = engine.process_oidc_claims(claims)
        self.assertEqual(identity["email"], "alex.analyst@company.com")
        self.assertEqual(identity["first_name"], "Alex")
        self.assertIn("Data-Analysts", identity["groups"])

        resolved = engine.resolve_mapped_role(["Data-Analysts"], {"Data-Analysts": "analyst"})
        self.assertEqual(resolved, "analyst")

    def test_03_scim_service_provider_config_and_schemas(self):
        res = self.client.get("/api/v1/identity/scim/v2/ServiceProviderConfig")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["patch"]["supported"])
        self.assertTrue(data["filter"]["supported"])

        res_schemas = self.client.get("/api/v1/identity/scim/v2/Schemas")
        self.assertEqual(res_schemas.status_code, 200)
        self.assertGreaterEqual(res_schemas.json()["totalResults"], 2)

    def test_04_scim_user_crud_and_deprovisioning(self):
        unique_user = f"scim_{uuid.uuid4().hex[:6]}"
        user_payload = {
            "userName": f"{unique_user}@infogenx.com",
            "externalId": f"ext_{unique_user}",
            "name": {"givenName": "Robert", "familyName": "Smith"},
            "emails": [{"value": f"{unique_user}@infogenx.com", "primary": True}],
            "active": True,
        }

        # Create
        res = self.client.post("/api/v1/identity/scim/v2/Users", json=user_payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        created = res.json()
        user_id = created["id"]
        self.assertEqual(created["userName"], f"{unique_user}@infogenx.com")
        self.assertTrue(created["active"])

        # Get
        res_get = self.client.get(f"/api/v1/identity/scim/v2/Users/{user_id}", headers=self.headers)
        self.assertEqual(res_get.status_code, 200)

        # Deprovision via PATCH (active = false)
        patch_payload = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        }
        res_patch = self.client.patch(f"/api/v1/identity/scim/v2/Users/{user_id}", json=patch_payload, headers=self.headers)
        self.assertEqual(res_patch.status_code, 200)
        self.assertFalse(res_patch.json()["active"])

        # Delete (Hard purge)
        res_del = self.client.delete(f"/api/v1/identity/scim/v2/Users/{user_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 204)

    def test_05_jit_role_elevation_workflow(self):
        # Request elevation
        payload = {"requested_role": "admin", "reason": "Quarterly audit review investigation", "duration_minutes": 30}
        res = self.client.post("/api/v1/identity/jit/requests", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        grant = res.json()["grant"]
        grant_id = grant["id"]
        self.assertEqual(grant["status"], JITStatus.PENDING)

        # Approve elevation
        res_appr = self.client.post(f"/api/v1/identity/jit/requests/{grant_id}/approve", headers=self.headers)
        self.assertEqual(res_appr.status_code, 200)
        self.assertEqual(res_appr.json()["grant"]["status"], JITStatus.APPROVED)
        self.assertIsNotNone(res_appr.json()["grant"]["expires_at"])

        # Auto-expiration engine unit test
        class DummyGrant:
            status = JITStatus.APPROVED
            expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        dummy = DummyGrant()
        expired = JITPAMEngine.check_and_expire_grant(dummy)
        self.assertTrue(expired)
        self.assertEqual(dummy.status, JITStatus.EXPIRED)

    def test_06_pam_break_glass_emergency_access(self):
        payload = {
            "ticket_reference": "INC-88910",
            "justification": "Production database connection pool exhaustion diagnosis and emergency remediation",
            "duration_minutes": 45,
        }
        res = self.client.post("/api/v1/identity/pam/break-glass", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        pam_session = res.json()["pam_record"]
        pam_id = pam_session["id"]
        self.assertEqual(pam_session["status"], PAMStatus.ACTIVE)

        # List active PAM sessions
        res_list = self.client.get("/api/v1/identity/pam/active", headers=self.headers)
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(s["id"] == pam_id for s in res_list.json()["pam_sessions"]))

        # Terminate PAM session early
        res_term = self.client.post(f"/api/v1/identity/pam/{pam_id}/terminate", headers=self.headers)
        self.assertEqual(res_term.status_code, 200)
        self.assertEqual(res_term.json()["status"], PAMStatus.TERMINATED)

    def test_07_access_review_campaigns_and_certification(self):
        payload = {"campaign_name": "Q4 Enterprise Security Certification", "due_days": 10}
        res = self.client.post("/api/v1/identity/access-reviews/campaigns", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        campaign_id = res.json()["campaign"]["id"]

        # Get review queue items
        res_items = self.client.get(f"/api/v1/identity/access-reviews/campaigns/{campaign_id}/items", headers=self.headers)
        self.assertEqual(res_items.status_code, 200)
        items = res_items.json()["items"]
        self.assertGreaterEqual(len(items), 1)

        item_id = items[0]["id"]
        # Certify: Approve
        res_decide = self.client.post(
            f"/api/v1/identity/access-reviews/items/{item_id}/decide",
            json={"decision": "APPROVED", "notes": "Verified business necessity with manager"},
            headers=self.headers,
        )
        self.assertEqual(res_decide.status_code, 200)
        self.assertEqual(res_decide.json()["decision"], "APPROVED")

    def test_08_service_identities_and_credentials(self):
        payload = {
            "name": "Datadog Integration Daemon",
            "allowed_scopes": ["leads:read", "metrics:read"],
            "allowed_ips": ["192.168.1.0/24"],
            "ttl_days": 180,
        }
        res = self.client.post("/api/v1/identity/service-identities", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        svc = res.json()["service_identity"]
        self.assertTrue(svc["client_id"].startswith("lnx_svc_"))
        self.assertTrue(res.json()["client_secret_raw"].startswith("lnx_sec_"))

        svc_id = svc["id"]
        # Delete
        res_del = self.client.delete(f"/api/v1/identity/service-identities/{svc_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 200)

    def test_09_session_posture_and_remote_revocation(self):
        # Create active session record via manager
        token_str = f"session-token-{uuid.uuid4().hex}"
        sess_dict = SessionPostureManager.create_session_record(
            user_id=self.user.id,
            session_token=token_str,
            ip_address="198.51.100.22",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        )
        sess = ActiveUserSession(**sess_dict)
        self.db.add(sess)
        self.db.commit()

        # Query sessions via API
        res = self.client.get("/api/v1/identity/sessions", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(s["id"] == sess.id for s in res.json()["sessions"]))

        # Revoke single session
        res_rev = self.client.post(f"/api/v1/identity/sessions/{sess.id}/revoke", headers=self.headers)
        self.assertEqual(res_rev.status_code, 200)

        # Revoke all sessions
        res_rev_all = self.client.post("/api/v1/identity/sessions/revoke-all", headers=self.headers)
        self.assertEqual(res_rev_all.status_code, 200)
        self.assertEqual(res_rev_all.json()["status"], "all_revoked")

    def test_10_identity_audit_log_verification(self):
        res = self.client.get("/api/v1/identity/audit-events?limit=20", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        events = res.json()["audit_events"]
        self.assertGreaterEqual(len(events), 1)
        event_types = [e["event_type"] for e in events]
        self.assertTrue(any("JIT" in t or "PAM" in t or "SCIM" in t or "SESSION" in t for t in event_types))


if __name__ == "__main__":
    unittest.main()
