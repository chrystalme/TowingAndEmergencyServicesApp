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


def _auth(headers: dict) -> dict:
    """Just the Authorization header, ignoring any test-only extras."""
    return {'Authorization': headers['Authorization']}


async def _go_online(
    client: AsyncClient, headers: dict, lat: float, lng: float, email: str | None = None
) -> None:
    """Approve a driver, then put them online.

    Registration creates a commuter and driving is permissioned, so the
    approval an administrator would perform has to happen first.
    """
    from app.tests.testdb import approve_driver

    if email is None:
        me = await client.get('/api/users/me', headers=_auth(headers))
        email = me.json()['email']
    await approve_driver(email)
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
    from app.tests.testdb import approve_driver

    await approve_driver("driver@example.com")
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


# --- Regression: re-dispatch after a decline ---
@pytest.mark.asyncio
async def test_redispatch_after_decline_does_not_break_reads(
    client: AsyncClient, auth_headers: dict
):
    """A declined request can be re-dispatched without 500ing the read paths.

    Declining returns the request to `pending`, so it can legitimately be
    dispatched again — leaving two dispatch rows for one request. The enriched
    queries used to join Dispatch straight onto request_id, so that second row
    made `one_or_none()` raise MultipleResultsFound (500 on GET and PATCH) and
    duplicated the request in the list endpoint.
    """
    drv = await _register_and_login(client, "redispatch-driver@example.com")
    await _go_online(client, drv, 40.0001, -74.0001)
    # A second, slightly farther driver: declining now falls through to them
    # rather than re-offering the same driver the job they just refused.
    backup = await _register_and_login(client, "redispatch-backup@example.com")
    await _go_online(client, backup, 40.0009, -74.0009)

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Re-dispatch regression",
            "location": "Nowhere",
            "latitude": 40.0,
            "longitude": -74.0,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]

    first = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert first.status_code == 201
    first_id = first.json()["dispatch"]["id"]

    declined = await client.post(
        f"/api/dispatch/{first_id}/respond", json={"status": "declined"}, headers=drv
    )
    assert declined.status_code == 200

    second = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert second.status_code == 201, second.text
    second_id = second.json()["dispatch"]["id"]
    assert second_id != first_id  # genuinely two rows for one request
    # ...and the fallback chain moved on to the next candidate.
    assert second.json()["dispatch"]["driver_email"] == "redispatch-backup@example.com"

    # The read paths must survive that.
    detail = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text

    patched = await client.patch(
        f"/api/service-requests/{sr_id}", json={"status": "in_progress"}, headers=auth_headers
    )
    assert patched.status_code == 200, patched.text

    listing = await client.get("/api/service-requests", headers=auth_headers)
    assert listing.status_code == 200
    assert len([r for r in listing.json() if r["id"] == sr_id]) == 1

    # ...and they must describe the CURRENT attempt, not an earlier one.
    current = await client.get(f"/api/dispatch/request/{sr_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["id"] == second_id


@pytest.mark.asyncio
async def test_cannot_stack_a_second_live_dispatch(client: AsyncClient, auth_headers: dict):
    """A request holding a live assignment refuses another one."""
    drv = await _register_and_login(client, "stack-driver@example.com")
    await _go_online(client, drv, 41.0001, -75.0001)

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "No stacking",
            "location": "Nowhere",
            "latitude": 41.0,
            "longitude": -75.0,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]

    first = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert first.status_code == 201

    # Force the request back to `pending` while the assignment is still live —
    # the inconsistent state the status check alone would not catch.
    await client.patch(
        f"/api/service-requests/{sr_id}", json={"status": "pending"}, headers=auth_headers
    )

    second = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert second.status_code == 409
    assert "live dispatch" in second.json()["detail"]


