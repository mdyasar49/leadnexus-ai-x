"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform, Connector SDK & Marketplace Routes
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.developer_platform import (
    ApplicationScope,
    ApplicationStatus,
    ApplicationType,
    Connector,
    ConnectorExecution,
    ConnectorInstallation,
    DeveloperAccount,
    DeveloperApplication,
    DeveloperAuditEvent,
    DeveloperRole,
    DeveloperSandbox,
    MarketplaceListing,
    MarketplaceTrustLevel,
    ScopeRiskLevel,
)
from packages.developer_platform.connector_sdk import (
    ConnectorContext,
    CustomWebhookExporterConnector,
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
)
from packages.developer_platform.marketplace_engine import (
    MarketplaceEngine,
)

router = APIRouter(prefix="/api/v1/developer", tags=["Developer Platform & Connector SDK"])

# Initialize default runner with built-in reference connectors
runner = SandboxedConnectorRunner()
runner.register_connector(PublicJobFeedConnector())
runner.register_connector(CustomWebhookExporterConnector())


# --- Request/Response Schemas ---

class CreateDeveloperAccountRequest(BaseModel):
    name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    role: str = Field(default="DEVELOPER")


class CreateApplicationRequest(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None
    application_type: str = Field(default="PRIVATE")
    requested_scopes: List[str] = Field(default_factory=list)


class ExecuteConnectorRequest(BaseModel):
    connector_id: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    granted_scopes: List[str] = Field(default_factory=list)
    is_sandbox: bool = False


class InstantiateTemplateRequest(BaseModel):
    template_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PublishConnectorRequest(BaseModel):
    connector_id: str
    name: str
    version: str = "1.0.0"
    category: str
    description: str
    author_name: str
    manifest: Dict[str, Any]
    trust_level: str = "COMMUNITY"
    source_code: Optional[str] = None


class InstallConnectorRequest(BaseModel):
    connector_id: str
    configuration: Dict[str, Any] = Field(default_factory=dict)


class CreateSandboxRequest(BaseModel):
    name: str
    app_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class SeedSandboxRequest(BaseModel):
    record_count: int = 3


class SimulateProviderRequest(BaseModel):
    endpoint_type: str
    simulation_mode: str = "SUCCESS"


# --- Developer Accounts ---

@router.get("/accounts")
def list_developer_accounts(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    accounts = db.query(DeveloperAccount).filter(DeveloperAccount.workspace_id == workspace.id).all()
    return {"accounts": accounts}


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_developer_account(
    req: CreateDeveloperAccountRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperAppService(db)
    account = service.register_developer_account(
        workspace_id=workspace.id,
        name=req.name,
        email=req.email,
        role=DeveloperRole(req.role) if req.role in [r.value for r in DeveloperRole] else DeveloperRole.DEVELOPER,
    )
    return {"account": account}


# --- Applications & Credentials ---

@router.get("/apps")
def list_applications(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    apps = db.query(DeveloperApplication).filter(DeveloperApplication.workspace_id == workspace.id).all()
    result = []
    for app in apps:
        scopes = db.query(ApplicationScope).filter(ApplicationScope.app_id == app.id).all()
        result.append({
            "id": app.id,
            "name": app.name,
            "description": app.description,
            "status": app.status,
            "application_type": app.application_type,
            "client_id": app.client_id,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "scopes": [{"scope_name": s.scope_name, "risk_level": s.risk_level, "is_approved": s.is_approved} for s in scopes],
        })
    return {"applications": result}


@router.post("/apps", status_code=status.HTTP_201_CREATED)
def create_application(
    req: CreateApplicationRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperAppService(db)
    app, client_secret, scopes = service.create_application(
        workspace_id=workspace.id,
        name=req.name,
        description=req.description,
        application_type=ApplicationType(req.application_type) if req.application_type in [t.value for t in ApplicationType] else ApplicationType.PRIVATE,
        requested_scopes=req.requested_scopes,
    )
    return {
        "application": {
            "id": app.id,
            "name": app.name,
            "client_id": app.client_id,
            "status": app.status,
        },
        "client_secret": client_secret,  # Only displayed once!
        "scopes": [{"scope_name": s.scope_name, "risk_level": s.risk_level, "is_approved": s.is_approved} for s in scopes],
        "warning": "Store client_secret securely. It will not be shown again.",
    }


@router.post("/apps/{app_id}/rotate-secret")
def rotate_application_secret(
    app_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperAppService(db)
    try:
        app, new_secret = service.rotate_client_secret(app_id=app_id, actor_id=user.id)
        return {
            "application_id": app.id,
            "client_id": app.client_id,
            "new_client_secret": new_secret,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Scopes Catalog & Approvals ---

@router.get("/scopes/catalog")
def get_scopes_catalog():
    return {"scopes": ScopeCatalog.KNOWN_SCOPES}


@router.post("/scopes/{scope_id}/approve")
def approve_scope(
    scope_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperAppService(db)
    try:
        scope = service.approve_scope(scope_id=scope_id, approver_id=user.id)
        return {"scope": scope}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Connectors & Sandboxed Execution ---

@router.get("/connectors")
def list_connectors(
    db: Session = Depends(get_sync_db),
):
    connectors = db.query(Connector).all()
    # If no DB records yet, return registered runner connectors
    if not connectors:
        builtins = [
            runner.get_connector("public_job_feed_connector").manifest.__dict__,
            runner.get_connector("webhook_intelligence_exporter").manifest.__dict__,
        ]
        return {"connectors": builtins}
    return {"connectors": connectors}


@router.post("/connectors/execute")
def execute_connector(
    req: ExecuteConnectorRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    ctx = ConnectorContext(
        workspace_id=workspace.id,
        installation_id="direct_run",
        configuration=req.configuration,
        granted_scopes=req.granted_scopes,
        is_sandbox=req.is_sandbox,
    )
    result = runner.execute_connector(req.connector_id, ctx)

    # Record execution metrics if status is known
    try:
        exec_record = ConnectorExecution(
            id=str(uuid.uuid4()),
            installation_id="direct_run",
            status=result.status.value,
            duration_ms=result.duration_ms,
            records_processed=result.records_processed,
            error_message=result.error_message,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(exec_record)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "connector_id": req.connector_id,
        "status": result.status.value,
        "records_processed": result.records_processed,
        "duration_ms": result.duration_ms,
        "records": result.records,
        "logs": result.logs,
        "error_message": result.error_message,
    }


# --- Templates ---

@router.get("/templates")
def list_integration_templates():
    templates = TemplateRegistry.list_templates()
    return {"templates": templates}


@router.post("/templates/{template_id}/instantiate")
def instantiate_template(
    template_id: str,
    req: InstantiateTemplateRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    try:
        instance = IntegrationTemplateEngine.instantiate_template(
            template_id=template_id,
            parameters=req.parameters,
            workspace_id=workspace.id,
        )
        return {"template_instance": instance}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Marketplace ---

@router.get("/marketplace/listings")
def browse_marketplace(
    category: Optional[str] = None,
    trust_level: Optional[str] = None,
    db: Session = Depends(get_sync_db),
):
    engine = MarketplaceEngine(db)
    listings = engine.list_marketplace_connectors(category=category, trust_level=trust_level)
    return {"listings": listings}


@router.post("/marketplace/publish", status_code=status.HTTP_201_CREATED)
def publish_connector_to_marketplace(
    req: PublishConnectorRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    engine = MarketplaceEngine(db)
    try:
        connector, listing, review_status = engine.publish_connector(
            connector_id=req.connector_id,
            name=req.name,
            version=req.version,
            category=req.category,
            description=req.description,
            author_name=req.author_name,
            manifest=req.manifest,
            trust_level=MarketplaceTrustLevel(req.trust_level) if req.trust_level in [t.value for t in MarketplaceTrustLevel] else MarketplaceTrustLevel.COMMUNITY,
            source_code=req.source_code,
        )
        return {
            "connector_id": connector.id,
            "title": listing.title,
            "security_review_status": review_status,
            "trust_level": connector.trust_level,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/marketplace/install")
def install_connector(
    req: InstallConnectorRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    engine = MarketplaceEngine(db)
    try:
        installation = engine.install_connector(
            workspace_id=workspace.id,
            connector_id=req.connector_id,
            configuration=req.configuration,
        )
        return {"installation": installation}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/marketplace/installations/{installation_id}")
def uninstall_connector(
    installation_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    engine = MarketplaceEngine(db)
    success = engine.uninstall_connector(installation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Installation not found.")
    return {"status": "UNINSTALLED", "installation_id": installation_id}


# --- Sandbox Management ---

@router.get("/sandbox")
def list_sandboxes(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    sandboxes = db.query(DeveloperSandbox).filter(DeveloperSandbox.workspace_id == workspace.id).all()
    return {"sandboxes": sandboxes}


@router.post("/sandbox", status_code=status.HTTP_201_CREATED)
def create_sandbox(
    req: CreateSandboxRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperSandboxService(db)
    sandbox = service.create_sandbox(
        workspace_id=workspace.id,
        name=req.name,
        app_id=req.app_id,
        config=req.config,
    )
    return {"sandbox": sandbox}


@router.post("/sandbox/{sandbox_id}/seed")
def seed_sandbox(
    sandbox_id: str,
    req: SeedSandboxRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperSandboxService(db)
    try:
        result = service.seed_synthetic_data(
            sandbox_id=sandbox_id,
            workspace_id=workspace.id,
            record_count=req.record_count,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sandbox/{sandbox_id}/reset")
def reset_sandbox(
    sandbox_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    service = DeveloperSandboxService(db)
    success = service.reset_sandbox(sandbox_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sandbox not found.")
    return {"status": "RESET", "sandbox_id": sandbox_id}


@router.post("/sandbox/simulate-provider")
def simulate_provider_call(
    req: SimulateProviderRequest,
    user: User = Depends(get_current_user),
):
    result = MockProviderSimulator.simulate_call(
        endpoint_type=req.endpoint_type,
        simulation_mode=req.simulation_mode,
    )
    return result
