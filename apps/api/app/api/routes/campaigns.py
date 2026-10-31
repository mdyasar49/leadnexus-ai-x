from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.campaign_service import CampaignService
from app.services.permission_service import get_current_user, get_active_workspace, require_permission
from app.models.user import User
from app.models.tenant import Workspace
from app.models.campaign import CampaignStatus
from app.schemas.campaign import (
    CampaignResponse,
    CampaignCreate,
    CampaignUpdate,
    CampaignTemplateResponse,
    TemplateInstantiateRequest,
)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[CampaignStatus] = Query(None),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists campaigns for the active workspace."""
    campaigns = await CampaignService.list_campaigns(db, workspace.id, status=status)
    return campaigns

@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    request: CampaignCreate,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new campaign in DRAFT state."""
    campaign = await CampaignService.create_campaign(db, workspace.id, user.id, request)
    return campaign

@router.get("/templates", response_model=List[CampaignTemplateResponse])
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists preconfigured industry campaign templates."""
    templates = await CampaignService.list_templates(db)
    return templates

@router.post("/templates/{template_id}/instantiate", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def instantiate_template(
    template_id: str,
    request: TemplateInstantiateRequest,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Instantiates a campaign from a preconfigured template."""
    campaign = await CampaignService.instantiate_template(db, template_id, workspace.id, user.id, request)
    return campaign

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches campaign details and configuration."""
    campaign = await CampaignService.get_campaign(db, campaign_id, workspace.id)
    return campaign

@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdate,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates campaign parameters and configuration."""
    campaign = await CampaignService.update_campaign(db, campaign_id, workspace.id, user.id, request)
    return campaign

@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Activates campaign for research execution."""
    campaign = await CampaignService.set_status(db, campaign_id, workspace.id, user.id, CampaignStatus.ACTIVE)
    return campaign

@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Pauses active campaign."""
    campaign = await CampaignService.set_status(db, campaign_id, workspace.id, user.id, CampaignStatus.PAUSED)
    return campaign

@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(
    campaign_id: str,
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Archives campaign."""
    campaign = await CampaignService.set_status(db, campaign_id, workspace.id, user.id, CampaignStatus.ARCHIVED)
    return campaign

