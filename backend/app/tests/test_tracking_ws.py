"""Tests for the live-tracking socket.

The authorization rules and the publish path are covered here against the app's
own objects. The socket handshake itself is exercised against the running stack
(see the PR notes) rather than through Starlette's sync TestClient, which would
need a second, differently-wired app instance to coexist with the async fixtures.
"""

import pytest
from httpx import AsyncClient

from app.api.tracking_ws import (
    ACTIVE_DISPATCH_STATES,
    channel_for,
    current_driver_position,
    publish_driver_position,
    user_from_token,
    _may_watch,
)
from app.core.broker import InProcessBroker
from app.models import User


async def _register_and_login(client: AsyncClient, email: str, password: str = "trackpass123") -> dict:
    resp = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    login = await client.post(
        "/api/auth/jwt/login", data={"username": email, "password": password}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}", "_raw": login.json()["access_token"]}


async def _go_online(client: AsyncClient, headers: dict, lat: float, lng: float) -> None:
    """Approve a driver, then put them online.

    Registration creates a commuter and driving is permissioned, so the
    approval an administrator would perform has to happen first.
    """
    from app.tests.testdb import approve_driver

    me = await client.get('/api/users/me', headers={'Authorization': headers['Authorization']})
    await approve_driver(me.json()['email'])

    resp = await client.put(
        "/api/drivers/me",
        json={"is_online": True, "current_status": "available", "current_lat": lat, "current_lng": lng},
        headers={"Authorization": headers["Authorization"]},
    )
    assert resp.status_code == 200, resp.text


async def _dispatched_job(client: AsyncClient, requester: dict, driver_email: str, lat: float, lng: float):
    drv = await _register_and_login(client, driver_email)
    await _go_online(client, drv, lat + 0.0001, lng + 0.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Track me", "location": "X", "latitude": lat, "longitude": lng},
        headers=requester,
    )
    sr_id = req.json()["id"]
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=requester)
    assert match.status_code == 201, match.text
    return sr_id, drv


def test_channel_is_scoped_per_request():
    """Two requests must never share a channel, or watchers cross streams."""
    assert channel_for(1) != channel_for(2)
    assert channel_for(42) == "request:42"


@pytest.mark.asyncio
async def test_token_resolves_to_the_right_user(client: AsyncClient, db_session):
    headers = await _register_and_login(client, "ws-token@example.com")
    user = await user_from_token(headers["_raw"], db_session)
    assert user is not None
    assert user.email == "ws-token@example.com"


@pytest.mark.asyncio
async def test_bad_tokens_resolve_to_nobody(client: AsyncClient, db_session):
    """A socket must not open on a missing, malformed, or forged token."""
    assert await user_from_token("", db_session) is None
    assert await user_from_token("not-a-jwt", db_session) is None
    assert await user_from_token("eyJhbGciOiJIUzI1NiJ9.e30.bad-signature", db_session) is None


@pytest.mark.asyncio
async def test_requester_and_assigned_driver_may_watch(
    client: AsyncClient, auth_headers: dict, db_session
):
    sr_id, drv = await _dispatched_job(
        client, auth_headers, "ws-driver@example.com", 60.0, -90.0
    )
    requester = await user_from_token(
        (await client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "testpassword123"},
        )).json()["access_token"],
        db_session,
    )
    driver = await user_from_token(drv["_raw"], db_session)

    allowed_requester, request = await _may_watch(db_session, requester, sr_id)
    allowed_driver, _ = await _may_watch(db_session, driver, sr_id)

    assert request is not None
    assert allowed_requester is True
    assert allowed_driver is True


@pytest.mark.asyncio
async def test_outsider_may_not_watch(client: AsyncClient, auth_headers: dict, db_session):
    """Someone with a valid token but no stake in the job is refused."""
    sr_id, _ = await _dispatched_job(
        client, auth_headers, "ws-driver2@example.com", 61.0, -91.0
    )
    nosy = await _register_and_login(client, "ws-nosy@example.com")
    outsider = await user_from_token(nosy["_raw"], db_session)

    allowed, request = await _may_watch(db_session, outsider, sr_id)
    assert request is not None
    assert allowed is False


@pytest.mark.asyncio
async def test_unknown_request_is_not_found(client: AsyncClient, auth_headers: dict, db_session):
    user = await user_from_token(
        (await client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "testpassword123"},
        )).json()["access_token"],
        db_session,
    )
    allowed, request = await _may_watch(db_session, user, 999999)
    assert request is None
    assert allowed is False


