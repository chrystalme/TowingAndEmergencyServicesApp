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
