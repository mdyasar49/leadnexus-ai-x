from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.lead import Contact
from app.models.enrichment import (
    ContactPoint,
    ContactVerification,
    DomainCandidate,
    PersonRoleObservation,
    PersonRoleChangeEvent
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.enrichment.contact_intelligence import ContactIntelligenceEngine
from packages.enrichment.person_intelligence import PersonIntelligenceEngine


contacts_router = APIRouter(prefix="/contacts", tags=["Contact Intelligence"])
people_router = APIRouter(prefix="/people", tags=["Person Intelligence & Roles"])
domains_router = APIRouter(prefix="/domains", tags=["Domain Intelligence"])
verification_router = APIRouter(prefix="/verification", tags=["Continuous Verification Engine"])


class EmailVerifyRequest(BaseModel):
    email: str
    is_pattern_predicted: bool = False
    is_publicly_listed: bool = True


class PhoneVerifyRequest(BaseModel):
    phone: str
    default_country_code: str = "61"


# --- Contacts Endpoints ---
@contacts_router.get("")
def list_contacts(
    company_id: Optional[str] = None,
    ownership_type: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists contacts with explicit ownership classification and deliverability tier."""
    q = db.query(Contact).filter(Contact.workspace_id == ws.id)
    if company_id:
        q = q.filter(Contact.company_id == company_id)
    records = q.limit(limit).all()

    results = []
    for c in records:
        ownership = ContactIntelligenceEngine.classify_email_ownership(c.email or "", c.full_name)
        results.append({
            "id": c.id,
            "company_id": c.company_id,
            "full_name": c.full_name,
            "job_title": c.job_title,
            "email": c.email,
            "email_status": c.email_status,
            "ownership_type": ownership,
            "business_phone": c.business_phone,
            "phone_status": c.phone_status,
            "is_decision_maker": c.is_decision_maker,
            "confidence_score": c.confidence_score,
            "source_url": c.source_url
        })
    return results


@contacts_router.get("/{contact_id}")
def get_contact_detail(
    contact_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns detailed contact intelligence, ownership semantics, and provenance."""
    c = db.query(Contact).filter(Contact.workspace_id == ws.id, Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")

    ownership = ContactIntelligenceEngine.classify_email_ownership(c.email or "", c.full_name)
    email_sem = ContactIntelligenceEngine.verify_email_semantics(
        c.email or "",
        is_pattern_predicted=(c.email_status == "PREDICTED"),
        is_publicly_listed=(c.email_status == "PUBLICLY_LISTED")
    )
    phone_norm = ContactIntelligenceEngine.normalize_phone(c.business_phone or "")

    return {
        "id": c.id,
        "company_id": c.company_id,
        "full_name": c.full_name,
        "job_title": c.job_title,
        "email": c.email,
        "email_status": c.email_status,
        "ownership_type": ownership,
        "email_semantics": email_sem,
        "phone_intelligence": phone_norm,
        "source_url": c.source_url,
        "confidence_score": c.confidence_score,
        "is_decision_maker": c.is_decision_maker
    }


@contacts_router.post("/{contact_id}/verify")
def verify_contact(
    contact_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Executes live compliant verification semantics on a contact point."""
    c = db.query(Contact).filter(Contact.workspace_id == ws.id, Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")

    email_sem = ContactIntelligenceEngine.verify_email_semantics(
        c.email or "",
        is_pattern_predicted=(c.email_status == "PREDICTED"),
        is_publicly_listed=True
    )
    return {
        "contact_id": c.id,
        "email": c.email,
        "verification_result": email_sem
    }


# --- People Endpoints ---
@people_router.get("/{person_id}/roles")
def get_person_roles(
    person_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns chronological professional role observations for a person."""
    roles = (
        db.query(PersonRoleObservation)
        .filter(PersonRoleObservation.workspace_id == ws.id, PersonRoleObservation.person_id == person_id)
        .order_by(PersonRoleObservation.observed_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "title": r.title,
            "department": r.department,
            "buying_committee_role": r.buying_committee_role,
            "is_current": r.is_current,
            "source_url": r.source_url,
            "confidence": r.confidence,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None
        }
        for r in roles
    ]


@people_router.get("/{person_id}/history")
def get_person_role_history(
    person_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns role change events (promotions, company switches)."""
    events = (
        db.query(PersonRoleChangeEvent)
        .filter(PersonRoleChangeEvent.workspace_id == ws.id, PersonRoleChangeEvent.person_id == person_id)
        .order_by(PersonRoleChangeEvent.detected_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "change_type": e.change_type,
            "previous_role": e.previous_role,
            "new_role": e.new_role,
            "detected_at": e.detected_at.isoformat() if e.detected_at else None,
            "source_url": e.source_url,
            "affects_buying_committee": e.affects_buying_committee
        }
        for e in events
    ]


# --- Domain Intelligence Endpoints ---
@domains_router.get("")
def list_domain_candidates(
    company_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists discovered candidate web domains with provenance confidence."""
    q = db.query(DomainCandidate).filter(DomainCandidate.workspace_id == ws.id)
    if company_id:
        q = q.filter(DomainCandidate.company_id == company_id)
    candidates = q.order_by(DomainCandidate.confidence.desc()).all()
    return [
        {
            "id": d.id,
            "company_id": d.company_id,
            "domain": d.domain,
            "normalized_domain": d.normalized_domain,
            "source_url": d.source_url,
            "confidence": d.confidence,
            "status": d.status,
            "first_seen": d.first_seen.isoformat() if d.first_seen else None,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None
        }
        for d in candidates
    ]


# --- Live Verification Endpoints ---
@verification_router.post("/email")
def verify_email_endpoint(
    req: EmailVerifyRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Verifies email RFC syntax, disposable domains, and deliverability semantics."""
    return ContactIntelligenceEngine.verify_email_semantics(
        email_str=req.email,
        is_pattern_predicted=req.is_pattern_predicted,
        is_publicly_listed=req.is_publicly_listed
    )


@verification_router.post("/phone")
def verify_phone_endpoint(
    req: PhoneVerifyRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """Normalizes phone to E.164 and checks telephone number metadata."""
    return ContactIntelligenceEngine.normalize_phone(
        raw_phone=req.phone,
        default_country_code=req.default_country_code
    )