@pytest.mark.asyncio
async def test_snapshot_returns_the_assigned_drivers_position(
    client: AsyncClient, auth_headers: dict, db_session
):
    """A watcher sees the truck on connect, not a blank map."""
    sr_id, _ = await _dispatched_job(
        client, auth_headers, "ws-driver3@example.com", 62.0, -92.0
    )
    snapshot = await current_driver_position(db_session, sr_id)
    assert snapshot is not None
    assert snapshot["type"] == "driver_position"
    assert snapshot["request_id"] == sr_id
    assert snapshot["lat"] == pytest.approx(62.0001)
    assert snapshot["dispatch_status"] in ACTIVE_DISPATCH_STATES


@pytest.mark.asyncio
async def test_heartbeat_publishes_to_watchers(
    client: AsyncClient, auth_headers: dict, db_session, monkeypatch
):
    """Moving the driver reaches the request's channel, and only that channel."""
    import app.api.tracking_ws as tracking

    broker = InProcessBroker()
    monkeypatch.setattr(tracking, "get_broker", lambda: broker)

    sr_id, drv = await _dispatched_job(
        client, auth_headers, "ws-driver4@example.com", 63.0, -93.0
    )
    driver = await user_from_token(drv["_raw"], db_session)

    received = []

    import asyncio

    agen = broker.subscribe(channel_for(sr_id))

    async def pump():
        async for message in agen:
            received.append(message)
            return

    task = asyncio.create_task(pump())
    await asyncio.sleep(0)

    published = await publish_driver_position(db_session, driver.id, 63.5, -93.5)
    assert published == 1

    await asyncio.wait_for(task, timeout=2.0)
    await agen.aclose()

    assert received[0]["lat"] == 63.5
    assert received[0]["driver_id"] == driver.id
    assert received[0]["request_id"] == sr_id


@pytest.mark.asyncio
async def test_position_without_a_live_job_publishes_nothing(
    client: AsyncClient, db_session
):
    """An idle driver moving around is not broadcast to anyone."""
    drv = await _register_and_login(client, "ws-idle@example.com")
    await _go_online(client, drv, 64.0, -94.0)
    driver = await user_from_token(drv["_raw"], db_session)
    assert await publish_driver_position(db_session, driver.id, 64.1, -94.1) == 0


@pytest.mark.asyncio
async def test_missing_coordinates_publish_nothing(client: AsyncClient, db_session):
    drv = await _register_and_login(client, "ws-nocoords@example.com")
    driver = await user_from_token(drv["_raw"], db_session)
    assert await publish_driver_position(db_session, driver.id, None, None) == 0


@pytest.mark.asyncio
async def test_status_changes_reach_the_request_channel(
    client: AsyncClient, auth_headers: dict, db_session, monkeypatch
):
    """A watcher must learn the job was accepted and completed, not just moved.

    The socket originally carried only driver_position, so a client watching a
    tow saw a dot move but was never told it had accepted, arrived or finished —
    the events they actually care about.
    """
    import asyncio

    import app.api.tracking_ws as tracking

    broker = InProcessBroker()
    monkeypatch.setattr(tracking, "get_broker", lambda: broker)

    sr_id, drv = await _dispatched_job(
        client, auth_headers, "ws-status@example.com", 65.0, -95.0
    )

    seen = []
    agen = broker.subscribe(channel_for(sr_id))

    async def pump():
        async for message in agen:
            seen.append(message)
            if len(seen) >= 2:
                return

    task = asyncio.create_task(pump())
    await asyncio.sleep(0)

    dispatch_id = (await client.get("/api/dispatch/mine", headers=drv)).json()[0]["id"]
    await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "accepted"}, headers=drv
    )
    await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "completed"}, headers=drv
    )

    await asyncio.wait_for(task, timeout=3.0)
    await agen.aclose()

    assert [e["type"] for e in seen] == ["dispatch_status", "dispatch_status"]
    assert [e["status"] for e in seen] == ["accepted", "completed"]
    # The linked request status travels too, so a client can render it directly.
    assert seen[-1]["request_status"] == "completed"
    assert seen[-1]["driver_email"] == "ws-status@example.com"


