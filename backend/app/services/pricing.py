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

The rate-card base/distance figures cover the callout and the moving itself.
On top of that the quote now carries **fuel** (distance * consumption * pump
price) and **labour-time** (travelling minutes scaled by traffic, plus on-site
minutes, at a per-minute rate). Both are layered under the same minimum-fare
floor and N100 round-up, so the final number is still one clean naira amount.
The new defaults are a starting point that needs commercial sign-off — in
particular the ₦1,000/litre fuel figure is a stand-in for the market pump
price, not a researched value.

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

# Fuel burnt per driven kilometre. Deliberately coarse — these are a
# commercial starting point for sign-off, not measured fleet figures.
DEFAULT_FUEL_LITRES_PER_KM: dict[str, float] = {
    "towing": 0.26,
    "roadside": 0.12,
    "recovery": 0.35,
    "other": 0.20,
}

# Stand-in for the Lagos pump price (₦/litre). Marked for commercial sign-off:
# this is the internal seam that used to be hidden inside the per-km slope.
DEFAULT_FUEL_PRICE_PER_LITRE = 1000

# How long the crew spends at the scene, per service type.
DEFAULT_ON_SITE_MINUTES: dict[str, int] = {
    "towing": 45,
    "roadside": 30,
    "recovery": 75,
    "other": 40,
}

# The ETA assumes a straight-line 40 km/h; Lagos traffic says otherwise, so
# travelling minutes are scaled by this. >1.0.
DEFAULT_TRAFFIC_MULTIPLIER = 1.3

# What the crew's time is billed at (₦/minute). Commercial placeholder.
DEFAULT_LABOUR_NGN_PER_MINUTE = 200

STATIC_RATE_CARD = RateCard(
    base_ngn=dict(DEFAULT_BASE_NGN),
    per_km_ngn=dict(DEFAULT_PER_KM_NGN),
    minimum_fare_ngn=DEFAULT_MINIMUM_FARE_NGN,
)


def job_minutes(
    distance_km: float,
    traffic_multiplier: float = 1.0,
    on_site_minutes: int = 0,
) -> float:
    """Total crew-clock minutes for a job: travel (scaled by traffic) + on site.

    Pure and independent of any rate card, so callers can display a job
    duration next to a quote without recomputing pricing internals.
    """
    # Imported inline: geo is a leaf module, but keeping the import local
    # avoids creating a wider coupling for one formula.
    from .geo import eta_minutes

    km = max(0.0, float(distance_km))
    multiplier = max(0.0, float(traffic_multiplier))
    site = max(0, int(on_site_minutes))
    return round(float(eta_minutes(km)) * multiplier + site, 2)


