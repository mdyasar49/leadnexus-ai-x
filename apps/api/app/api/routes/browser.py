import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.browser import BrowserJob, BrowserSnapshot, RawArtifact, PageAccessStatus
from app.services.permission_service import get_active_workspace, get_current_user
from packages.browser.browser_engine import BrowserEngine

router = APIRouter(prefix="/browser", tags=["Browser Intelligence"])
browser_engine = BrowserEngine()


class BrowserFetchRequest(BaseModel):
    url: str
    campaign_id: Optional[str] = None


@router.post("/fetch", status_code=status.HTTP_201_CREATED)
async def execute_browser_fetch(
    req: BrowserFetchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Performs sandboxed browser extraction with SSRF validation,
    DOM/JSON-LD parsing, and PageAccessStatus classification.
    """
    job = BrowserJob(
        workspace_id=ws.id,
        campaign_id=req.campaign_id,
        url=req.url,
        status="RUNNING"
    )
    db.add(job)
    await db.flush()

    extraction = browser_engine.fetch_and_extract(req.url)

    job.status = "COMPLETED" if not extraction.get("error") else "FAILED"
    job.access_status = extraction.get("access_status", PageAccessStatus.UNKNOWN.value)
    job.http_status_code = extraction.get("status_code", 200)
    job.navigation_time_ms = extraction.get("navigation_time_ms", 0)
    job.error = extraction.get("error")

    # Store Snapshot if successfully fetched
    if extraction.get("rendered_text") or extraction.get("title"):
        snapshot = BrowserSnapshot(
            job_id=job.id,
            workspace_id=ws.id,
            url=extraction.get("final_url", req.url),
            canonical_url=extraction.get("canonical_url"),
            title=extraction.get("title"),
            content_hash=extraction.get("content_hash", hashlib.sha256(req.url.encode()).hexdigest()),
            rendered_text=extraction.get("rendered_text"),
            json_ld=extraction.get("json_ld", []),
            opengraph=extraction.get("opengraph", {}),
            twitter_meta=extraction.get("twitter_meta", {}),
            headings=extraction.get("headings", {}),
            links=extraction.get("links", [])
        )
        db.add(snapshot)

    # Store RawArtifact
    raw_artifact = RawArtifact(
        workspace_id=ws.id,
        url=req.url,
        content_hash=extraction.get("content_hash", hashlib.sha256(req.url.encode()).hexdigest()),
        mime_type="text/html",
        status_code=extraction.get("status_code", 200),
        raw_payload_text=extraction.get("rendered_text", "")[:10000]
    )
    db.add(raw_artifact)

    await db.commit()

    return {
        "job_id": job.id,
        "url": req.url,
        "access_status": job.access_status,
        "status": job.status,
        "title": extraction.get("title"),
        "navigation_time_ms": job.navigation_time_ms,
        "error": job.error
    }


@router.get("/jobs")
async def list_browser_jobs(
    limit: int = Query(50, ge=1, le=200),
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = (
        select(BrowserJob)
        .where(BrowserJob.workspace_id == ws.id)
        .order_by(desc(BrowserJob.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/jobs/{job_id}")
async def get_browser_job_details(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(BrowserJob).where(BrowserJob.id == job_id, BrowserJob.workspace_id == ws.id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Browser job not found")
    return job

