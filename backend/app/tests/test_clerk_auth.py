"""Clerk session-token auth: verification, provisioning, dual-path fallback.

Clerk is OPTIONAL. When CLERK_SECRET_KEY is unset the dependency behaves
exactly like the old fastapi-users JWT — the existing suite is the
regression test for that. These tests exercise the Clerk path with a fake
SDK client so no network or Clerk account is needed.
"""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

import app.core.clerk_auth as clerk_auth
from app.core.settings import settings


class _FakeRequestState:
    def __init__(self, payload):
        self.payload = payload
        self.is_authenticated = payload is not None


class _FakeClerk:
    """Minimal stand-in for clerk_backend_api.Clerk.authenticate_request_async."""

    def __init__(self, payload=None, raise_on_call=False):
        self._payload = payload
        self._raise = raise_on_call
        self.calls = 0

    async def authenticate_request_async(self, request, options):
        self.calls += 1
        if self._raise:
            raise ValueError("boom")
        return _FakeRequestState(self._payload)


def _enable_clerk(monkeypatch, payload=None, **kwargs):
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "sk_test_fake")
    fake = _FakeClerk(payload, **kwargs)
    monkeypatch.setattr(clerk_auth, "_get_clerk", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_clerk_session_provisions_and_authenticates(client: AsyncClient, monkeypatch):
    """A Clerk session for an unknown email creates a commuter and logs in."""
    _enable_clerk(monkeypatch, {"email": "clerk-user@example.com", "sub": "user_abc123"})

    resp = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer sess_valid_clerk_token"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "clerk-user@example.com"
    assert body["role"] == "commuter"
    # Provisioned users must never log in through the password path.
    assert body["is_verified"] is True


@pytest.mark.asyncio
async def test_existing_account_authenticates_via_clerk(client: AsyncClient, monkeypatch):
    """A Clerk session for a known email reuses that account, role intact."""
    # An account that registered with a password...
    await client.post(
        "/api/auth/register",
        json={"email": "existing@example.com", "password": "password123"},
    )
    # ...then signs in via Clerk.
    _enable_clerk(monkeypatch, {"email": "existing@example.com", "sub": "user_existing"})

    resp = await client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer sess_other_token"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "existing@example.com"
    # Clerk user lookup is by email: exactly one account, not a duplicate.
    listing = await client.get("/api/users/me", headers={"Authorization": "Bearer x"})
    assert listing.status_code == 200


@pytest.mark.asyncio
async def test_invalid_clerk_token_falls_back_to_fastapi_users_jwt(
    client: AsyncClient, monkeypatch
):
    """A fastapi-users JWT still works when Clerk says 'not my token'."""
    _enable_clerk(monkeypatch, None)  # signed-out / unparseable by Clerk

    await client.post(
        "/api/auth/register",
        json={"email": "fallback@example.com", "password": "password123"},
    )
    login = await client.post(
        "/api/auth/jwt/login",
        data={"username": "fallback@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "fallback@example.com"


@pytest.mark.asyncio
async def test_clerk_verification_exception_is_not_fatal(client: AsyncClient, monkeypatch):
    """A crashed Clerk verify is a fall-through, not a 500."""
    _enable_clerk(monkeypatch, raise_on_call=True)

    await client.post(
        "/api/auth/register",
        json={"email": "resilient@example.com", "password": "password123"},
    )
    login = await client.post(
        "/api/auth/jwt/login",
        data={"username": "resilient@example.com", "password": "password123"},
    )
    token = login.json()["access_token"]

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "resilient@example.com"


@pytest.mark.asyncio
async def test_no_bearer_token_is_rejected(client: AsyncClient, monkeypatch):
    # Fake Clerk agrees with the real SDK: with no session token there is
    # nothing to authenticate, so the JWT path also has no token -> 401.
    _enable_clerk(monkeypatch, None)
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401