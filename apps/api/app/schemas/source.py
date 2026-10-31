"""Source registry schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.models.source import SourceType, SourceHealthStatus


class ResearchSourceResponse(BaseModel):
    id: str
    key: str
    name: str
    source_type: SourceType
    description: Optional[str] = None
    is_active: bool
    requires_auth: bool
    health_status: SourceHealthStatus
    rate_limit_per_minute: int
    concurrency_limit: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignSourceResponse(BaseModel):
    id: str
    campaign_id: str
    source_id: str
    is_enabled: bool
    priority: int
    custom_rate_limit: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignSourceUpdate(BaseModel):
    is_enabled: bool = True
    priority: int = 1
    custom_rate_limit: Optional[int] = None

