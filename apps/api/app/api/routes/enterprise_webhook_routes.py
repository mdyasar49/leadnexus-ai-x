"""
LeadNexus AI X — Enterprise Webhook Delivery Routes
Phase 35: Cryptographic HMAC-SHA256 Signing, Replay Defense, Circuit Breakers & Dead-Letter Redrive
"""

import time
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.user import User
from app.models.tenant import Workspace
from app.models.webhooks import (
    EnterpriseWebhookEndpoint,
    EnterpriseWebhookDelivery,
    WebhookRedriveJob,
)
from packages.webhooks import (
    WebhookSignatureSigner,
    ReplayDefenseGuard,
    WebhookCircuitBreaker,
    WebhookDeliveryService,
    WebhookRedriveService,
)

router = APIRouter(prefix="/webhooks", tags=["Enterprise Webhooks"])

# Singleton services for the route layer
_circuit_breaker = WebhookCircuitBreaker()
_delivery_service = WebhookDeliveryService(circuit_breaker=_circuit_breaker)
_redrive_service = WebhookRedriveService(delivery_service=_delivery_service)
_replay_guard = ReplayDefenseGuard()


# --- Pydantic Schemas ---

class CreateEndpointRequest(BaseModel):
    name: str = Field(..., example="Customer Sync Service")
    url: str = Field(..., example="https://api.enterprise.com/webhooks/leadnexus")
    event_patterns: List[str] = Field(default=["company.*", "lead.scored"], example=["company.*", "lead.scored"])
    secret_token: Optional[str] = Field(None, example="whsec_...")


class UpdateEndpointRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    event_patterns: Optional[List[str]] = None
    is_active: Optional[bool] = None


class VerifyIncomingRequest(BaseModel):
    payload: Dict[str, Any]
    secret_token: str
    signature_header: str
    timestamp: int
    nonce: str


class TriggerRedriveRequest(BaseModel):
    endpoint_id: Optional[str] = None
    filter_status: str = Field(default="DEAD_LETTER", example="DEAD_LETTER")
    max_attempts: int = Field(default=50, ge=1, le=500)


# --- Endpoint Handlers ---

