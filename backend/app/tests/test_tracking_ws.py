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
