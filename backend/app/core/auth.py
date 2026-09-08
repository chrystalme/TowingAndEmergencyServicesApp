"""FastAPI-Users authentication configuration - simplified setup."""

from collections.abc import AsyncGenerator
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users import FastAPIUsers, BaseUserManager, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .settings import settings
from .database import get_async_session
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

# Roles. A user is a commuter by default; driving is a permissioned role,
# not something you get by tapping a button.
ROLE_COMMUTER = "commuter"
ROLE_DRIVER = "driver"
ROLE_COMPANY = "company"
ROLE_ADMIN = "admin"
ASSIGNABLE_ROLES = (ROLE_COMMUTER, ROLE_DRIVER, ROLE_COMPANY, ROLE_ADMIN)


def is_admin(user: User) -> bool:
    return bool(user.is_superuser) or (user.role or "").lower() == ROLE_ADMIN


def may_drive(user: User) -> bool:
    """Whether this user may enter the dispatch pool.

    Tow van operators are vetted — vehicle, licence, insurance — so driving
    is granted, never self-assigned. Admins are included so support can
    reproduce a driver's view.
    """
    return is_admin(user) or (user.role or "").lower() in (ROLE_DRIVER, ROLE_COMPANY)


# Dependencies for current user
#
# `current_active_user` accepts EITHER a fastapi-users JWT (the built-in
# email/password login) OR a Clerk session token (when Clerk is configured) —
# whichever the user signed in with works. The resolver is defined here so
# the name stays the same and no router or call site needs to change. See
# app/core/clerk_auth.py for the Clerk half.
async def current_active_user(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> User:
    # Clerk session-token path (no-op unless CLERK_SECRET_KEY is set).
    from .clerk_auth import resolve_clerk_user

    clerk_user = await resolve_clerk_user(request, session)
    if clerk_user is not None:
        return clerk_user

    # Built-in email/password JWT path — the original behaviour.
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:].strip() if authorization.startswith("Bearer ") else None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    strategy = get_jwt_strategy()
    manager = UserManager(SQLAlchemyUserDatabase(session, User))
    user = await strategy.read_token(token, manager)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Routers
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(schemas.BaseUser[int], schemas.BaseUserCreate)
# Note: get_reset_password_router and get_verify_router have different signatures in newer versions
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(schemas.BaseUser[int])

class UserRead(schemas.BaseUser[int]):
    """BaseUser plus the role, so a client can tell what surfaces to show.

    Without this /api/users/me returns no role at all and the apps have no
    way to know whether the caller may drive.
    """

    role: str = ROLE_COMMUTER


# Thin replacement for fastapi-users' users router.
#
# The library's own router wires its internal `authenticator.current_user`
# into GET/PATCH /users/me, which only understands the built-in JWT — a Clerk
# session would 401 as "Unauthorized" even though the dual-path
# `current_active_user` accepted it. Building the two endpoints here with the
# shared dependency keeps the surface identical while making both auth paths
# work. Nothing in the repo uses fastapi-users' list/get/delete /users/{id}
# routes (superuser management goes through /admin/users), so they are not
# re-created.
users_router = APIRouter()


@users_router.get("/me", response_model=UserRead, name="users:current_user")
async def users_me(user: User = Depends(current_active_user)) -> UserRead:
    """The signed-in user's profile, whichever way they signed in."""
    return UserRead.model_validate(user)


@users_router.patch(
    "/me", response_model=UserRead, name="users:patch_current_user"
)
async def users_patch_me(
    user_update: schemas.BaseUserUpdate,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager = Depends(get_user_manager),
) -> UserRead:
    """Update the signed-in user (email/password/is_active).

    A Clerk-provisioned user who sets a password here gains the email/password
    path too; the placeholder hash is replaced.
    """
    updated = await user_manager.update(user_update, user, safe=True, request=None)
    return UserRead.model_validate(updated)