"""API tests for the Towing & Emergency Services backend."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str, password: str = "testpassword123") -> dict:
    """Register a fresh user and return auth headers for them."""
    resp = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    login = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Health / DB ping tests ---
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_db_ping(client: AsyncClient):
    response = await client.get("/api/db-ping")
    assert response.status_code == 200
    assert response.json() == {"db": "ok"}


# --- Auth tests ---
@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    user_data = {"email": "newuser@example.com", "password": "newpassword123"}
    response = await client.post("/api/auth/register", json=user_data)
    assert response.status_code == 201
    assert response.json()["email"] == user_data["email"]
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_login_user(client: AsyncClient, test_user: dict):
    response = await client.post("/api/auth/jwt/login", data={
        "username": test_user["email"],
        "password": test_user["password"],
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


# --- ServiceRequest CRUD tests ---
@pytest.mark.asyncio
async def test_create_service_request(client: AsyncClient, auth_headers: dict):
    data = {"description": "Car broke down", "location": "123 Main St"}
    response = await client.post("/api/service-requests", json=data, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["description"] == data["description"]
    assert response.json()["location"] == data["location"]
    assert response.json()["status"] == "pending"
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_list_service_requests(client: AsyncClient, auth_headers: dict):
    for i in range(3):
        await client.post("/api/service-requests", json={
            "description": f"Request {i}",
            "location": f"Location {i}",
        }, headers=auth_headers)
    response = await client.get("/api/service-requests", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_get_service_request(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/service-requests", json={
        "description": "Single request",
        "location": "Single location",
    }, headers=auth_headers)
    sr_id = create_resp.json()["id"]
    response = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == sr_id


@pytest.mark.asyncio
async def test_update_service_request(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/service-requests", json={
        "description": "Original",
        "location": "Original loc",
    }, headers=auth_headers)
    sr_id = create_resp.json()["id"]
    response = await client.patch(f"/api/service-requests/{sr_id}", json={
        "status": "completed",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_service_request(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/service-requests", json={
        "description": "To delete",
        "location": "Delete loc",
    }, headers=auth_headers)
    sr_id = create_resp.json()["id"]
    response = await client.delete(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert response.status_code == 204
    get_resp = await client.get(f"/api/service-requests/{sr_id}", headers=auth_headers)
    assert get_resp.status_code == 404


# --- Admin visibility: admin sees the whole request history ---
@pytest.mark.asyncio
async def test_admin_sees_all_service_requests(client: AsyncClient, admin_factory):
    # A regular commuter files two requests.
    commuter = await _register_and_login(client, "commuter-admin-test@example.com")
    for i in range(2):
        resp = await client.post(
            "/api/service-requests",
            json={
                "description": f"Commuter request {i}",
                "location": f"Loc {i}",
                "latitude": 37.77,
                "longitude": -122.42,
            },
            headers=commuter,
        )
        assert resp.status_code == 201

    # The commuter themselves only sees their own two.
    mine = await client.get("/api/service-requests", headers=commuter)
    assert mine.status_code == 200
    assert len(mine.json()) == 2

    # Create an admin directly (registration can't grant superuser).
    admin_headers = await admin_factory("admin-test@example.com")

    # Admin sees both requests, requester identity is exposed, and each entry
    # is dispatch-enriched (coords present, driver fields nullable when undriven).
    all_reqs = await client.get("/api/service-requests", headers=admin_headers)
    assert all_reqs.status_code == 200
    body = all_reqs.json()
    assert len(body) == 2
    assert all(r["requester_email"] == "commuter-admin-test@example.com" for r in body)
    assert all(r["latitude"] == 37.77 for r in body)
    assert all(r["driver_email"] is None for r in body)  # no dispatch yet


@pytest.mark.asyncio
async def test_admin_can_read_others_request_detail(client: AsyncClient, admin_factory):
    other = await _register_and_login(client, "other-admin-test@example.com")
    created = await client.post(
        "/api/service-requests",
        json={"description": "Someone else's tow", "location": "Elsewhere"},
        headers=other,
    )
    sr_id = created.json()["id"]

    admin_headers = await admin_factory("admin2-test@example.com")

    # A non-owner commuter cannot read it (404).
    outsider = await _register_and_login(client, "outsider-test@example.com")
    forbidden = await client.get(f"/api/service-requests/{sr_id}", headers=outsider)
    assert forbidden.status_code == 404

    # Admin can.
    ok = await client.get(f"/api/service-requests/{sr_id}", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["requester_email"] == "other-admin-test@example.com"


# --- Vehicle CRUD tests ---
@pytest.mark.asyncio
async def test_create_vehicle(client: AsyncClient, auth_headers: dict):
    data = {"make": "Toyota", "model": "Camry", "year": 2020, "plate_number": "ABC123"}
    response = await client.post("/api/vehicles", json=data, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["make"] == "Toyota"
    assert response.json()["plate_number"] == "ABC123"


@pytest.mark.asyncio
async def test_list_vehicles(client: AsyncClient, auth_headers: dict):
    for i in range(2):
        await client.post("/api/vehicles", json={
            "make": f"Make{i}", "model": f"Model{i}", "year": 2020 + i, "plate_number": f"PLATE{i}"
        }, headers=auth_headers)
    response = await client.get("/api/vehicles", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


# --- EmergencyLog CRUD tests ---
@pytest.mark.asyncio
async def test_create_emergency_log(client: AsyncClient, auth_headers: dict):
    data = {"incident_type": "accident", "description": "Car crash on highway"}
    response = await client.post("/api/emergency-logs", json=data, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["incident_type"] == "accident"
    assert response.json()["resolved"] is False


@pytest.mark.asyncio
async def test_list_emergency_logs(client: AsyncClient, auth_headers: dict):
    for i in range(2):
        await client.post("/api/emergency-logs", json={
            "incident_type": f"type{i}", "description": f"Description {i}"
        }, headers=auth_headers)
    response = await client.get("/api/emergency-logs", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2