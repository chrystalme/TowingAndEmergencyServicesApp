"""Nearest-driver dispatch service.

Given a service request with coordinates, finds the nearest *available* online
driver (straight-line Haversine for MVP), creates a ``Dispatch`` assignment,
and prices the job server-side. The matching query/ranking here is the single
place to swap in PostGIS KNN or a routing/matrix provider later.
"""

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Dispatch, Driver, ServiceRequest, User
from ..schemas import DispatchRead, DriverCandidate
from .geo import eta_minutes, haversine_km
from .pricing import calculate_price

# How many nearby candidates to consider / report alongside the assignment.
CANDIDATE_LIMIT = 5


async def list_available_drivers(session: AsyncSession):
    """All online, available drivers that currently have a position."""
    result = await session.execute(
        select(Driver, User)
        .join(User, User.id == Driver.user_id)
        .where(
            and_(
                Driver.is_online.is_(True),
                Driver.current_status == "available",
                Driver.current_lat.is_not(None),
                Driver.current_lng.is_not(None),
            )
        )
    )
    return result.all()  # list[(Driver, User)]


def rank_candidates(drivers, lat: float, lng: float, limit: int = CANDIDATE_LIMIT):
    """Compute distance/ETA for each driver and return them sorted nearest-first."""
    scored = []
    for driver, user in drivers:
        distance_km = haversine_km(lat, lng, driver.current_lat, driver.current_lng)
        scored.append(
            {
                "driver": driver,
                "user": user,
                "distance_km": round(distance_km, 2),
                "eta_minutes": eta_minutes(distance_km),
            }
        )
    scored.sort(key=lambda x: x["distance_km"])
    return scored[:limit]


def _candidate_schema(scored) -> DriverCandidate:
    return DriverCandidate(
        driver_id=scored["user"].id,
        name=scored.get("name"),
        email=scored["user"].email,
        current_lat=scored["driver"].current_lat,
        current_lng=scored["driver"].current_lng,
        distance_km=scored["distance_km"],
        eta_minutes=scored["eta_minutes"],
    )


def dispatch_to_read(dispatch: Dispatch, driver: User = None, driver_profile: Driver = None) -> DispatchRead:
    """Serialize a Dispatch, denormalizing driver display fields."""
    return DispatchRead(
        id=dispatch.id,
        request_id=dispatch.request_id,
        driver_id=dispatch.driver_id,
        status=dispatch.status,
        distance_km=dispatch.distance_km,
        eta_minutes=dispatch.eta_minutes,
        price=float(dispatch.price) if dispatch.price is not None else None,
        created_at=dispatch.created_at,
        responded_at=dispatch.responded_at,
        driver_name=(driver.email if driver else None),
        driver_email=(driver.email if driver else None),
        driver_lat=(driver_profile.current_lat if driver_profile else None),
        driver_lng=(driver_profile.current_lng if driver_profile else None),
    )


async def match_request(session: AsyncSession, request: ServiceRequest):
    """Find the nearest available driver for a request and create a Dispatch.

    Returns (dispatch, drivers, candidates) where ``drivers`` is the raw
    (Driver, User) list and ``candidates`` is the ranked schema list. Raises
    ``LookupError`` when no driver is available or the request has no coords.
    """
    if request.latitude is None or request.longitude is None:
        raise LookupError("Request has no coordinates; cannot dispatch.")

    all_drivers = await list_available_drivers(session)
    if not all_drivers:
        raise LookupError("No drivers are currently available.")

    ranked = rank_candidates(all_drivers, request.latitude, request.longitude)
    top = ranked[0]
    driver_row, driver_user = top["driver"], top["user"]

    price = calculate_price(request.service_type, request.vehicle_type, top["distance_km"])

    dispatch = Dispatch(
        request_id=request.id,
        driver_id=driver_user.id,
        status="assigned",
        distance_km=top["distance_km"],
        eta_minutes=top["eta_minutes"],
        price=price,
    )
    session.add(dispatch)
    request.status = "assigned"
    await session.commit()
    await session.refresh(dispatch)

    candidates = [_candidate_schema(r) for r in ranked]
    return dispatch, driver_row, driver_user, candidates
