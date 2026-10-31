from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ResearchGapType(str, Enum):
    DOMAIN_MISSING = "DOMAIN_MISSING"
    DECISION_MAKER_MISSING = "DECISION_MAKER_MISSING"
    PHONE_MISSING = "PHONE_MISSING"
    EMAIL_MISSING = "EMAIL_MISSING"
    ODOO_EVIDENCE_WEAK = "ODOO_EVIDENCE_WEAK"
    LOCATION_UNCERTAIN = "LOCATION_UNCERTAIN"
    TECHNOLOGY_STALE = "TECHNOLOGY_STALE"


class SourceHealth(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_health_records"

    source_id = Column(String(36), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=True)
    source_key = Column(String(50), nullable=False, unique=True, index=True)
    
    success_rate = Column(Float, default=100.0, nullable=False)
    http_errors_count = Column(Integer, default=0, nullable=False)
    timeout_rate = Column(Float, default=0.0, nullable=False)
    blocked_rate = Column(Float, default=0.0, nullable=False)
    latency_ms = Column(Integer, default=150, nullable=False)
    
    is_healthy = Column(Boolean, default=True, nullable=False)
    status_summary = Column(String(100), default="OPERATIONAL", nullable=False)
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SourceHealthEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_health_events"

    source_key = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # e.g., "RATE_LIMITED", "BLOCKED", "TIMEOUT"
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    meta_info = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchCostEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_cost_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    source_key = Column(String(50), nullable=False, index=True)
    
    cost_usd = Column(Float, default=0.0, nullable=False)
    units = Column(Float, default=1.0, nullable=False)
    unit_type = Column(String(50), default="HTTP_REQUEST", nullable=False)  # "BROWSER_RENDER", "AI_TOKENS", "API_QUERY"
    meta_payload = Column(JSON, default=dict, nullable=False)


class UsageBudget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_budgets"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    period = Column(String(50), default="MONTHLY", nullable=False)
    max_budget_usd = Column(Float, default=500.0, nullable=False)
    current_spend_usd = Column(Float, default=0.0, nullable=False)
    alert_threshold_pct = Column(Float, default=80.0, nullable=False)
    is_enforced = Column(Boolean, default=True, nullable=False)


class ResearchGap(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_gaps"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    gap_type = Column(String(50), default="DECISION_MAKER_MISSING", nullable=False, index=True)
    priority = Column(String(20), default="HIGH", nullable=False)
    status = Column(String(50), default="OPEN", nullable=False, index=True)
    suggested_query = Column(String(500), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)


class WebChangeEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "web_change_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    url = Column(String(1000), nullable=False, index=True)
    old_hash = Column(String(64), nullable=False)
    new_hash = Column(String(64), nullable=False)
    diff_summary = Column(Text, nullable=True)
    is_meaningful = Column(Boolean, default=True, nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SystemAlert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "system_alerts"

    severity = Column(String(20), default="WARNING", nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    source_component = Column(String(100), default="collector_engine", nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    meta_info = Column(JSON, default=dict, nullable=False)


class CollectorCheckpoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "collector_checkpoints"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=False, index=True)
    source_key = Column(String(50), nullable=False, index=True)
    
    cursor_data = Column(JSON, default=dict, nullable=False)
    last_url = Column(String(1000), nullable=True)
    items_processed = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

