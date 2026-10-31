"""Permission, authentication and RBAC dependency services."""
from typing import Optional, List, Callable
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
    TenantAccessDeniedException,
    ResourceNotFoundException,
)
from app.security.tokens import decode_token, TokenType
from app.models.user import User
from app.models.tenant import Workspace, WorkspaceMembership, OrganizationMembership
from app.models.rbac import Role, Permission, RolePermission

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return active User with roles."""
    if not credentials:
        raise AuthenticationException("Authorization token missing")

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise AuthenticationException("Invalid or expired access token")

    token_type = payload.get("type")
    if token_type != TokenType.ACCESS:
        raise AuthenticationException("Provided token is not an access token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Malformed token claims")

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationException("User not found")

    if not user.is_active:
        raise AuthenticationException("User account is inactive")

    return user


async def get_user_permissions(user: User, db: AsyncSession) -> List[str]:
    """Retrieve all permission codes for a user across roles."""
    if user.is_superuser:
        # Superuser has all permissions
        stmt = select(Permission.code)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # Get roles via workspace/org memberships
    # For now, collect permissions from role_permissions joined with memberships
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(WorkspaceMembership, WorkspaceMembership.role == Role.name)
        .where(WorkspaceMembership.user_id == user.id)
    )
    result = await db.execute(stmt)
    perms = set(result.scalars().all())

    # Also check organization membership roles
    org_stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(OrganizationMembership, OrganizationMembership.role == Role.name)
        .where(OrganizationMembership.user_id == user.id)
    )
    org_result = await db.execute(org_stmt)
    perms.update(org_result.scalars().all())

    return list(perms)


def require_permission(permission_code: str) -> Callable:
    """Dependency that enforces a specific permission code."""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        perms = await get_user_permissions(current_user, db)
        if permission_code not in perms and "*" not in perms:
            raise PermissionDeniedException(f"Missing required permission: '{permission_code}'")

        return current_user

    return permission_checker


async def get_active_workspace(
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Validate and resolve tenant workspace context for the current request."""
    if not x_workspace_id:
        # Fall back to user's first available workspace
        stmt = (
            select(Workspace)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(WorkspaceMembership.user_id == current_user.id)
            .limit(1)
        )
        result = await db.execute(stmt)
        workspace = result.scalar_one_or_none()
        if not workspace:
            if current_user.is_superuser:
                # Fallback to any active workspace for superuser
                all_ws = await db.execute(select(Workspace).limit(1))
                workspace = all_ws.scalar_one_or_none()
            if not workspace:
                raise TenantAccessDeniedException("No workspace found for user")
        return workspace

    # Verify workspace exists
    stmt = select(Workspace).where(Workspace.id == x_workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise ResourceNotFoundException("Workspace", x_workspace_id)

    # Superuser bypasses tenant membership check
    if current_user.is_superuser:
        return workspace

    # Verify user has membership in workspace or org
    mem_stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == x_workspace_id,
        WorkspaceMembership.user_id == current_user.id,
    )
    mem_result = await db.execute(mem_stmt)
    membership = mem_result.scalar_one_or_none()

    if not membership:
        # Check org level membership
        org_mem_stmt = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == workspace.organization_id,
            OrganizationMembership.user_id == current_user.id,
        )
        org_mem_result = await db.execute(org_mem_stmt)
        if not org_mem_result.scalar_one_or_none():
            raise TenantAccessDeniedException(f"User is not a member of workspace '{x_workspace_id}'")

    return workspace

