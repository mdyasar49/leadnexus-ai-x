from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.source_service import SourceService
from app.services.permission_service import get_current_user
from app.models.user import User
from app.schemas.source import (
    ResearchSourceResponse,
    CampaignSourceResponse,
    CampaignSourceUpdate,
)

router = APIRouter(prefix="/sources", tags=["Research Sources"])

@router.get("", response_model=List[ResearchSourceResponse])
async def list_sources(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all available legal/permitted research sources and their health status."""
    sources = await SourceService.list_sources(db, only_active=True)
    return sources

@router.get("/campaign/{campaign_id}", response_model=List[CampaignSourceResponse])
async def get_campaign_sources(
    campaign_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns source configuration mappings for a given campaign."""
    sources = await SourceService.get_campaign_sources(db, campaign_id)
    return sources

@router.put("/campaign/{campaign_id}/source/{source_id}", response_model=CampaignSourceResponse)
async def configure_campaign_source(
    campaign_id: str,
    source_id: str,
    data: CampaignSourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Configures rate limit and priority for a specific source in a campaign."""
    cs = await SourceService.configure_campaign_source(db, campaign_id, source_id, data)
    return cs

