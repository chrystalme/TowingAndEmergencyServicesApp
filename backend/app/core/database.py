"""Database utilities for the FastAPI app.

Provides:
- ``engine`` – async SQLAlchemy engine using the ``DATABASE_URL``
- ``AsyncSessionLocal`` – session factory for dependency injection
- ``get_async_session`` – FastAPI dependency that yields a session
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from ..core.settings import settings

# Create async engine – echo disabled for production, enable for debugging if needed
engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

# Session factory – ``expire_on_commit=False`` keeps objects usable after commit
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    future=True,
)

async def get_async_session() -> AsyncSession:
    """FastAPI dependency that provides a transactional async session.

    Usage::
        @router.get('/')
        async def read(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
