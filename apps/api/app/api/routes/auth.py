from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.services.permission_service import get_current_user
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    AuthSessionResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new user, creates initial organization & workspace, and returns auth session."""
    session = await AuthService.register(db, request)
    await db.commit()
    return session

@router.post("/login", response_model=AuthSessionResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticates a user and returns tokens with tenant context."""
    session = await AuthService.login(db, request)
    await db.commit()
    return session

@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Rotates refresh token and returns fresh token pair."""
    tokens = await AuthService.refresh_tokens(db, request.refresh_token)
    await db.commit()
    return tokens

@router.post("/logout")
async def logout(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Revokes refresh token."""
    await AuthService.logout(db, request.refresh_token)
    return {"status": "ok", "message": "Successfully logged out"}

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    """Returns profile and roles for the authenticated user."""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        roles=[],
        permissions=[],
    )