def quote(
    rate_card: RateCard,
    service_type: str,
    vehicle_type: str,
    distance_km: float,
    *,
    fuel_ngn_per_litre: float | int | None = None,
    fuel_litres_per_km: float | int | None = None,
    labour_ngn_per_minute: float | int | None = None,
    on_site_minutes: float | int | None = None,
    traffic_multiplier: float | int | None = None,
) -> Decimal:
    """Price a job against an explicit rate card.

    Pure: no database, no clock. The runtime-configurable path resolves a
    RateCard first and then calls this, so the arithmetic can be tested
    without a session.

    Optional fuel/labour inputs layer on top of the base+distance cost. When
    every one of them is omitted (or zero), the result is *exactly* the
    classic rate-card quote — that is the backward-compatibility contract the
    existing tests rely on:

    * ``None`` fuel price/litres or labour rate/minutes -> 0 contribution;
    * ``None`` traffic multiplier -> 1.0 (travelling minutes unscaled).
    """
    base, per_km = rate_card.for_service(service_type)
    surcharge = VEHICLE_SURCHARGE_PERCENT.get(vehicle_type, DEFAULT_SURCHARGE_PERCENT)

    # Negative or absurd distances would otherwise flow straight into a quote.
    km = Decimal(str(max(0.0, float(distance_km))))

    distance_cost = Decimal(per_km) * km * (Decimal(100 + surcharge) / Decimal(100))

    # Fuel: straight distance * consumption * pump price, no vehicle surcharge.
    fuel_price = Decimal(str(float(fuel_ngn_per_litre or 0)))
    litres_per_km = Decimal(str(float(fuel_litres_per_km or 0)))
    fuel_cost = km * litres_per_km * fuel_price

    # Labour: travel minutes (straight-line ETA, inflated by traffic) plus the
    # on-site minutes, billed at the crew's per-minute rate.
    minutes = job_minutes(
        float(distance_km),
        traffic_multiplier=float(traffic_multiplier) if traffic_multiplier is not None else 1.0,
        on_site_minutes=int(on_site_minutes) if on_site_minutes is not None else 0,
    )
    labour_cost = Decimal(str(minutes)) * Decimal(str(float(labour_ngn_per_minute or 0)))

    total = Decimal(base) + distance_cost + fuel_cost + labour_cost

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
    *,
    fuel_ngn_per_litre: Optional[float] = None,
    labour_ngn_per_minute: Optional[float] = None,
    traffic_multiplier: Optional[float] = None,
) -> Decimal:
    """Return the server-side quote for a job, honouring live rate overrides.

    The optional fuel/labour inputs take precedence when given; otherwise the
    values come from the runtime knobs (constant defaults when ``session`` is
    None, so the no-session path is deterministic). Fuel consumption and
    on-site minutes are *always* taken per service type from the settings —
    they are structural to the service, not per-call tweaks.
    """
    rate_card = await load_rate_card(session)

    # Imported here: runtime_settings imports this module for its defaults.
    from .runtime_settings import (
        FUEL_LITRES_PER_KM_KNOBS,
        FUEL_PRICE_PER_LITRE,
        LABOUR_NGN_PER_MINUTE,
        ON_SITE_MINUTES_KNOBS,
        TRAFFIC_MULTIPLIER_PERMILLE,
        get_int,
    )

    fuel_price = (
        float(fuel_ngn_per_litre)
        if fuel_ngn_per_litre is not None
        else (
            float(await get_int(session, FUEL_PRICE_PER_LITRE))
            if session is not None
            else float(DEFAULT_FUEL_PRICE_PER_LITRE)
        )
    )
    litres_per_km = (
        (await get_int(session, FUEL_LITRES_PER_KM_KNOBS[service_type]) / 1000.0)
        if session is not None
        else DEFAULT_FUEL_LITRES_PER_KM.get(service_type, DEFAULT_FUEL_LITRES_PER_KM["other"])
    )
    on_site_minutes = (
        await get_int(session, ON_SITE_MINUTES_KNOBS[service_type])
        if session is not None
        else DEFAULT_ON_SITE_MINUTES.get(service_type, DEFAULT_ON_SITE_MINUTES["other"])
    )
    labour_per_minute = (
        float(labour_ngn_per_minute)
        if labour_ngn_per_minute is not None
        else (
            float(await get_int(session, LABOUR_NGN_PER_MINUTE)) / 10.0
            if session is not None
            else float(DEFAULT_LABOUR_NGN_PER_MINUTE)
        )
    )
    traffic = (
        float(traffic_multiplier)
        if traffic_multiplier is not None
        else (
            await get_int(session, TRAFFIC_MULTIPLIER_PERMILLE) / 1000.0
            if session is not None
            else DEFAULT_TRAFFIC_MULTIPLIER
        )
    )

    return quote(
        rate_card,
        service_type,
        vehicle_type,
        distance_km,
        fuel_ngn_per_litre=fuel_ngn_per_litre,
        fuel_litres_per_km=litres_per_km,
        labour_ngn_per_minute=labour_per_minute,
        on_site_minutes=on_site_minutes,
        traffic_multiplier=traffic,
    )
