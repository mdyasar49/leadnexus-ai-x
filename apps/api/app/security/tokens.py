import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from app.core.config import settings

class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"

class TokenService:
    @staticmethod
    def create_access_token(data: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = (data or {}).copy()
        if user_id:
            to_encode["sub"] = str(user_id)
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        
        to_encode.update({
            "token_type": "access",
            "type": "access",
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4())
        })
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(data: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None, expires_delta: Optional[timedelta] = None) -> tuple[str, str, datetime]:
        """Returns (raw_token, token_jti, expires_at)."""
        to_encode = (data or {}).copy()
        if user_id:
            to_encode["sub"] = str(user_id)
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
        token_jti = str(uuid.uuid4())

        to_encode.update({
            "token_type": "refresh",
            "type": "refresh",
            "iat": now,
            "exp": expire,
            "jti": token_jti
        })
        raw_token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return raw_token, token_jti, expire

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decodes and validates a JWT token."""
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Computes SHA-256 hash of refresh token for database storage."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

create_access_token = TokenService.create_access_token
create_refresh_token = TokenService.create_refresh_token
decode_token = TokenService.decode_token
hash_token = TokenService.hash_token
