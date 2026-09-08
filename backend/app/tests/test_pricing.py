"""Rate card behaviour.

The arithmetic is tested against an explicit RateCard rather than the live
one, so these do not start failing the day someone reprices a service.
"""

import pytest
from decimal import Decimal

from app.services import pricing
from app.services.pricing import RateCard, quote

CARD = RateCard(
    base_ngn={"towing": 15000, "roadside": 8000, "recovery": 25000, "other": 10000},
    per_km_ngn={"towing": 900, "roadside": 500, "recovery": 1200, "other": 600},
    minimum_fare_ngn=10000,
)


def test_price_is_base_plus_distance():
    # 15000 + 900*5 = 19500, already a multiple of 100.
    assert quote(CARD, "towing", "car", 5) == Decimal("19500.00")


def test_quotes_are_whole_hundreds_of_naira():
    """Nobody in Lagos is billed 32 kobo.

    The old card produced quotes like 19464.32, which reads as a machine's
    arithmetic rather than a price.
    """
    for km in (0.3, 1.7, 4.44, 9.99, 23.6):
        amount = quote(CARD, "towing", "car", km)
        assert amount % 100 == 0, f"{km} km -> {amount}"


def test_rounding_is_upward_so_a_quote_never_undercuts_cost():
    # 15000 + 900*1.11 = 15999 -> must land on 16000, not 15900.
    assert quote(CARD, "towing", "car", 1.11) == Decimal("16000.00")


def test_minimum_fare_floors_a_short_cheap_job():
    """A 200 m roadside call is not worth sending a truck for at base alone."""
    assert quote(CARD, "roadside", "car", 0.2) == Decimal("10000.00")


def test_heavier_vehicles_pay_a_surcharge_on_distance_only():
    car = quote(CARD, "towing", "car", 10)
    truck = quote(CARD, "towing", "truck", 10)
    assert truck > car
    # The surcharge applies to the distance portion, not the callout: 20% of
    # 900*10 = 1800 more, not 20% of the whole quote.
    assert truck - car == Decimal("1800.00")


def test_unknown_service_type_falls_back_to_other_not_to_the_cheapest():
    fallback = quote(CARD, "spaceship-recovery", "car", 5)
    assert fallback == quote(CARD, "other", "car", 5)
    # 'other' must not be the cheapest, or an unclassified job is underpriced.
    assert fallback > quote(CARD, "roadside", "car", 5)


def test_negative_distance_cannot_discount_a_job():
    """A bad coordinate must not produce a cheaper quote than a zero-distance one."""
    assert quote(CARD, "towing", "car", -50) == quote(CARD, "towing", "car", 0)


def test_fuel_price_raises_the_quote():
    """Fuel meters by distance × consumption × pump price, over the same card."""
    plain = quote(CARD, "towing", "car", 5)
    with_fuel = quote(
        CARD, "towing", "car", 5,
        fuel_ngn_per_litre=500, fuel_litres_per_km=0.26,
    )
    # 5 * 0.26 * 500 = 650, rounded up to N100.
    assert with_fuel == plain + Decimal("700.00")


def test_traffic_multiplier_raises_the_quote():
    """A fatter traffic multiplier inflates travelling minutes only."""
    plain = quote(CARD, "towing", "car", 5)
    busy = quote(
        CARD, "towing", "car", 5,
        labour_ngn_per_minute=200, traffic_multiplier=2.0,
    )
    # eta(5 km) = 7.5 min; 7.5 * 2.0 * 200 = 3000 -> a round +N3000.
    assert busy == plain + Decimal("3000.00")


def test_fuel_only_job_is_still_floored_by_the_minimum_fare():
    """Fuel is a surcharge on top, not a way under the floor."""
    floored = quote(
        CARD, "roadside", "car", 0.2,
        fuel_ngn_per_litre=1000, fuel_litres_per_km=0.26,
    )
    # 0.2 km barely moves: base + distance + ~N52 of fuel is far below the
    # N10,000 floor and must not produce a sub-floor quote.
    assert floored == Decimal("10000.00")
    assert floored == quote(CARD, "roadside", "car", 0.2)


def test_on_site_minutes_add_labour_time_to_the_quote():
    """Crew time on the scene is billable on top of travel time."""
    plain = quote(CARD, "towing", "car", 5)
    on_site = quote(
        CARD, "towing", "car", 5,
        labour_ngn_per_minute=200, on_site_minutes=30,
    )
    # 37.5 min × ₦200 = 7,500: 7.5 min travel (eta at 40 km/h) + 30 min on site.
    assert on_site == plain + Decimal("7500.00")


def test_zero_fuel_and_labour_reproduce_the_classic_rate_card_quote():
    """The new inputs default away to exactly the old base+distance result."""
    plain = quote(CARD, "towing", "car", 12.3)
    zeroed = quote(
        CARD, "towing", "car", 12.3,
        fuel_ngn_per_litre=0, fuel_litres_per_km=0.26,
        labour_ngn_per_minute=0, on_site_minutes=45,
        traffic_multiplier=1.0,
    )
    assert zeroed == plain


@pytest.mark.asyncio
async def test_live_card_falls_back_to_defaults_without_a_session():
    card = await pricing.load_rate_card(None)
    assert card == pricing.STATIC_RATE_CARD


@pytest.mark.asyncio
async def test_stored_override_changes_the_quote(db_session):
    """Repricing must take effect without a redeploy - that is why it is a knob."""
    from app.services.runtime_settings import PRICE_BASE_KNOBS, set_int

    before = await pricing.calculate_price(db_session, "towing", "car", 5)
    await set_int(db_session, PRICE_BASE_KNOBS["towing"], 20000)
    after = await pricing.calculate_price(db_session, "towing", "car", 5)

    assert after - before == Decimal("5000.00")
