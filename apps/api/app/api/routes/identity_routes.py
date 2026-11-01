"""
Enterprise Identity & Workforce Access API Routes (Phase 38)
Provides SSO, SAML 2.0 / OIDC callbacks, SCIM 2.0 provisioning, JIT elevations,
PAM break-glass emergencies, access certification campaigns, service accounts, and session posture controls.
"""

from datetime import datetime, timezone, timedelta
import secrets
import hashlib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
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
    AccessReviewStatus,
    ReviewDecision,
    IdentityEventType,
)
from packages.identity.saml_oidc_engine import SAMLOIDCEngine, IdentitySecurityError
from packages.identity.scim_engine import SCIMEngine, SCIMError
from packages.identity.jit_pam_engine import JITPAMEngine, AccessElevationError
from packages.identity.session_posture_manager import SessionPostureManager
from packages.identity.access_review_manager import AccessReviewManager

router = APIRouter(prefix="/identity", tags=["Enterprise Identity & Workforce Access"])


# --- Schemas ---

class SSOProviderCreate(BaseModel):
    provider_type: str = Field(default="SAML")  # SAML or OIDC
    name: str
    entity_id_or_issuer: str
    sso_url: str
    certificate_or_jwks_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    jit_provisioning_enabled: bool = True
    default_role: str = "viewer"


class GroupRoleMappingCreate(BaseModel):
    provider_id: str
    idp_group_name: str
    target_role: str  # admin, member, analyst, viewer


class SAMLConsumeRequest(BaseModel):
    provider_id: str
    saml_response_base64: str
    relay_state: Optional[str] = None


class OIDCCallbackRequest(BaseModel):
    provider_id: str
    claims: Dict[str, Any]


class JITRequestCreate(BaseModel):
    requested_role: str
    reason: str
    duration_minutes: int = 60


class PAMBreakGlassRequest(BaseModel):
    ticket_reference: str
    justification: str
    duration_minutes: int = 30


class AccessReviewCampaignCreate(BaseModel):
    campaign_name: str
    due_days: int = 14


class ReviewDecisionRequest(BaseModel):
    decision: str  # APPROVED or REVOKED
    notes: Optional[str] = None


class ServiceIdentityCreate(BaseModel):
    name: str
    allowed_scopes: List[str] = Field(default_factory=list)
    allowed_ips: List[str] = Field(default_factory=list)
    ttl_days: Optional[int] = 365


# --- Audit Helper ---

