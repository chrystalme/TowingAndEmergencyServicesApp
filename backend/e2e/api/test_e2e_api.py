"""End-to-end API tests.

These run against a REAL, live FastAPI server backed by Postgres (not the
in-memory SQLite fixtures from app/tests). They prove the full user journey —
register -> login -> CRUD every resource -> ownership isolation — over HTTP.

Prereqs:
  - Docker stack up:  docker compose up -d --build db api
  - API reachable at BASE_URL (default http://localhost:8000)

Run:
  .venv/bin/pytest e2e/api/test_e2e_api.py -v
  (or with a custom base:  E2E_BASE_URL=http://host:8000 pytest ...)
"""

import os
import time
import uuid

import pytest
import httpx

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@e2e.com"


def _wait_ready(base: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/health", timeout=2)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    pytest.fail(f"API at {base} not healthy within {timeout}s")


pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def e2e_ready():
    _wait_ready(BASE_URL)


@pytest.fixture
def users(e2e_ready):
    """Return two registered (email, password, token) tuples."""
    created = []
    for _ in range(2):
        email = _unique("e2e")
        password = "password123"
        r = httpx.post(f"{BASE_URL}/api/auth/register",
                       json={"email": email, "password": password}, timeout=10)
        assert r.status_code == 201, r.text
        lr = httpx.post(f"{BASE_URL}/api/auth/jwt/login",
                        data={"username": email, "password": password},
                        timeout=10)
        assert lr.status_code == 200, lr.text
        token = lr.json()["access_token"]
        created.append({"email": email, "password": password,
                        "token": token,
                        "auth": {"Authorization": f"Bearer {token}"}})
    return created


# ---------------------------------------------------------------- health / F1
def test_health(e2e_ready):
    r = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_db_ping(e2e_ready):
    r = httpx.get(f"{BASE_URL}/api/db-ping", timeout=5)
    assert r.status_code == 200
    assert r.json() == {"db": "ok"}


# ---------------------------------------------------------------- auth / F2-F4
def test_register_login_me(users):
    u = users[0]
    r = httpx.get(f"{BASE_URL}/api/users/me", headers=u["auth"], timeout=5)
    assert r.status_code == 200
    assert r.json()["email"] == u["email"]


def test_crud_endpoints_require_auth(e2e_ready):
    for path in ("/api/service-requests", "/api/vehicles", "/api/emergency-logs"):
        r = httpx.get(f"{BASE_URL}{path}", timeout=5)
        assert r.status_code == 401, f"{path} should require auth, got {r.status_code}"


# ------------------------------------------------------- service requests / F5
def test_service_request_full_crud(users):
    u = users[0]
    # create
    r = httpx.post(f"{BASE_URL}/api/service-requests", headers=u["auth"],
                   json={"description": "Car broke down on I-95",
                         "location": "Mile 42, I-95"}, timeout=10)
    assert r.status_code == 201, r.text
    sr = r.json()
    sr_id = sr["id"]
    assert sr["status"] == "pending"
    # list + get
    assert any(x["id"] == sr_id for x in
               httpx.get(f"{BASE_URL}/api/service-requests", headers=u["auth"], timeout=5).json())
    assert httpx.get(f"{BASE_URL}/api/service-requests/{sr_id}", headers=u["auth"], timeout=5).json()["id"] == sr_id
    # update (status lifecycle)
    r = httpx.patch(f"{BASE_URL}/api/service-requests/{sr_id}", headers=u["auth"],
                    json={"status": "in_progress"}, timeout=5)
    assert r.status_code == 200 and r.json()["status"] == "in_progress", r.text
    # delete
    assert httpx.delete(f"{BASE_URL}/api/service-requests/{sr_id}", headers=u["auth"], timeout=5).status_code == 204
    assert httpx.get(f"{BASE_URL}/api/service-requests/{sr_id}", headers=u["auth"], timeout=5).status_code == 404


# ---------------------------------------------------------------- vehicles / F6
def test_vehicle_crud(users):
    u = users[0]
    r = httpx.post(f"{BASE_URL}/api/vehicles", headers=u["auth"],
                   json={"make": "Toyota", "model": "Camry", "year": 2020,
                         "plate_number": f"E2E{uuid.uuid4().hex[:4].upper()}"}, timeout=10)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    assert any(v["id"] == vid for v in
               httpx.get(f"{BASE_URL}/api/vehicles", headers=u["auth"], timeout=5).json())
    assert httpx.get(f"{BASE_URL}/api/vehicles/{vid}", headers=u["auth"], timeout=5).json()["id"] == vid
    assert httpx.patch(f"{BASE_URL}/api/vehicles/{vid}", headers=u["auth"],
                       json={"year": 2021}, timeout=5).json()["year"] == 2021
    assert httpx.delete(f"{BASE_URL}/api/vehicles/{vid}", headers=u["auth"], timeout=5).status_code == 204


# ---------------------------------------------------------- emergency logs / F7
def test_emergency_log_crud(users):
    u = users[0]
    r = httpx.post(f"{BASE_URL}/api/emergency-logs", headers=u["auth"],
                   json={"incident_type": "accident", "description": "Crash on highway"}, timeout=10)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert r.json()["resolved"] is False
    assert any(x["id"] == lid for x in
               httpx.get(f"{BASE_URL}/api/emergency-logs", headers=u["auth"], timeout=5).json())
    assert httpx.patch(f"{BASE_URL}/api/emergency-logs/{lid}", headers=u["auth"],
                       json={"resolved": True}, timeout=5).json()["resolved"] is True
    assert httpx.delete(f"{BASE_URL}/api/emergency-logs/{lid}", headers=u["auth"], timeout=5).status_code == 204


# ------------------------------------------------------- ownership isolation
def test_ownership_isolation(users):
    """User A must not see or mutate user B's rows."""
    a, b = users
    r = httpx.post(f"{BASE_URL}/api/service-requests", headers=a["auth"],
                   json={"description": "A's private", "location": "loc"}, timeout=10)
    a_id = r.json()["id"]
    # B cannot read A's request
    assert httpx.get(f"{BASE_URL}/api/service-requests/{a_id}", headers=b["auth"], timeout=5).status_code == 404
    # B cannot update A's request
    assert httpx.patch(f"{BASE_URL}/api/service-requests/{a_id}", headers=b["auth"],
                       json={"status": "completed"}, timeout=5).status_code == 404
    # B cannot delete A's request
    assert httpx.delete(f"{BASE_URL}/api/service-requests/{a_id}", headers=b["auth"], timeout=5).status_code == 404
    # B's list does not include A's request
    assert all(x["id"] != a_id for x in
               httpx.get(f"{BASE_URL}/api/service-requests", headers=b["auth"], timeout=5).json())
