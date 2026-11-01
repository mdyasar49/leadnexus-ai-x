"""
Just-In-Time (JIT) & Privileged Access Management (PAM) Engine (Phase 38)
Handles ephemeral privilege elevation, break-glass emergency overrides, and automatic entitlement expiry.
"""

from datetime import datetime, timezone, timedelta
import uuid
from typing import Any, Dict, List, Optional
from app.models.enterprise_identity import JITStatus, PAMStatus


class AccessElevationError(Exception):
    pass


class JITPAMEngine:
    """Manages ephemeral privilege elevation and Break-Glass emergency access."""

    @classmethod
    def request_jit_elevation(
        cls,
        workspace_id: str,
        user_id: str,
        requested_role: str,
        reason: str,
        duration_minutes: int = 60,
    ) -> Dict[str, Any]:
        """Creates a pending Just-In-Time role elevation request."""
        if duration_minutes < 5 or duration_minutes > 1440:
            raise AccessElevationError("JIT duration must be between 5 minutes and 24 hours (1440 mins).")

        return {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "requested_role": requested_role,
            "reason": reason,
            "duration_minutes": duration_minutes,
            "status": JITStatus.PENDING,
            "approved_by": None,
            "expires_at": None,
            "created_at": datetime.now(timezone.utc),
        }

    @classmethod
    def approve_jit_request(
        cls,
        grant: Any,
        approver_id: str,
    ) -> Dict[str, Any]:
        """Approves a pending JIT request, computing its expiration timestamp."""
        if getattr(grant, "status", "") != JITStatus.PENDING:
            raise AccessElevationError(f"Cannot approve request in status: {getattr(grant, 'status', '')}")

        now = datetime.now(timezone.utc)
        duration_minutes = getattr(grant, "duration_minutes", 60)
        expires_at = now + timedelta(minutes=duration_minutes)

        grant.status = JITStatus.APPROVED
        grant.approved_by = approver_id
        grant.expires_at = expires_at

        return {
            "id": str(grant.id),
            "status": JITStatus.APPROVED,
            "approved_by": approver_id,
            "expires_at": expires_at,
        }

    @classmethod
    def check_and_expire_grant(cls, grant: Any) -> bool:
        """Checks if an approved grant has passed its expiration time and updates it if so."""
        if getattr(grant, "status", "") == JITStatus.APPROVED and getattr(grant, "expires_at", None):
            expires_at = grant.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                grant.status = JITStatus.EXPIRED
                return True
        return False

    @classmethod
    def trigger_pam_break_glass(
        cls,
        workspace_id: str,
        user_id: str,
        ticket_reference: str,
        justification: str,
        duration_minutes: int = 30,
    ) -> Dict[str, Any]:
        """Activates Break-Glass emergency access with audit trail."""
        if not ticket_reference or len(ticket_reference.strip()) < 3:
            raise AccessElevationError("PAM Break-Glass requires a valid incident or ticket reference (e.g., INC-9102).")

        if not justification or len(justification.strip()) < 10:
            raise AccessElevationError("Detailed justification is mandatory for emergency PAM break-glass activation.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=duration_minutes)

        return {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "ticket_reference": ticket_reference.strip(),
            "justification": justification.strip(),
            "status": PAMStatus.ACTIVE,
            "duration_minutes": duration_minutes,
            "created_at": now,
            "expires_at": expires_at,
        }

    @classmethod
    def terminate_pam_session(cls, pam_record: Any) -> Dict[str, Any]:
        """Manually terminates an ongoing emergency break-glass session."""
        pam_record.status = PAMStatus.TERMINATED
        return {
            "id": str(pam_record.id),
            "status": PAMStatus.TERMINATED,
            "terminated_at": datetime.now(timezone.utc).isoformat(),
        }
