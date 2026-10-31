from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.workspace_ui import Bookmark, ResearchNote
from app.services.permission_service import get_active_workspace, get_current_user
from packages.search.lead_workspace_service import LeadWorkspaceService


router = APIRouter(prefix="/leads", tags=["Lead Intelligence 360 Workspace"])


class CompareRequest(BaseModel):
    company_ids: List[str]


class BulkActionRequest(BaseModel):
    action: str  # SUPPRESS, ARCHIVE, REVIEW, QUALIFY, RESEARCH_QUEUE
    company_ids: List[str]
    parameters: Optional[Dict[str, Any]] = None


class NoteCreateRequest(BaseModel):
    note_text: str
    tags: Optional[List[str]] = None


class BookmarkRequest(BaseModel):
    notes: Optional[str] = None


@router.post("/compare")
def compare_leads(
    req: CompareRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Side-by-side comparison of 2 to 5 companies."""
    try:
        return LeadWorkspaceService.compare_companies(
            db=db,
            workspace_id=ws.id,
            company_ids=req.company_ids
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/bulk-action")
def apply_bulk_action(
    req: BulkActionRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Applies bulk review, suppression, archiving, or research enqueue across leads."""
    try:
        return LeadWorkspaceService.apply_bulk_action(
            db=db,
            workspace_id=ws.id,
            user_id=user.id,
            action=req.action,
            company_ids=req.company_ids,
            parameters=req.parameters
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/{company_id}")
def get_lead_dossier(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Compiles complete 360-degree Lead Intelligence dossier."""
    dossier = LeadWorkspaceService.get_lead_360(
        db=db,
        workspace_id=ws.id,
        company_id=company_id
    )
    if not dossier:
        raise HTTPException(status_code=404, detail="Company lead not found")
    return dossier


@router.get("/{company_id}/timeline")
def get_lead_timeline(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns chronological intent events and signals."""
    dossier = LeadWorkspaceService.get_lead_360(db=db, workspace_id=ws.id, company_id=company_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Company lead not found")
    return dossier.get("intent_timeline", [])


@router.get("/{company_id}/people")
def get_lead_people(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns decision makers and buying committee assignments."""
    dossier = LeadWorkspaceService.get_lead_360(db=db, workspace_id=ws.id, company_id=company_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Company lead not found")
    return dossier.get("people", [])


@router.get("/{company_id}/notes")
def list_lead_notes(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    notes = (
        db.query(ResearchNote)
        .filter(ResearchNote.workspace_id == ws.id, ResearchNote.company_id == company_id)
        .order_by(ResearchNote.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "author": n.author_name,
            "text": n.note_text,
            "tags": n.tags,
            "created_at": n.created_at.isoformat() if n.created_at else None
        }
        for n in notes
    ]


@router.post("/{company_id}/notes", status_code=status.HTTP_201_CREATED)
def add_lead_note(
    company_id: str,
    req: NoteCreateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    author = getattr(user, "full_name", None) or getattr(user, "email", "Analyst")
    note = ResearchNote(
        workspace_id=ws.id,
        user_id=user.id,
        company_id=company_id,
        author_name=author,
        note_text=req.note_text,
        tags=req.tags or []
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "company_id": company_id, "status": "CREATED"}


@router.post("/{company_id}/bookmarks")
def toggle_bookmark(
    company_id: str,
    req: BookmarkRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Toggles bookmark status on a company lead."""
    bm = (
        db.query(Bookmark)
        .filter(
            Bookmark.workspace_id == ws.id,
            Bookmark.user_id == user.id,
            Bookmark.entity_type == "COMPANY",
            Bookmark.entity_id == company_id
        )
        .first()
    )
    if bm:
        db.delete(bm)
        db.commit()
        return {"bookmarked": False, "company_id": company_id}
    else:
        new_bm = Bookmark(
            workspace_id=ws.id,
            user_id=user.id,
            entity_type="COMPANY",
            entity_id=company_id,
            notes=req.notes
        )
        db.add(new_bm)
        db.commit()
        return {"bookmarked": True, "company_id": company_id}
