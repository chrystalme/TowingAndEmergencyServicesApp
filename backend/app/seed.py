"""Seed script: creates demo data so the whole app can be walked through.

Run (from ``backend/``) against a Postgres that already has the schema (after
``alembic upgrade head``), or against a fresh local DB — this script will also
call ``Base.metadata.create_all`` if no tables exist yet::

    source .venv/bin/activate
    DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/towing \
        python -m app.seed

The script is idempotent: existing emails (users) are skipped, and new rows are
added only if the target table is empty. Passwords are hashed with the exact
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


async def _ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
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
