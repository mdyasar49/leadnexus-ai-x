"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform
Developer Application Service: Application registration, client credentials, scope hierarchy, and secret rotation.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.developer_platform import (
    ApplicationScope,
    ApplicationStatus,
    ApplicationType,
    DeveloperAccount,
    DeveloperApplication,
    DeveloperAuditEvent,
    DeveloperRole,
    ScopeRiskLevel,
)


class ScopeCatalog:
    """Enterprise Scope Catalog defining permissions, descriptions, and risk levels."""

    KNOWN_SCOPES: Dict[str, Dict[str, Any]] = {
        "companies:read": {
            "description": "Read company intelligence, domains, and technologies",
            "risk": ScopeRiskLevel.LOW,
        },
        "companies:write": {
            "description": "Submit new company records or suggested attributes",
            "risk": ScopeRiskLevel.MEDIUM,
        },
        "contacts:read": {
            "description": "Read verified contact points and titles",
            "risk": ScopeRiskLevel.LOW,
        },
        "contacts:write": {
            "description": "Submit contact verification updates",
            "risk": ScopeRiskLevel.MEDIUM,
        },
        "research:run": {
            "description": "Trigger and monitor autonomous research workflows",
            "risk": ScopeRiskLevel.MEDIUM,
        },
        "exports:create": {
            "description": "Export verified lead intelligence to authorized webhooks or datasets",
            "risk": ScopeRiskLevel.HIGH,
        },
        "webhooks:manage": {
            "description": "Configure and listen to real-time platform event webhooks",
            "risk": ScopeRiskLevel.MEDIUM,
        },
        "admin:manage": {
            "description": "Administrative management of workspace developer settings",
            "risk": ScopeRiskLevel.RESTRICTED,
        },
        "admin:all": {
            "description": "Full wildcard administrative access across the workspace",
            "risk": ScopeRiskLevel.RESTRICTED,
        },
    }

    @classmethod
    def get_risk_level(cls, scope_name: str) -> ScopeRiskLevel:
        meta = cls.KNOWN_SCOPES.get(scope_name)
        return meta["risk"] if meta else ScopeRiskLevel.HIGH

    @classmethod
    def is_valid_scope(cls, scope_name: str) -> bool:
        return scope_name in cls.KNOWN_SCOPES


