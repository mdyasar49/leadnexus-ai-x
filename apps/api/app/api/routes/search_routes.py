from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.workspace_ui import SavedSearch, SavedView, Watchlist
from app.services.permission_service import get_active_workspace, get_current_user
from packages.search.search_service import GlobalSearchService
from packages.search.search_dsl import NaturalLanguageQueryBuilder, SearchDSLParser, SearchDSLError


router = APIRouter(prefix="/search", tags=["Enterprise Search & Query Engine"])


class LeadSearchRequest(BaseModel):
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    sort_field: str = "lead_priority_score"
    sort_direction: str = "desc"
    limit: int = 25
    cursor: Optional[str] = None


class NLQueryRequest(BaseModel):
    query: str


class ExplainSearchRequest(BaseModel):
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class SavedSearchCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    sort_field: str = "lead_score"
    sort_direction: str = "desc"
    columns: Optional[List[str]] = None
    alert_enabled: bool = False
    alert_channel: str = "IN_APP"
    alert_frequency: str = "DAILY"
    alert_threshold: float = 0.0


class SavedViewCreate(BaseModel):
    name: str
    view_type: str = "LEADS"
    columns: Optional[List[str]] = None
    sort_by: str = "lead_priority_score"
    sort_direction: str = "desc"
    filters: Optional[Dict[str, Any]] = None
    is_default: bool = False


class WatchlistCreate(BaseModel):
    watch_type: str
    target_value: str
    criteria: Optional[Dict[str, Any]] = None


@router.get("")
@router.get("/global")
def global_search(
    q: str = Query(..., description="Global search query string"),
    limit: int = Query(10, ge=1, le=50),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Unified global search across Companies, Contacts, Technologies, and Signals."""
    return GlobalSearchService.global_search(
        db=db,
        workspace_id=ws.id,
        query=q,
        limit_per_category=limit
    )


@router.post("/leads")
def search_leads(
    req: LeadSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """High-performance filtered search with keyset cursor pagination."""
    try:
        return GlobalSearchService.execute_lead_search(
            db=db,
            workspace_id=ws.id,
            query=req.query,
            filters=req.filters,
            sort_field=req.sort_field,
            sort_direction=req.sort_direction,
            limit=req.limit,
            cursor=req.cursor
        )
    except SearchDSLError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/facets")
def get_search_facets(
    q: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Calculates dynamic aggregation facet counts across key lead dimensions."""
    return GlobalSearchService.get_search_facets(
        db=db,
        workspace_id=ws.id,
        query=q
    )


@router.post("/natural-language")
def parse_natural_language_query(
    req: NLQueryRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user)
):
    """
    Safely converts human natural language queries into verified Search DSL schemas
    with a structured explanation. Never executes unvalidated SQL.
    """
    return NaturalLanguageQueryBuilder.parse_nl_query(req.query)


@router.post("/explain")
def explain_search_query(
    req: ExplainSearchRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Provides query planning, index utilization estimates, and safety explanation."""
    try:
        return GlobalSearchService.explain_search(
            db=db,
            workspace_id=ws.id,
            filters=req.filters,
            query=req.query
        )
    except SearchDSLError as err:
        raise HTTPException(status_code=400, detail=str(err))


# Saved Searches
@router.get("/saved")
def list_saved_searches(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    searches = (
        db.query(SavedSearch)
        .filter(SavedSearch.workspace_id == ws.id)
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "query": s.query,
            "filters": s.filters,
            "alert_enabled": s.alert_enabled,
            "alert_channel": s.alert_channel,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in searches
    ]


@router.post("/saved", status_code=status.HTTP_201_CREATED)
def create_saved_search(
    req: SavedSearchCreate,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    saved = SavedSearch(
        workspace_id=ws.id,
        user_id=user.id,
        name=req.name,
        description=req.description,
        query=req.query,
        filters=req.filters or {},
        sort_field=req.sort_field,
        sort_direction=req.sort_direction,
        columns=req.columns or [],
        alert_enabled=req.alert_enabled,
        alert_channel=req.alert_channel,
        alert_frequency=req.alert_frequency,
        alert_threshold=req.alert_threshold
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"id": saved.id, "name": saved.name, "status": "CREATED"}


@router.delete("/saved/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    search_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    saved = (
        db.query(SavedSearch)
        .filter(SavedSearch.workspace_id == ws.id, SavedSearch.id == search_id)
        .first()
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Saved search not found")
    db.delete(saved)
    db.commit()
    return None


# Saved Views
@router.get("/views")
def list_saved_views(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    views = (
        db.query(SavedView)
        .filter(SavedView.workspace_id == ws.id)
        .all()
    )
    return [
        {
            "id": v.id,
            "name": v.name,
            "view_type": v.view_type,
            "columns": v.columns,
            "sort_by": v.sort_by,
            "sort_direction": v.sort_direction,
            "filters": v.filters,
            "is_default": v.is_default
        }
        for v in views
    ]


@router.post("/views", status_code=status.HTTP_201_CREATED)
def create_saved_view(
    req: SavedViewCreate,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    view = SavedView(
        workspace_id=ws.id,
        user_id=user.id,
        name=req.name,
        view_type=req.view_type,
        columns=req.columns or [],
        sort_by=req.sort_by,
        sort_direction=req.sort_direction,
        filters=req.filters or {},
        is_default=req.is_default
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return {"id": view.id, "name": view.name, "status": "CREATED"}


# Watchlists
@router.get("/watchlists")
def list_watchlists(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    items = (
        db.query(Watchlist)
        .filter(Watchlist.workspace_id == ws.id, Watchlist.is_active.is_(True))
        .all()
    )
    return [
        {
            "id": w.id,
            "watch_type": w.watch_type,
            "target_value": w.target_value,
            "criteria": w.criteria,
            "created_at": w.created_at.isoformat() if w.created_at else None
        }
        for w in items
    ]


@router.post("/watchlists", status_code=status.HTTP_201_CREATED)
def create_watchlist_entry(
    req: WatchlistCreate,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    item = Watchlist(
        workspace_id=ws.id,
        user_id=user.id,
        watch_type=req.watch_type.upper(),
        target_value=req.target_value,
        criteria=req.criteria or {},
        is_active=True
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "target_value": item.target_value, "status": "CREATED"}
