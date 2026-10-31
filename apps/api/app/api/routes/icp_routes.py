from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.tenant import Workspace
from app.models.lead import Company
from app.models.scoring import ICPProfile
from app.services.permission_service import get_active_workspace, get_current_user
from packages.scoring.icp_engine import ICPEngine

router = APIRouter(prefix="/icp", tags=["ICP Management & Evaluation"])


class ICPCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    target_industries: List[str] = ["Retail", "Manufacturing", "IT"]
    target_countries: List[str] = ["Australia"]
    target_technologies: List[str] = ["Odoo", "ERP"]
    target_job_titles: List[str] = ["CTO", "IT Manager"]
    min_employees: int = 5
    max_employees: int = 5000


@router.get("/profiles")
async def list_icp_profiles(
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(ICPProfile).where(ICPProfile.workspace_id == ws.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def create_icp_profile(
    req: ICPCreateRequest,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = ICPProfile(
        workspace_id=ws.id,
        name=req.name,
        description=req.description,
        target_industries=req.target_industries,
        target_countries=req.target_countries,
        target_technologies=req.target_technologies,
        target_job_titles=req.target_job_titles,
        min_employees=req.min_employees,
        max_employees=req.max_employees
    )
    db.add(profile)
    await db.commit()
    return profile


@router.get("/evaluate/{lead_id}")
async def evaluate_lead_icp(
    lead_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Company).where(Company.id == lead_id, Company.workspace_id == ws.id)
    comp = (await db.execute(stmt)).scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Lead not found")

    company_payload = {
        "name": comp.name,
        "country": comp.country,
        "industry": comp.industry,
        "employee_count_range": comp.employee_count_range
    }
    evaluation = ICPEngine.evaluate_fit(company_payload)
    return evaluation