def log_identity_audit(
    db: Session,
    workspace_id: str,
    event_type: str,
    user_id: Optional[str] = None,
    severity: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
):
    audit = IdentityAuditEvent(
        workspace_id=workspace_id,
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        details=details or {},
        timestamp=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()


# --- SSO & SAML / OIDC Endpoints ---

@router.get("/sso/providers")
def list_sso_providers(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Lists configured SSO identity providers for current workspace."""
    providers = db.query(SSOProviderConfig).filter(SSOProviderConfig.workspace_id == ws.id).all()
    return {"providers": providers}


@router.post("/sso/providers", status_code=status.HTTP_201_CREATED)
def create_sso_provider(
    payload: SSOProviderCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Configures a new SAML or OIDC Identity Provider."""
    secret_hash = None
    if payload.client_secret:
        secret_hash = hashlib.sha256(payload.client_secret.encode("utf-8")).hexdigest()

    provider = SSOProviderConfig(
        workspace_id=ws.id,
        provider_type=payload.provider_type.upper(),
        name=payload.name,
        entity_id_or_issuer=payload.entity_id_or_issuer,
        sso_url=payload.sso_url,
        certificate_or_jwks_url=payload.certificate_or_jwks_url,
        client_id=payload.client_id,
        client_secret_hash=secret_hash,
        jit_provisioning_enabled=payload.jit_provisioning_enabled,
        default_role=payload.default_role,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    log_identity_audit(
        db,
        ws.id,
        event_type="SSO_PROVIDER_CONFIGURED",
        user_id=current_user.id,
        details={"provider_id": provider.id, "type": provider.provider_type, "name": provider.name},
    )

    return {"status": "created", "provider": provider}


@router.get("/sso/metadata.xml")
def get_sp_saml_metadata():
    """Generates standard SAML 2.0 Service Provider Metadata XML."""
    engine = SAMLOIDCEngine()
    xml_content = engine.generate_sp_metadata_xml()
    return Response(content=xml_content, media_type="application/xml")


@router.post("/sso/saml/consume")
def consume_saml_assertion(
    payload: SAMLConsumeRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    """Consumes and parses a SAML 2.0 response from an IdP, extracting claims and mapping roles."""
    provider = db.query(SSOProviderConfig).filter(
        SSOProviderConfig.id == payload.provider_id,
        SSOProviderConfig.workspace_id == ws.id,
    ).first()

    if not provider or not provider.is_active:
        raise HTTPException(status_code=400, detail="SSO Provider is inactive or not found.")

    engine = SAMLOIDCEngine()
    try:
        identity = engine.parse_saml_assertion(payload.saml_response_base64)
    except IdentitySecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch group mappings
    mappings = db.query(GroupRoleMapping).filter(
        GroupRoleMapping.provider_id == provider.id,
        GroupRoleMapping.is_active == True,
    ).all()
    mapping_dict = {m.idp_group_name: m.target_role for m in mappings}

    resolved_role = engine.resolve_mapped_role(
        identity.get("groups", []),
        mapping_dict,
        default_role=provider.default_role,
    )

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SSO_LOGIN,
        details={"email": identity.get("email"), "role": resolved_role, "protocol": "SAML"},
    )

    return {
        "status": "authenticated",
        "email": identity.get("email"),
        "first_name": identity.get("first_name"),
        "last_name": identity.get("last_name"),
        "resolved_role": resolved_role,
        "groups": identity.get("groups", []),
        "relay_state": payload.relay_state,
    }


@router.post("/sso/oidc/callback")
def handle_oidc_callback(
    payload: OIDCCallbackRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    """Processes OpenID Connect claims, maps roles, and performs JIT provisioning check."""
    provider = db.query(SSOProviderConfig).filter(
        SSOProviderConfig.id == payload.provider_id,
        SSOProviderConfig.workspace_id == ws.id,
    ).first()

    if not provider or not provider.is_active:
        raise HTTPException(status_code=400, detail="OIDC Provider is inactive or not found.")

    engine = SAMLOIDCEngine()
    try:
        identity = engine.process_oidc_claims(payload.claims)
    except IdentitySecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))

    mappings = db.query(GroupRoleMapping).filter(
        GroupRoleMapping.provider_id == provider.id,
        GroupRoleMapping.is_active == True,
    ).all()
    mapping_dict = {m.idp_group_name: m.target_role for m in mappings}

    resolved_role = engine.resolve_mapped_role(
        identity.get("groups", []),
        mapping_dict,
        default_role=provider.default_role,
    )

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SSO_LOGIN,
        details={"email": identity.get("email"), "role": resolved_role, "protocol": "OIDC"},
    )

    return {
        "status": "authenticated",
        "email": identity.get("email"),
        "first_name": identity.get("first_name"),
        "last_name": identity.get("last_name"),
        "resolved_role": resolved_role,
        "groups": identity.get("groups", []),
    }


# --- Group Mappings ---

@router.get("/group-mappings")
def list_group_mappings(
    provider_id: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    query = db.query(GroupRoleMapping)
    if provider_id:
        query = query.filter(GroupRoleMapping.provider_id == provider_id)
    mappings = query.all()
    return {"mappings": mappings}


@router.post("/group-mappings", status_code=status.HTTP_201_CREATED)
def create_group_mapping(
    payload: GroupRoleMappingCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    mapping = GroupRoleMapping(
        provider_id=payload.provider_id,
        idp_group_name=payload.idp_group_name,
        target_role=payload.target_role.lower(),
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return {"status": "created", "mapping": mapping}


@router.delete("/group-mappings/{mapping_id}")
def delete_group_mapping(
    mapping_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    mapping = db.query(GroupRoleMapping).filter(GroupRoleMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found.")
    db.delete(mapping)
    db.commit()
    return {"status": "deleted"}


# --- SCIM 2.0 Directory Sync Endpoints ---

@router.get("/scim/v2/ServiceProviderConfig")
def scim_service_provider_config():
    """RFC 7644 SCIM 2.0 Service Provider Configuration."""
    return SCIMEngine.get_service_provider_config()


@router.get("/scim/v2/Schemas")
def scim_schemas():
    """RFC 7643 SCIM 2.0 Resource Schemas."""
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 2,
        "itemsPerPage": 2,
        "startIndex": 1,
        "Resources": [
            {"id": SCIMEngine.SCIM_USER_SCHEMA, "name": "User"},
            {"id": SCIMEngine.SCIM_GROUP_SCHEMA, "name": "Group"},
        ],
    }


@router.get("/scim/v2/Users")
def scim_list_users(
    filter: Optional[str] = Query(None),
    startIndex: int = Query(1),
    count: int = Query(100),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    """Lists SCIM users with optional filter."""
    query = db.query(SCIMUserRecord).filter(SCIMUserRecord.workspace_id == ws.id)
    if filter and "userName eq" in filter:
        target_user = filter.split("userName eq")[-1].replace('"', '').strip()
        query = query.filter(SCIMUserRecord.user_name == target_user)

    total = query.count()
    users = query.offset(startIndex - 1).limit(count).all()
    formatted = [SCIMEngine.format_scim_user(u) for u in users]
    return SCIMEngine.format_list_response(formatted, start_index=startIndex, total_count=total)


@router.post("/scim/v2/Users", status_code=status.HTTP_201_CREATED)
def scim_create_user(
    payload: Dict[str, Any],
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    """Provisions a new user into the workspace via SCIM 2.0."""
    user_name = payload.get("userName")
    emails = payload.get("emails", [])
    primary_email = emails[0].get("value") if emails else user_name
    name_obj = payload.get("name", {})

    if not user_name or not primary_email:
        raise HTTPException(status_code=400, detail="userName and email are required for SCIM provisioning.")

    existing = db.query(SCIMUserRecord).filter(
        SCIMUserRecord.workspace_id == ws.id,
        SCIMUserRecord.user_name == user_name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User {user_name} already exists.")

    scim_user = SCIMUserRecord(
        external_id=payload.get("externalId", user_name),
        workspace_id=ws.id,
        user_name=user_name,
        email=primary_email,
        given_name=name_obj.get("givenName"),
        family_name=name_obj.get("familyName"),
        active=payload.get("active", True),
        raw_attributes=payload,
    )
    db.add(scim_user)
    db.commit()
    db.refresh(scim_user)

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SCIM_PROVISION,
        details={"email": scim_user.email, "userName": scim_user.user_name},
    )

    return SCIMEngine.format_scim_user(scim_user)


@router.get("/scim/v2/Users/{user_id}")
def scim_get_user(
    user_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    user = db.query(SCIMUserRecord).filter(
        SCIMUserRecord.id == user_id,
        SCIMUserRecord.workspace_id == ws.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return SCIMEngine.format_scim_user(user)


@router.patch("/scim/v2/Users/{user_id}")
def scim_patch_user(
    user_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    """Applies SCIM 2.0 PATCH operations (e.g., active: false to deprovision)."""
    user = db.query(SCIMUserRecord).filter(
        SCIMUserRecord.id == user_id,
        SCIMUserRecord.workspace_id == ws.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    operations = payload.get("Operations", [])
    for op in operations:
        val = op.get("value")
        path = op.get("path")
        if path == "active" or (isinstance(val, dict) and "active" in val):
            new_active = val if path == "active" else val["active"]
            user.active = bool(new_active)
            if not user.active:
                log_identity_audit(
                    db,
                    ws.id,
                    event_type=IdentityEventType.SCIM_DEPROVISION,
                    details={"email": user.email, "userName": user.user_name},
                )

    db.commit()
    db.refresh(user)
    return SCIMEngine.format_scim_user(user)


@router.delete("/scim/v2/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def scim_delete_user(
    user_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
):
    user = db.query(SCIMUserRecord).filter(
        SCIMUserRecord.id == user_id,
        SCIMUserRecord.workspace_id == ws.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SCIM_DEPROVISION,
        details={"email": user.email, "action": "HARD_DELETE"},
    )
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- JIT Role Elevation & PAM Endpoints ---

@router.get("/jit/requests")
def list_jit_requests(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    grants = db.query(JITAccessGrant).filter(JITAccessGrant.workspace_id == ws.id).all()
    # Auto-expire
    for g in grants:
        if JITPAMEngine.check_and_expire_grant(g):
            db.commit()
    return {"grants": grants}


@router.post("/jit/requests", status_code=status.HTTP_201_CREATED)
def request_jit_access(
    payload: JITRequestCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Requests Just-In-Time ephemeral role elevation."""
    grant = JITAccessGrant(
        workspace_id=ws.id,
        user_id=current_user.id,
        requested_role=payload.requested_role,
        reason=payload.reason,
        duration_minutes=payload.duration_minutes,
        status=JITStatus.PENDING,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.JIT_REQUEST,
        user_id=current_user.id,
        details={"requested_role": payload.requested_role, "reason": payload.reason},
    )

    return {"status": "requested", "grant": grant}


@router.post("/jit/requests/{grant_id}/approve")
def approve_jit_access(
    grant_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Approves a pending JIT elevation request."""
    grant = db.query(JITAccessGrant).filter(
        JITAccessGrant.id == grant_id,
        JITAccessGrant.workspace_id == ws.id,
    ).first()
    if not grant:
        raise HTTPException(status_code=404, detail="Grant request not found.")

    try:
        res = JITPAMEngine.approve_jit_request(grant, approver_id=current_user.id)
        db.commit()
        db.refresh(grant)
    except AccessElevationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.JIT_APPROVAL,
        user_id=grant.user_id,
        details={"approved_by": current_user.id, "role": grant.requested_role, "expires_at": grant.expires_at.isoformat()},
    )

    return {"status": "approved", "grant": grant}


@router.post("/pam/break-glass", status_code=status.HTTP_201_CREATED)
def trigger_pam_break_glass(
    payload: PAMBreakGlassRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Activates high-severity Break-Glass emergency access."""
    try:
        pam_dict = JITPAMEngine.trigger_pam_break_glass(
            workspace_id=ws.id,
            user_id=current_user.id,
            ticket_reference=payload.ticket_reference,
            justification=payload.justification,
            duration_minutes=payload.duration_minutes,
        )
    except AccessElevationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pam_record = PAMEmergencyAccess(**pam_dict)
    db.add(pam_record)
    db.commit()
    db.refresh(pam_record)

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.PAM_ACTIVATION,
        user_id=current_user.id,
        severity="CRITICAL",
        details={
            "ticket": payload.ticket_reference,
            "justification": payload.justification,
            "expires_at": pam_record.expires_at.isoformat(),
        },
    )

    return {"status": "activated", "pam_record": pam_record}


@router.get("/pam/active")
def list_active_pam_sessions(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    sessions = db.query(PAMEmergencyAccess).filter(
        PAMEmergencyAccess.workspace_id == ws.id,
        PAMEmergencyAccess.status == PAMStatus.ACTIVE,
    ).all()
    # Check expiry
    for s in sessions:
        exp = s.expires_at.replace(tzinfo=timezone.utc) if s.expires_at.tzinfo is None else s.expires_at
        if now > exp:
            s.status = PAMStatus.EXPIRED
            db.commit()
    return {"pam_sessions": sessions}


@router.post("/pam/{pam_id}/terminate")
def terminate_pam_session(
    pam_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    pam_record = db.query(PAMEmergencyAccess).filter(
        PAMEmergencyAccess.id == pam_id,
        PAMEmergencyAccess.workspace_id == ws.id,
    ).first()
    if not pam_record:
        raise HTTPException(status_code=404, detail="PAM session not found.")

    res = JITPAMEngine.terminate_pam_session(pam_record)
    db.commit()
    return res


# --- Access Reviews ---

@router.get("/access-reviews/campaigns")
def list_campaigns(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    campaigns = db.query(AccessReviewCampaign).filter(
        AccessReviewCampaign.workspace_id == ws.id
    ).all()
    return {"campaigns": campaigns}


@router.post("/access-reviews/campaigns", status_code=status.HTTP_201_CREATED)
def create_access_review_campaign(
    payload: AccessReviewCampaignCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Launches an access certification campaign across active workspace users."""
    camp_dict = AccessReviewManager.create_campaign(
        workspace_id=ws.id,
        campaign_name=payload.campaign_name,
        due_days=payload.due_days,
    )
    campaign = AccessReviewCampaign(**camp_dict)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Populate items from current users
    workspace_users = [{"id": current_user.id, "email": current_user.email, "role": "admin"}]
    # Also include SCIM users if any
    scim_users = db.query(SCIMUserRecord).filter(SCIMUserRecord.workspace_id == ws.id).all()
    for su in scim_users:
        workspace_users.append({"id": su.id, "email": su.email, "role": "member"})

    items = AccessReviewManager.populate_review_items(campaign.id, workspace_users)
    for it in items:
        db.add(AccessReviewItem(**it))
    db.commit()

    return {"status": "created", "campaign": campaign, "items_count": len(items)}


@router.get("/access-reviews/campaigns/{campaign_id}/items")
def get_campaign_items(
    campaign_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    items = db.query(AccessReviewItem).filter(AccessReviewItem.campaign_id == campaign_id).all()
    stats = AccessReviewManager.calculate_campaign_progress(items)
    return {"items": items, "stats": stats}


@router.post("/access-reviews/items/{item_id}/decide")
def decide_access_review_item(
    item_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    item = db.query(AccessReviewItem).filter(AccessReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found.")

    res = AccessReviewManager.record_decision(
        item,
        reviewer_id=current_user.id,
        decision=payload.decision.upper(),
        notes=payload.notes,
    )
    db.commit()

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.ACCESS_REVIEW_DECISION,
        user_id=item.user_id,
        details={"decision": item.decision, "reviewer": current_user.id, "role": item.assigned_role},
    )

    return res


# --- Service / Machine Identities ---

@router.get("/service-identities")
def list_service_identities(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    identities = db.query(ServiceIdentity).filter(ServiceIdentity.workspace_id == ws.id).all()
    return {"service_identities": identities}


@router.post("/service-identities", status_code=status.HTTP_201_CREATED)
def create_service_identity(
    payload: ServiceIdentityCreate,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    """Issues client credentials for machine-to-machine automation."""
    client_id = f"lnx_svc_{secrets.token_hex(8)}"
    raw_secret = f"lnx_sec_{secrets.token_urlsafe(32)}"
    secret_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

    expires_at = None
    if payload.ttl_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.ttl_days)

    svc = ServiceIdentity(
        workspace_id=ws.id,
        name=payload.name,
        client_id=client_id,
        client_secret_hash=secret_hash,
        allowed_scopes=payload.allowed_scopes,
        allowed_ips=payload.allowed_ips,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)

    return {
        "status": "created",
        "service_identity": svc,
        "client_secret_raw": raw_secret,  # Only returned upon creation
    }


@router.delete("/service-identities/{service_id}")
def delete_service_identity(
    service_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    svc = db.query(ServiceIdentity).filter(
        ServiceIdentity.id == service_id,
        ServiceIdentity.workspace_id == ws.id,
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service identity not found.")
    db.delete(svc)
    db.commit()
    return {"status": "deleted"}


# --- Sessions & Posture Controls ---

@router.get("/sessions")
def list_user_sessions(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    sessions = db.query(ActiveUserSession).filter(
        ActiveUserSession.user_id == current_user.id,
    ).order_by(ActiveUserSession.last_activity_at.desc()).all()
    return {"sessions": sessions}


@router.post("/sessions/{session_id}/revoke")
def revoke_single_session(
    session_id: str,
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    sess = db.query(ActiveUserSession).filter(
        ActiveUserSession.id == session_id,
        ActiveUserSession.user_id == current_user.id,
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    SessionPostureManager.revoke_session(sess)
    db.commit()

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SESSION_REVOCATION,
        user_id=current_user.id,
        details={"session_id": session_id, "scope": "SINGLE"},
    )

    return {"status": "revoked", "session_id": session_id}


@router.post("/sessions/revoke-all")
def revoke_all_sessions(
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    user_sessions = db.query(ActiveUserSession).filter(
        ActiveUserSession.user_id == current_user.id,
    ).all()
    count = SessionPostureManager.revoke_all_user_sessions(user_sessions)
    db.commit()

    log_identity_audit(
        db,
        ws.id,
        event_type=IdentityEventType.SESSION_REVOCATION,
        user_id=current_user.id,
        severity="WARNING",
        details={"revoked_count": count, "scope": "ALL"},
    )

    return {"status": "all_revoked", "revoked_count": count}


# --- Identity Audit Events ---

@router.get("/audit-events")
def list_identity_audit_events(
    limit: int = Query(50),
    db: Session = Depends(get_sync_db),
    ws: Workspace = Depends(get_active_workspace),
    current_user: User = Depends(get_current_user),
):
    events = db.query(IdentityAuditEvent).filter(
        IdentityAuditEvent.workspace_id == ws.id,
    ).order_by(IdentityAuditEvent.timestamp.desc()).limit(limit).all()
    return {"audit_events": events}
