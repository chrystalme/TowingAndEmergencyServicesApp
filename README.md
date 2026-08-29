# TowAssist — Towing & Emergency Services App

A monorepo for a towing & emergency-services platform: a **FastAPI** backend
serving a **Next.js 14** web app and a **Flutter** mobile app. A client requests
a tow/roadside help, the backend matches the nearest available driver
(Haversine + server-side pricing), and the driver accepts and comes out.

## Repo layout

| Path        | What it is                                                        |
|-------------|-------------------------------------------------------------------|
| `backend/`  | FastAPI + async SQLAlchemy 2.0 + asyncpg, FastAPI-Users JWT auth, Alembic migrations |
| `web/`      | Next.js 14 App Router web app (TypeScript, Tailwind, MUI, RHF + Zod, axios) |
| `mobile/`   | Flutter app (Provider, GoRouter, flutter_secure_storage, http) |
| `docker-compose.yml` | Postgres + API + web for one-command local stack |

## Prerequisites

- Docker (with `docker compose` v2) for the full stack, or a local Postgres.
- Python 3.12 + `uv` (for the backend venv) if you run the backend outside Docker.
- Node 18+ (for `web/`) and Flutter 3.x (for `mobile/`).

## Quick start (Docker)

```bash
docker compose up -d --build db api
```

The `api` container runs `alembic upgrade head` and then the demo seed before
starting uvicorn, so a fresh database is migrated and populated for you.
Migrations hard-fail (the app cannot serve without a schema); the seed is
advisory and merely logs if its guards refuse (see below).

