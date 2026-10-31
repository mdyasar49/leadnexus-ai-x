from datetime import datetime, timezone, time
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.monitoring import (
    Notification,
    NotificationPreference,
    NotificationChannel,
    DigestFrequency,
    SignificanceLevel
)


class NotificationService:
    """
    Handles in-app notifications, user notification preferences,
    quiet-hours filtering, notification grouping, and digest generation.
    """

    SEVERITY_RANKS = {
        "INFO": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_preference(
        self,
        workspace_id: str,
        user_id: str,
        category: str = "LEAD",
        min_severity: str = "MEDIUM",
        channel: str = "IN_APP",
        digest_frequency: str = "IMMEDIATE",
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None
    ) -> NotificationPreference:
        """Fetch or initialize notification preferences for a user."""
        pref = self.db.query(NotificationPreference).filter(
            and_(
                NotificationPreference.workspace_id == workspace_id,
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category
            )
        ).first()

        if not pref:
            pref = NotificationPreference(
                workspace_id=workspace_id,
                user_id=user_id,
                category=category,
                min_severity=min_severity,
                channel=channel,
                digest_frequency=digest_frequency,
                quiet_hours_start=quiet_hours_start,
                quiet_hours_end=quiet_hours_end
            )
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def update_preference(
        self,
        workspace_id: str,
        user_id: str,
        category: str,
        min_severity: Optional[str] = None,
        channel: Optional[str] = None,
        digest_frequency: Optional[str] = None,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None
    ) -> NotificationPreference:
        """Update user preferences for a category."""
        pref = self.get_or_create_preference(workspace_id=workspace_id, user_id=user_id, category=category)
        if min_severity:
            pref.min_severity = min_severity
        if channel:
            pref.channel = channel
        if digest_frequency:
            pref.digest_frequency = digest_frequency
        if quiet_hours_start is not None:
            pref.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
            pref.quiet_hours_end = quiet_hours_end

        self.db.commit()
        self.db.refresh(pref)
        return pref

    def is_in_quiet_hours(self, quiet_hours_start: Optional[str], quiet_hours_end: Optional[str]) -> bool:
        """
        Check if the current UTC time falls within quiet hours (e.g. 22:00 to 07:00).
        Supports overnight ranges (e.g., 22:00 to 07:00).
        """
        if not quiet_hours_start or not quiet_hours_end:
            return False

        try:
            sh, sm = map(int, quiet_hours_start.split(":"))
            eh, em = map(int, quiet_hours_end.split(":"))
            start_time = time(sh, sm)
            end_time = time(eh, em)

            now_time = datetime.now(timezone.utc).time()

            if start_time <= end_time:
                # Same day range, e.g. 01:00 to 06:00
                return start_time <= now_time <= end_time
            else:
                # Overnight range, e.g. 22:00 to 07:00
                return now_time >= start_time or now_time <= end_time
        except Exception:
            return False

    def dispatch_notification(
        self,
        workspace_id: str,
        user_id: str,
        title: str,
        message: str,
        severity: str = "MEDIUM",
        category: str = "LEAD",
        alert_id: Optional[str] = None,
        force_dispatch: bool = False
    ) -> Optional[Notification]:
        """
        Dispatches notification adhering to user preference filters and quiet hours.
        Returns Notification if dispatched, or None if suppressed/queued.
        """
        pref = self.get_or_create_preference(workspace_id=workspace_id, user_id=user_id, category=category)

        # Check severity threshold
        user_min_rank = self.SEVERITY_RANKS.get(pref.min_severity, 2)
        notif_rank = self.SEVERITY_RANKS.get(severity, 2)

        if not force_dispatch and notif_rank < user_min_rank:
            # Below user threshold
            return None

        # Check quiet hours (Critical severity always bypasses quiet hours)
        if not force_dispatch and severity != "CRITICAL":
            if self.is_in_quiet_hours(pref.quiet_hours_start, pref.quiet_hours_end):
                # Suppressed during quiet hours; will be included in digest
                return None

        # Create in-app notification
        notif = Notification(
            workspace_id=workspace_id,
            user_id=user_id,
            alert_id=alert_id,
            title=title,
            message=message,
            channel=pref.channel,
            severity=severity,
            category=category,
            is_read=False
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def list_notifications(
        self,
        workspace_id: str,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """List notifications for a user."""
        query = self.db.query(Notification).filter(
            and_(Notification.workspace_id == workspace_id, Notification.user_id == user_id)
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()

    def mark_as_read(self, workspace_id: str, user_id: str, notification_id: str) -> bool:
        """Mark a single notification as read."""
        notif = self.db.query(Notification).filter(
            and_(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
                Notification.id == notification_id
            )
        ).first()
        if not notif:
            return False
        notif.is_read = True
        self.db.commit()
        return True

    def mark_all_as_read(self, workspace_id: str, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        unread = self.db.query(Notification).filter(
            and_(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).all()
        for n in unread:
            n.is_read = True
        self.db.commit()
        return len(unread)

    def generate_digest(
        self,
        workspace_id: str,
        user_id: str,
        frequency: str = "DAILY"
    ) -> Dict[str, Any]:
        """
        Bundles notifications into a daily or weekly digest summary.
        Groups notifications by category and severity.
        """
        notifications = self.db.query(Notification).filter(
            and_(
                Notification.workspace_id == workspace_id,
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).order_by(desc(Notification.created_at)).all()

        by_category: Dict[str, List[Dict[str, Any]]] = {}
        by_severity: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

        for n in notifications:
            by_severity[n.severity] = by_severity.get(n.severity, 0) + 1
            if n.category not in by_category:
                by_category[n.category] = []
            by_category[n.category].append({
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "created_at": n.created_at.isoformat() if n.created_at else None
            })

        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "frequency": frequency,
            "total_pending_count": len(notifications),
            "severity_breakdown": by_severity,
            "category_groups": by_category,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
