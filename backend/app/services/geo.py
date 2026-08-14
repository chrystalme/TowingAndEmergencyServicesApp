"""Geographic helpers for nearest-driver matching.

Straight-line (Haversine) distance is the MVP ranking metric and the foundation
any road-travel-time upgrade (OSRM / Mapbox / Google matrix) will build on.
Keeping it in one module means the router upgrade is a one-file change.
"""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0
# Assumed average dispatch speed (km/h) used only to derive an ETA from the
# straight-line distance. A real routing provider replaces this.
DEFAULT_AVG_SPEED_KMPH = 40.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lng points."""
    lat1, lon1, lat2, lon2 = radians(lat1), radians(lon1), radians(lat2), radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def eta_minutes(distance_km: float, avg_speed_kmph: float = DEFAULT_AVG_SPEED_KMPH) -> float:
    """Rough drive-time estimate in minutes for a straight-line distance."""
    if avg_speed_kmph <= 0:
        return 0.0
    return round((distance_km / avg_speed_kmph) * 60.0, 1)