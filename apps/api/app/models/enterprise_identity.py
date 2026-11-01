"""
Enterprise Identity & Workforce Access Models (Phase 38)
Supports SSO (SAML 2.0 / OIDC), SCIM 2.0 directory sync, JIT access, PAM break-glass,
access reviews, service accounts, and session posture controls.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class SSOProviderType:
    SAML = "SAML"
    OIDC = "OIDC"


class JITStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class PAMStatus:
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


class AccessReviewStatus:
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ReviewDecision:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"


class IdentityEventType:
    SSO_LOGIN = "SSO_LOGIN"
    SCIM_PROVISION = "SCIM_PROVISION"
    SCIM_DEPROVISION = "SCIM_DEPROVISION"
    JIT_REQUEST = "JIT_REQUEST"
    JIT_APPROVAL = "JIT_APPROVAL"
    PAM_ACTIVATION = "PAM_ACTIVATION"
    ACCESS_REVIEW_DECISION = "ACCESS_REVIEW_DECISION"
    SESSION_REVOCATION = "SESSION_REVOCATION"


class SSOProviderConfig(Base):
    """Configuration for enterprise SSO identity providers (SAML 2.0 or OIDC)."""

    __tablename__ = "sso_provider_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    provider_type = Column(String(16), nullable=False, default=SSOProviderType.SAML)
    name = Column(String(128), nullable=False)
    entity_id_or_issuer = Column(String(255), nullable=False)
    sso_url = Column(String(512), nullable=False)
    certificate_or_jwks_url = Column(Text, nullable=True)
    client_id = Column(String(128), nullable=True)
    client_secret_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    jit_provisioning_enabled = Column(Boolean, default=True, nullable=False)
    default_role = Column(String(32), default="viewer", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class GroupRoleMapping(Base):
    """Maps Identity Provider groups (from SAML/OIDC or SCIM) to LeadNexus roles."""

    __tablename__ = "group_role_mappings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(String(36), ForeignKey("sso_provider_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    idp_group_name = Column(String(128), nullable=False)
    target_role = Column(String(32), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SCIMUserRecord(Base):
    """SCIM 2.0 user directory sync record."""

    __tablename__ = "scim_user_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = Column(String(128), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    user_name = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False)
    given_name = Column(String(128), nullable=True)
    family_name = Column(String(128), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    raw_attributes = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class SCIMGroupRecord(Base):
    """SCIM 2.0 group directory sync record."""

    __tablename__ = "scim_group_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = Column(String(128), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    members = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class JITAccessGrant(Base):
    """Just-In-Time role elevation request and grant."""

    __tablename__ = "jit_access_grants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    requested_role = Column(String(32), nullable=False)
    reason = Column(Text, nullable=False)
    approved_by = Column(String(36), nullable=True)
    status = Column(String(16), default=JITStatus.PENDING, nullable=False)
    duration_minutes = Column(Integer, default=60, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PAMEmergencyAccess(Base):
    """Privileged Access Management (PAM) Break-Glass emergency access session."""

    __tablename__ = "pam_emergency_accesses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    ticket_reference = Column(String(64), nullable=False)
    justification = Column(Text, nullable=False)
    status = Column(String(16), default=PAMStatus.ACTIVE, nullable=False)
    duration_minutes = Column(Integer, default=30, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AccessReviewCampaign(Base):
    """Quarterly/Periodic access certification campaign."""

    __tablename__ = "access_review_campaigns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_name = Column(String(128), nullable=False)
    status = Column(String(16), default=AccessReviewStatus.ACTIVE, nullable=False)
    due_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AccessReviewItem(Base):
    """Individual user entitlement item inside an access review campaign."""

    __tablename__ = "access_review_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String(36), ForeignKey("access_review_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    user_email = Column(String(255), nullable=False)
    assigned_role = Column(String(32), nullable=False)
    decision = Column(String(16), default=ReviewDecision.PENDING, nullable=False)
    reviewer_id = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class ServiceIdentity(Base):
    """Machine/Service account identity for automated system-to-system access."""

    __tablename__ = "service_identities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    client_id = Column(String(64), unique=True, nullable=False, index=True)
    client_secret_hash = Column(String(255), nullable=False)
    allowed_scopes = Column(JSON, default=list, nullable=False)
    allowed_ips = Column(JSON, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ActiveUserSession(Base):
    """User session posture, device tracking, and instant remote revocation."""

    __tablename__ = "active_user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    session_token_hash = Column(String(64), unique=True, nullable=False, index=True)
    ip_address = Column(String(64), nullable=False)
    user_agent = Column(String(255), nullable=False)
    device_info = Column(String(128), default="Desktop Browser", nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    last_activity_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IdentityAuditEvent(Base):
    """Audit log for identity events (SAML, OIDC, SCIM, JIT, PAM, Reviews, Sessions)."""

    __tablename__ = "identity_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True)
    event_type = Column(String(32), nullable=False)
    severity = Column(String(16), default="INFO", nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
