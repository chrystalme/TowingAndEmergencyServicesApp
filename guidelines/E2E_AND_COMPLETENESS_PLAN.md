# E2E Test & Feature-Completeness Plan

Towing & Emergency Services — a plan to reach **per-feature completeness** by
proving each feature works end-to-end across backend + web + mobile, and filling
the gaps the current code shows.

The goal is "singularity of each feature": one feature, fully working, verified
across every layer it touches (API → persistence → every UI that consumes it),
with no dead links, dropped fields, or half-wired screens.

## 1. Feature inventory (what exists today, traced from code)

| # | Feature | Backend | Web | Mobile |
|---|---------|---------|-----|--------|
| F1 | Health / DB ping | `/health`, `/api/db-ping`, `/api/ping` ✓ | — | — |
| F2 | Register (JWT) | `/api/auth/register` ✓ (tested) | `/register` ✓ | login-only — **no register screen** |
| F3 | Login (JWT) | `/api/auth/jwt/login` ✓ | `/login` ✓ | `/login` ✓ |
| F4 | Users/me | `/api/users/me` ✓ | dashboard reads it ✓ | — |
| F5 | Service Request CRUD | create/list/get/patch/delete ✓ (all tested) | create `/request` ✓; **list/update/delete only in `/dashboard`** | create `/request` ✓; list ✓; **no update/delete** |
| F6 | Vehicles CRUD | create/list/get/patch/delete ✓ (create/list tested) | **`/dashboard/vehicles` link → 404, no page** | — |
| F7 | Emergency Logs CRUD | create/list/get/patch/delete ✓ (create/list tested) | **no UI at all** | — |
| F8 | Request status lifecycle | `pending|assigned|in_progress|completed|cancelled` via PATCH ✓ | **no UI to change status** | renders status colors only |
| F9 | Geolocation pickup | — | `/request` Share Location ✓ (nominatim reverse geocode) | `/request` mock fixed coords `37.7749,-122.4194` only |
| F10 | Pricing / dispatch | **not implemented** (see `guidelines/methododolgy.md` §§2,6,7,10) | — | — |

Legend ✓ = implemented and (where noted) unit-tested. The gaps are what this
plan closes.

## 2. Completeness gaps found (evidence-based, from source)

1. **Dead nav links (web F5/F6):** `/dashboard` renders links to
   `/dashboard/vehicles`, `/dashboard/settings`, and
   `/dashboard/requests/{id}` — none of these route pages exist
   (`web/src/app/` has only `dashboard`, `login`, `page`, `register`,
   `request`). Clicking them returns 404.
2. **Request form field loss (F5):** the `/request` form collects
   `serviceType`, `vehicleType`, `name`, `phoneNumber` — but the web POST sends
   the whole form object and backend `ServiceRequestCreate` only accepts
   `description` + `location`. FastAPI silently ignores the extra fields, so
   service type / vehicle type / contact are **not persisted.** Additionally the
   mobile dashboard/request-list reads `service_type` / `vehicle_type` from the
   response, which the backend never returns.
3. **No status control anywhere (F8):** backend supports the full lifecycle but
   there is no UI (web or mobile) to advance `pending → assigned →
   in_progress → completed` (or cancel). Only data entered manually via API.
4. **Mobile auth surface (F2):** Flutter app has Login/Dashboard/Request/RequestList
   but **no register or password-reset screen**.
5. **Vehicles & Emergency Logs have no customer-facing UI (F6/F7)** — backend
   and even web `api.ts` client methods exist, but nothing renders them.
6. **Mobile API client is not wired to a real backend default** — 
   `mobile/lib/services/api_service.dart` uses SecureStorage; local E2E must
   point at the Docker `api` on `localhost:8000`.
7. **No end-to-end test tooling installed** (no Playwright/Cypress; mobile tests
   are placeholders; the web tests are unit-level only).

## 3. Per-feature completeness definition (Definition of Done per feature)

A feature is **complete** only when ALL hold:

- **API**: correct create/read/update/delete + auth gating + validation,
  verified against the real Postgres-backed server (not in-memory mocks).
- **Web**: every link to it resolves (no 404), it renders real data, and user
  actions round-trip through the API (create → appears, update → re-renders).
- **Mobile**: the screen exists for the same action and talks to the same API,
  reacting to the same response shape.
- **Field parity**: every field a client sends is either persisted or explicitly
  rejected; every field a client reads is returned by the API (no silent drops,
  no phantom keys).
