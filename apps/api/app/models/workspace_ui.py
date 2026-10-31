from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AlertChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class EntityType(str, Enum):
    COMPANY = "COMPANY"
    PERSON = "PERSON"
    EVIDENCE = "EVIDENCE"
    RUN = "RUN"


class ExportStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExportFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"
    GOOGLE_SHEET = "GOOGLE_SHEET"


class SavedSearch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_searches"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    query = Column(String(500), nullable=True)
    filters = Column(JSON, default=dict, nullable=False)
    sort_field = Column(String(100), default="lead_score", nullable=False)
    sort_direction = Column(String(10), default="desc", nullable=False)
    columns = Column(JSON, default=list, nullable=False)
    
    alert_enabled = Column(Boolean, default=False, nullable=False)
    alert_channel = Column(String(50), default="IN_APP", nullable=False)
    alert_frequency = Column(String(50), default="DAILY", nullable=False)
    alert_threshold = Column(Float, default=0.0, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    is_shared = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_saved_search_ws_user", "workspace_id", "user_id"),
    )


class SavedView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_views"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    view_type = Column(String(50), default="LEADS", nullable=False)
    columns = Column(JSON, default=list, nullable=False)
    sort_by = Column(String(100), default="lead_priority_score", nullable=False)
    sort_direction = Column(String(10), default="desc", nullable=False)
    filters = Column(JSON, default=dict, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_saved_view_ws_user", "workspace_id", "user_id"),
    )


class Bookmark(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bookmarks"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    entity_type = Column(String(50), default="COMPANY", nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_bookmark_ws_user_entity", "workspace_id", "user_id", "entity_type", "entity_id", unique=True),
    )


class ResearchNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_notes"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    author_name = Column(String(255), nullable=True)
    note_text = Column(Text, nullable=False)
    tags = Column(JSON, default=list, nullable=False)

    __table_args__ = (
        Index("idx_note_ws_company", "workspace_id", "company_id"),
    )


class Watchlist(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlists"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    watch_type = Column(String(50), nullable=False, index=True)  # COMPANY, TECHNOLOGY, INTENT, SAVED_SEARCH
    target_value = Column(String(255), nullable=False)
    criteria = Column(JSON, default=dict, nullable=False)
    last_notified_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_watchlist_ws_user", "workspace_id", "user_id"),
    )


class ExportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "export_jobs"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    export_format = Column(String(50), default="CSV", nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    file_path = Column(String(1000), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    filter_snapshot = Column(JSON, default=dict, nullable=False)
    sensitive_fields_included = Column(Boolean, default=False, nullable=False)
    download_url = Column(String(500), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_export_ws_user", "workspace_id", "user_id"),
    )


class SearchDataset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "search_datasets"

    workspace_id = Column(String(36), nullable=False, index=True)
    query_hash = Column(String(64), nullable=False, index=True)
    filters = Column(JSON, default=dict, nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    result_blob = Column(JSON, default=dict, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_dataset_ws_hash", "workspace_id", "query_hash"),
    )
