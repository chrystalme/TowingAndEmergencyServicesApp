"""Seed script: creates demo data so the whole app can be walked through.

Run (from ``backend/``) against a Postgres that already has the schema (after
``alembic upgrade head``), or against a fresh local DB — this script will also
call ``Base.metadata.create_all`` if no tables exist yet::

    source .venv/bin/activate
    ALLOW_DEMO_SEED=yes \
    DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing \
        python -m app.seed

DEVELOPMENT ONLY. This creates a superuser whose password is published in the
README, so it is protected by two independent guards and refuses to run unless
BOTH pass:

1. ALLOW_DEMO_SEED must be set to yes/true/1. The safe default is off, so any
   environment that simply never sets it is protected without any action.
2. The users table must hold no account outside DEMO_EMAILS. A single real
   user aborts the run, so this is freely re-runnable against a dev database
   but can never fire against a populated one.

To create a real superuser in production use app/create_admin.py instead.

Within a demo-only database this is re-runnable: the five demo users are reused
when already present, and other tables are populated only when empty. The
example command below therefore needs ALLOW_DEMO_SEED=yes in its environment.

Passwords are hashed with the exact
same Argon2 ``PasswordHelper`` that fastapi-users uses for ``/api/auth/jwt/login``,
so every demo login below works against the running API.

Demo accounts (email / password / role):

    admin@towassist.com   / Admin123!   admin (is_superuser=True)
    dan@towassist.com     / Driver123!  driver — online + available
    mercy@towassist.com   / Driver123!  driver — online + available
    alice@towassist.com   / Commuter123! commuter
    bob@towassist.com     / Commuter123! commuter
"""

import asyncio
import os
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models import (
    Base,
    Dispatch,
    Driver,
    EmergencyLog,
    ServiceRequest,
    User,
    Vehicle,
)
from fastapi_users.password import PasswordHelper

PH = PasswordHelper()


def _hash(password: str) -> str:
    return PH.hash(password)


# Every account this script is allowed to own. The guard below refuses to touch
# a database containing any user outside this set, so the seed can be re-run
# freely against a dev database but can never fire against a real one.
DEMO_EMAILS = {
    "admin@towassist.com",
    "dan@towassist.com",
    "mercy@towassist.com",
    "alice@towassist.com",
    "bob@towassist.com",
}

# Opt-in flag. Absent/false means "do not seed" — the safe default, so an
# environment that simply never sets it is protected without any action.
_SEED_FLAG = "ALLOW_DEMO_SEED"


def _require_opt_in() -> None:
    """Refuse to run unless the environment explicitly opted in."""
    if os.getenv(_SEED_FLAG, "").strip().lower() not in ("yes", "true", "1"):
        raise SystemExit(
            f"refusing to seed: {_SEED_FLAG} is not set. "
            "This script creates demo accounts including a superuser with a "
            "well-known password. Set ALLOW_DEMO_SEED=yes to confirm this is a "
            "throwaway development database."
        )


def _require_demo_only_database(existing_emails: set[str]) -> None:
    """Refuse to run if the database holds any user this script doesn't own."""
    foreign = existing_emails - DEMO_EMAILS
    if foreign:
        sample = ", ".join(sorted(foreign)[:3])
        raise SystemExit(
            f"refusing to seed: database contains {len(foreign)} non-demo "
            f"user(s) (e.g. {sample}). This looks like a real database; "
            "seeding it would create a superuser with a published password."
        )


