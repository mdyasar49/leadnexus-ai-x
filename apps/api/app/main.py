import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure application path and packages path are on sys.path
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONOREPO_ROOT = os.path.dirname(os.path.dirname(APP_DIR))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if MONOREPO_ROOT not in sys.path:
    sys.path.insert(0, MONOREPO_ROOT)

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import LeadNexusException
from app.middleware.request_id import RequestIDMiddleware
from app.db.session import init_db, AsyncSessionLocal
from app.db.seed import seed_initial_data
from app.api.router import root_router, api_v1_router, api_direct_router

logger = get_logger("leadnexus.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for initialization and graceful teardown."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode...")
    
    # 1. Initialize DB schema
    await init_db()
    
    # 2. Seed system roles, sources, and templates
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    logger.info(f"{settings.APP_NAME} initialized successfully. Listening on {settings.API_HOST}:{settings.API_PORT}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Lead Intelligence, Research, Verification & Qualification Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request ID Tracking Middleware
app.add_middleware(RequestIDMiddleware)

# 3. Exception Handlers
@app.exception_handler(LeadNexusException)
async def leadnexus_exception_handler(request: Request, exc: LeadNexusException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"Unhandled exception [request_id={request_id}]: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "request_id": request_id
            }
        }
    )

# 4. Mount Routers
app.include_router(root_router)
app.include_router(api_v1_router)
app.include_router(api_direct_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=settings.DEBUG)

