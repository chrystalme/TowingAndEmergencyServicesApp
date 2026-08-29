"""Create (or promote) a superuser. Safe to run against production.

This is the counterpart to ``app/seed.py``. The seed is throwaway demo fixtures
and deliberately refuses to touch a real database; this script does the one
thing you legitimately need on a fresh production database — bootstrap the
first administrator — and takes its credentials at run time so nothing is ever
committed to the repo.

Usage (credentials from the environment, never from argv, so the password does
not land in shell history or the process list)::

    ADMIN_EMAIL=ops@example.com ADMIN_PASSWORD='...' python -m app.create_admin

As a one-off task against a deployed stack::

    docker compose run --rm -e ADMIN_EMAIL=... -e ADMIN_PASSWORD=... api \\
        python -m app.create_admin

Idempotent: if the email already exists the account is promoted to superuser
and its password is left untouched, so re-running is safe. It never creates
tables — the production schema comes from ``alembic upgrade head`` — and it
never prints the password.
"""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models import User
from fastapi_users.password import PasswordHelper

PH = PasswordHelper()

MIN_PASSWORD_LENGTH = 12

# Passwords that ship in this repository's docs/fixtures. Refused outright so a
# demo credential can never become a production administrator.
PUBLISHED_PASSWORDS = {"Admin123!", "Driver123!", "Commuter123!"}


def _read_credentials() -> tuple[str, str]:
    """Pull and validate the admin credentials from the environment."""
    email = os.getenv("ADMIN_EMAIL", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")

    problems = []
    if not email:
        problems.append("ADMIN_EMAIL is required")
    elif "@" not in email:
        problems.append(f"ADMIN_EMAIL does not look like an address: {email!r}")

    if not password:
        problems.append("ADMIN_PASSWORD is required")
    elif len(password) < MIN_PASSWORD_LENGTH:
        problems.append(
            f"ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    elif password in PUBLISHED_PASSWORDS:
        problems.append(
            "ADMIN_PASSWORD is one of this repository's published demo "
            "passwords; choose a private one"
        )

    if problems:
        raise SystemExit(
            "refusing to create an administrator:"
            + "".join(f"\n  - {p}" for p in problems)
        )

    return email, password


async def create_admin() -> None:
    email, password = _read_credentials()

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if existing is not None:
            # Promote in place. Deliberately leaves hashed_password alone so
            # re-running never resets a working administrator's credentials.
            already = existing.is_superuser
            existing.is_superuser = True
            existing.is_active = True
            existing.is_verified = True
            existing.role = "admin"
            await session.commit()
            verb = "already a superuser; refreshed" if already else "promoted to superuser"
            print(f"{email}: {verb} (password unchanged)")
        else:
            session.add(
                User(
                    email=email,
                    hashed_password=PH.hash(password),
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                    role="admin",
                )
            )
            await session.commit()
            print(f"{email}: created as superuser")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(create_admin())
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        raise
