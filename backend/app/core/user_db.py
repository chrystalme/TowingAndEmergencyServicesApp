"""FastAPI-Users database adapter and user manager."""

from collections.abc import AsyncGenerator
from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users import BaseUserManager
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..core.settings import settings


class UserManager(BaseUserManager[User, int]):
    """User manager for FastAPI-Users with custom logic if needed."""

    reset_password_token_secret = settings.JWT_SECRET_KEY
    verification_token_secret = settings.JWT_SECRET_KEY

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")


# Note: The user manager is created via FastAPI-Users internally.
# We just need to provide the database adapter dependency.

async def get_user_db(session: AsyncSession) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """FastAPI dependency that yields a user database adapter."""
    yield SQLAlchemyUserDatabase(session, User)