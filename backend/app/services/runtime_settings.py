"""Operational knobs that change without a deploy.

Environment variables cannot serve this purpose on a PaaS: editing one on
Railway restarts the service, which is exactly what "tune it live" is meant to
avoid. So each knob has an environment-provided **default** and an optional
**override** row in ``app_settings`` that wins when present.

Every knob declares its bounds. A dispatch offer window of 0 seconds would
expire instantly and a window of a day would strand a client, so the API
refuses both rather than trusting whoever is typing into the admin endpoint.

Reads hit the database. That is one small indexed lookup on a primary key, on
paths that are already doing several queries — cheap enough that caching would
buy little and would reintroduce the staleness this module exists to avoid.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..models import AppSetting


@dataclass(frozen=True)
class IntSetting:
    """An integer knob with a default and a permitted range."""

    key: str
    default: int
    minimum: int
    maximum: int
    description: str

    def clamp_or_raise(self, value: int) -> int:
        if not self.minimum <= value <= self.maximum:
            raise ValueError(
                f"{self.key} must be between {self.minimum} and {self.maximum} "
                f"(got {value})"
            )
        return value


# How long an unanswered offer stays with the matched driver before it lapses
# and the request is re-offered to the next candidate.
OFFER_TIMEOUT = IntSetting(
    key="dispatch_offer_timeout_seconds",
    default=settings.DISPATCH_OFFER_TIMEOUT_SECONDS,
    minimum=30,
    maximum=900,
    description="Seconds a driver has to accept or decline before the offer lapses.",
)

# How much extra time one extension buys the driver.
OFFER_EXTENSION = IntSetting(
    key="dispatch_offer_extension_seconds",
    default=settings.DISPATCH_OFFER_EXTENSION_SECONDS,
    minimum=15,
    maximum=600,
    description="Seconds added when a driver extends an offer.",
)

# How many times one offer may be extended, so a request cannot be held open
# indefinitely while the client waits.
MAX_EXTENSIONS = IntSetting(
    key="dispatch_offer_max_extensions",
    default=settings.DISPATCH_OFFER_MAX_EXTENSIONS,
    minimum=0,
    maximum=10,
    description="How many times a driver may extend a single offer.",
)

KNOBS: dict[str, IntSetting] = {
    knob.key: knob for knob in (OFFER_TIMEOUT, OFFER_EXTENSION, MAX_EXTENSIONS)
}


async def get_int(session: AsyncSession, knob: IntSetting) -> int:
    """The current value: the stored override if valid, else the default.

    A stored value that is unparseable or out of range falls back to the
    default rather than propagating a bad write into dispatch behaviour.
    """
    row = await session.get(AppSetting, knob.key)
    if row is None:
        return knob.default
    try:
        return knob.clamp_or_raise(int(row.value))
    except (TypeError, ValueError):
        return knob.default


async def set_int(
    session: AsyncSession, knob: IntSetting, value: int, user_id: Optional[int] = None
) -> int:
    """Store an override, validating against the knob's bounds first."""
    knob.clamp_or_raise(value)
    row = await session.get(AppSetting, knob.key)
    if row is None:
        row = AppSetting(key=knob.key, value=str(value), updated_by=user_id)
        session.add(row)
    else:
        row.value = str(value)
        row.updated_by = user_id
    await session.commit()
    return value


async def describe_all(session: AsyncSession) -> list[dict]:
    """Every knob with its current value and where that value came from."""
    stored = {
        row.key: row
        for row in (await session.execute(select(AppSetting))).scalars().all()
    }
    out = []
    for key, knob in KNOBS.items():
        row = stored.get(key)
        effective = await get_int(session, knob)
        out.append(
            {
                "key": key,
                "value": effective,
                "default": knob.default,
                "minimum": knob.minimum,
                "maximum": knob.maximum,
                "source": "override" if row is not None else "default",
                "description": knob.description,
                "updated_at": row.updated_at if row is not None else None,
            }
        )
    return out
