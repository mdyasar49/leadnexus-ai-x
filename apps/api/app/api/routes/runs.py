from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.run_service import RunService
from app.services.permission_service import get_current_user, get_active_workspace
from app.models.user import User
from app.models.tenant import Workspace
from app.schemas.run import (
    ResearchRunResponse,
    RunStartRequest,
    RunActionResponse,
)

router = APIRouter(tags=["Research Runs & Orchestration"])

@router.post("/campaigns/{campaign_id}/run", response_model=ResearchRunResponse, status_code=status.HTTP_201_CREATED)
async def start_research_run(
    campaign_id: str,
    request: RunStartRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiates a research run for a campaign, scheduling collector jobs."""
    run = await RunService.start_run(db, campaign_id, workspace.id, user.id, request)
    return run

@router.get("/campaigns/{campaign_id}/runs", response_model=List[ResearchRunResponse])
async def list_campaign_runs(
    campaign_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all historical and active runs for a given campaign."""
    runs = await RunService.list_runs(db, campaign_id)
    return runs

@router.get("/runs/{run_id}", response_model=ResearchRunResponse)
async def get_run_details(
    run_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Gets details, metrics, and sub-job states of a specific research run."""
    run = await RunService.get_run(db, run_id)
    return run

@router.post("/runs/{run_id}/pause", response_model=RunActionResponse)
async def pause_run(
    run_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Pauses an executing research run."""
    return await RunService.pause_run(db, run_id, workspace.id, user.id)

@router.post("/runs/{run_id}/resume", response_model=RunActionResponse)
async def resume_run(
    run_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resumes a paused research run."""
    return await RunService.resume_run(db, run_id, workspace.id, user.id)

@router.post("/runs/{run_id}/cancel", response_model=RunActionResponse)
async def cancel_run(
    run_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancels a research run and marks its pending jobs as cancelled."""
    return await RunService.cancel_run(db, run_id, workspace.id, user.id)

