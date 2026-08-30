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


# The engine lives in app/tests/testdb.py so ordinary test helpers can import
# it. Importing it from conftest re-executes this file under a second module
# name and builds a different, empty database.
from app.tests.testdb import TestAsyncSessionLocal, test_engine  # noqa: E402


async def override_get_async_session() -> AsyncSession:
    async with TestAsyncSessionLocal() as session:
        yield session


# Override the auth module's engine and session factory for tests.
# NOTE: we intentionally point the USER database at the SAME in-memory engine as
# the app data. Keeping them split (as originally) put `users` in a separate
# SQLite DB from `drivers`/`service_requests`/`dispatches`, which broke any query
# that joins User with app data (e.g. nearest-driver dispatch). In production all
# tables share one Postgres DB, so the single-engine test setup is the faithful one.


async def override_get_user_db():
    """Override for user database in tests - uses the same engine as app data."""
    async with TestAsyncSessionLocal() as session:
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
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """A session on the same in-memory engine the app is using.

    Tests must take this rather than importing TestAsyncSessionLocal directly:
    pytest loads conftest under its own module name, so a plain import
    re-executes this file and builds a second, empty database.
    """
    async with TestAsyncSessionLocal() as session:
        yield session


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


@pytest_asyncio.fixture
async def driver_factory(client: AsyncClient):
    """Register a user and approve them to drive.

    Driving is a granted role, so a freshly registered account cannot go
    online. Tests that need a working driver must approve one first, exactly
    as an administrator would.
    """
    from app.models import User as UserModel
    from sqlalchemy import select as _select

    async def _make(email: str, password: str = 'driverpass123'):
        resp = await client.post(
            '/api/auth/register', json={'email': email, 'password': password}
        )
        assert resp.status_code == 201, resp.text
        async with TestAsyncSessionLocal() as session:
            user = (
                await session.execute(_select(UserModel).where(UserModel.email == email))
            ).scalar_one()
            user.role = 'driver'
            await session.commit()
        login = await client.post(
            '/api/auth/jwt/login', data={'username': email, 'password': password}
        )
        assert login.status_code == 200, login.text
        return {'Authorization': f"Bearer {login.json()['access_token']}"}

    return _make


@pytest_asyncio.fixture
async def admin_factory(client: AsyncClient):
    """Factory that creates an admin/superuser directly in the shared test DB
    and returns login headers for them (registration can't grant superuser)."""
    from fastapi_users.password import PasswordHelper
    from app.models import User

    async def _make(email: str, password: str = "adminpass123"):
        async with TestAsyncSessionLocal() as session:
            session.add(
                User(
                    email=email,
                    hashed_password=PasswordHelper().hash(password),
                    is_superuser=True,
                    is_verified=True,
                    role="admin",
                )
            )
            await session.commit()
        login = await client.post(
            "/api/auth/jwt/login",
            data={"username": email, "password": password},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make