# --- Driver's own job list ---
@pytest.mark.asyncio
async def test_driver_sees_and_accepts_own_assignments(client: AsyncClient, auth_headers: dict):
    """A driver can discover what they were matched to, then act on it.

    Responding needs a dispatch id, and /service-requests/{id} is scoped to the
    requester and admins, so without this endpoint a driver had no way to learn
    the id in the first place.
    """
    drv = await _register_and_login(client, "mine-driver@example.com")
    await _go_online(client, drv, 42.0001, -76.0001)

    # Nothing assigned yet.
    empty = await client.get("/api/dispatch/mine", headers=drv)
    assert empty.status_code == 200
    assert empty.json() == []

    req = await client.post(
        "/api/service-requests",
        json={
            "service_type": "recovery",
            "vehicle_type": "suv",
            "description": "Stuck in a ditch off the highway",
            "location": "Mile 42",
            "latitude": 42.0,
            "longitude": -76.0,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert match.status_code == 201
    dispatch_id = match.json()["dispatch"]["id"]

    mine = await client.get("/api/dispatch/mine", headers=drv)
    assert mine.status_code == 200
    jobs = mine.json()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["id"] == dispatch_id
    assert job["status"] == "assigned"
    # Enough of the request to judge the job without a second call.
    assert job["request_location"] == "Mile 42"
    assert job["request_description"].startswith("Stuck in a ditch")
    assert job["request_service_type"] == "recovery"
    assert job["request_vehicle_type"] == "suv"
    assert job["request_lat"] == 42.0

    accepted = await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "accepted"}, headers=drv
    )
    assert accepted.status_code == 200

    still_mine = await client.get("/api/dispatch/mine", headers=drv)
    assert [j["status"] for j in still_mine.json()] == ["accepted"]


@pytest.mark.asyncio
async def test_driver_only_sees_their_own_jobs(client: AsyncClient, auth_headers: dict):
    """One driver's assignments must not leak into another's list."""
    mine = await _register_and_login(client, "isolation-a@example.com")
    other = await _register_and_login(client, "isolation-b@example.com")
    await _go_online(client, mine, 43.0001, -77.0001)

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Isolation check",
            "location": "Somewhere",
            "latitude": 43.0,
            "longitude": -77.0,
        },
        headers=auth_headers,
    )
    await client.post("/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers)

    assert len((await client.get("/api/dispatch/mine", headers=mine)).json()) == 1
    assert (await client.get("/api/dispatch/mine", headers=other)).json() == []


# --- Job lifecycle ---
async def _accepted_job(client: AsyncClient, requester: dict, driver_email: str, lat: float, lng: float):
    """Drive a request through to an accepted dispatch; return (sr_id, dispatch_id, drv)."""
    drv = await _register_and_login(client, driver_email)
    await _go_online(client, drv, lat + 0.0001, lng + 0.0001)
    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Lifecycle job",
            "location": "Somewhere",
            "latitude": lat,
            "longitude": lng,
        },
        headers=requester,
    )
    sr_id = req.json()["id"]
    match = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=requester)
    dispatch_id = match.json()["dispatch"]["id"]
    accepted = await client.post(
        f"/api/dispatch/{dispatch_id}/respond", json={"status": "accepted"}, headers=drv
    )
    assert accepted.status_code == 200
    return sr_id, dispatch_id, drv


