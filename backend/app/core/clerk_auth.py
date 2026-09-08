"""Clerk session-token verification, mapped onto the local user table.

The app's primary login is email/password via fastapi-users (a JWT the API
signs itself). Clerk is an *alternative* identity provider layered on top:
a client that presents a valid Clerk session token authenticates as a real
local user row, found or provisioned by email. Both paths keep working side
by side — see ``app.core.auth.current_active_user``.

Clerk tokens are verified by `clerk-backend-api` (networkless when
``CLERK_JWT_KEY`` is supplied, otherwise a JWKS fetch). Everything here is a
no-op when ``CLERK_SECRET_KEY`` is unset, so the API behaves exactly as it
did before Clerk existed.
"""

from typing import Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clerk_backend_api.security import AuthenticateRequestOptions

from ..models import User
from .settings import settings

# Password hash for users provisioned from a Clerk session. They authenticate
# through Clerk and must never be able to use the email/password path, so
# this is not a valid bcrypt hash and carries a marker that audit trails and
# support can recognise.
CLERK_PLACEHOLDER_PASSWORD = "!clerk!no-password!"

# Lazily-created SDK client (it owns an httpx client and a JWKS cache).
_clerk = None


def _get_clerk():
    """The Clerk SDK client, or None when Clerk is not configured."""
    global _clerk
    if not settings.CLERK_SECRET_KEY:
        return None
    if _clerk is None:
        from clerk_backend_api import Clerk

        _clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
    return _clerk


def reset_client() -> None:
    """Drop the cached SDK client (test seam / key rotation)."""
    global _clerk
    _clerk = None


def _authorized_parties() -> Optional[list[str]]:
    parties = [p.strip() for p in settings.CLERK_AUTHORIZED_PARTIES.split(",") if p.strip()]
    return parties or None


async def clerk_session_payload(request: Request) -> Optional[dict]:
    """Verify the request's Clerk session token, returning its claims.

    Returns None when Clerk is not configured OR the token is not a valid
    Clerk session token. Crucially, an invalid/foreign token returns None
    rather than raising: the caller then falls through to the built-in JWT
    path, so a fastapi-users token is never rejected because Clerk was
    consulted first.
    """
    clerk = _get_clerk()
    if clerk is None:
        return None

    try:
        state = await clerk.authenticate_request_async(
            request,
            AuthenticateRequestOptions(
                secret_key=settings.CLERK_SECRET_KEY,
                authorized_parties=_authorized_parties(),
            ),
        )
    except Exception:
        # A malformed/expired token is a "keep trying the other path" signal,
        # not an error the caller needs to act on.
        return None

    if not state.is_authenticated:
        return None
    return state.payload if isinstance(state.payload, dict) else None


async def resolve_clerk_user(request: Request, session: AsyncSession) -> Optional[User]:
    """Map a Clerk session to a local user row, provisioning one if needed.

    The Clerk user's email is the join key: an existing account with that
    email authenticates via Clerk (bringing its role, driver profile,
    history), otherwise a bare commuter account is created so "either login
    works, whichever the user wants" holds from the first visit.
    """
    payload = await clerk_session_payload(request)
    if payload is None:
        return None

    email = (payload.get("email") or "").strip().lower()
    if not email:
        return None

    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()

    if user is None:
        # Imported lazily: auth imports this module, so a top-level import of
        # auth here would be circular.
        from .auth import ROLE_COMMUTER

        user = User(
            email=email,
            hashed_password=CLERK_PLACEHOLDER_PASSWORD,
            is_active=True,
            is_verified=True,
            role=ROLE_COMMUTER,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    if not user.is_active:
        return None
    return user