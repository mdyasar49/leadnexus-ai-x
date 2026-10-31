from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db, AsyncSessionLocal
from app.models.tenant import Workspace
from app.models.discovery import DiscoveryRun, DiscoveryCandidate, DiscoveryMethod
from app.services.permission_service import get_active_workspace, get_current_user
from packages.collectors.plugins.search_engine import SearchEnginePlugin

router = APIRouter(prefix="/discovery", tags=["Discovery Engine"])
search_plugin = SearchEnginePlugin()


class SearchDiscoveryRequest(BaseModel):
    query: str
    country: Optional[str] = "Australia"
    industry: Optional[str] = "Enterprise Software"
    campaign_id: Optional[str] = None


@router.post("/search", status_code=status.HTTP_201_CREATED)
async def execute_discovery_search(
    req: SearchDiscoveryRequest,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes universal search discovery across public search engines.
    Creates a DiscoveryRun and populates DiscoveryCandidate records.
    """
    # Create run record
    disc_run = DiscoveryRun(
        workspace_id=ws.id,
        campaign_id=req.campaign_id,
        query=req.query,
        source_type="SEARCH_ENGINE",
        filters={"country": req.country, "industry": req.industry}
    )
    db.add(disc_run)
    await db.flush()

    # Discover candidate leads
    config = {
        "intent_keywords": [req.query],
        "country": req.country,
        "industry": req.industry
    }
    raw_candidates = search_plugin.discovery(config)

    added_candidates = []
    for c in raw_candidates:
        cand = DiscoveryCandidate(
            workspace_id=ws.id,
            campaign_id=req.campaign_id,
            discovery_run_id=disc_run.id,
            url=c["url"],
            normalized_url=c["normalized_url"],
            source=c["source"],
            title=c["title"],
            snippet=c["snippet"],
            query=c["query"],
            source_rank=c["source_rank"],
            content_type=c["content_type"],
            discovery_method=DiscoveryMethod.SEARCH_QUERY.value,
            preliminary_relevance=c["preliminary_relevance"],
            confidence=c["confidence"],
            evidence_pointer=c["evidence_pointer"]
        )
        db.add(cand)
        added_candidates.append(cand)

    disc_run.candidates_count = len(added_candidates)
    await db.commit()

    return {
        "discovery_run_id": disc_run.id,
        "query": req.query,
        "candidates_discovered": len(added_candidates),
        "status": "COMPLETED"
    }


@router.get("/candidates")
async def list_discovery_candidates(
    campaign_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = (
        select(DiscoveryCandidate)
        .where(DiscoveryCandidate.workspace_id == ws.id)
        .order_by(desc(DiscoveryCandidate.preliminary_relevance))
        .limit(limit)
    )
    if campaign_id:
        stmt = stmt.where(DiscoveryCandidate.campaign_id == campaign_id)

    result = await db.execute(stmt)
    candidates = result.scalars().all()
    return candidates


@router.get("/runs")
async def list_discovery_runs(
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = (
        select(DiscoveryRun)
        .where(DiscoveryRun.workspace_id == ws.id)
        .order_by(desc(DiscoveryRun.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/runs/{run_id}")
async def get_discovery_run_details(
    run_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(DiscoveryRun).where(DiscoveryRun.id == run_id, DiscoveryRun.workspace_id == ws.id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")
    return run

