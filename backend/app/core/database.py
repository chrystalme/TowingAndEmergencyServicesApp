"""Database utilities for the FastAPI app.

Provides:
- ``engine`` – async SQLAlchemy engine using the ``DATABASE_URL``
- ``AsyncSessionLocal`` – session factory for dependency injection
- ``get_async_session`` – FastAPI dependency that yields a session
"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

from ..core.settings import settings

# How long a connection may sit inside an open transaction doing nothing before
# Postgres closes it. This is a BACKSTOP, not the fix: a leaked transaction holds
# its locks for as long as it lives, and one that lived an hour blocked a
# migration's ALTER TABLE until the deploy gave up and rolled back.
#
# Sixty seconds is far longer than any request here legitimately needs, and short
# enough that a leak cannot outlive a deploy. Migrations are unaffected: Alembic
# connects through its own synchronous engine, and a running migration is
# *active*, not idle.
IDLE_IN_TRANSACTION_TIMEOUT_MS = 60_000


def _connect_args() -> dict:
    """asyncpg server settings, when the target actually is asyncpg.

    Guarded because the same module is imported when the URL points at SQLite
    (tests, tooling), where ``server_settings`` is not a valid argument and
    would fail at connect time rather than here.
    """
    if "+asyncpg" not in settings.DATABASE_URL:
        return {}
    return {
        "server_settings": {
            "idle_in_transaction_session_timeout": str(IDLE_IN_TRANSACTION_TIMEOUT_MS),
        }
    }


engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    # Hand back a connection the server has since closed and the first query
    # fails; pre-ping trades a trivial round trip for not surfacing that as a
    # 500 to whoever happened to arrive next.
    pool_pre_ping=True,
    connect_args=_connect_args(),
)

# Session factory – ``expire_on_commit=False`` keeps objects usable after commit
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    future=True,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that provides a transactional async session.

    The session is always closed out explicitly, because relying on the context
    manager alone was not enough. A read opens a transaction whether or not the
    handler writes anything, and if that transaction is still open when the
    connection returns to the pool, Postgres reports the connection as
    ``idle in transaction`` and it keeps every lock it acquired.

    **Do not use this on a WebSocket route.** A dependency lives as long as the
    connection it was injected into, so on a socket that stays open for hours,
    so does the session and its transaction. Open a short-lived session with
    ``AsyncSessionLocal`` around the queries instead — see ``tracking_ws``.

    Usage::
        @router.get('/')
        async def read(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            # Includes the client disconnecting mid-request, which raises
            # through the dependency and would otherwise leave the transaction
            # open until the pool happened to recycle the connection.
            await session.rollback()
            raise
        else:
            # A handler that only read has still opened a transaction. End it
            # here rather than leaving it to be cleaned up later.
            await session.rollback()
