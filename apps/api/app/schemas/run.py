"""ResearchRun and ResearchJob schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.run import RunStatus, JobStatus


class ResearchJobResponse(BaseModel):
    id: str
    run_id: str
    source_key: str
    stage: str
    status: JobStatus
    items_discovered: int
    items_processed: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ResearchRunResponse(BaseModel):
    id: str
    campaign_id: str
    status: RunStatus
    trigger_type: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stats: Dict[str, Any]
    error_summary: Optional[str] = None
    created_at: datetime
    jobs: List[ResearchJobResponse] = []

    class Config:
        from_attributes = True


class RunStartRequest(BaseModel):
    trigger_type: str = "manual"
    source_filter: Optional[List[str]] = None


class RunActionResponse(BaseModel):
    run_id: str
    action: str
    status: RunStatus
    message: str

