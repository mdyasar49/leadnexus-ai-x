import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.workspace_ui import ExportJob
from app.services.permission_service import get_active_workspace, get_current_user
from packages.search.export_service import ExportService


router = APIRouter(prefix="/exports", tags=["Safe Export Engine"])


class ExportPreviewRequest(BaseModel):
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class ExportCreateRequest(BaseModel):
    export_format: str = "CSV"  # CSV, XLSX, JSON, GOOGLE_SHEET
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@router.post("/preview")
def preview_export(
    req: ExportPreviewRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Calculates row count, estimated file size, and verifies safety."""
    return ExportService.preview_export(
        db=db,
        workspace_id=ws.id,
        filters=req.filters,
        query=req.query
    )


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_export(
    req: ExportCreateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Generates an export job with formula injection protection."""
    try:
        job = ExportService.create_export_job(
            db=db,
            workspace_id=ws.id,
            user_id=user.id,
            export_format=req.export_format,
            filters=req.filters,
            query=req.query
        )
        return {
            "id": job.id,
            "format": job.export_format,
            "status": job.status,
            "record_count": job.record_count,
            "download_url": job.download_url
        }
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/{job_id}")
def get_export_status(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Checks the status and metadata of an export job."""
    job = (
        db.query(ExportJob)
        .filter(ExportJob.workspace_id == ws.id, ExportJob.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    return {
        "id": job.id,
        "format": job.export_format,
        "status": job.status,
        "record_count": job.record_count,
        "download_url": job.download_url,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message
    }


@router.get("/{job_id}/download")
def download_export_file(
    job_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Downloads the generated export file."""
    job = (
        db.query(ExportJob)
        .filter(ExportJob.workspace_id == ws.id, ExportJob.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(status_code=404, detail="Export file not ready or missing on disk")

    media_types = {
        "CSV": "text/csv",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "JSON": "application/json"
    }
    media_type = media_types.get(job.export_format, "application/octet-stream")
    filename = os.path.basename(job.file_path)

    return FileResponse(
        path=job.file_path,
        media_type=media_type,
        filename=filename
    )
