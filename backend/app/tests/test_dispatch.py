"""Tests for the routing/dispatch system (nearest-driver matching + pricing)."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str, password: str = "driverpass123") -> dict:
    """Register a fresh user and return auth headers for them."""
    resp = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    login = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _go_online(client: AsyncClient, headers: dict, lat: float, lng: float) -> None:
    resp = await client.put(
        "/api/drivers/me",
        json={"is_online": True, "current_status": "available", "current_lat": lat, "current_lng": lng},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


# --- Request form persistence (camelCase in, snake_case out) ---
@pytest.mark.asyncio
async def test_service_request_persists_dispatch_fields_and_coords(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/service-requests",
        json={
            "service_type": "towing",
            "vehicle_type": "suv",
            "name": "Jane Doe",
            "phone_number": "5551234567",
            "description": "Van broke down on the freeway near exit 5",
            "location": "Highway 101",
            "latitude": 37.77,
            "longitude": -122.42,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["service_type"] == "towing"
    assert body["vehicle_type"] == "suv"
    assert body["name"] == "Jane Doe"
    assert body["phone_number"] == "5551234567"
    assert body["latitude"] == 37.77
    assert body["longitude"] == -122.42
    assert body["status"] == "pending"


# --- Driver availability ---
@pytest.mark.asyncio
async def test_driver_goes_online_with_position(client: AsyncClient):
    headers = await _register_and_login(client, "driver@example.com")
    resp = await client.put(
        "/api/drivers/me",
        json={"is_online": True, "current_status": "available", "current_lat": 37.7, "current_lng": -122.4},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_online"] is True
    assert body["current_status"] == "available"
    assert body["current_lat"] == 37.7
    assert body["last_position_at"] is not None


@pytest.mark.asyncio
async def test_nearby_drivers_returns_ranked_candidates(client: AsyncClient, auth_headers: dict):
    # Two drivers: one far, one near. Request point sits next to the near one.
    far = await _register_and_login(client, "far@example.com")
    near = await _register_and_login(client, "near@example.com")
    await _go_online(client, far, 37.0, -122.5)   # ~90km away
    await _go_online(client, near, 37.769, -122.42)  # ~1km away

    resp = await client.get(
        "/api/dispatch/available?lat=37.7749&lng=-122.4194",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    candidates = resp.json()
    assert len(candidates) == 2
    # Nearest first
    assert candidates[0]["distance_km"] < candidates[1]["distance_km"]
    # The near driver ranks first
    assert candidates[0]["email"] == "near@example.com"


# --- Dispatch matching ---
@pytest.mark.asyncio
async def test_dispatch_matches_nearest_driver_and_prices(client: AsyncClient, auth_headers: dict):
    far = await _register_and_login(client, "far2@example.com")
    near = await _register_and_login(client, "near2@example.com")
    await _go_online(client, far, 37.0, -122.5)
    await _go_online(client, near, 37.77, -122.42)

    # Requester files a request with coords near the 'near' driver.
    req = await client.post(
        "/api/service-requests",
        json={
            "service_type": "towing",
            "vehicle_type": "car",
            "description": "Flat tire, need a tow near the airport",
            "location": "SFO",
            "latitude": 37.7749,
            "longitude": -122.4194,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]

    # Driver near2 becomes enroute (held) after matching, so near2 is the only
    # candidate left here — but the match happens once. Manually move far2 also.
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert match.status_code == 201, match.text
    body = match.json()
    assert body["request_status"] == "assigned"
    assert body["dispatch"]["driver_email"] == "near2@example.com"
    assert body["dispatch"]["distance_km"] is not None
    assert body["dispatch"]["distance_km"] < 2.0
    assert body["dispatch"]["price"] is not None and body["dispatch"]["price"] > 0
    assert len(body["candidates"]) >= 1
    assert body["candidates"][0]["email"] == "near2@example.com"

    # Overlapping match is rejected (request no longer pending).
    again = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_dispatch_fails_when_no_driver_available(client: AsyncClient, auth_headers: dict):
    req = await client.post(
        "/api/service-requests",
        json={
            "description": "No one around",
            "location": "Nowhere",
            "latitude": 10.0,
            "longitude": 10.0,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    resp = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_driver_accepts_and_declines(client: AsyncClient, auth_headers: dict):
    drv = await _register_and_login(client, "responder@example.com")
    await _go_online(client, drv, 37.77, -122.42)

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Engine won't start, need help",
            "location": "Downtown",
            "latitude": 37.7749,
            "longitude": -122.4194,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    dispatch_id = match.json()["dispatch"]["id"]

    # The request owner cannot respond (they aren't the driver).
    owner_resp = await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "accepted"}, headers=auth_headers
    )
    assert owner_resp.status_code == 403

    # Driver accepts.
    accept = await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "accepted"}, headers=drv
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["status"] == "accepted"

    # Requester can now see the live assignment.
    view = await client.get(f"/api/dispatch/request/{sr_id}", headers=auth_headers)
    assert view.status_code == 200
    assert view.json()["driver_email"] == "responder@example.com"


@pytest.mark.asyncio
async def test_driver_decline_resets_request(client: AsyncClient, auth_headers: dict):
    drv = await _register_and_login(client, "decliner@example.com")
    await _go_online(client, drv, 37.77, -122.42)

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Decline scenario",
            "location": "Midtown",
            "latitude": 37.7749,
            "longitude": -122.4194,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    dispatch_id = match.json()["dispatch"]["id"]

    decline = await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "declined"}, headers=drv
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"

    status_resp = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert status_resp.json()["status"] == "pending"

    # Driver becomes available again so another request can match them.
    prof = await client.get("/api/drivers/me", headers=drv)
    assert prof.json()["current_status"] == "available"


# --- Ownership rules ---
@pytest.mark.asyncio
async def test_cannot_dispatch_someone_elses_request(client: AsyncClient, auth_headers: dict):
    other = await _register_and_login(client, "other@example.com")
    req = await client.post(
        "/api/service-requests",
        json={"description": "Mine", "location": "Here", "latitude": 1.0, "longitude": 1.0},
        headers=auth_headers,
    )
    sr_id = req.json()["id"]

    resp = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=other)
    assert resp.status_code == 404
