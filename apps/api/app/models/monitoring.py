from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MonitorTargetType(str, Enum):
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    CONTACT = "CONTACT"
    DOMAIN = "DOMAIN"
    WEBSITE = "WEBSITE"
    TECHNOLOGY = "TECHNOLOGY"
    JOB = "JOB"
    GITHUB_REPOSITORY = "GITHUB_REPOSITORY"
    INTENT = "INTENT"
    SAVED_SEARCH = "SAVED_SEARCH"


class ChangeClass(str, Enum):
    NOISE = "NOISE"
    LAYOUT_ONLY = "LAYOUT_ONLY"
    CONTENT_CHANGE = "CONTENT_CHANGE"
    BUSINESS_CHANGE = "BUSINESS_CHANGE"
    TECHNOLOGY_CHANGE = "TECHNOLOGY_CHANGE"
    LEADERSHIP_CHANGE = "LEADERSHIP_CHANGE"
    CONTACT_CHANGE = "CONTACT_CHANGE"
    INTENT_CHANGE = "INTENT_CHANGE"
    SCORE_CHANGE = "SCORE_CHANGE"
    QUALITY_CHANGE = "QUALITY_CHANGE"


class SignificanceLevel(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    SNOOZED = "SNOOZED"
    EXPIRED = "EXPIRED"


class WatchlistType(str, Enum):
    ENTITY_WATCHLIST = "ENTITY_WATCHLIST"
    SEARCH_WATCHLIST = "SEARCH_WATCHLIST"
    CAMPAIGN_WATCHLIST = "CAMPAIGN_WATCHLIST"
    TECHNOLOGY_WATCHLIST = "TECHNOLOGY_WATCHLIST"
    SIGNAL_WATCHLIST = "SIGNAL_WATCHLIST"


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class DigestFrequency(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class AlertFeedbackType(str, Enum):
    USEFUL = "USEFUL"
    NOT_USEFUL = "NOT_USEFUL"
    DUPLICATE = "DUPLICATE"
    WRONG = "WRONG"
    TOO_FREQUENT = "TOO_FREQUENT"
    NOT_RELEVANT = "NOT_RELEVANT"


# 1. Monitoring Rules & Checkpoints
class MonitorRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitor_rules"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    target_type = Column(String(50), default="COMPANY", nullable=False)
    target_id = Column(String(36), nullable=True, index=True)
    frequency = Column(String(50), default="DAILY", nullable=False)
    conditions = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_mon_rule_ws_type", "workspace_id", "target_type"),
    )


class MonitorCheckpoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitor_checkpoints"

    workspace_id = Column(String(36), nullable=False, index=True)
    monitor_id = Column(String(36), ForeignKey("monitor_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    cursor = Column(String(255), nullable=True)
    snapshot_hash = Column(String(64), nullable=True)
    last_attempt = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)


# 2. Change Events
class EntityChangeEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_change_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_class = Column(String(50), default="CONTENT_CHANGE", nullable=False)
    significance_score = Column(Float, default=50.0, nullable=False)  # 0-100
    significance_level = Column(String(50), default="MEDIUM", nullable=False, index=True)
    
    source_name = Column(String(100), nullable=False)
    source_url = Column(String(1000), nullable=False)
    evidence_snippet = Column(Text, nullable=True)
    
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_chg_event_ws_entity", "workspace_id", "entity_type", "entity_id"),
        Index("idx_chg_event_ws_sig", "workspace_id", "significance_level"),
    )


# 3. Intelligent Alerts & Deduplication
class Alert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alerts"

    workspace_id = Column(String(36), nullable=False, index=True)
    rule_id = Column(String(36), nullable=True, index=True)
    change_event_id = Column(String(36), ForeignKey("entity_change_events.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    
    alert_category = Column(String(50), default="LEAD", nullable=False, index=True)
    severity = Column(String(50), default="MEDIUM", nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    evidence_summary = Column(Text, nullable=True)
    
    status = Column(String(50), default="OPEN", nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(36), nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_alert_ws_status", "workspace_id", "status"),
        Index("idx_alert_ws_fingerprint", "workspace_id", "fingerprint"),
    )


class AlertFingerprint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alert_fingerprints"

    workspace_id = Column(String(36), nullable=False, index=True)
    fingerprint_hash = Column(String(64), nullable=False, index=True)
    alert_id = Column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    occurrence_count = Column(Integer, default=1, nullable=False)


class AlertFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "alert_feedbacks"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)


# 4. Watchlists
class Watchlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitoring_watchlists"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    watchlist_type = Column(String(50), default="ENTITY_WATCHLIST", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_wl_ws_user", "workspace_id", "user_id"),
    )


class WatchlistItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "monitoring_watchlist_items"

    workspace_id = Column(String(36), nullable=False, index=True)
    watchlist_id = Column(String(36), ForeignKey("monitoring_watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    priority = Column(String(50), default="NORMAL", nullable=False)
    last_checked = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


# 5. Notifications & Preferences
class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(String(36), nullable=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(String(50), default="IN_APP", nullable=False)
    severity = Column(String(50), default="MEDIUM", nullable=False)
    category = Column(String(50), default="LEAD", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)

    __table_args__ = (
        Index("idx_notif_ws_user_read", "workspace_id", "user_id", "is_read"),
    )


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_preferences"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), default="LEAD", nullable=False)
    min_severity = Column(String(50), default="MEDIUM", nullable=False)
    channel = Column(String(50), default="IN_APP", nullable=False)
    digest_frequency = Column(String(50), default="IMMEDIATE", nullable=False)
    quiet_hours_start = Column(String(10), nullable=True)  # e.g. "22:00"
    quiet_hours_end = Column(String(10), nullable=True)    # e.g. "07:00"


# 6. Collaboration (Notes, Comments, Mentions, Tags)
class EntityNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_notes"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    author_name = Column(String(255), nullable=True)
    note_text = Column(Text, nullable=False)
    tags = Column(JSON, default=list, nullable=False)


class EntityComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_comments"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    comment_text = Column(Text, nullable=False)
    mentions = Column(JSON, default=list, nullable=False)  # list of user_ids mentioned


class EntityTag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_tags"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    tag_name = Column(String(100), nullable=False, index=True)


# 7. Intelligence Briefs
class IntelligenceBrief(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intelligence_briefs"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=True)
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=False)
    top_changes = Column(JSON, default=list, nullable=False)
    affected_leads = Column(JSON, default=list, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
