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

class IntegrationType(str, enum.Enum):
    DATA_SOURCE = "DATA_SOURCE"
    DATA_DESTINATION = "DATA_DESTINATION"
    BIDIRECTIONAL_SYNC = "BIDIRECTIONAL_SYNC"
    EVENT_SOURCE = "EVENT_SOURCE"
    EVENT_DESTINATION = "EVENT_DESTINATION"
    ENRICHMENT_PROVIDER = "ENRICHMENT_PROVIDER"
    VERIFICATION_PROVIDER = "VERIFICATION_PROVIDER"
    ANALYTICS_DESTINATION = "ANALYTICS_DESTINATION"
    STORAGE_DESTINATION = "STORAGE_DESTINATION"
    IDENTITY_PROVIDER = "IDENTITY_PROVIDER"
    NOTIFICATION_PROVIDER = "NOTIFICATION_PROVIDER"


class ConnectionStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    EXPIRED = "EXPIRED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class AuthType(str, enum.Enum):
    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    WEBHOOK_SIGNATURE = "WEBHOOK_SIGNATURE"
    NONE = "NONE"


class ConflictResolution(str, enum.Enum):
    KEEP_CANONICAL = "KEEP_CANONICAL"
    ACCEPT_EXTERNAL = "ACCEPT_EXTERNAL"
    MERGE = "MERGE"
    REQUEST_REVIEW = "REQUEST_REVIEW"
    IGNORE = "IGNORE"


class IntegrationJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# --- Integration Provider Models ---

class IntegrationProvider(Base):
    __tablename__ = "integration_providers"

    id = Column(String(100), primary_key=True)  # e.g. "google_sheets", "github", "slack"
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # PRODUCTIVITY, COMMUNICATION, CODE, VERIFICATION
    version = Column(String(50), default="1.0.0", nullable=False)
    capabilities = Column(JSON, default=list)  # ["IMPORT", "EXPORT", "SYNC", "WEBHOOK", "VERIFY"]
    authentication_type = Column(String(50), default=AuthType.API_KEY.value, nullable=False)
    configuration_schema = Column(JSON, default=dict)
    input_schema = Column(JSON, default=dict)
    output_schema = Column(JSON, default=dict)
    rate_policy = Column(JSON, default=dict)
    retry_policy = Column(JSON, default=dict)
    security_policy = Column(JSON, default=dict)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationProviderVersion(Base):
    __tablename__ = "integration_provider_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(String(100), ForeignKey("integration_providers.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Connection & Credential Models ---

class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider_id = Column(String(100), ForeignKey("integration_providers.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default=ConnectionStatus.DISCONNECTED.value, nullable=False)
    auth_type = Column(String(50), default=AuthType.API_KEY.value, nullable=False)
    configuration = Column(JSON, default=dict)
    credential_reference = Column(String(255), nullable=True)  # Reference to SecretManager / Encrypted Key ID
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_health_check = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_conn_ws_status", "workspace_id", "status"),
    )


class IntegrationCredentialReference(Base):
    __tablename__ = "integration_credential_references"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(String(36), ForeignKey("integration_connections.id"), nullable=False, index=True)
    credential_type = Column(String(50), nullable=False)  # OAUTH_TOKEN, API_KEY, SERVICE_ACCOUNT, WEBHOOK_SECRET
    encrypted_secret = Column(Text, nullable=False)  # Encrpyted via secret manager
    expires_at = Column(DateTime, nullable=True)
    rotated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Mapping & Field Transformation Models ---

class IntegrationMapping(Base):
    __tablename__ = "integration_mappings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    connection_id = Column(String(36), ForeignKey("integration_connections.id"), nullable=True, index=True)
    target_entity = Column(String(50), default="COMPANY", nullable=False)  # COMPANY, PERSON, CONTACT, LEAD
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationFieldMapping(Base):
    __tablename__ = "integration_field_mappings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mapping_id = Column(String(36), ForeignKey("integration_mappings.id"), nullable=False, index=True)
    source_field = Column(String(255), nullable=False)
    target_field = Column(String(255), nullable=False)
    transformation_rule = Column(String(50), default="DIRECT", nullable=False)  # TRIM, LOWERCASE, NORMALIZE_EMAIL, etc.
    default_value = Column(String(255), nullable=True)
    is_required = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Job & Task Models ---

class IntegrationJob(Base):
    __tablename__ = "integration_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    connection_id = Column(String(36), ForeignKey("integration_connections.id"), nullable=False, index=True)
    job_type = Column(String(50), default="IMPORT", nullable=False)  # IMPORT, EXPORT, SYNC
    status = Column(String(50), default=IntegrationJobStatus.PENDING.value, nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    failed_records = Column(Integer, default=0, nullable=False)
    error_summary = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationTask(Base):
    __tablename__ = "integration_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("integration_jobs.id"), nullable=False, index=True)
    task_type = Column(String(50), nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)
    payload = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Conflict Resolution ---

class IntegrationConflict(Base):
    __tablename__ = "integration_conflicts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    canonical_value = Column(JSON, nullable=True)
    external_value = Column(JSON, nullable=True)
    source = Column(String(100), nullable=False)
    confidence = Column(Float, default=0.5, nullable=False)
    resolution = Column(String(50), default=ConflictResolution.KEEP_CANONICAL.value, nullable=False)
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Webhooks Models ---

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    target_url = Column(String(1024), nullable=False)
    secret_token = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    events = Column(JSON, default=list)  # ["RESEARCH_COMPLETED", "LEAD_SCORE_CHANGED"]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endpoint_id = Column(String(36), ForeignKey("webhook_endpoints.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    filter_expression = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    provider = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict)
    payload_hash = Column(String(64), nullable=False, index=True)
    signature_verified = Column(Boolean, default=False, nullable=False)
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endpoint_id = Column(String(36), ForeignKey("webhook_endpoints.id"), nullable=False, index=True)
    event_id = Column(String(36), ForeignKey("webhook_events.id"), nullable=False, index=True)
    status = Column(String(50), default="SUCCESS", nullable=False)
    attempt_count = Column(Integer, default=1, nullable=False)
    last_status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    latency_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- API Keys & Service Accounts ---

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(String(16), nullable=False)
    scopes = Column(JSON, default=list)  # ["companies:read", "leads:read", "research:run"]
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ServiceAccount(Base):
    __tablename__ = "service_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    client_id = Column(String(64), nullable=False, unique=True, index=True)
    client_secret_hash = Column(String(64), nullable=False)
    scopes = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Idempotency & Raw Payloads ---

class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    response_code = Column(Integer, default=200, nullable=False)
    response_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_idem_ws_key", "workspace_id", "idempotency_key", unique=True),
    )


class RawIntegrationPayload(Base):
    __tablename__ = "raw_integration_payloads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    connection_id = Column(String(36), ForeignKey("integration_connections.id"), nullable=True, index=True)
    provider = Column(String(100), nullable=False)
    payload_hash = Column(String(64), nullable=False, index=True)
    raw_data = Column(JSON, default=dict)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Health & Audit ---

class IntegrationHealth(Base):
    __tablename__ = "integration_health"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(String(36), ForeignKey("integration_connections.id"), nullable=True, index=True)
    provider_id = Column(String(100), ForeignKey("integration_providers.id"), nullable=False, index=True)
    status = Column(String(50), default="HEALTHY", nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    error_rate = Column(Float, default=0.0, nullable=False)
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class IntegrationAuditEvent(Base):
    __tablename__ = "integration_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