class DeveloperAppService:
    """Manages developer accounts, registered applications, client credentials, and access scopes."""

    CLIENT_ID_PREFIX = "lnx_app_"
    CLIENT_SECRET_PREFIX = "lnx_sec_"

    @classmethod
    def generate_credentials(cls) -> Tuple[str, str, str]:
        """Generates client_id, plaintext client_secret, and sha256 client_secret_hash."""
        client_id = f"{cls.CLIENT_ID_PREFIX}{secrets.token_hex(16)}"
        plaintext_secret = f"{cls.CLIENT_SECRET_PREFIX}{secrets.token_urlsafe(32)}"
        secret_hash = hashlib.sha256(plaintext_secret.encode("utf-8")).hexdigest()
        return client_id, plaintext_secret, secret_hash

    @classmethod
    def hash_secret(cls, secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @classmethod
    def verify_secret(cls, provided_secret: str, stored_hash: str) -> bool:
        computed_hash = cls.hash_secret(provided_secret)
        return hmac.compare_digest(computed_hash, stored_hash)

    def __init__(self, db_session: Any):
        self.db = db_session

    def register_developer_account(
        self,
        workspace_id: str,
        name: str,
        email: str,
        role: DeveloperRole = DeveloperRole.DEVELOPER,
    ) -> DeveloperAccount:
        """Registers a developer account inside a workspace."""
        account = DeveloperAccount(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name=name,
            email=email.strip().lower(),
            role=role.value if isinstance(role, DeveloperRole) else role,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def create_application(
        self,
        workspace_id: str,
        name: str,
        developer_id: Optional[str] = None,
        description: Optional[str] = None,
        application_type: ApplicationType = ApplicationType.PRIVATE,
        requested_scopes: Optional[List[str]] = None,
        auto_approve_low_risk: bool = True,
    ) -> Tuple[DeveloperApplication, str, List[ApplicationScope]]:
        """
        Creates a developer application, issues credentials, and requests requested scopes.
        Returns: (DeveloperApplication, plaintext_client_secret, List[ApplicationScope])
        Note: plaintext_client_secret is returned only once at creation time!
        """
        client_id, plaintext_secret, secret_hash = self.generate_credentials()

        app = DeveloperApplication(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            developer_id=developer_id,
            name=name,
            description=description,
            status=ApplicationStatus.ACTIVE.value,
            application_type=application_type.value if isinstance(application_type, ApplicationType) else application_type,
            client_id=client_id,
            client_secret_hash=secret_hash,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(app)
        self.db.flush()

        # Add requested scopes
        assigned_scopes: List[ApplicationScope] = []
        if requested_scopes:
            for scope_name in requested_scopes:
                risk = ScopeCatalog.get_risk_level(scope_name)
                # Auto-approve LOW and MEDIUM if allowed, require review for HIGH or RESTRICTED
                is_approved = auto_approve_low_risk if risk in (ScopeRiskLevel.LOW, ScopeRiskLevel.MEDIUM) else False

                scope_record = ApplicationScope(
                    id=str(uuid.uuid4()),
                    app_id=app.id,
                    scope_name=scope_name,
                    risk_level=risk.value,
                    is_approved=is_approved,
                    granted_by=developer_id if is_approved else None,
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(scope_record)
                assigned_scopes.append(scope_record)

        # Audit Event
        audit = DeveloperAuditEvent(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            actor_id=developer_id or "system",
            action="APPLICATION_CREATED",
            target_type="DEVELOPER_APP",
            target_id=app.id,
            details={"name": name, "client_id": client_id, "scopes_count": len(assigned_scopes)},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(app)

        return app, plaintext_secret, assigned_scopes

    def rotate_client_secret(self, app_id: str, actor_id: Optional[str] = None) -> Tuple[DeveloperApplication, str]:
        """Rotates the client secret for an existing developer application."""
        app = self.db.query(DeveloperApplication).filter(DeveloperApplication.id == app_id).first()
        if not app:
            raise ValueError(f"Application with ID '{app_id}' not found.")

        _, new_secret, new_hash = self.generate_credentials()
        app.client_secret_hash = new_hash
        app.updated_at = datetime.now(timezone.utc)

        audit = DeveloperAuditEvent(
            id=str(uuid.uuid4()),
            workspace_id=app.workspace_id,
            actor_id=actor_id or "system",
            action="CREDENTIAL_ROTATED",
            target_type="DEVELOPER_APP",
            target_id=app.id,
            details={"client_id": app.client_id},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(app)
        return app, new_secret

    def approve_scope(self, scope_id: str, approver_id: str) -> ApplicationScope:
        """Approves a high or restricted risk scope."""
        scope = self.db.query(ApplicationScope).filter(ApplicationScope.id == scope_id).first()
        if not scope:
            raise ValueError(f"Scope with ID '{scope_id}' not found.")

        scope.is_approved = True
        scope.granted_by = approver_id
        self.db.commit()
        self.db.refresh(scope)
        return scope

    def authenticate_app(self, client_id: str, client_secret: str) -> Optional[DeveloperApplication]:
        """Authenticates client_id and client_secret, verifying app status."""
        app = self.db.query(DeveloperApplication).filter(DeveloperApplication.client_id == client_id).first()
        if not app:
            return None

        if app.status != ApplicationStatus.ACTIVE.value:
            return None

        if not self.verify_secret(client_secret, app.client_secret_hash):
            return None

        return app

    def get_approved_scopes(self, app_id: str) -> List[str]:
        """Returns list of approved scope names for an application."""
        scopes = self.db.query(ApplicationScope).filter(
            ApplicationScope.app_id == app_id,
            ApplicationScope.is_approved == True,
        ).all()
        return [s.scope_name for s in scopes]