@pytest.mark.asyncio
async def test_driver_walks_job_to_completion_and_is_released(
    client: AsyncClient, auth_headers: dict
):
    """accepted -> enroute -> arrived -> completed, freeing the driver at the end.

    Nothing could previously write past 'accepted', so a driver who finished a
    job stayed 'enroute' forever and was never matched again.
    """
    sr_id, dispatch_id, drv = await _accepted_job(
        client, auth_headers, "lifecycle-driver@example.com", 44.0, -78.0
    )

    # Busy while the job is live.
    assert (await client.get("/api/drivers/me", headers=drv)).json()["current_status"] == "enroute"

    for target, expected_request in (
        ("enroute", "enroute"),
        ("arrived", "in_progress"),
        ("completed", "completed"),
    ):
        resp = await client.post(
            f"/api/dispatch/{dispatch_id}/status", json={"status": target}, headers=drv
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == target
        sr = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
        assert sr.json()["status"] == expected_request

    # Released back into the pool, and the finished job leaves the active list.
    assert (await client.get("/api/drivers/me", headers=drv)).json()["current_status"] == "available"
    assert (await client.get("/api/dispatch/mine", headers=drv)).json() == []


@pytest.mark.asyncio
async def test_completed_driver_can_take_another_job(client: AsyncClient, auth_headers: dict):
    """The whole point of releasing: a driver is matchable again afterwards."""
    _, dispatch_id, drv = await _accepted_job(
        client, auth_headers, "reuse-driver@example.com", 45.0, -79.0
    )
    await client.post(f"/api/dispatch/{dispatch_id}/status", json={"status": "completed"}, headers=drv)

    second = await client.post(
        "/api/service-requests",
        json={
            "description": "Second job for the same driver",
            "location": "Nearby",
            "latitude": 45.0,
            "longitude": -79.0,
        },
        headers=auth_headers,
    )
    match = await client.post(
        "/api/dispatch", json={"request_id": second.json()["id"]}, headers=auth_headers
    )
    assert match.status_code == 201, match.text
    assert match.json()["dispatch"]["driver_email"] == "reuse-driver@example.com"


@pytest.mark.asyncio
async def test_illegal_transitions_are_rejected(client: AsyncClient, auth_headers: dict):
    """The state machine refuses moves that skip or reverse the flow."""
    _, dispatch_id, drv = await _accepted_job(
        client, auth_headers, "illegal-driver@example.com", 46.0, -80.0
    )

    # Cannot go back to 'assigned'.
    back = await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "assigned"}, headers=drv
    )
    assert back.status_code == 409

    # Terminal means terminal.
    await client.post(f"/api/dispatch/{dispatch_id}/status", json={"status": "completed"}, headers=drv)
    again = await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "enroute"}, headers=drv
    )
    assert again.status_code == 409
    assert "terminal" in again.json()["detail"] or "Cannot move" in again.json()["detail"]


@pytest.mark.asyncio
async def test_requester_may_cancel_but_not_advance(client: AsyncClient, auth_headers: dict):
    """The requester can call the job off; only the driver can progress it."""
    sr_id, dispatch_id, drv = await _accepted_job(
        client, auth_headers, "cancel-driver@example.com", 47.0, -81.0
    )

    forbidden = await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "arrived"}, headers=auth_headers
    )
    assert forbidden.status_code == 403

    cancelled = await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "cancelled"}, headers=auth_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    sr = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert sr.json()["status"] == "cancelled"
    # Cancelling also frees the driver.
    assert (await client.get("/api/drivers/me", headers=drv)).json()["current_status"] == "available"


@pytest.mark.asyncio
async def test_outsider_cannot_touch_a_job(client: AsyncClient, auth_headers: dict):
    """Someone who is neither the driver nor the requester sees a 404."""
    _, dispatch_id, _ = await _accepted_job(
        client, auth_headers, "outsider-driver@example.com", 48.0, -82.0
    )
    outsider = await _register_and_login(client, "outsider-nosy@example.com")
    resp = await client.post(
        f"/api/dispatch/{dispatch_id}/status", json={"status": "completed"}, headers=outsider
    )
    assert resp.status_code == 404


# --- Offer expiry, fallback chain, and runtime settings ---
async def _expire_now(session, dispatch_id: int):
    """Backdate an offer deadline so the next sweep lapses it.

    Beats sleeping through a real two-minute window in a unit test, and still
    exercises the production sweep rather than a test-only shortcut. Takes the
    db_session fixture: importing the session factory from conftest would
    re-execute that module and hit a different, empty database.
    """
    from datetime import datetime, timedelta
    from app.models import Dispatch

    dispatch = await session.get(Dispatch, dispatch_id)
    dispatch.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await session.commit()


