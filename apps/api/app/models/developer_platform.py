import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


# --- Enums ---

class ApplicationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    ARCHIVED = "ARCHIVED"


class ApplicationType(str, enum.Enum):
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    TENANT_APP = "TENANT_APP"
    PUBLIC_APP = "PUBLIC_APP"
    PARTNER_APP = "PARTNER_APP"
    SYSTEM_APP = "SYSTEM_APP"


class DeveloperRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"
    AUDITOR = "AUDITOR"


class ScopeRiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    RESTRICTED = "RESTRICTED"


class MarketplaceTrustLevel(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    VERIFIED_PARTNER = "VERIFIED_PARTNER"
    COMMUNITY = "COMMUNITY"
    PRIVATE = "PRIVATE"
    INTERNAL = "INTERNAL"


# --- Developer Account Models ---

class DeveloperAccount(Base):
    __tablename__ = "developer_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), default=DeveloperRole.DEVELOPER.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Developer Application Models ---

class DeveloperApplication(Base):
    __tablename__ = "developer_applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    developer_id = Column(String(36), ForeignKey("developer_accounts.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default=ApplicationStatus.ACTIVE.value, nullable=False)
    application_type = Column(String(50), default=ApplicationType.PRIVATE.value, nullable=False)
    client_id = Column(String(64), nullable=False, unique=True, index=True)
    client_secret_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_dev_app_ws_status", "workspace_id", "status"),
    )


class DeveloperApplicationVersion(Base):
    __tablename__ = "developer_application_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey("developer_applications.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ApplicationScope(Base):
    __tablename__ = "application_scopes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(String(36), ForeignKey("developer_applications.id"), nullable=False, index=True)
    scope_name = Column(String(100), nullable=False)  # e.g. "companies:read", "research:run"
    risk_level = Column(String(50), default=ScopeRiskLevel.LOW.value, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    granted_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Connector Models ---

class Connector(Base):
    __tablename__ = "connectors"

    id = Column(String(100), primary_key=True)  # e.g. "custom_job_scraper", "custom_bi_exporter"
    name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0.0", nullable=False)
    category = Column(String(100), nullable=False)
    trust_level = Column(String(50), default=MarketplaceTrustLevel.COMMUNITY.value, nullable=False)
    manifest = Column(JSON, default=dict)
    permissions = Column(JSON, default=list)
    is_published = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ConnectorVersion(Base):
    __tablename__ = "connector_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id = Column(String(100), ForeignKey("connectors.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    package_hash = Column(String(64), nullable=False)
    manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ConnectorInstallation(Base):
    __tablename__ = "connector_installations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    connector_id = Column(String(100), ForeignKey("connectors.id"), nullable=False, index=True)
    status = Column(String(50), default="ACTIVE", nullable=False)
    configuration = Column(JSON, default=dict)
    installed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ConnectorExecution(Base):
    __tablename__ = "connector_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    installation_id = Column(String(36), ForeignKey("connector_installations.id"), nullable=False, index=True)
    status = Column(String(50), default="SUCCESS", nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    records_processed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Integration Templates ---

class IntegrationTemplate(Base):
    __tablename__ = "integration_templates"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)
    version = Column(String(50), default="1.0.0", nullable=False)
    variables_schema = Column(JSON, default=dict)
    steps_definition = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationTemplateVersion(Base):
    __tablename__ = "integration_template_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(100), ForeignKey("integration_templates.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    definition = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Developer Sandbox Models ---

class DeveloperSandbox(Base):
    __tablename__ = "developer_sandboxes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    app_id = Column(String(36), ForeignKey("developer_applications.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False)
    config = Column(JSON, default=dict)
    is_test_data = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Marketplace Models ---

class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_id = Column(String(100), ForeignKey("connectors.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    author_name = Column(String(255), nullable=False)
    rating = Column(Float, default=5.0, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    security_review_status = Column(String(50), default="APPROVED", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Developer Audit Event ---

class DeveloperAuditEvent(Base):
    __tablename__ = "developer_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