async def _ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
    _require_opt_in()
    await _ensure_tables()

    async with AsyncSessionLocal() as session:
        # ---------------------------------------------------------------- users
        users = {
            "admin@towassist.com": User(
                email="admin@towassist.com",
                hashed_password=_hash("Admin123!"),
                is_active=True,
                is_superuser=True,
                is_verified=True,
                role="admin",
                created_at=datetime.utcnow(),
            ),
            "dan@towassist.com": User(
                email="dan@towassist.com",
                hashed_password=_hash("Driver123!"),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="driver",
                created_at=datetime.utcnow(),
            ),
            "mercy@towassist.com": User(
                email="mercy@towassist.com",
                hashed_password=_hash("Driver123!"),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="driver",
                created_at=datetime.utcnow(),
            ),
            "alice@towassist.com": User(
                email="alice@towassist.com",
                hashed_password=_hash("Commuter123!"),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="commuter",
                created_at=datetime.utcnow(),
            ),
            "bob@towassist.com": User(
                email="bob@towassist.com",
                hashed_password=_hash("Commuter123!"),
                is_active=True,
                is_superuser=False,
                is_verified=True,
                role="commuter",
                created_at=datetime.utcnow(),
            ),
        }

        existing = set()
        result = await session.execute(select(User.email))
        for (email,) in result.all():
            existing.add(email)

        _require_demo_only_database(existing)

        created_users = {}
        for email, u in users.items():
            if email in existing:
                # Reuse the row already in the DB.
                db_user = (  # noqa: F841
                    await session.execute(select(User).where(User.email == email))
                ).scalar_one()
                created_users[email] = db_user
            else:
                session.add(u)
                await session.flush()
                created_users[email] = u

        await session.commit()

        # ------------------------------------------------------------------ drivers
        driver_rows = [
            Driver(
                user_id=created_users["dan@towassist.com"].id,
                is_online=True,
                current_status="available",
                current_lat=-1.2850,
                current_lng=36.8150,
                last_position_at=datetime.utcnow(),
            ),
            Driver(
                user_id=created_users["mercy@towassist.com"].id,
                is_online=True,
                current_status="available",
                current_lat=-1.3000,
                current_lng=36.8300,
                last_position_at=datetime.utcnow(),
            ),
        ]

        if await session.scalar(select(Driver.id).limit(1)) is None:
            session.add_all(driver_rows)
            await session.flush()

        # ------------------------------------------------------------------ vehicles
        if await session.scalar(select(Vehicle.id).limit(1)) is None:
            vehicles = [
                Vehicle(
                    owner_id=created_users["alice@towassist.com"].id,
                    make="Toyota",
                    model="Camry",
                    year=2019,
                    plate_number="KDA 123A",
                ),
                Vehicle(
                    owner_id=created_users["bob@towassist.com"].id,
                    make="Honda",
                    model="CR-V",
                    year=2021,
                    plate_number="KCB 456B",
                ),
                Vehicle(
                    owner_id=created_users["dan@towassist.com"].id,
                    make="Isuzu",
                    model="NPR Tow Truck",
                    year=2018,
                    plate_number="KDE 789C",
                ),
            ]
            session.add_all(vehicles)
            await session.flush()

        # ------------------------------------------------------------- service requests
        if await session.scalar(select(ServiceRequest.id).limit(1)) is None:
            now = datetime.utcnow()
            requests = [
                # Pending request owned by alice — created but NOT yet dispatched,
                # so the user can walk the request → dispatch flow on it.
                ServiceRequest(
                    user_id=created_users["alice@towassist.com"].id,
                    service_type="towing",
                    vehicle_type="car",
                    name="Alice Johnson",
                    phone_number="+254700111222",
                    description="Car broke down on Mombasa Road, needs a tow to the nearest garage.",
                    location="Mombasa Road, Nairobi",
                    status="pending",
                    latitude=-1.3080,
                    longitude=36.8170,
                    created_at=now,
                    updated_at=now,
                ),
                # Already-enroute request owned by bob, matched to dan (dispatch below).
                ServiceRequest(
                    user_id=created_users["bob@towassist.com"].id,
                    service_type="roadside",
                    vehicle_type="suv",
                    name="Bob Otieno",
                    phone_number="+254722333444",
                    description="Flat tyre on Waiyaki Way, need roadside assistance to change it.",
                    location="Waiyaki Way, Nairobi",
                    status="enroute",
                    latitude=-1.2650,
                    longitude=36.7900,
                    created_at=now - timedelta(minutes=30),
                    updated_at=now,
                ),
                # Completed historical request for alice (shows up in History tab).
                ServiceRequest(
                    user_id=created_users["alice@towassist.com"].id,
                    service_type="recovery",
                    vehicle_type="suv",
                    name="Alice Johnson",
                    phone_number="+254700111222",
                    description="Recovered vehicle after a minor accident in Westlands.",
                    location="Westlands, Nairobi",
                    status="completed",
                    latitude=-1.2670,
                    longitude=36.8070,
                    created_at=now - timedelta(days=3),
                    updated_at=now - timedelta(days=2),
                ),
            ]
            session.add_all(requests)
            await session.flush()
            bob_pending = requests[1]

            # ------------------------------------------------------------------ dispatch
            if await session.scalar(select(Dispatch.id).limit(1)) is None:
                dispatch = Dispatch(
                    request_id=bob_pending.id,
                    driver_id=created_users["dan@towassist.com"].id,
                    status="accepted",
                    distance_km=3.2,
                    eta_minutes=9.0,
                    price=1250.00,
                    created_at=now - timedelta(minutes=28),
                    responded_at=now - timedelta(minutes=25),
                )
                session.add(dispatch)

        # -------------------------------------------------------------- emergency logs
        if await session.scalar(select(EmergencyLog.id).limit(1)) is None:
            logs = [
                EmergencyLog(
                    reporter_id=created_users["alice@towassist.com"].id,
                    incident_type="breakdown",
                    description="Engine stalled on the highway; requesting a tow.",
                    timestamp=datetime.utcnow() - timedelta(days=3),
                    resolved=True,
                ),
                EmergencyLog(
                    reporter_id=created_users["bob@towassist.com"].id,
                    incident_type="puncture",
                    description="Flat tyre, need roadside assistance.",
                    timestamp=datetime.utcnow() - timedelta(minutes=30),
                    resolved=False,
                ),
            ]
            session.add_all(logs)

        await session.commit()

    await engine.dispose()

    print("Seeding complete.")
    print("  admin     : admin@towassist.com   / Admin123!")
    print("  drivers   : dan@towassist.com     / Driver123!")
    print("              mercy@towassist.com   / Driver123!")
    print("  commuters : alice@towassist.com   / Commuter123!")
    print("              bob@towassist.com     / Commuter123!")


if __name__ == "__main__":
    asyncio.run(seed())
