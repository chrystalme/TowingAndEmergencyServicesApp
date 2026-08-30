"""The test database engine, in a plain importable module.

conftest.py cannot serve this purpose. pytest loads it under its own module
name, so `from app.tests.conftest import TestAsyncSessionLocal` re-executes the
file and builds a *second*, empty in-memory database — queries then fail with
"no such table" that look nothing like the actual cause.

Keeping the engine here means conftest and ordinary test helpers share one
object, and helpers can reach the database without that trap.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# StaticPool keeps every session on the same in-memory connection, so the schema
# created by the init_db fixture is visible everywhere.
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def approve_driver(email: str) -> None:
    """Grant the driver role, as an administrator would.

    Registration creates a commuter. Driving is permissioned, so a test that
    needs a working driver has to approve one — the same step the product
    requires before a tow van can receive real clients.
    """
    from sqlalchemy import select

    from app.models import User

    async with TestAsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one()
        user.role = "driver"
        await session.commit()