@pytest.mark.asyncio
async def test_new_offer_carries_a_deadline(client: AsyncClient, auth_headers: dict):
    drv = await _register_and_login(client, "deadline-driver@example.com")
    await _go_online(client, drv, 50.0001, -83.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Deadline", "location": "X", "latitude": 50.0, "longitude": -83.0},
        headers=auth_headers,
    )
    match = await client.post(
        "/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers
    )
    assert match.status_code == 201
    jobs = (await client.get("/api/dispatch/mine", headers=drv)).json()
    assert jobs[0]["expires_at"] is not None
    assert jobs[0]["extension_count"] == 0


@pytest.mark.asyncio
async def test_unanswered_offer_lapses_and_frees_the_driver(
    client: AsyncClient, auth_headers: dict, db_session
):
    """A driver who never answers must not hold the request or their own slot."""
    drv = await _register_and_login(client, "silent-driver@example.com")
    await _go_online(client, drv, 51.0001, -84.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Ignored", "location": "X", "latitude": 51.0, "longitude": -84.0},
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    dispatch_id = (
        await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    ).json()["dispatch"]["id"]

    await _expire_now(db_session, dispatch_id)

    # Reading the job list sweeps: the stale offer leaves the active list.
    assert (await client.get("/api/dispatch/mine", headers=drv)).json() == []
    # Driver is back in the pool, request is dispatchable again.
    assert (await client.get("/api/drivers/me", headers=drv)).json()["current_status"] == "available"
    sr = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert sr.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_lapsed_offer_falls_through_to_the_next_candidate(
    client: AsyncClient, auth_headers: dict, db_session
):
    """The ranked list becomes a real chain: nearest ignores it, next gets it."""
    near = await _register_and_login(client, "chain-near@example.com")
    far = await _register_and_login(client, "chain-far@example.com")
    await _go_online(client, near, 52.0001, -85.0001)
    await _go_online(client, far, 52.0020, -85.0020)

    req = await client.post(
        "/api/service-requests",
        json={"description": "Chain", "location": "X", "latitude": 52.0, "longitude": -85.0},
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    first = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert first.json()["dispatch"]["driver_email"] == "chain-near@example.com"

    await _expire_now(db_session, first.json()["dispatch"]["id"])

    second = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert second.status_code == 201, second.text
    assert second.json()["dispatch"]["driver_email"] == "chain-far@example.com"


@pytest.mark.asyncio
async def test_chain_reports_exhaustion_rather_than_looping(
    client: AsyncClient, auth_headers: dict, db_session
):
    """Once everyone nearby has been tried, say so instead of re-offering."""
    only = await _register_and_login(client, "chain-only@example.com")
    await _go_online(client, only, 53.0001, -86.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Exhaust", "location": "X", "latitude": 53.0, "longitude": -86.0},
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    first = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    await _expire_now(db_session, first.json()["dispatch"]["id"])

    again = await client.post("/api/dispatch", json={"request_id": sr_id}, headers=auth_headers)
    assert again.status_code == 422
    assert "already been tried" in again.json()["detail"]


@pytest.mark.asyncio
async def test_driver_can_extend_an_offer_up_to_the_cap(
    client: AsyncClient, auth_headers: dict
):
    """A driver mid-decision buys time; the cap stops it being held forever."""
    drv = await _register_and_login(client, "extend-driver@example.com")
    await _go_online(client, drv, 54.0001, -87.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Extend", "location": "X", "latitude": 54.0, "longitude": -87.0},
        headers=auth_headers,
    )
    dispatch_id = (
        await client.post(
            "/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers
        )
    ).json()["dispatch"]["id"]

    original = (await client.get("/api/dispatch/mine", headers=drv)).json()[0]["expires_at"]

    first = await client.post(f"/api/dispatch/{dispatch_id}/extend", json={}, headers=drv)
    assert first.status_code == 200, first.text
    assert first.json()["extension_count"] == 1
    assert first.json()["expires_at"] > original

    second = await client.post(f"/api/dispatch/{dispatch_id}/extend", json={}, headers=drv)
    assert second.status_code == 200
    assert second.json()["extension_count"] == 2

    # Default cap is 2.
    third = await client.post(f"/api/dispatch/{dispatch_id}/extend", json={}, headers=drv)
    assert third.status_code == 409
    assert "limit is 2" in third.json()["detail"]


@pytest.mark.asyncio
async def test_only_the_assigned_driver_can_extend(client: AsyncClient, auth_headers: dict):
    drv = await _register_and_login(client, "extend-owner@example.com")
    await _go_online(client, drv, 55.0001, -88.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Extend authz", "location": "X", "latitude": 55.0, "longitude": -88.0},
        headers=auth_headers,
    )
    dispatch_id = (
        await client.post(
            "/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers
        )
    ).json()["dispatch"]["id"]

    # The requester is not the driver.
    assert (
        await client.post(f"/api/dispatch/{dispatch_id}/extend", json={}, headers=auth_headers)
    ).status_code == 403


@pytest.mark.asyncio
async def test_settings_change_takes_effect_without_restart(
    client: AsyncClient, auth_headers: dict, admin_factory
):
    """The whole point: change the timeout live and the next offer uses it."""
    admin = await admin_factory("settings-admin@example.com")

    listed = await client.get("/api/admin/settings", headers=admin)
    assert listed.status_code == 200
    by_key = {row["key"]: row for row in listed.json()}
    assert by_key["dispatch_offer_timeout_seconds"]["value"] == 120  # the default
    assert by_key["dispatch_offer_timeout_seconds"]["source"] == "default"

    changed = await client.put(
        "/api/admin/settings/dispatch_offer_timeout_seconds",
        json={"value": 300},
        headers=admin,
    )
    assert changed.status_code == 200
    assert changed.json()["value"] == 300
    assert changed.json()["source"] == "override"

    # A new offer picks the new window up immediately.
    drv = await _register_and_login(client, "settings-driver@example.com")
    await _go_online(client, drv, 56.0001, -89.0001)
    req = await client.post(
        "/api/service-requests",
        json={"description": "Live setting", "location": "X", "latitude": 56.0, "longitude": -89.0},
        headers=auth_headers,
    )
    await client.post("/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers)

    from datetime import datetime

    job = (await client.get("/api/dispatch/mine", headers=drv)).json()[0]
    window = (datetime.fromisoformat(job["expires_at"]) - datetime.utcnow()).total_seconds()
    assert 240 < window <= 300, f"expected the 300s override, got {window}s"


@pytest.mark.asyncio
async def test_settings_are_bounded_and_admin_only(
    client: AsyncClient, auth_headers: dict, admin_factory
):
    admin = await admin_factory("bounds-admin@example.com")

    # Out of range is refused rather than making offers expire instantly.
    too_small = await client.put(
        "/api/admin/settings/dispatch_offer_timeout_seconds", json={"value": 1}, headers=admin
    )
    assert too_small.status_code == 422
    assert "between 30 and 900" in too_small.json()["detail"]

    unknown = await client.put("/api/admin/settings/nope", json={"value": 5}, headers=admin)
    assert unknown.status_code == 404

    # Ordinary users cannot read or change operational settings.
    assert (await client.get("/api/admin/settings", headers=auth_headers)).status_code == 403
    assert (
        await client.put(
            "/api/admin/settings/dispatch_offer_timeout_seconds",
            json={"value": 300},
            headers=auth_headers,
        )
    ).status_code == 403


# --- Driving is a permissioned role ---
@pytest.mark.asyncio
async def test_unapproved_user_cannot_enter_the_dispatch_pool(client: AsyncClient):
    """A commuter must not be able to make themselves dispatchable.

    This previously succeeded AND promoted the caller to the driver role on the
    way in, so tapping a button was enough to start receiving real clients.
    Hiding the button in the app would not have fixed it.
    """
    commuter = await _register_and_login(client, "not-a-driver@example.com")

    resp = await client.put(
        "/api/drivers/me",
        json={"is_online": True, "current_status": "available",
              "current_lat": 6.5, "current_lng": 3.3},
        headers=commuter,
    )
    assert resp.status_code == 403
    assert "not approved to drive" in resp.json()["detail"]

    # And the role was not quietly changed by the attempt.
    me = await client.get("/api/users/me", headers=commuter)
    assert me.json()["role"] == "commuter"


@pytest.mark.asyncio
async def test_all_driver_endpoints_are_gated(client: AsyncClient):
    """Reading and position updates are gated too, not just going online."""
    commuter = await _register_and_login(client, "gated@example.com")
    assert (await client.get("/api/drivers/me", headers=commuter)).status_code == 403
    assert (
        await client.post(
            "/api/drivers/me/position",
            json={"current_lat": 6.5, "current_lng": 3.3},
            headers=commuter,
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_admin_grants_and_revokes_the_driver_role(
    client: AsyncClient, admin_factory
):
    """Granting `driver` is the approval step; revoking pulls them from the pool."""
    admin = await admin_factory("role-admin@example.com")
    applicant = await _register_and_login(client, "applicant@example.com")

    # Blocked before approval.
    assert (
        await client.put(
            "/api/drivers/me",
            json={"is_online": True, "current_status": "available",
                  "current_lat": 6.5, "current_lng": 3.3},
            headers=applicant,
        )
    ).status_code == 403

    listed = await client.get("/api/admin/users?role=commuter", headers=admin)
    assert listed.status_code == 200
    target = next(u for u in listed.json() if u["email"] == "applicant@example.com")

    granted = await client.put(
        f"/api/admin/users/{target['id']}/role", json={"role": "driver"}, headers=admin
    )
    assert granted.status_code == 200
    assert granted.json()["role"] == "driver"

    # Now they can go online.
    online = await client.put(
        "/api/drivers/me",
        json={"is_online": True, "current_status": "available",
              "current_lat": 6.5, "current_lng": 3.3},
        headers=applicant,
    )
    assert online.status_code == 200
    assert online.json()["is_online"] is True

    # Revoking takes them out of the pool immediately, not when they notice.
    revoked = await client.put(
        f"/api/admin/users/{target['id']}/role", json={"role": "commuter"}, headers=admin
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_online"] is False
    assert revoked.json()["current_status"] == "off_duty"


@pytest.mark.asyncio
async def test_role_admin_endpoints_are_admin_only(client: AsyncClient, auth_headers: dict):
    assert (await client.get("/api/admin/users", headers=auth_headers)).status_code == 403
    assert (
        await client.put(
            "/api/admin/users/1/role", json={"role": "driver"}, headers=auth_headers
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_unknown_role_is_rejected(client: AsyncClient, admin_factory):
    admin = await admin_factory("role-admin2@example.com")
    resp = await client.put(
        "/api/admin/users/1/role", json={"role": "wizard"}, headers=admin
    )
    assert resp.status_code == 422
    assert "Unknown role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_driver_contact_is_hidden_until_the_job_is_accepted(
    client: AsyncClient, auth_headers: dict
):
    """A driver who has not accepted has agreed to nothing.

    An offer can lapse or be declined, and disclosing the number at offer
    time would leak it to a client whose job that driver never took. This
    is also the seam the planned free/paid tiering hangs off.
    """
    from sqlalchemy import select

    from app.models import Driver, Vehicle
    from app.tests.testdb import TestAsyncSessionLocal

    drv = await _register_and_login(client, "contactable@example.com")
    await _go_online(client, drv, 6.4550, 3.3841)

    # Give the driver a number and a truck to disclose.
    async with TestAsyncSessionLocal() as session:
        profile = await session.scalar(select(Driver).order_by(Driver.id.desc()))
        truck = Vehicle(
            owner_id=profile.user_id,
            make="Isuzu",
            model="NPR Tow Truck",
            year=2018,
            plate_number="APP-305-XA",
        )
        session.add(truck)
        await session.flush()
        profile.phone_number = "+2348031234567"
        profile.vehicle_id = truck.id
        await session.commit()

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Gearbox failure on Third Mainland Bridge",
            "location": "Third Mainland Bridge, Lagos",
            "latitude": 6.4881,
            "longitude": 3.3841,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    match = await client.post(
        "/api/dispatch", json={"request_id": sr_id}, headers=auth_headers
    )
    offered = match.json()["dispatch"]
    dispatch_id = offered["id"]

    # Offered, not accepted: nothing disclosed.
    assert offered["status"] == "assigned"
    assert offered["driver_phone"] is None
    assert offered["driver_vehicle_plate"] is None

    accepted = await client.post(
        f"/api/dispatch/{dispatch_id}/respond",
        json={"status": "accepted"},
        headers=drv,
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["driver_phone"] == "+2348031234567"
    assert body["driver_vehicle_make"] == "Isuzu"
    assert body["driver_vehicle_plate"] == "APP-305-XA"


@pytest.mark.asyncio
async def test_declined_offer_never_discloses_the_number(
    client: AsyncClient, auth_headers: dict
):
    """The case the gate exists for: a driver who said no."""
    from sqlalchemy import select

    from app.models import Driver
    from app.tests.testdb import TestAsyncSessionLocal

    drv = await _register_and_login(client, "declines@example.com")
    await _go_online(client, drv, 6.4550, 3.3841)
    async with TestAsyncSessionLocal() as session:
        profile = await session.scalar(select(Driver).order_by(Driver.id.desc()))
        profile.phone_number = "+2348050000000"
        await session.commit()

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Flat tyre",
            "location": "Lekki-Epe Expressway, Lagos",
            "latitude": 6.4698,
            "longitude": 3.5852,
        },
        headers=auth_headers,
    )
    match = await client.post(
        "/api/dispatch", json={"request_id": req.json()["id"]}, headers=auth_headers
    )
    dispatch_id = match.json()["dispatch"]["id"]

    declined = await client.post(
        f"/api/dispatch/{dispatch_id}/respond",
        json={"status": "declined"},
        headers=drv,
    )
    assert declined.status_code == 200
    assert declined.json()["driver_phone"] is None

@pytest.mark.asyncio
async def test_request_view_discloses_contact_on_the_same_terms(
    client: AsyncClient, auth_headers: dict
):
    """The client sits on their request, not on the dispatch.

    So the request view has to carry the same details under the same rule -
    otherwise a client with an accepted job still has no way to call the
    driver, which is the whole point of showing it.
    """
    from sqlalchemy import select

    from app.models import Driver, Vehicle
    from app.tests.testdb import TestAsyncSessionLocal

    drv = await _register_and_login(client, "reachable@example.com")
    await _go_online(client, drv, 6.4550, 3.3841)
    async with TestAsyncSessionLocal() as session:
        profile = await session.scalar(select(Driver).order_by(Driver.id.desc()))
        truck = Vehicle(
            owner_id=profile.user_id,
            make="Mitsubishi",
            model="Canter Flatbed",
            year=2020,
            plate_number="KJA-914-LA",
        )
        session.add(truck)
        await session.flush()
        profile.phone_number = "+2348059876543"
        profile.vehicle_id = truck.id
        await session.commit()

    req = await client.post(
        "/api/service-requests",
        json={
            "description": "Overheating",
            "location": "Ikoyi, Lagos",
            "latitude": 6.4550,
            "longitude": 3.4350,
        },
        headers=auth_headers,
    )
    sr_id = req.json()["id"]
    match = await client.post(
        "/api/dispatch", json={"request_id": sr_id}, headers=auth_headers
    )
    dispatch_id = match.json()["dispatch"]["id"]

    # While the offer is outstanding the request must not carry the number.
    pending = await client.get(
        f"/api/service-requests/{sr_id}", headers=auth_headers
    )
    assert pending.json()["driver_phone"] is None

    await client.post(
        f"/api/dispatch/{dispatch_id}/respond",
        json={"status": "accepted"},
        headers=drv,
    )

    accepted = await client.get(
        f"/api/service-requests/{sr_id}", headers=auth_headers
    )
    body = accepted.json()
    assert body["driver_phone"] == "+2348059876543"
    assert body["driver_vehicle_plate"] == "KJA-914-LA"
    assert body["driver_vehicle_model"] == "Canter Flatbed"