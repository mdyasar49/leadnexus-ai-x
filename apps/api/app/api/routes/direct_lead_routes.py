"""
LeadNexus AI X — Direct Lead Research, Save & Export API Routes
Phase 13: REST Endpoints for Universal Search, Explicit Lead Saving & Dual Exports
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.services.lead_search_service import LeadSearchService
from app.services.saved_lead_service import SavedLeadService
from app.services.saved_lead_export_service import SavedLeadExportService

router = APIRouter(tags=["B2B Lead Intelligence"])


# --- Schemas ---

class SearchRequest(BaseModel):
    query: Optional[str] = Field(default="", example="Odoo Australia")
    criteria: List[Dict[str, str]] = Field(default=[], example=[{"category": "Keyword", "value": "Odoo"}, {"category": "Location", "value": "Australia"}])
    country: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SaveLeadRequest(BaseModel):
    company_id: str = Field(..., example="comp-123")
    contact_id: Optional[str] = Field(None, example="contact-456")
    source_name: Optional[str] = Field(default="Public Registry")
    source_url: Optional[str] = Field(default=None)
    evidence: Optional[str] = Field(default=None)
    search_keyword: Optional[str] = Field(default="B2B Lead")


# --- Health Endpoint ---

@router.get("/health", status_code=status.HTTP_200_OK)
def api_health_check():
    """Liveness probe for backend API."""
    return {"status": "ok", "service": "LeadNexus AI X"}


# --- Universal Search Endpoints ---

@router.get("/search/suggestions")
def get_search_suggestions(
    q: str = Query("", description="Prefix or keyword query"),
    db: Session = Depends(get_sync_db),
):
    """
    Returns debounced categorized suggestions (Keyword, Location, Industry, Technology, Job Title, Company Type).
    """
    suggestions = LeadSearchService.get_suggestions(query=q, db=db, limit=10)
    return {"query": q, "suggestions": suggestions}


@router.post("/search")
def search_leads(
    req: SearchRequest,
    db: Session = Depends(get_sync_db),
):
    """
    Universal search over companies and decision makers using query text and confirmed criteria chips.
    """
    filters = {}
    if req.country:
        filters["country"] = req.country
    if req.industry:
        filters["industry"] = req.industry
    if req.city:
        filters["city"] = req.city

    results = LeadSearchService.search_leads(
        query=req.query,
        criteria=req.criteria,
        filters=filters,
        limit=req.limit,
        offset=req.offset,
        db=db,
    )
    return results


# --- Saved Leads Endpoints ---

@router.post("/leads/save", status_code=status.HTTP_201_CREATED)
def save_lead(
    req: SaveLeadRequest,
    db: Session = Depends(get_sync_db),
):
    """
    Explicitly adds a selected lead to the PostgreSQL/SQLite saved_leads table.
    Enforces duplicate prevention.
    """
    try:
        saved, is_new = SavedLeadService.save_lead(
            db=db,
            company_id=req.company_id,
            contact_id=req.contact_id,
            source_name=req.source_name,
            source_url=req.source_url,
            evidence=req.evidence,
            search_keyword=req.search_keyword,
        )
        return {
            "message": "Lead saved successfully" if is_new else "Lead was already saved",
            "saved_id": saved.id,
            "company_id": saved.company_id,
            "contact_id": saved.contact_id,
            "is_new": is_new,
            "saved_at": saved.saved_at.isoformat() if saved.saved_at else None,
        }
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


@router.get("/leads")
def list_saved_leads(
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    job_title: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_sync_db),
):
    """
    Retrieves ONLY leads explicitly saved in the saved_leads table.
    Temporary search results must NEVER appear here.
    """
    items, total = SavedLeadService.list_saved_leads(
        db=db,
        search=search,
        company=company,
        location=location,
        industry=industry,
        job_title=job_title,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "leads": items,
    }


@router.get("/leads/count")
def get_saved_leads_count(db: Session = Depends(get_sync_db)):
    """Returns total count of saved leads for navbar badges."""
    return {"saved_count": SavedLeadService.get_saved_count(db)}


@router.get("/leads/{lead_id}")
def get_saved_lead_detail(
    lead_id: str,
    db: Session = Depends(get_sync_db),
):
    """Retrieves a single saved lead by ID, or company 360 dossier if matching company ID."""
    lead = SavedLeadService.get_saved_lead(db=db, saved_lead_id=lead_id)
    if lead:
        return lead

    # Fallback to 360 dossier for company records
    from app.models.lead import Company
    comp = db.query(Company).filter(Company.id == lead_id).first()
    if comp:
        from packages.search.lead_workspace_service import LeadWorkspaceService
        dossier = LeadWorkspaceService.get_lead_360(db=db, workspace_id=comp.workspace_id, company_id=lead_id)
        if dossier:
            return dossier

    raise HTTPException(status_code=404, detail="Saved lead not found")


@router.delete("/leads/{lead_id}")
def delete_saved_lead(
    lead_id: str,
    db: Session = Depends(get_sync_db),
):
    """Deletes an explicitly saved lead from PostgreSQL."""
    deleted = SavedLeadService.delete_saved_lead(db=db, saved_lead_id=lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved lead not found")
    return {"message": "Saved lead removed successfully", "id": lead_id}


# --- Export Endpoints ---

@router.get("/export/csv")
def export_saved_leads_csv(
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    job_title: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
):
    """
    Exports ONLY user-saved leads from PostgreSQL to CSV with UTF-8 BOM encoding.
    """
    filters = {
        "search": search,
        "company": company,
        "location": location,
        "industry": industry,
        "job_title": job_title,
    }
    return SavedLeadExportService.generate_csv_response(db=db, filters=filters)


@router.get("/export/excel")
def export_saved_leads_excel(
    search: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    job_title: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
):
    """
    Exports ONLY user-saved leads from PostgreSQL to formatted Excel (.xlsx) using OpenPyXL.
    """
    filters = {
        "search": search,
        "company": company,
        "location": location,
        "industry": industry,
        "job_title": job_title,
    }
    return SavedLeadExportService.generate_excel_response(db=db, filters=filters)
