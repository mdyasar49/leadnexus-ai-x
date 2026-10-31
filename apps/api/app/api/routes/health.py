from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic liveness probe."""
    return {"status": "ok", "service": settings.APP_NAME}

@router.get("/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness probe checking database and cache dependencies."""
    dependencies = {
        "database": "unknown",
        "redis": "unknown"
    }
    is_ready = True

    # 1. Database check
    try:
        await db.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception as e:
        dependencies["database"] = f"failed: {str(e)}"
        is_ready = False

    # 2. Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.5)
        await r.ping()
        await r.aclose()
        dependencies["redis"] = "ok"
    except Exception:
        # If redis is optional in dev, we note it
        dependencies["redis"] = "degraded/unavailable"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "dependencies": dependencies}

    return {"status": "ready", "dependencies": dependencies}

