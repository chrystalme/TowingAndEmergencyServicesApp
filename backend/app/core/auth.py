"""FastAPI-Users authentication configuration - simplified setup."""

from collections.abc import AsyncGenerator
from typing import Any
from fastapi import Depends
from fastapi_users import FastAPIUsers, BaseUserManager, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .settings import settings
from ..models import User


class UserManager(BaseUserManager[User, int]):
    """User manager for FastAPI-Users with custom logic if needed."""

    reset_password_token_secret = settings.JWT_SECRET_KEY
    verification_token_secret = settings.JWT_SECRET_KEY

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")

    def parse_id(self, value: Any) -> int:
        """Parse a value into a correct ID instance."""
        return int(value)


# Create a dedicated engine and session factory for user management
# This avoids the dependency chain issue with get_async_session
user_engine = create_async_engine(settings.DATABASE_URL, echo=False)
UserAsyncSessionLocal = async_sessionmaker(
    bind=user_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """FastAPI dependency that yields a user database adapter."""
    async with UserAsyncSessionLocal() as session:
        yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """FastAPI dependency that yields a UserManager instance."""
    yield UserManager(user_db)


# Transport: Bearer token (JWT in Authorization header)
bearer_transport = BearerTransport(tokenUrl="/api/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.JWT_SECRET_KEY, lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


# FastAPI-Users instance
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# Dependencies for current user
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Routers
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(schemas.BaseUser[int], schemas.BaseUserCreate)
# Note: get_reset_password_router and get_verify_router have different signatures in newer versions
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(schemas.BaseUser[int])
users_router = fastapi_users.get_users_router(schemas.BaseUser[int], schemas.BaseUserUpdate)