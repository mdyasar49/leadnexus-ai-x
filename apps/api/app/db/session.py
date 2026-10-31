from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.db.base import Base

async_connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
sync_connect_args = {"check_same_thread": False} if "sqlite" in settings.SYNC_DATABASE_URL else {}

# Async Engine & Session (FastAPI routes)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=async_connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Synchronous Engine & Session (Worker tasks, batch scripts & unit tests)
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,
    connect_args=sync_connect_args
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_sync_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """Initializes tables for development/testing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def init_sync_db():
    """Synchronous database table creation."""
    Base.metadata.create_all(bind=sync_engine)