- **E2E proof**: a green e2e test covers the full journey.

## 4. Work plan (ordered; smallest risk first)

### Phase A — E2E harness (proves current state, before any fill)
1. Add **API e2e** suite (`e2e/api/`): boot real FastAPI against the Docker
   Postgres (`DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing`),
   drive it over HTTP with `httpx`. Cover: health, register → login, CRUD for
   service-requests, vehicles, emergency-logs, and the ownership rule (user A
   cannot read user B's rows). Reuse `backend/.venv`.
2. Add **Web e2e** with Playwright (`web/e2e/`):
   - `auth.spec.ts` — register + login flows (validation, happy path).
   - `request.spec.ts` — full request submission, assert success toast + redirect
     to dashboard, assert fields persisted.
   - `dashboard.spec.ts` — asserts the three quick-action links resolve
     (this test **fails today** on the 404 gaps → drives Phase B).
3. Add **Mobile** `integration_test/` scaffold driving the real login + request
   screens against a device/emulator, pointing `API_URL` at `localhost:8000`.
   (Run requires an emulator; provide config + CI hook but don't block Phase A.)

### Phase B — Close feature gaps (in dependency order)
1. **Persist the full request form** (F5): extend `ServiceRequest` model +
   schema + Alembic migration to add `service_type`, `vehicle_type`, `name`,
   `phone_number`; update `service_requests.py` create; update mobile + web
   request flow. Re-run API + web e2e → green.
2. **Make `/dashboard/requests/[id]` a real detail screen** (read + status
   update via PATCH). Add status transition UI (buttons/select) for
   `assigned/in_progress/completed/cancelled` → closes F8.
3. **Add `/dashboard/vehicles` page** (F6): list + create (delete/update
   optional), wired to existing backend + `api.ts` methods.
4. **Add `/dashboard/settings` page** (F4): show `/users/me`; password update
   via FastAPI-Users if desired. If out of scope, remove the dead link instead.
5. **Add mobile register screen** (F2) and mobile request-list create→view
   parity; wire mobile to read `service_type`/`vehicle_type` once Phase B.1
   returns them.
6. **Emergency Logs** (F7): decide product intent — expose as an "incident
   report" screen or an ops/admin view, or drop the surface. Add matching UI or
   remove the API surface. (Decision required.)
7. **Pricing/dispatch** (F10): stubbed end-to-end (server-side quote endpoint
   + display) or explicitly declared out of scope. (Decision required.)

### Phase C — Final gate
- Run `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` in `web/`;
  `flutter analyze` + `flutter test` in `mobile/`; `pytest -v` in `backend/`.
- Run the full API + web Playwright suite green.
- Every item in the "Completeness gaps" list is either fixed or explicitly
  approved as out-of-scope.

## 5. Env / commands (verified)

- API e2e env: `DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing`
  (matches `docker-compose.yml`). Server: `uvicorn app.main:app --port 8000`
  via the running container at `http://localhost:8000`.
- Web dev: `cd web && npm run dev` (defaults API to `http://localhost:8000`).
- Playwright: `cd web && npx playwright install` then `npx playwright test`.
- Mobile: `flutter drive` / `integration_test` needs an emulator; API base in
  `mobile/lib/services/api_service.dart`.

## 6. Decisions to confirm with the owner
1. F7 Emergency Logs — customer "incident report" screen, admin view, or remove?
2. F10 Pricing/dispatch — implement server-side quote now or defer?
3. F6 vehicle delete/update — include in the `/dashboard/vehicles` page or list+create only?
4. Scope of `/dashboard/settings` — real settings or remove the dead link?

## 7. Test map (feature → where proven)

| Feature | API e2e | Web e2e | Mobile e2e |
|---------|:-------:|:-------:|:----------:|
| F1 health | ✅ | — | — |
| F2 register | ✅ | auth.spec | register screen |
| F3 login | ✅ | auth.spec | login ✓ |
| F4 users/me | ✅ | settings.spec | — |
| F5 request CRUD | ✅ | request+dashboard.spec | request/request-list |
| F6 vehicles | ✅ | vehicles.spec (new) | — |
| F7 emergency logs | ✅ | (pending decision) | — |
| F8 status | ✅ | detail.spec (new) | status render ✓ |
| F9 geolocation | — | request.spec (mock) | mock ✓ |
