# Towing & Emergency Services App

Monorepo for a towing & emergency-services platform: a FastAPI backend serving a
Next.js 14 web app and a Flutter mobile app. Auth is JWT via FastAPI-Users
(registration via email/password; dispatch/pricing logic is planned per
`guidelines/methododolgy.md`). Mock UI design is generated from a Figma Make
prototype.

## Layout

- `backend/` — FastAPI + async SQLAlchemy 2.0 + asyncpg, FastAPI-Users JWT auth, Alembic migrations. Python 3.12 (`uv` for deps).
- `web/` — Next.js 14 App Router, TypeScript, Tailwind, MUI, React Hook Form + Zod, axios. The real web app lives HERE.
- `mobile/` — Flutter (Provider, GoRouter, flutter_secure_storage, http).
- Root `package.json` + `src/` + `vite.config.ts` are leftover Figma-Make scaffolding, NOT the web app. Ignore it; work in `web/`.
- `guidelines/methododolgy.md` — product requirements/methodology.

## Dev environment

- Backend: `cd backend && uv venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- Web: `cd web && npm ci` (use `--legacy-peer-deps` if peer conflicts)
- Mobile: `cd mobile && flutter pub get`

## Build & test (exact commands)

Backend (from `backend/`):
- `pytest -v --tb=short` — tests hit an in-memory SQLite/aiosqlite engine via fixtures in `app/tests/conftest.py`; no Postgres needed locally.
- `alembic upgrade head` — run migrations (needs Postgres/`DATABASE_URL`).

Web (from `web/`):
- `npm run dev` / `npm run build` — dev/build
- `npm run lint` (= `next lint`)
- `npx tsc --noEmit` — type check
- `npm test` — Jest + Testing Library (`src/**/*.test.ts(x)`)

Mobile (from `mobile/`):
- `flutter analyze`
- `flutter test`

CI (`.github/workflows/ci-cd.yml`): backend pytest against a Postgres 15 service
(run `alembic upgrade head` first), web npm-ci → lint → tsc → jest → build,
mobile analyze → test, then Docker multi-arch build+push to GHCR on `main`.

## Run full stack (Docker)

`docker compose up -d --build` — services: `db` (Postgres 16, port 5432), `api`
(port 8000), `web` (host 3001 → container 3000). The web `next.config.js` uses
`output: 'standalone'` and `/api/*` is rewritten to `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`).

## Conventions

- Commit messages follow Conventional Commits scoped by app, e.g. `feat(backend):`, `feat(web):`, `feat(mobile):`, `feat(infra):`.
- Backend: FastAPI routers in `backend/app/api/`, SQLAlchemy models in `backend/app/models` (single `Base` for Alembic), Pydantic schemas in `backend/app/schemas`, shared config/auth in `backend/app/core/`. Auth/health endpoints mounted under `/api`, health at `/health`.
- Backend settings come from env via pydantic-settings in `app/core/settings.py`: `DATABASE_URL`, `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (defaults for local dev; `JWT_SECRET_KEY` defaults to `super-secret-key`).
- Web API client is `src/lib/api.ts` (axios, JWT from localStorage); `@/` maps to `src/` (jest + tsconfig).
- Mobile: state in `lib/providers/` (Provider), auth/API in `lib/services/`, screens in `lib/screens/`, shared widgets in `lib/widgets/`.

## Pitfalls

- Don't `npm install` at the repo root — the root package.json is Figma-Make scaffolding. All web work/server commands run inside `web/`.
- Env-var name drift: README and CI export `SECRET_KEY`/`ALGORITHM`, but `app/core/settings.py` actually reads `JWT_SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES`. Setting `SECRET_KEY` has no effect; to override auth secret set `JWT_SECRET_KEY`.
- `mobile/test/api_service_test.dart` is an empty placeholder — real API tests need dependency injection for `http.Client` and `FlutterSecureStorage`; don't expect coverage there.
- Web Docker runtime uses `.next/standalone`; keep `output: 'standalone'` in `next.config.js` or the image breaks.
- Mobile `test/` and generated iOS/Android build dirs are committed; don't hand-edit `GeneratedPluginRegistrant.*` or `.gradle`/`build/` output.
