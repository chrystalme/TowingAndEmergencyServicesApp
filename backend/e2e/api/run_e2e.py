#!/usr/bin/env python3
"""Stdlib-only API E2E runner (no httpx/pytest needed).

Runs the full e2e journey for every resource against a live server — the same
coverage as test_e2e_api.py — but with only the Python standard library, so it
runs under stock python3 against a dockerized stack.

Usage:
  docker compose up -d --build db api     # real Postgres + FastAPI on :8000
  python3 backend/e2e/api/run_e2e.py       # optionally E2E_BASE_URL=http://...
"""
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import uuid

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
API = BASE + "/api"

passed = failed = 0


def req(method, path, body=None, token=None, raw_form=None):
    data = None
    headers = {}
    if raw_form is not None:
        data = urllib.parse.urlencode(raw_form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            code = resp.status
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        code = e.code
        raw = e.read().decode()
    return code, (json.loads(raw) if raw and raw[0] in "[{]" else raw)


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} {extra}")


def uniq(p):
    return f"{p}-{uuid.uuid4().hex[:8]}@e2e.com"


def main(argv=None):
    global passed, failed
    passed = failed = 0
    print(f"== API E2E against {BASE} ==")

    # F1 health / db
    with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
        check("/health ok", r.status == 200 and json.loads(r.read())["status"] == "ok")
    c, j = req("GET", "/db-ping")
    check("db-ping 200 + db:ok", c == 200 and j.get("db") == "ok")

    # F2/F3 auth: register + login two users
    users = []
    for lbl in ("alice", "bob"):
        em = uniq(lbl)
        cc, _ = req("POST", "/auth/register", {"email": em, "password": "password123"})
        if cc != 201:
            print(f"register {lbl} -> {cc}")
            sys.exit(1)
        cc, j = req("POST", "/auth/jwt/login", raw_form={"username": em, "password": "password123"})
        if cc != 200:
            print(f"login {lbl} -> {cc}")
            sys.exit(1)
        users.append({"email": em, "token": j["access_token"]})
    check("register+login x2", True)
    a, b = users

    # auth-gated endpoints -> 401 without a token
    for p in ("/service-requests", "/vehicles", "/emergency-logs"):
        cc, _ = req("GET", p)
        check(f"unauth GET {p} -> 401", cc == 401)

    # F4 users/me
    cc, j = req("GET", "/users/me", token=a["token"])
    check("users/me returns own email", cc == 200 and j["email"] == a["email"])

    # F5 service request full CRUD
    cc, j = req("POST", "/service-requests", {"description": "Breakdown I-95",
                "location": "Mile 42"}, token=a["token"])
    sr_id = j["id"]
    check("create SR 201 pending", cc == 201 and j["status"] == "pending")
    cc, lst = req("GET", "/service-requests", token=a["token"])
    check("list SR contains id", any(x["id"] == sr_id for x in lst))
    cc, j = req("GET", f"/service-requests/{sr_id}", token=a["token"])
    check("get SR", cc == 200 and j["id"] == sr_id)
    cc, j = req("PATCH", f"/service-requests/{sr_id}", {"status": "in_progress"}, token=a["token"])
    check("patch SR status", cc == 200 and j["status"] == "in_progress")
    cc, _ = req("DELETE", f"/service-requests/{sr_id}", token=a["token"])
    check("delete SR 204", cc == 204)
    cc, _ = req("GET", f"/service-requests/{sr_id}", token=a["token"])
    check("get deleted SR 404", cc == 404)

    # F6 vehicle CRUD
    V = f"PLATE-{uuid.uuid4().hex[:5].upper()}"
    cc, j = req("POST", "/vehicles", {"make": "Toyota", "model": "Camry",
                "year": 2020, "plate_number": V}, token=a["token"])
    vid = j["id"]
    check("create vehicle 201", cc == 201)
    cc, j = req("PATCH", f"/vehicles/{vid}", {"year": 2021}, token=a["token"])
    check("patch vehicle year", cc == 200 and j["year"] == 2021)
    cc, _ = req("DELETE", f"/vehicles/{vid}", token=a["token"])
    check("delete vehicle", cc == 204)

    # F7 emergency log CRUD
    cc, j = req("POST", "/emergency-logs", {"incident_type": "accident",
                "description": "crash"}, token=a["token"])
    lid = j["id"]
    check("create log + resolved False", cc == 201 and j["resolved"] is False)
    cc, j = req("PATCH", f"/emergency-logs/{lid}", {"resolved": True}, token=a["token"])
    check("patch log resolved", cc == 200 and j["resolved"] is True)
    cc, _ = req("DELETE", f"/emergency-logs/{lid}", token=a["token"])
    check("delete log", cc == 204)

    # ownership isolation
    cc, j = req("POST", "/service-requests", {"description": "A private",
                "location": "loc"}, token=a["token"])
    a_id = j["id"]
    check("B cannot read A's SR (404)",
          req("GET", f"/service-requests/{a_id}", token=b["token"])[0] == 404)
    check("B cannot update A's SR (404)",
          req("PATCH", f"/service-requests/{a_id}", {"status": "completed"}, token=b["token"])[0] == 404)
    check("B cannot delete A's SR (404)",
          req("DELETE", f"/service-requests/{a_id}", token=b["token"])[0] == 404)
    cc, lst = req("GET", "/service-requests", token=b["token"])
    check("B's list excludes A's row", all(x["id"] != a_id for x in lst))

    print(f"\n== RESULT: {passed} passed, {failed} failed ==")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
