"""Campaign and CampaignConfig Pydantic schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.campaign import CampaignStatus


class CampaignConfigBase(BaseModel):
    country: Optional[str] = "Global"
    state: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    company_keywords: List[str] = Field(default_factory=list)
    intent_keywords: List[str] = Field(default_factory=list)
    target_job_titles: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=lambda: ["github", "company_website"])
    maximum_results: int = Field(default=100, ge=1, le=10000)
    icp_rules: Dict[str, Any] = Field(default_factory=dict)
    exclusion_criteria: Dict[str, Any] = Field(default_factory=dict)
    rate_limits: Dict[str, Any] = Field(default_factory=dict)


class CampaignConfigCreate(CampaignConfigBase):
    pass


class CampaignConfigUpdate(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    company_keywords: Optional[List[str]] = None
    intent_keywords: Optional[List[str]] = None
    target_job_titles: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    maximum_results: Optional[int] = None
    icp_rules: Optional[Dict[str, Any]] = None
    exclusion_criteria: Optional[Dict[str, Any]] = None
    rate_limits: Optional[Dict[str, Any]] = None


class CampaignConfigResponse(CampaignConfigBase):
    id: str
    campaign_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    template_id: Optional[str] = None
    config: Optional[CampaignConfigCreate] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    config: Optional[CampaignConfigUpdate] = None


class CampaignResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str] = None
    status: CampaignStatus
    version: int
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    config: Optional[CampaignConfigResponse] = None

    class Config:
        from_attributes = True


class CampaignTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    description: Optional[str] = None
    is_system: bool
    config_defaults: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateInstantiateRequest(BaseModel):
    campaign_name: str = Field(..., min_length=2, max_length=255)
    overrides: Optional[Dict[str, Any]] = None