@router.post("/endpoints", status_code=status.HTTP_201_CREATED)
def create_webhook_endpoint(
    req: CreateEndpointRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Registers a new webhook endpoint with auto-generated HMAC secret if omitted.
    """
    secret = req.secret_token or WebhookSignatureSigner.generate_secret_token()
    endpoint = EnterpriseWebhookEndpoint(
        id=str(uuid.uuid4()),
        tenant_id=workspace.id,
        name=req.name,
        url=req.url,
        secret_token=secret,
        event_patterns=req.event_patterns,
        is_active=True,
        circuit_status="CLOSED",
        consecutive_failures=0,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "url": endpoint.url,
        "secret_token": endpoint.secret_token,
        "event_patterns": endpoint.event_patterns,
        "is_active": endpoint.is_active,
        "circuit_status": endpoint.circuit_status,
        "created_at": endpoint.created_at.isoformat() if endpoint.created_at else None,
    }


@router.get("/endpoints")
def list_webhook_endpoints(
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Lists all webhook endpoints and their current circuit breaker status for the workspace.
    """
    endpoints = db.query(EnterpriseWebhookEndpoint).filter(
        EnterpriseWebhookEndpoint.tenant_id == workspace.id
    ).order_by(EnterpriseWebhookEndpoint.created_at.desc()).all()

    return [
        {
            "id": ep.id,
            "name": ep.name,
            "url": ep.url,
            "secret_token": ep.secret_token[:12] + "..." if ep.secret_token else None,
            "event_patterns": ep.event_patterns,
            "is_active": ep.is_active,
            "circuit_status": _circuit_breaker.get_state(ep.id).value if ep.circuit_status != "CLOSED" else ep.circuit_status,
            "consecutive_failures": ep.consecutive_failures,
            "last_success_at": ep.last_success_at.isoformat() if ep.last_success_at else None,
            "last_failure_at": ep.last_failure_at.isoformat() if ep.last_failure_at else None,
            "created_at": ep.created_at.isoformat() if ep.created_at else None,
        }
        for ep in endpoints
    ]


@router.get("/endpoints/{endpoint_id}")
def get_webhook_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Retrieves full details of a single webhook endpoint.
    """
    ep = db.query(EnterpriseWebhookEndpoint).filter(
        EnterpriseWebhookEndpoint.id == endpoint_id,
        EnterpriseWebhookEndpoint.tenant_id == workspace.id,
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    return {
        "id": ep.id,
        "name": ep.name,
        "url": ep.url,
        "secret_token": ep.secret_token,
        "event_patterns": ep.event_patterns,
        "is_active": ep.is_active,
        "circuit_status": _circuit_breaker.get_state(ep.id).value if ep.circuit_status != "CLOSED" else ep.circuit_status,
        "consecutive_failures": ep.consecutive_failures,
        "last_success_at": ep.last_success_at.isoformat() if ep.last_success_at else None,
        "last_failure_at": ep.last_failure_at.isoformat() if ep.last_failure_at else None,
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
    }


@router.put("/endpoints/{endpoint_id}")
def update_webhook_endpoint(
    endpoint_id: str,
    req: UpdateEndpointRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Updates an existing webhook endpoint configuration.
    """
    ep = db.query(EnterpriseWebhookEndpoint).filter(
        EnterpriseWebhookEndpoint.id == endpoint_id,
        EnterpriseWebhookEndpoint.tenant_id == workspace.id,
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    if req.name is not None:
        ep.name = req.name
    if req.url is not None:
        ep.url = req.url
    if req.event_patterns is not None:
        ep.event_patterns = req.event_patterns
    if req.is_active is not None:
        ep.is_active = req.is_active

    db.commit()
    db.refresh(ep)
    return {"message": "Webhook endpoint updated successfully", "id": ep.id}


@router.delete("/endpoints/{endpoint_id}")
def delete_webhook_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Deletes a registered webhook endpoint.
    """
    ep = db.query(EnterpriseWebhookEndpoint).filter(
        EnterpriseWebhookEndpoint.id == endpoint_id,
        EnterpriseWebhookEndpoint.tenant_id == workspace.id,
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    db.delete(ep)
    db.commit()
    return {"message": "Webhook endpoint deleted successfully", "id": endpoint_id}


@router.post("/endpoints/{endpoint_id}/ping")
def ping_webhook_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Dispatches an audited test ping event with HMAC-SHA256 signature to verify endpoint health.
    """
    ep = db.query(EnterpriseWebhookEndpoint).filter(
        EnterpriseWebhookEndpoint.id == endpoint_id,
        EnterpriseWebhookEndpoint.tenant_id == workspace.id,
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    ping_payload = {
        "event": "leadnexus.ping",
        "timestamp": int(time.time()),
        "message": "LeadNexus AI X Ping Test Delivery",
        "endpoint_id": ep.id,
    }

    delivery = _delivery_service.dispatch(
        db=db,
        endpoint=ep,
        event_id=f"ping-{uuid.uuid4().hex[:8]}",
        event_type="leadnexus.ping",
        payload=ping_payload,
        attempt_number=1,
        max_retries=1,
    )

    return {
        "delivery_id": delivery.id,
        "status": delivery.status,
        "status_code": delivery.status_code,
        "execution_duration_ms": delivery.execution_duration_ms,
        "signed_headers": delivery.headers,
    }


@router.get("/deliveries")
def list_webhook_deliveries(
    endpoint_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Lists historical webhook delivery attempts with optional filtering.
    """
    query = db.query(EnterpriseWebhookDelivery).filter(
        EnterpriseWebhookDelivery.tenant_id == workspace.id
    )
    if endpoint_id:
        query = query.filter(EnterpriseWebhookDelivery.endpoint_id == endpoint_id)
    if status_filter:
        query = query.filter(EnterpriseWebhookDelivery.status == status_filter)

    deliveries = query.order_by(EnterpriseWebhookDelivery.created_at.desc()).limit(limit).all()

    return [
        {
            "id": d.id,
            "endpoint_id": d.endpoint_id,
            "event_id": d.event_id,
            "event_type": d.event_type,
            "status": d.status,
            "status_code": d.status_code,
            "execution_duration_ms": d.execution_duration_ms,
            "attempt_number": d.attempt_number,
            "max_retries": d.max_retries,
            "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in deliveries
    ]


@router.get("/deliveries/{delivery_id}")
def get_webhook_delivery_detail(
    delivery_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Inspects full delivery details including signed headers and payload.
    """
    d = db.query(EnterpriseWebhookDelivery).filter(
        EnterpriseWebhookDelivery.id == delivery_id,
        EnterpriseWebhookDelivery.tenant_id == workspace.id,
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Delivery record not found")

    return {
        "id": d.id,
        "endpoint_id": d.endpoint_id,
        "event_id": d.event_id,
        "event_type": d.event_type,
        "status": d.status,
        "status_code": d.status_code,
        "execution_duration_ms": d.execution_duration_ms,
        "payload": d.payload,
        "headers": d.headers,
        "attempt_number": d.attempt_number,
        "max_retries": d.max_retries,
        "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
        "error_message": d.error_message,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.post("/redrive")
def trigger_dead_letter_redrive(
    req: TriggerRedriveRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Launches an audited batch redrive for dead-lettered webhook deliveries.
    """
    job = _redrive_service.create_redrive_job(
        db=db,
        tenant_id=workspace.id,
        initiated_by=str(user.id),
        endpoint_id=req.endpoint_id,
        filter_status=req.filter_status,
        max_attempts=req.max_attempts,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "total_eligible": job.total_eligible,
        "redriven_count": job.redriven_count,
        "success_count": job.success_count,
        "failed_count": job.failed_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/redrive/{job_id}")
def get_redrive_job_status(
    job_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
):
    """
    Polls the progress and results of a redrive execution job.
    """
    job = db.query(WebhookRedriveJob).filter(
        WebhookRedriveJob.id == job_id,
        WebhookRedriveJob.tenant_id == workspace.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Redrive job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "total_eligible": job.total_eligible,
        "redriven_count": job.redriven_count,
        "success_count": job.success_count,
        "failed_count": job.failed_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post("/verify-incoming")
def verify_incoming_webhook(req: VerifyIncomingRequest):
    """
    Utility endpoint allowing consumers to test and verify signature & replay defenses.
    """
    canonical_payload = WebhookSignatureSigner.canonicalize_payload(req.payload)
    
    # 1. Check signature
    sig_valid = WebhookSignatureSigner.verify_signature(
        payload_str=canonical_payload,
        secret=req.secret_token,
        signature_header=req.signature_header,
        timestamp=req.timestamp,
        nonce=req.nonce,
    )
    if not sig_valid:
        return {
            "is_valid": False,
            "error": "Invalid HMAC-SHA256 signature digest.",
        }

    # 2. Check replay defense
    replay_valid, replay_reason = _replay_guard.validate_request(
        timestamp=req.timestamp,
        nonce=req.nonce,
    )
    if not replay_valid:
        return {
            "is_valid": False,
            "error": f"Replay defense rejected: {replay_reason}",
        }

    return {
        "is_valid": True,
        "message": "Signature verified and replay defense validated successfully.",
    }
