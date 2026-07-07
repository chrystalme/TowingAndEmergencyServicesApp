"""Test configuration and fixtures."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_async_session
from app.models import Base
from app.core.auth import get_user_manager, user_engine, UserAsyncSessionLocal
from app.core.settings import settings
from fastapi import Depends


# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

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


async def override_get_async_session() -> AsyncSession:
    async with TestAsyncSessionLocal() as session:
        yield session


# Override the auth module's engine and session factory for tests
test_user_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestUserAsyncSessionLocal = async_sessionmaker(
    bind=test_user_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def override_get_user_db():
    """Override for user database in tests."""
    async with TestUserAsyncSessionLocal() as session:
        from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
        from app.models import User
        yield SQLAlchemyUserDatabase(session, User)


async def override_get_user_manager(
    user_db=Depends(override_get_user_db),
):
    """Override for user manager in tests."""
    from app.core.auth import UserManager
    yield UserManager(user_db)


@pytest_asyncio.fixture(autouse=True)
async def init_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Also create tables in the test user engine
    async with test_user_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with test_user_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_async_session] = override_get_async_session
    # Also override auth dependencies
    from app.core.auth import get_user_manager
    app.dependency_overrides[get_user_manager] = override_get_user_manager
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(client: AsyncClient):
    """Create a test user and return its credentials."""
    user_data = {"email": "test@example.com", "password": "testpassword123"}
    response = await client.post("/api/auth/register", json=user_data)
    assert response.status_code == 201
    return user_data


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: dict):
    """Get auth headers for the test user."""
    response = await client.post("/api/auth/jwt/login", data={
        "username": test_user["email"],
        "password": test_user["password"],
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}