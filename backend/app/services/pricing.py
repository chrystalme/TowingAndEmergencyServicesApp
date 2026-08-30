"""Server-side pricing, per guideline methodology §10.

Price = base(service_type) + per_km(service_type) * distance_km, with a
vehicle-type surcharge on the distance portion, then a minimum fare and
rounding applied. Distance is the driver-to-situation straight-line distance at
match time; if a routing provider is added the same formula uses road distance
instead.

Amounts are NAIRA (NGN), held as **whole naira integers**. Kobo is not used in
practice in Lagos and a quote of "N19,464.32" reads as a machine's arithmetic
rather than a price, so the rate card carries no sub-naira precision at all and
the final quote is rounded up to the nearest N100.

Where the numbers come from
---------------------------
The towing base is anchored to the figure Lagos operators and listing sites
converge on for towing a car within the city, roughly N15,000. The per-km
slopes are **not** published by anyone - operators quote distance privately -
so they are a commercial decision rather than a researched fact, and they are
the numbers most likely to need changing.

That is precisely why the rate card is a set of runtime knobs rather than
constants: fuel prices here move, and a rate card that can only change by
rebuilding and redeploying an image will simply go stale. Every figure below
is an environment-provided default that an admin can override live through
``PUT /api/admin/settings/{key}``; see ``app/services/runtime_settings.py``.

Treat the defaults as a starting point to be signed off commercially, not as
a finished rate card.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

# ISO 4217 code, surfaced so clients stop hardcoding a symbol.
CURRENCY = "NGN"
CURRENCY_SYMBOL = "₦"  # naira sign

# Quotes are rounded UP to this multiple. Rounding up rather than to-nearest
# keeps the quote from ever undercutting the computed cost, and N100 is the
# smallest unit anyone actually transacts in.
ROUNDING_UNIT = Decimal("100")

SERVICE_TYPES = ("towing", "roadside", "recovery", "other")

# Vehicle-type surcharge applied to the distance portion only: a heavier
# vehicle costs more to move per kilometre, but the callout itself does not
# get more expensive. Expressed in percent so it can be an integer knob.
VEHICLE_SURCHARGE_PERCENT: dict[str, int] = {
    "car": 0,
    "motorcycle": 0,
    "suv": 10,
    "truck": 20,
    "other": 15,
}
DEFAULT_SURCHARGE_PERCENT = 0


@dataclass(frozen=True)
class RateCard:
    """A resolved rate card: whole naira, no I/O, trivially testable."""

    base_ngn: dict[str, int]
    per_km_ngn: dict[str, int]
    minimum_fare_ngn: int

    def for_service(self, service_type: str) -> tuple[int, int]:
        key = service_type if service_type in self.base_ngn else "other"
        return self.base_ngn[key], self.per_km_ngn[key]


# Defaults. See the module docstring on provenance: the towing base is anchored
# to the going rate for a car tow within Lagos; the slopes are a commercial
# decision. All are overridable at runtime.
DEFAULT_BASE_NGN: dict[str, int] = {
    # Callout plus loading for a standard car tow within the city.
    "towing": 15000,
    # Attending at the roadside - jump start, tyre change, fuel run. No load,
    # so materially cheaper than a tow.
    "roadside": 8000,
    # Winching out of a ditch, off a kerb, or out of flood water. Heavier
    # equipment and longer on site than a straight tow.
    "recovery": 25000,
    # Anything not classified yet. Deliberately not the cheapest, so an
    # unclassified job is never accidentally underpriced.
    "other": 10000,
}

DEFAULT_PER_KM_NGN: dict[str, int] = {
    "towing": 900,
    "roadside": 500,
    "recovery": 1200,
    "other": 600,
}

# Below this, a job is not worth dispatching a truck for. Also protects against
# a near-zero distance producing a quote of just the base.
DEFAULT_MINIMUM_FARE_NGN = 10000

STATIC_RATE_CARD = RateCard(
    base_ngn=dict(DEFAULT_BASE_NGN),
    per_km_ngn=dict(DEFAULT_PER_KM_NGN),
    minimum_fare_ngn=DEFAULT_MINIMUM_FARE_NGN,
)


def quote(
    rate_card: RateCard,
    service_type: str,
    vehicle_type: str,
    distance_km: float,
) -> Decimal:
    """Price a job against an explicit rate card.

    Pure: no database, no clock. The runtime-configurable path resolves a
    RateCard first and then calls this, so the arithmetic can be tested
    without a session.
    """
    base, per_km = rate_card.for_service(service_type)
    surcharge = VEHICLE_SURCHARGE_PERCENT.get(vehicle_type, DEFAULT_SURCHARGE_PERCENT)

    # Negative or absurd distances would otherwise flow straight into a quote.
    km = Decimal(str(max(0.0, float(distance_km))))

    distance_cost = Decimal(per_km) * km * (Decimal(100 + surcharge) / Decimal(100))
    total = Decimal(base) + distance_cost

    if total < rate_card.minimum_fare_ngn:
        total = Decimal(rate_card.minimum_fare_ngn)

    # Round UP to the nearest N100 so the quote never undercuts the computation.
    rounded = (total / ROUNDING_UNIT).quantize(
        Decimal("1"), rounding=ROUND_CEILING
    ) * ROUNDING_UNIT
    return rounded.quantize(Decimal("0.01"))


async def load_rate_card(session: Optional[AsyncSession]) -> RateCard:
    """The live rate card: stored overrides where present, defaults otherwise.

    Accepts None so callers with no session (and the tests) can price against
    the defaults without reaching for a database.
    """
    if session is None:
        return STATIC_RATE_CARD

    # Imported here: runtime_settings imports this module for its defaults.
    from .runtime_settings import (
        MINIMUM_FARE,
        PRICE_BASE_KNOBS,
        PRICE_PER_KM_KNOBS,
        get_int,
    )

    base = {}
    per_km = {}
    for service_type in SERVICE_TYPES:
        base[service_type] = await get_int(session, PRICE_BASE_KNOBS[service_type])
        per_km[service_type] = await get_int(session, PRICE_PER_KM_KNOBS[service_type])
    minimum = await get_int(session, MINIMUM_FARE)
    return RateCard(base_ngn=base, per_km_ngn=per_km, minimum_fare_ngn=minimum)


async def calculate_price(
    session: Optional[AsyncSession],
    service_type: str,
    vehicle_type: str,
    distance_km: float,
) -> Decimal:
    """Return the server-side quote for a job, honouring live rate overrides."""
    rate_card = await load_rate_card(session)
    return quote(rate_card, service_type, vehicle_type, distance_km)
