"""
Session Posture & Visibility Manager (Phase 38)
Tracks active enterprise user sessions, client device postures, concurrent sessions,
and provides remote session revocation kill-switches.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import uuid
from typing import Any, Dict, List, Optional


class SessionPostureManager:
    """Manages active user sessions, device tracking, and instant remote revocation."""

    @classmethod
    def hash_session_token(cls, token: str) -> str:
        """Deterministically hashes session token using SHA-256."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def parse_device_info(cls, user_agent: str) -> str:
        """Derives friendly device & browser classification from User-Agent string."""
        ua_lower = user_agent.lower()
        device = "Desktop"
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device = "Mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device = "Tablet"

        browser = "Browser"
        if "edg" in ua_lower:
            browser = "Edge"
        elif "chrome" in ua_lower:
            browser = "Chrome"
        elif "firefox" in ua_lower:
            browser = "Firefox"
        elif "safari" in ua_lower:
            browser = "Safari"

        return f"{device} ({browser})"

    @classmethod
    def create_session_record(
        cls,
        user_id: str,
        session_token: str,
        ip_address: str,
        user_agent: str,
        ttl_hours: int = 24,
    ) -> Dict[str, Any]:
        """Creates metadata for a new active session."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)
        token_hash = cls.hash_session_token(session_token)
        device_info = cls.parse_device_info(user_agent)

        return {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_token_hash": token_hash,
            "ip_address": ip_address or "127.0.0.1",
            "user_agent": user_agent or "Unknown",
            "device_info": device_info,
            "is_revoked": False,
            "last_activity_at": now,
            "expires_at": expires_at,
            "created_at": now,
        }

    @classmethod
    def is_session_valid(cls, session: Any) -> bool:
        """Checks if session is active, unrevoked, and unexpired."""
        if getattr(session, "is_revoked", False):
            return False

        expires_at = getattr(session, "expires_at", None)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False

        return True

    @classmethod
    def revoke_session(cls, session: Any) -> bool:
        """Revokes a specific session."""
        session.is_revoked = True
        return True

    @classmethod
    def revoke_all_user_sessions(cls, sessions: List[Any], except_session_hash: Optional[str] = None) -> int:
        """Revokes all sessions for a user, optionally preserving the current one."""
        revoked_count = 0
        for s in sessions:
            if except_session_hash and getattr(s, "session_token_hash", "") == except_session_hash:
                continue
            if not getattr(s, "is_revoked", False):
                s.is_revoked = True
                revoked_count += 1
        return revoked_count

