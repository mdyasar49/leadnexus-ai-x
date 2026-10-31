from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.lead import Company, Contact
from app.models.enrichment import (
    FieldObservation,
    EnrichmentJob,
    EnrichmentTask,
    EnrichmentRecommendation,
    EnrichmentQuality,
    EnrichmentCoverage,
    JobStatus as EnrichmentJobStatus
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.enrichment.field_resolver import FieldResolver
from packages.enrichment.smart_enrichment import SmartEnrichmentEngine
from packages.enrichment.quality_coverage import QualityAndCoverageEngine
from packages.enrichment.event_bus import EnrichmentEventBus


router = APIRouter(prefix="/enrichment", tags=["Enterprise Data Enrichment Engine"])


class CreateJobRequest(BaseModel):
    company_ids: List[str]
    depth: str = "STANDARD"  # MINIMAL, STANDARD, DEEP, FORENSIC
    budget_limit_usd: float = 50.0


class FieldObservationCreate(BaseModel):
    field_name: str
    value: Any
    source_name: str
    source_url: str
    confidence: float = 1.0


@router.get("/companies/{company_id}")
def get_company_enrichment_profile(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns field-level provenance, freshness, and quality for a company."""
    comp = db.query(Company).filter(Company.workspace_id == ws.id, Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")

    observations = (
        db.query(FieldObservation)
        .filter(FieldObservation.workspace_id == ws.id, FieldObservation.entity_id == company_id)
        .order_by(FieldObservation.observed_at.desc())
        .all()
    )

    quality = QualityAndCoverageEngine.calculate_company_enrichment_quality(db, ws.id, company_id)
    recs = SmartEnrichmentEngine.evaluate_company_gaps(db, ws.id, company_id)

    return {
        "company_id": comp.id,
        "name": comp.name,
        "domain": comp.domain,
        "quality_score": quality.quality_score,
        "completeness_score": quality.completeness_score,
        "freshness_score": quality.freshness_score,
        "verification_score": quality.verification_score,
        "conflict_rate": quality.conflict_rate,
        "observations_count": len(observations),
        "observations": [
            {
                "id": o.id,
                "field_name": o.field_name,
                "value": o.value,
                "source_name": o.source_name,
                "source_url": o.source_url,
                "confidence": o.confidence,
                "freshness": o.freshness,
                "status": o.status,
                "observed_at": o.observed_at.isoformat() if o.observed_at else None
            }
            for o in observations
        ],
        "recommendations": [
            {
                "action": r.recommended_action,
                "target_field": r.target_field,
                "priority": r.priority,
                "expected_gain": r.expected_gain,
                "reason": r.reason
            }
            for r in recs
        ]
    }


@router.post("/companies/{company_id}/observe", status_code=status.HTTP_201_CREATED)
def record_company_observation(
    company_id: str,
    req: FieldObservationCreate,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Records a new atomic field observation with provenance and conflict detection."""
    comp = db.query(Company).filter(Company.workspace_id == ws.id, Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")

    obs, is_conflicted = FieldResolver.record_observation(
        db=db,
        workspace_id=ws.id,
        entity_type="COMPANY",
        entity_id=company_id,
        field_name=req.field_name,
        value=req.value,
        source_name=req.source_name,
        source_url=req.source_url,
        confidence=req.confidence
    )

    EnrichmentEventBus.emit("FIELD_DISCOVERED", {
        "workspace_id": ws.id,
        "company_id": company_id,
        "field_name": req.field_name,
        "is_conflicted": is_conflicted
    })

    return {
        "id": obs.id,
        "field_name": obs.field_name,
        "value": obs.value,
        "confidence": obs.confidence,
        "freshness": obs.freshness,
        "is_conflicted": is_conflicted,
        "status": obs.status
    }


@router.get("/recommendations/{entity_id}")
def get_recommendations(
    entity_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns prioritized next-research recommendations ranked by Expected Information Value / Cost."""
    recs = SmartEnrichmentEngine.evaluate_company_gaps(db, ws.id, entity_id)
    return [
        {
            "recommended_action": r.recommended_action,
            "target_field": r.target_field,
            "target_role": r.target_role,
            "priority": r.priority,
            "expected_gain": r.expected_gain,
            "reason": r.reason
        }
        for r in recs
    ]


@router.get("/quality/{company_id}")
def get_enrichment_quality(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Calculates and returns the Enrichment Quality Score (0-100)."""
    try:
        quality = QualityAndCoverageEngine.calculate_company_enrichment_quality(db, ws.id, company_id)
        return {
            "company_id": company_id,
            "quality_score": quality.quality_score,
            "completeness_score": quality.completeness_score,
            "freshness_score": quality.freshness_score,
            "verification_score": quality.verification_score,
            "conflict_rate": quality.conflict_rate,
            "last_assessed_at": quality.last_assessed_at.isoformat() if quality.last_assessed_at else None
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@router.get("/coverage")
def get_enrichment_coverage(
    campaign_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns global enrichment coverage across key entity dimensions."""
    cov = QualityAndCoverageEngine.calculate_workspace_coverage(db, ws.id, campaign_id)
    return {
        "workspace_id": ws.id,
        "campaign_id": campaign_id,
        "pct_domain": cov.pct_domain,
        "pct_technology": cov.pct_technology,
        "pct_decision_maker": cov.pct_decision_maker,
        "pct_business_email": cov.pct_business_email,
        "pct_business_phone": cov.pct_business_phone,
        "pct_verified_contacts": cov.pct_verified_contacts,
        "pct_fresh_fields": cov.pct_fresh_fields,
        "calculated_at": cov.calculated_at.isoformat() if cov.calculated_at else None
    }


# Job Management
@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_enrichment_job(
    req: CreateJobRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Launches an enterprise enrichment batch governed by budget limits."""
    job = SmartEnrichmentEngine.create_enrichment_job(
        db=db,
        workspace_id=ws.id,
        user_id=user.id,
        company_ids=req.company_ids,
        depth=req.depth,
        budget_limit_usd=req.budget_limit_usd
    )

    EnrichmentEventBus.emit("ENRICHMENT_STARTED", {
        "job_id": job.id,
        "workspace_id": ws.id,
        "total_entities": job.total_entities
    })

    return {
        "id": job.id,
        "job_type": job.job_type,
        "depth": job.depth,
        "status": job.status,
        "total_entities": job.total_entities,
        "completed_entities": job.completed_entities,
        "cost_usd": job.cost_usd
    }


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    job = db.query(EnrichmentJob).filter(EnrichmentJob.workspace_id == ws.id, EnrichmentJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Enrichment job not found")
    return {
        "id": job.id,
        "status": job.status,
        "depth": job.depth,
        "total_entities": job.total_entities,
        "completed_entities": job.completed_entities,
        "cost_usd": job.cost_usd,
        "budget_limit_usd": job.budget_limit_usd,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@router.post("/jobs/{job_id}/pause")
def pause_job(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    job = db.query(EnrichmentJob).filter(EnrichmentJob.workspace_id == ws.id, EnrichmentJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Enrichment job not found")
    job.status = EnrichmentJobStatus.PAUSED.value
    db.commit()
    return {"id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/resume")
def resume_job(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    job = db.query(EnrichmentJob).filter(EnrichmentJob.workspace_id == ws.id, EnrichmentJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Enrichment job not found")
    job.status = EnrichmentJobStatus.RUNNING.value
    db.commit()
    return {"id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    job = db.query(EnrichmentJob).filter(EnrichmentJob.workspace_id == ws.id, EnrichmentJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Enrichment job not found")
    job.status = EnrichmentJobStatus.FAILED.value
    db.commit()
    return {"id": job.id, "status": "CANCELLED"}
