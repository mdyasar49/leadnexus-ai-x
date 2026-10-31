"""Research source registry and health inspection service."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import ResourceNotFoundException
from app.models.source import ResearchSource, CampaignSource, SourceHealthStatus
from app.schemas.source import CampaignSourceUpdate


class SourceService:
    @staticmethod
    async def list_sources(db: AsyncSession, only_active: bool = True) -> List[ResearchSource]:
        """List all registered research sources."""
        stmt = select(ResearchSource)
        if only_active:
            stmt = stmt.where(ResearchSource.is_active.is_(True))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_source_by_key(db: AsyncSession, key: str) -> Optional[ResearchSource]:
        stmt = select(ResearchSource).where(ResearchSource.key == key)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_campaign_sources(db: AsyncSession, campaign_id: str) -> List[CampaignSource]:
        stmt = select(CampaignSource).where(CampaignSource.campaign_id == campaign_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def configure_campaign_source(
        db: AsyncSession,
        campaign_id: str,
        source_id: str,
        data: CampaignSourceUpdate,
    ) -> CampaignSource:
        stmt = select(CampaignSource).where(
            CampaignSource.campaign_id == campaign_id,
            CampaignSource.source_id == source_id,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.is_enabled = data.is_enabled
            existing.priority = data.priority
            existing.custom_rate_limit = data.custom_rate_limit
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        new_cs = CampaignSource(
            campaign_id=campaign_id,
            source_id=source_id,
            is_enabled=data.is_enabled,
            priority=data.priority,
            custom_rate_limit=data.custom_rate_limit,
        )
        db.add(new_cs)
        await db.commit()
        await db.refresh(new_cs)
        return new_cs

