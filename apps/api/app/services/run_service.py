"""Research run orchestration and job lifecycle service."""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    ConflictException,
)
from app.models.campaign import Campaign, CampaignStatus
from app.models.run import ResearchRun, ResearchJob, RunStatus, JobStatus
from app.models.source import CampaignSource, ResearchSource
from app.schemas.run import RunStartRequest, RunActionResponse
from app.services.audit_service import AuditService


class RunService:
    @staticmethod
    async def list_runs(db: AsyncSession, campaign_id: str) -> List[ResearchRun]:
        stmt = (
            select(ResearchRun)
            .where(ResearchRun.campaign_id == campaign_id)
            .options(selectinload(ResearchRun.jobs))
            .order_by(ResearchRun.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_run(db: AsyncSession, run_id: str) -> ResearchRun:
        stmt = (
            select(ResearchRun)
            .where(ResearchRun.id == run_id)
            .options(selectinload(ResearchRun.jobs))
        )
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ResourceNotFoundException("ResearchRun", run_id)
        return run

    @staticmethod
    async def start_run(
        db: AsyncSession,
        campaign_id: str,
        workspace_id: str,
        user_id: str,
        request: RunStartRequest,
    ) -> ResearchRun:
        # Verify campaign exists in workspace and is ACTIVE
        camp_stmt = (
            select(Campaign)
            .where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
            .options(selectinload(Campaign.config))
        )
        campaign = (await db.execute(camp_stmt)).scalar_one_or_none()
        if not campaign:
            raise ResourceNotFoundException("Campaign", campaign_id)

        if campaign.status != CampaignStatus.ACTIVE:
            raise ValidationException(
                f"Campaign cannot start a research run while in '{campaign.status.value}' state. Must be ACTIVE."
            )

        # Check for already running run
        running_stmt = select(ResearchRun).where(
            ResearchRun.campaign_id == campaign_id,
            ResearchRun.status.in_([RunStatus.RUNNING, RunStatus.QUEUED]),
        )
        active_run = (await db.execute(running_stmt)).scalar_one_or_none()
        if active_run:
            raise ConflictException(f"Run {active_run.id} is currently running for this campaign")

        # Determine sources to run
        sources_to_query = campaign.config.sources if campaign.config else ["github"]
        if request.source_filter:
            sources_to_query = [s for s in sources_to_query if s in request.source_filter]

        if not sources_to_query:
            sources_to_query = ["github"]

        # Create Run record
        now = datetime.now(timezone.utc)
        run = ResearchRun(
            campaign_id=campaign.id,
            workspace_id=campaign.workspace_id,
            status=RunStatus.RUNNING,
            trigger_type=request.trigger_type,
            started_at=now,
            stats={"sources_total": len(sources_to_query), "signals_found": 0, "companies_found": 0},
        )
        db.add(run)
        await db.flush()

        # Create ResearchJob for each source
        for src_key in sources_to_query:
            job = ResearchJob(
                run_id=run.id,
                source_key=src_key,
                stage="discovery",
                status=JobStatus.QUEUED,
                payload={
                    "campaign_name": campaign.name,
                    "country": campaign.config.country if campaign.config else "Global",
                    "intent_keywords": campaign.config.intent_keywords if campaign.config else [],
                    "company_keywords": campaign.config.company_keywords if campaign.config else [],
                    "target_job_titles": campaign.config.target_job_titles if campaign.config else [],
                    "maximum_results": campaign.config.maximum_results if campaign.config else 100,
                },
            )
            db.add(job)

        await db.commit()

        await AuditService.log_action(
            db=db,
            action="run.start",
            entity_type="research_run",
            entity_id=run.id,
            user_id=user_id,
            workspace_id=workspace_id,
            details={"campaign_id": campaign_id, "sources": sources_to_query},
        )

        return await RunService.get_run(db, run.id)

    @staticmethod
    async def pause_run(db: AsyncSession, run_id: str, workspace_id: str, user_id: str) -> RunActionResponse:
        run = await RunService.get_run(db, run_id)
        if run.status != RunStatus.RUNNING:
            raise ValidationException(f"Cannot pause run in '{run.status.value}' status")

        run.status = RunStatus.PAUSED
        db.add(run)
        await db.commit()

        await AuditService.log_action(
            db=db,
            action="run.pause",
            entity_type="research_run",
            entity_id=run.id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return RunActionResponse(
            run_id=run.id,
            action="pause",
            status=run.status,
            message="Research run successfully paused",
        )

    @staticmethod
    async def resume_run(db: AsyncSession, run_id: str, workspace_id: str, user_id: str) -> RunActionResponse:
        run = await RunService.get_run(db, run_id)
        if run.status != RunStatus.PAUSED:
            raise ValidationException(f"Cannot resume run in '{run.status.value}' status")

        run.status = RunStatus.RUNNING
        db.add(run)
        await db.commit()

        await AuditService.log_action(
            db=db,
            action="run.resume",
            entity_type="research_run",
            entity_id=run.id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return RunActionResponse(
            run_id=run.id,
            action="resume",
            status=run.status,
            message="Research run successfully resumed",
        )

    @staticmethod
    async def cancel_run(db: AsyncSession, run_id: str, workspace_id: str, user_id: str) -> RunActionResponse:
        run = await RunService.get_run(db, run_id)
        if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
            raise ValidationException(f"Cannot cancel run in terminal '{run.status.value}' status")

        run.status = RunStatus.CANCELLED
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)

        # Cancel any pending jobs
        for job in run.jobs:
            if job.status in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]:
                job.status = JobStatus.CANCELLED
                job.completed_at = run.completed_at
                db.add(job)

        await db.commit()

        await AuditService.log_action(
            db=db,
            action="run.cancel",
            entity_type="research_run",
            entity_id=run.id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        return RunActionResponse(
            run_id=run.id,
            action="cancel",
            status=run.status,
            message="Research run successfully cancelled",
        )


