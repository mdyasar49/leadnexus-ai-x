from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.tenant_service import TenantService
from app.services.permission_service import get_current_user
from app.models.user import User
from app.schemas.tenant import (
    OrganizationResponse,
    WorkspaceResponse,
    WorkspaceCreate,
)

router = APIRouter(tags=["Tenancy & Workspaces"])

@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists organizations that the authenticated user belongs to."""
    orgs = await TenantService.list_user_organizations(db, user.id)
    return orgs

@router.get("/workspaces", response_model=List[WorkspaceResponse])
async def list_workspaces(
    organization_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists workspaces accessible to the user."""
    workspaces = await TenantService.list_user_workspaces(db, user.id, organization_id=organization_id)
    return workspaces

@router.post("/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new workspace within an organization."""
    workspace = await TenantService.create_workspace(db, user.id, request)
    return workspace