# --- Device registration and push behaviour ---
@pytest.mark.asyncio
async def test_device_registration_round_trip(client: AsyncClient, auth_headers: dict):
    """Register, re-register the same token, then unregister."""
    resp = await client.post(
        "/api/devices", json={"token": "tok-abc-123", "platform": "android"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["platform"] == "android"

    # Re-registering the same token updates rather than duplicating: FCM tokens
    # are re-sent on every launch.
    again = await client.post(
        "/api/devices", json={"token": "tok-abc-123", "platform": "android"},
        headers=auth_headers,
    )
    assert again.status_code == 201
    assert again.json()["id"] == resp.json()["id"]

    gone = await client.request(
        "DELETE", "/api/devices",
        json={"token": "tok-abc-123", "platform": "android"},
        headers=auth_headers,
    )
    assert gone.status_code == 204

    # Unregistering something already gone is not an error; sign-out is noisy
    # enough without a 404.
    twice = await client.request(
        "DELETE", "/api/devices",
        json={"token": "tok-abc-123", "platform": "android"},
        headers=auth_headers,
    )
    assert twice.status_code == 204


@pytest.mark.asyncio
async def test_a_phone_handed_to_another_user_is_reclaimed(
    client: AsyncClient, auth_headers: dict
):
    """The same device registering under a new user must move, not duplicate.

    Otherwise the previous owner keeps receiving that phone's job
    notifications.
    """
    await client.post(
        "/api/devices", json={"token": "shared-phone", "platform": "android"},
        headers=auth_headers,
    )
    second = await _register_and_login(client, "second-owner@example.com")
    resp = await client.post(
        "/api/devices", json={"token": "shared-phone", "platform": "android"},
        headers={"Authorization": second["Authorization"]},
    )
    assert resp.status_code == 201

    from sqlalchemy import func, select as _select

    from app.models import DeviceToken
    from app.tests.testdb import TestAsyncSessionLocal

    async with TestAsyncSessionLocal() as s:
        count = await s.scalar(
            _select(func.count()).select_from(DeviceToken).where(
                DeviceToken.token == "shared-phone"
            )
        )
    assert count == 1


@pytest.mark.asyncio
async def test_push_is_optional(client: AsyncClient, auth_headers: dict, db_session):
    """With no Firebase credentials the app works and simply skips sending.

    This is what lets the suite and a bare local run work without a Firebase
    project — and it must never raise into the request that triggered it.
    """
    from app.services import push

    assert push.is_enabled() is False
    sent = await push.send_to_user(db_session, 1, "Title", "Body")
    assert sent == 0


@pytest.mark.asyncio
async def test_unusable_firebase_credentials_disable_push_instead_of_crashing(
    db_session, monkeypatch
):
    """A malformed credential must degrade to 'push off', not take the API down.

    Push is configured by a single environment variable that is easy to
    truncate or paste wrong. If that turned into an exception on the first
    dispatch, a bad copy-paste would stop drivers being assigned at all -
    so the failure has to stay contained to the notification.
    """
    from app.core.settings import settings as live_settings
    from app.services import push

    monkeypatch.setattr(
        live_settings, "FIREBASE_CREDENTIALS_JSON", '{"not": "a service account"}'
    )
    push.reset()

    assert push.is_enabled() is False
    assert await push.send_to_user(db_session, 1, "Title", "Body") == 0


@pytest.mark.asyncio
async def test_status_push_is_silent_for_internal_transitions(
    client: AsyncClient, auth_headers: dict, db_session
):
    """A client should not be pinged when a job is re-offered internally."""
    from app.services import push

    class _D:
        status = "declined"
        request_id = 1
        id = 1

    class _R:
        user_id = 1

    assert await push.notify_requester_of_status(db_session, _D(), _R()) == 0


def test_tracking_socket_does_not_hold_a_session_for_its_lifetime():
    """The socket must not take a session as a dependency.

    A FastAPI dependency lives as long as the connection it was injected into.
    On a socket a client keeps open while waiting for a tow, that held one
    pooled connection and one open transaction for the whole watch - and an
    open transaction holds its locks. Two such sessions, left over from a QA
    run, blocked a migration's ALTER TABLE until the deploy timed out.

    Asserted structurally because the failure is invisible to a test that only
    checks the socket's replies: it behaved perfectly while leaking.
    """
    import inspect

    from app.api import tracking_ws

    signature = inspect.signature(tracking_ws.track_request)
    assert "session" not in signature.parameters, (
        "track_request must open its own short-lived session rather than "
        "receiving one via Depends - see the docstring on get_async_session"
    )

    source = inspect.getsource(tracking_ws.track_request)
    assert "AsyncSessionLocal" in source
    # Everything needing the database happens before the streaming loop.
    assert source.index("async with AsyncSessionLocal") < source.index("broker.subscribe")


@pytest.mark.asyncio
async def test_session_dependency_leaves_no_open_transaction():
    """A read-only request must not leave its transaction open.

    Postgres reports such a connection as 'idle in transaction' and it keeps
    every lock it acquired, which is what blocks schema changes.
    """
    from sqlalchemy import select

    from app.models import User
    from app.tests.testdb import TestAsyncSessionLocal

    async def dependency():
        """The production dependency's shape, against the test engine."""
        async with TestAsyncSessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.rollback()

    agen = dependency()
    session = await agen.__anext__()
    # A plain read - no writes, no explicit commit, the common case.
    await session.execute(select(User).limit(1))
    assert session.in_transaction()

    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()

    assert not session.in_transaction(), (
        "the dependency returned the connection with a transaction still open"
    )
