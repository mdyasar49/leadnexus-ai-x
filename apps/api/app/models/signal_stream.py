"""
LeadNexus AI X - Phase 47: Real-Time Streaming Intelligence & Live Signal Broadcast Models
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Float, JSON, Integer, Boolean
from app.db.base import Base


class SignalType(str, Enum):
    TECH_ADOPTION = "TECH_ADOPTION"
    HIRING_SURGE = "HIRING_SURGE"
    LEADERSHIP_CHANGE = "LEADERSHIP_CHANGE"
    FUNDING_ROUND = "FUNDING_ROUND"
    BUYING_INTENT = "BUYING_INTENT"
    CONTRACT_AWARD = "CONTRACT_AWARD"


class LiveSignalRecord(Base):
    __tablename__ = "live_stream_signals"

    id = Column(String(64), primary_key=True, default=lambda: f"sig_{uuid.uuid4().hex[:12]}")
    signal_type = Column(String(32), nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    entity_key = Column(String(255), nullable=True, index=True)
    topic = Column(String(128), nullable=False, index=True)
    payload = Column(JSON, default=dict)
    confidence = Column(Float, default=0.95)
    source = Column(String(128), default="LIVE_STREAM")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class StreamSubscriptionRecord(Base):
    __tablename__ = "stream_subscriptions"

    id = Column(String(64), primary_key=True, default=lambda: f"sub_{uuid.uuid4().hex[:12]}")
    user_id = Column(String(64), nullable=True, index=True)
    topic = Column(String(128), nullable=False, index=True)
    filter_criteria = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SignalAnomalyAlert(Base):
    __tablename__ = "signal_anomaly_alerts"

    id = Column(String(64), primary_key=True, default=lambda: f"anom_{uuid.uuid4().hex[:12]}")
    company_name = Column(String(255), nullable=False, index=True)
    signal_count = Column(Integer, default=1)
    window_seconds = Column(Integer, default=300)
    severity = Column(String(32), default="HIGH")
    description = Column(String(512), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# --- Pydantic Schemas ---

class PublishSignalRequest(BaseModel):
    signal_type: SignalType
    company_name: str
    topic: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.95
    source: str = "LIVE_STREAM"
    entity_key: Optional[str] = None


class LiveSignalResponse(BaseModel):
    id: str
    signal_type: str
    company_name: str
    entity_key: Optional[str] = None
    topic: str
    payload: Dict[str, Any]
    confidence: float
    source: str
    timestamp: datetime


class CreateSubscriptionRequest(BaseModel):
    topic: str
    filter_criteria: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None


class SubscriptionResponse(BaseModel):
    id: str
    topic: str
    filter_criteria: Dict[str, Any]
    is_active: bool
    created_at: datetime


class AnomalyAlertResponse(BaseModel):
    id: str
    company_name: str
    signal_count: int
    window_seconds: int
    severity: str
    description: str
    timestamp: datetime


class StreamStatsResponse(BaseModel):
    active_subscriptions: int
    active_websocket_clients: int
    buffered_signals: int
    total_signals_published: int
    throughput_signals_per_sec: float
    drop_rate_percent: float
    active_topics: List[str]
