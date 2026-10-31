"""Tenant management service for Organizations and Workspaces."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import ResourceNotFoundException, ConflictException
from app.models.tenant import Organization, Workspace, OrganizationMembership, WorkspaceMembership
from app.schemas.tenant import OrganizationCreate, WorkspaceCreate


class TenantService:
    @staticmethod
    async def list_user_organizations(db: AsyncSession, user_id: str) -> List[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == user_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_user_workspaces(db: AsyncSession, user_id: str, organization_id: Optional[str] = None) -> List[Workspace]:
        stmt = (
            select(Workspace)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == user_id)
        )
        if organization_id:
            stmt = stmt.where(Workspace.organization_id == organization_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_workspace(db: AsyncSession, user_id: str, request: WorkspaceCreate) -> Workspace:
        # Check org exists
        org = await db.get(Organization, request.organization_id)
        if not org:
            raise ResourceNotFoundException("Organization", request.organization_id)

        workspace = Workspace(
            organization_id=request.organization_id,
            name=request.name,
            slug=request.slug,
            description=request.description,
            is_active=request.is_active,
        )
        db.add(workspace)
        await db.flush()

        # Add creator membership
        membership = WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user_id,
            role="ADMIN",
        )
        db.add(membership)
        await db.commit()
        await db.refresh(workspace)
        return workspace

