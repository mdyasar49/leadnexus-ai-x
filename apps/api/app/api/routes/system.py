from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["System"])

@router.get("/info")
async def get_system_info():
    """System information endpoint."""
    return {
        "application": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "1.0.0",
        "debug": settings.DEBUG,
        "features": {
            "campaign_studio": True,
            "source_registry": True,
            "research_runs": True,
            "rbac": True,
            "multi_tenancy": True
        }
    }

