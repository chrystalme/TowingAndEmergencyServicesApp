"""Server-side pricing, per guideline methodology §10.

Price = base(service_type) + per_km(service_type) * distance_km, with a small
vehicle-type surcharge for heavier equipment. Distance is the driver-to-situation
straight-line distance at match time; if a routing provider is added the same
formula uses road distance instead.
"""

from decimal import Decimal

# Rate card keyed by service_type -> (base, per_km).
SERVICE_RATES: dict[str, tuple[Decimal, Decimal]] = {
    "towing": (Decimal("50.00"), Decimal("3.50")),
    "roadside": (Decimal("45.00"), Decimal("2.50")),
    "recovery": (Decimal("80.00"), Decimal("4.00")),
    "other": (Decimal("40.00"), Decimal("2.00")),
}

# Vehicle-type surcharge multiplier applied on top of the distance portion.
VEHICLE_SURCHARGE: dict[str, Decimal] = {
    "car": Decimal("1.0"),
    "suv": Decimal("1.1"),
    "truck": Decimal("1.2"),
    "motorcycle": Decimal("1.0"),
    "other": Decimal("1.15"),
}

DEFAULT_BASE = Decimal("40.00")
DEFAULT_PER_KM = Decimal("2.00")
DEFAULT_SURCHARGE = Decimal("1.0")


def calculate_price(
    service_type: str, vehicle_type: str, distance_km: float
) -> Decimal:
    """Return the server-side quote for a job as a Decimal (rounded to 0.01)."""
    base, per_km = SERVICE_RATES.get(service_type, (DEFAULT_BASE, DEFAULT_PER_KM))
    surcharge = VEHICLE_SURCHARGE.get(vehicle_type, DEFAULT_SURCHARGE)
    price = base + per_km * Decimal(str(distance_km)) * surcharge
    return price.quantize(Decimal("0.01"))