> **The `web` service does not build.** Its Dockerfile has no build stage and
> `.dockerignore` excludes `src/`, so start the frontend locally instead:
> `cd web && npm install && npm run dev` (http://localhost:3000). Use
> `npm install`, not `npm ci` — the committed lockfile is stale.

| Service | URL        | Notes                        |
|---------|------------|------------------------------|
| Web     | http://localhost:3000 | Next.js frontend — run locally, see above |
| API     | http://localhost:8000 | FastAPI (docs at `/docs`) |
| DB      | localhost:5432         | Postgres 16, db `towing`  |

## Demo accounts (seeded)

The database ships pre-loaded with demo users so you can log straight in. All
passwords work against the live login endpoint (they are hashed with the same
Argon2 helper FastAPI-Users verifies against).

| Role     | Email                | Password       | What you can do                        |
|----------|----------------------|----------------|----------------------------------------|
| **Admin** | `admin@towassist.com` | `Admin123!` | `is_superuser`; all users/routes |
| Driver   | `dan@towassist.com`   | `Driver123!`   | Driver Console, accept dispatches      |
| Driver   | `mercy@towassist.com` | `Driver123!`   | Driver Console, accept dispatches      |
| Commuter | `alice@towassist.com` | `Commuter123!` | Request service, view requests         |
| Commuter | `bob@towassist.com`   | `Commuter123!` | Request service, view requests         |

Both drivers are seeded **online + available** with coordinates near the demo
requests, so dispatch always has a candidate to match.

### Seeded data

- 5 users (2 drivers, 2 commuters, 1 admin)
- 2 `drivers` records — `dan` (online, available) and `mercy` (online, available)
- 3 `service_requests`:
  - id 1 — **alice**, `pending` tow (not yet dispatched → ideal for the walkthrough)
  - id 2 — **bob**, `enroute` road-side help, already matched to **dan** (`accepted`)
  - id 3 — **alice**, `completed` recovery (shows under History)
- 3 `vehicles` — alice's Camry, bob's CR-V, dan's tow truck
- 2 `emergency_logs`, 1 `dispatch` (dan → bob's request, priced server-side)

## Running the seed yourself

The seed lives at `backend/app/seed.py`. It is **development only** — it creates
a superuser whose password is published in this file — and refuses to run
unless **both** guards pass:

1. `ALLOW_DEMO_SEED` is set to `yes`/`true`/`1`. The default is off, so any
   environment that never sets it is protected without any action.
2. The `users` table contains no account outside the five demo emails. One
   real user aborts the run — so the seed is freely re-runnable against a dev
   database but can never fire against a populated one.

`docker-compose.yml` sets `ALLOW_DEMO_SEED=yes` for the `api` service, so this
is already unlocked locally and nowhere else. Within a demo-only database the
seed is re-runnable: demo users are reused and other tables fill only when
empty.

With Docker compose running:

```bash
docker compose exec api sh -c "cd /app && python -m app.seed"
```

Or against a local venv + Postgres:

```bash
cd backend
source .venv/bin/activate
ALLOW_DEMO_SEED=yes \
DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing \
  python -m app.seed
```

### Creating the first administrator (production)

Because the seed cannot reach a real database, bootstrap a real superuser with
`backend/app/create_admin.py`. It takes credentials from the environment at run
time (nothing is committed), never creates tables, and never prints the
password:

```bash
docker compose run --rm \
  -e ADMIN_EMAIL=ops@example.com -e ADMIN_PASSWORD='...' \
  api python -m app.create_admin
```

It rejects passwords under 12 characters and any password published in this
repo. It is idempotent: if the email already exists the account is promoted to
superuser and its **password is left untouched**, so re-running never resets a
working administrator. That also makes it the way to promote someone who
already registered through the app normally.

To re-seed from scratch after schema changes:

```bash
# reset the schema (WARNING: drops all data)
docker compose exec db psql -U postgres -d towing -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;"
docker compose exec api sh -c "cd /app && python -m alembic upgrade head && python -m app.seed"
```

## Test-case walkthrough (5 minutes)

These steps exercise the full flow using the seeded data. Open
http://localhost:3001 in a browser.

### 1. Admin logs in

1. Go to **Sign in**, use `admin@towassist.com` / `Admin123!`.
2. Confirm the dashboard loads and `/api/users/me` returns
   `"is_superuser": true`.

### 2. Commuter requests service (Alice)

1. Log out, sign in as `alice@towassist.com` / `Commuter123!`.
2. Dashboard should show the seeded **pending tow** (id 1) under **Active
   Requests** and the **completed recovery** under **History**.
3. Open **Request service**, pick _Service: Emergency Towing / Vehicle: Car_,
   describe the issue, click **Share current location** (or type any location),
   and submit.
4. The backend matches the **nearest available driver** — in the seeded data
   that is **mercy** (~1.7 km). A green *Driver Dispatched* card shows her
   email, distance, ETA and an estimated price.
5. Check the same assignment from **View Details** on the request.

### 3. Driver accepts the job (Mercy)

1. Log out, sign in as `mercy@towassist.com` / `Driver123!`.
2. Wait — since request 1 was an *existing* pending request, dispatch was
   triggered at creation. In live use the **Driver Console** shows you online
   and lists nearby ranked drivers when you go online.
3. Confirm via the API that the dispatch is assigned to you and accept it:

```bash
# get the dispatch id for request 1 (as Alice)
curl -s http://localhost:8000/api/dispatch/request/1 \
  -H "Authorization: Bearer <alice_token>"
# accept it as Mercy
curl -s -X POST http://localhost:8000/api/dispatch/<id>/respond \
  -H "Authorization: Bearer <mercy_token>" \
  -H "Content-Type: application/json" \
  -d '{"status":"accepted"}'
```

### 4. Driver Console + vehicles

1. As **dan** (`dan@towassist.com` / `Driver123!`), open **Driver Console**.
   He is seeded online + available; you can go offline/back to test the
   availability heartbeat (`PUT /api/drivers/me`).
2. **Manage Vehicles** shows dan's Isuzu tow truck.

### 4b. Driver status semantics (phone location = dispatch location)

A driver's position is used for dispatch matching **only while they are
active**, and the active state is driven by a phone location heartbeat:

- **Active** = the driver is online *and* `available` *and* has a position. The
  backend stores the driver's phone GPS (`current_lat`/`current_lng`) and matches
  the nearest available driver against the request's coordinates.
- **Offline / busy** = the driver is offline (`off_duty`) **or** is handling a
  request (`assigned`/`enroute`). A busy driver is **not** re-matched and does
  not receive new jobs until they finish.

Concretely, the backend only ever considers drivers with
`is_online = true AND current_status = 'available' AND current_lat/lng` set
(`backend/app/services/dispatch.py::list_available_drivers`). Going offline or
accepting a job flips the driver out of that pool automatically — no stale
position is reused for dispatch.

The **mobile Driver Console** (`mobile/lib/screens/driver_console_screen.dart` +
`mobile/lib/providers/driver_provider.dart`) exposes this: tap **Go Active** to
share your (simulated) phone location, **Refresh Location** to update the
heartbeat while staying available, and **Go Offline** to leave the dispatch
pool. While busy it shows *"Busy — handling a request"* instead of available.

The **web Driver Console** (`web/src/app/dashboard/driver/page.tsx`) does the
same with browser geolocation: **Go Online** captures your position and shows
the ranked nearby driver pool.

### 5. (Optional) Read the seed's pre-made dispatch

As **bob** (`bob@towassist.com` / `Commuter123!`), his `enroute` request is
already matched to dan (`accepted`, priced at 1250.00) — the "View Details"
screen renders the live driver + ETA + price without any extra steps.

### Reset the demo state

Request 1 is seeded as `pending`. After you dispatch and accept it, restore it
so the walkthrough is repeatable:

```bash
docker exec towingandemergencyservicesapp-db-1 psql -U postgres -d towing -c \
  "DELETE FROM dispatches WHERE request_id=1;
   UPDATE service_requests SET status='pending' WHERE id=1;
   UPDATE drivers SET current_status='available' WHERE user_id IN (2,3);"
```

## Local (non-Docker) development

```bash
# Backend
cd backend
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Web
cd web
npm ci            # add --legacy-peer-deps if peer conflicts
npm run dev       # http://localhost:3000
```

### Mobile (iOS simulator)

The app only needs the backend reachable at `http://localhost:8000/api` — the
iOS Simulator shares the host's network, so `localhost` resolves to your Mac.
Start the backend first (non-Docker command above, or `docker compose up -d --build`
and use port 8000 from the `api` service).

Requirements: Flutter 3.x, Xcode (with a downloaded simulator runtime), and
CocoaPods (`sudo gem install cocoapods` if missing).

```bash
# 1. Check Flutter sees the toolchain
cd mobile
flutter doctor            # Xcode + iOS section should be green

# 2. Start a simulator
open -a Simulator         # boots the default device
# or pick a specific one:
xcrun simctl list devices available
xcrun simctl boot "iPhone 16 Pro" && open -a Simulator

# 3. Fetch deps and run (picks the booted simulator)
flutter pub get
flutter run               # or: flutter run -d <device-id>
```

Notes:

- First launch compiles the iOS app and runs `pod install` automatically —
  it takes a few minutes; subsequent runs are fast.
- With the app running, use `r` to hot-reload, `R` to hot-restart, `q` to quit.
- The driver GPS heartbeat is simulated in the Driver Console (tap
  **Go Active**), so no location permissions are needed in the simulator.
- Android emulators do **not** share the host network — `localhost` there
  refers to the emulator itself, so the hardcoded
  `http://localhost:8000/api` in `mobile/lib/services/api_service.dart` only
  works on iOS / macOS / desktop targets.

## Environment variables

### Backend
```env
DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing
JWT_SECRET_KEY=super-secret-key        # NOTE: read as JWT_SECRET_KEY, not SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENVIRONMENT=development                # anything else = deployed, see below
CORS_ORIGINS=*                         # comma-separated origins; "*" is dev-only
```

> The env name is `JWT_SECRET_KEY` (see `backend/app/core/settings.py`).
> Setting `SECRET_KEY` / `ALGORITHM` has no effect — a legacy README/CI trap.

#### JWT_SECRET_KEY outside local development

`super-secret-key` is the **public** default: it lives in this README, in
`docker-compose.yml`, and in git history. Anyone who has read the repo can use
it to forge a token for any user, including the administrator. It is fine for a
throwaway local database and nowhere else.

The app therefore refuses to start with that default whenever it looks
deployed — that is, when `ENVIRONMENT` is set to anything outside
`development`/`dev`/`local`/`test`/`testing`, **or** when `RAILWAY_ENVIRONMENT`
is present (Railway injects it into every service, so a deploy trips the guard
even if nobody set `ENVIRONMENT`). Local development needs no configuration:
the safe state is the one you get by doing nothing.

Generate a real secret and set it as a platform variable — never commit it:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Changing it invalidates every issued token, so all users must log in again.

### Web
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```


## Deploying the API + database (Railway)

The backend is deploy-ready; the web app is not (see the Quick start note).

**What to create in Railway**

1. A new project, then **+ New > Database > Add PostgreSQL**.
2. **+ New > GitHub Repo**, pointed at this repository.
3. On that service: **Settings > Root Directory = `backend`**. Railway then
   reads `backend/railway.json` and builds `backend/Dockerfile`.

**Variables to set on the API service**

| Variable | Value |
|---|---|
| `DATABASE_URL` | reference the Postgres service, e.g. `${{Postgres.DATABASE_URL}}` |
| `JWT_SECRET_KEY` | a private random value (see above) — **required**, the app refuses to boot without it |
| `CORS_ORIGINS` | your web origin, e.g. `https://app.example.com` |
| `ENVIRONMENT` | `production` (optional — Railway's own `RAILWAY_ENVIRONMENT` already trips the guard) |

Prefer Railway's **private** Postgres URL where offered: it is faster and
does not bill egress.

**What is already handled**

- *Driver mismatch.* Railway hands out `postgresql://...`, which SQLAlchemy's
  async engine rejects outright, and often appends `?sslmode=require`, which
  asyncpg rejects on the first query. `settings.py` normalizes both, so the
  platform's `DATABASE_URL` can be referenced verbatim.
- *Port.* The image binds `$PORT` (falling back to 8000 locally).
- *Migrations.* `railway.json` declares a pre-deploy command of
  `python -m alembic upgrade head`, so migrations are a discrete step that must
  succeed before the new release goes live — never a race between replicas.
  **But see the warning below: that file is not applied for CLI deploys.**
- *Demo data.* `app/seed.py` cannot run: `ALLOW_DEMO_SEED` is set only in
  `docker-compose.yml`, so the deployed image has no path to it.

**railway.json is not enough on its own**

`railway.json` is *not* applied when you deploy with `railway up`. A service
deployed that way starts healthy against an unmigrated database, and every
endpoint returns 500 until something runs alembic — the health check passes
because `/health` never touches the database. This was confirmed on a real
deploy, not inferred.

The Infrastructure-as-Code format cannot express it either: `railway config
migrate` emits `preDeployCommand` as an inert comment, and `railway config
pull` does not return it even while it is set and running. So the setting
lives on the Railway service, which no new service or environment inherits.

Apply it from the repo instead of clicking, after linking a project:

```bash
cd backend
python scripts/railway_apply_config.py --service api   # --dry-run to preview
railway up -s api                                      # redeploy to take effect
```

Re-running is safe. Verify it actually took by registering a user — a 500
means the schema is still missing:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$API/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"probe@example.com","password":"probepassword123"}'
```

**First administrator**

```bash
railway run -s <api-service> \
  -e ADMIN_EMAIL=ops@example.com -e ADMIN_PASSWORD='...' \
  python -m app.create_admin
```

If `railway.json` and the dashboard ever disagree, the dashboard wins — the
same three settings (pre-deploy command, health check path, start command)
can be set under **Settings > Deploy**.

## Testing

```bash
# Backend (needs PYTHONPATH=. so `app` is importable)
cd backend && PYTHONPATH=. pytest -v --tb=short

# Web (from web/)
npm run lint && npx tsc --noEmit && npm test && npm run build

# Mobile (from mobile/)
flutter analyze && flutter test
```

## API surface (high level)

| Method | Route                                    | Auth | Purpose                          |
|--------|------------------------------------------|------|----------------------------------|
| POST   | `/api/auth/register`                     | —    | Sign up                          |
| POST   | `/api/auth/jwt/login`                    | —    | Login (form-encoded) → JWT       |
| GET    | `/api/users/me`                          | ✔    | Current user                     |
| POST   | `/api/service-requests`                  | ✔    | Create a service request         |
| GET    | `/api/service-requests`                  | ✔    | List own requests                |
| PUT    | `/api/drivers/me`                        | ✔    | Availability + position upsert   |
| GET    | `/api/drivers/me`                        | ✔    | Own driver profile               |
| GET    | `/api/dispatch/available?lat=&lng=`      | ✔    | Nearest available drivers (preview) |
| POST   | `/api/dispatch`                          | ✔    | Match nearest driver to a request |
| POST   | `/api/dispatch/{id}/respond`             | ✔    | Driver accepts/declines          |
| GET    | `/api/dispatch/request/{id}`             | ✔    | Requester view of assignment     |
| CRUD   | `/api/vehicles`, `/api/emergency-logs`   | ✔    | Vehicles, emergency logs         |
| GET    | `/health`, `/api/db-ping`, `/api/ping`   | —    | Health checks                    |

## License

MIT — see the LICENSE file for details.