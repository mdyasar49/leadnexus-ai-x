"""Authentication and identity management service."""
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    ResourceNotFoundException,
)
from app.security.password import hash_password, verify_password
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    TokenType,
)
from app.models.user import User, RefreshToken
from app.models.tenant import Organization, Workspace, OrganizationMembership, WorkspaceMembership
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
    AuthSessionResponse,
)
from app.services.permission_service import get_user_permissions
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    async def register(db: AsyncSession, request: UserRegisterRequest) -> AuthSessionResponse:
        """Register a new user, create an organization & default workspace if needed, and issue tokens."""
        # Check for existing email
        existing_stmt = select(User).where(User.email == request.email.lower())
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ConflictException(f"User with email '{request.email}' already exists")

        # Create user
        user = User(
            email=request.email.lower(),
            password_hash=hash_password(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()

        # Create default organization & workspace
        org_name = request.organization_name or f"{request.first_name}'s Org"
        slug_base = org_name.lower().replace(" ", "-").replace("'", "")
        org = Organization(
            name=org_name,
            slug=f"{slug_base}-{user.id[:8]}",
            domain=request.email.split("@")[1] if "@" in request.email else None,
        )
        db.add(org)
        await db.flush()

        # Add Org Admin membership
        org_mem = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role="ADMIN",
        )
        db.add(org_mem)

        # Create Default Workspace
        ws = Workspace(
            organization_id=org.id,
            name="Default Workspace",
            slug=f"default-{user.id[:8]}",
            description="Default workspace for campaigns",
        )
        db.add(ws)
        await db.flush()

        # Add Workspace Admin membership
        ws_mem = WorkspaceMembership(
            workspace_id=ws.id,
            user_id=user.id,
            role="ADMIN",
        )
        db.add(ws_mem)
        await db.flush()

        # Issue tokens
        tokens = await AuthService._create_session_tokens(db, user.id)

        # Log audit
        await AuditService.log_action(
            db=db,
            action="user.register",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            organization_id=org.id,
            workspace_id=ws.id,
        )

        permissions = await get_user_permissions(user, db)
        user_profile = UserProfileResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            roles=["ADMIN"],
            permissions=permissions,
        )

        return AuthSessionResponse(
            user=user_profile,
            tokens=tokens,
            active_organization_id=org.id,
            active_workspace_id=ws.id,
        )

    @staticmethod
    async def login(db: AsyncSession, request: UserLoginRequest) -> AuthSessionResponse:
        """Authenticate user by email and password, issuing access & refresh tokens."""
        stmt = select(User).where(User.email == request.email.lower())
        user = (await db.execute(stmt)).scalar_one_or_none()

        if not user or not verify_password(request.password, user.password_hash):
            raise AuthenticationException("Invalid email or password")

        if not user.is_active:
            raise AuthenticationException("Account is inactive")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        db.add(user)

        tokens = await AuthService._create_session_tokens(db, user.id)

        # Find default org and workspace
        org_mem_stmt = select(OrganizationMembership).where(OrganizationMembership.user_id == user.id).limit(1)
        org_mem = (await db.execute(org_mem_stmt)).scalar_one_or_none()

        ws_mem_stmt = select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id).limit(1)
        ws_mem = (await db.execute(ws_mem_stmt)).scalar_one_or_none()

        org_id = org_mem.organization_id if org_mem else None
        ws_id = ws_mem.workspace_id if ws_mem else None

        await AuditService.log_action(
            db=db,
            action="user.login",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            organization_id=org_id,
            workspace_id=ws_id,
        )

        permissions = await get_user_permissions(user, db)
        roles = []
        if org_mem:
            roles.append(org_mem.role)

        user_profile = UserProfileResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            roles=roles,
            permissions=permissions,
        )

        return AuthSessionResponse(
            user=user_profile,
            tokens=tokens,
            active_organization_id=org_id,
            active_workspace_id=ws_id,
        )

    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
        """Validate refresh token, enforce single-use rotation, and issue a fresh pair."""
        payload = decode_token(refresh_token_str)
        if not payload or payload.get("type") != TokenType.REFRESH:
            raise AuthenticationException("Invalid refresh token")

        token_id = payload.get("jti")
        user_id = payload.get("sub")
        token_hash = hash_token(refresh_token_str)

        # Check in DB
        stmt = select(RefreshToken).where(
            RefreshToken.id == token_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        stored_token = (await db.execute(stmt)).scalar_one_or_none()
        if not stored_token:
            raise AuthenticationException("Refresh token is revoked or invalid")

        if stored_token.expires_at < datetime.now(timezone.utc):
            raise AuthenticationException("Refresh token has expired")

        # Mark previous token revoked (Rotation)
        stored_token.revoked = True
        db.add(stored_token)
        await db.flush()

        # Issue new token pair
        return await AuthService._create_session_tokens(db, user_id)

    @staticmethod
    async def logout(db: AsyncSession, refresh_token_str: str) -> bool:
        """Revoke a refresh token on logout."""
        token_hash = hash_token(refresh_token_str)
        stmt = update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True)
        await db.execute(stmt)
        await db.commit()
        return True

    @staticmethod
    async def _create_session_tokens(db: AsyncSession, user_id: str) -> TokenResponse:
        access_token = create_access_token(user_id=user_id)
        refresh_token, jti, expires_at = create_refresh_token(user_id=user_id)

        token_record = RefreshToken(
            id=jti,
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
            revoked=False,
        )
        db.add(token_record)
        await db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

