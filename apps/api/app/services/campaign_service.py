"""Campaign lifecycle and configuration management service."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    ConflictException,
)
from app.models.campaign import Campaign, CampaignConfig, CampaignTemplate, CampaignStatus
from app.models.source import ResearchSource, CampaignSource
from app.models.tenant import Workspace
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignConfigCreate,
    CampaignConfigUpdate,
    TemplateInstantiateRequest,
)
from app.services.audit_service import AuditService


class CampaignService:
    @staticmethod
    async def list_campaigns(
        db: AsyncSession,
        workspace_id: str,
        status: Optional[CampaignStatus] = None,
    ) -> List[Campaign]:
        stmt = (
            select(Campaign)
            .where(Campaign.workspace_id == workspace_id)
            .options(selectinload(Campaign.config))
            .order_by(Campaign.created_at.desc())
        )
        if status:
            stmt = stmt.where(Campaign.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_campaign(
        db: AsyncSession,
        campaign_id: str,
        workspace_id: str,
    ) -> Campaign:
        stmt = (
            select(Campaign)
            .where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
            .options(selectinload(Campaign.config))
        )
        result = await db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise ResourceNotFoundException("Campaign", campaign_id)
        return campaign

    @staticmethod
    async def create_campaign(
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        request: CampaignCreate,
    ) -> Campaign:
        # Check uniqueness in workspace
        existing = await db.execute(
            select(Campaign).where(
                Campaign.workspace_id == workspace_id,
                Campaign.name == request.name,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"Campaign with name '{request.name}' already exists in this workspace")

        ws = await db.get(Workspace, workspace_id)
        campaign = Campaign(
            organization_id=ws.organization_id if ws else '',
            workspace_id=workspace_id,
            name=request.name,
            description=request.description or '',
            status=CampaignStatus.DRAFT,
            created_by_user_id=user_id,
        )
        db.add(campaign)
        await db.flush()

        # Build config
        cfg_data = request.config.model_dump() if request.config else {}
        config = CampaignConfig(
            campaign_id=campaign.id,
            country=cfg_data.get("country", "Global"),
            state=cfg_data.get("state"),
            city=cfg_data.get("city"),
            industry=cfg_data.get("industry"),
            company_keywords=cfg_data.get("company_keywords", []),
            intent_keywords=cfg_data.get("intent_keywords", []),
            target_job_titles=cfg_data.get("target_job_titles", []),
            sources=cfg_data.get("sources", ["github", "company_website"]),
            maximum_results=cfg_data.get("maximum_results", 100),
            icp_rules=cfg_data.get("icp_rules", {}),
            exclusion_criteria=cfg_data.get("exclusion_criteria", {}),
            rate_limits=cfg_data.get("rate_limits", {}),
        )
        db.add(config)
        await db.flush()

        # Link sources
        sources_to_enable = config.sources or ["github", "company_website"]
        for src_key in sources_to_enable:
            src_stmt = select(ResearchSource).where(ResearchSource.key == src_key)
            src_res = await db.execute(src_stmt)
            src_obj = src_res.scalar_one_or_none()
            if src_obj:
                c_src = CampaignSource(
                    campaign_id=campaign.id,
                    source_id=src_obj.id,
                    is_enabled=True,
                    priority=1,
                )
                db.add(c_src)

        await db.commit()

        await AuditService.log_action(
            db=db,
            action="campaign.create",
            entity_type="campaign",
            entity_id=campaign.id,
            user_id=user_id,
            workspace_id=workspace_id,
            details={"name": campaign.name},
        )

        return await CampaignService.get_campaign(db, campaign.id, workspace_id)

    @staticmethod
    async def update_campaign(
        db: AsyncSession,
        campaign_id: str,
        workspace_id: str,
        user_id: str,
        request: CampaignUpdate,
    ) -> Campaign:
        campaign = await CampaignService.get_campaign(db, campaign_id, workspace_id)

        if request.name is not None:
            campaign.name = request.name
        if request.description is not None:
            campaign.description = request.description
        if request.status is not None:
            campaign.status = request.status

        campaign.version += 1
        db.add(campaign)

        if request.config and campaign.config:
            cfg_updates = request.config.model_dump(exclude_unset=True)
            for k, v in cfg_updates.items():
                if hasattr(campaign.config, k):
                    setattr(campaign.config, k, v)
            db.add(campaign.config)

        await db.commit()

        await AuditService.log_action(
            db=db,
            action="campaign.update",
            entity_type="campaign",
            entity_id=campaign.id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return await CampaignService.get_campaign(db, campaign.id, workspace_id)

    @staticmethod
    async def set_status(
        db: AsyncSession,
        campaign_id: str,
        workspace_id: str,
        user_id: str,
        target_status: CampaignStatus,
    ) -> Campaign:
        campaign = await CampaignService.get_campaign(db, campaign_id, workspace_id)

        # Validate lifecycle transition rules
        current = campaign.status
        if current == CampaignStatus.ARCHIVED:
            raise ValidationException("Cannot transition out of ARCHIVED state")

        if target_status == CampaignStatus.ACTIVE:
            # Must have valid config with at least 1 intent keyword or company keyword
            if not campaign.config or (
                not campaign.config.intent_keywords and not campaign.config.company_keywords
            ):
                raise ValidationException("Campaign must have at least one intent keyword or company keyword before activation")

        campaign.status = target_status
        campaign.version += 1
        db.add(campaign)
        await db.commit()

        await AuditService.log_action(
            db=db,
            action=f"campaign.{target_status.value.lower()}",
            entity_type="campaign",
            entity_id=campaign.id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return await CampaignService.get_campaign(db, campaign.id, workspace_id)

    @staticmethod
    async def list_templates(db: AsyncSession) -> List[CampaignTemplate]:
        stmt = select(CampaignTemplate).order_by(CampaignTemplate.category, CampaignTemplate.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def instantiate_template(
        db: AsyncSession,
        template_id: str,
        workspace_id: str,
        user_id: str,
        request: TemplateInstantiateRequest,
    ) -> Campaign:
        stmt = select(CampaignTemplate).where(CampaignTemplate.id == template_id)
        result = await db.execute(stmt)
        tpl = result.scalar_one_or_none()
        if not tpl:
            raise ResourceNotFoundException("CampaignTemplate", template_id)

        # Merge defaults with overrides
        merged_config = dict(tpl.default_config or tpl.config_defaults or {})
        if request.overrides:
            merged_config.update(request.overrides)

        cfg_create = CampaignConfigCreate(**merged_config)
        camp_create = CampaignCreate(
            name=request.campaign_name,
            description=f"Instantiated from template: {tpl.name}. {tpl.description or ''}",
            config=cfg_create,
        )

        return await CampaignService.create_campaign(
            db=db,
            workspace_id=workspace_id,
            user_id=user_id,
            request=camp_create,
        )


