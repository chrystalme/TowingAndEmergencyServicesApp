"""Nearest-driver dispatch service.

Given a service request with coordinates, finds the nearest *available* online
driver (straight-line Haversine for MVP), creates a ``Dispatch`` assignment,
and prices the job server-side. The matching query/ranking here is the single
place to swap in PostGIS KNN or a routing/matrix provider later.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Dispatch, Driver, ServiceRequest, User
from ..schemas import DispatchRead, DriverCandidate
from .geo import eta_minutes, haversine_km
from .pricing import CURRENCY, calculate_price
from .runtime_settings import OFFER_TIMEOUT, get_int

logger = logging.getLogger(__name__)

# How many nearby candidates to consider / report alongside the assignment.
CANDIDATE_LIMIT = 5

# The job lifecycle, as a state machine rather than ad-hoc status writes.
#
#   assigned --accept--> accepted --> enroute --> arrived --> completed
#       |                    |            |           |
#       +-- decline -------> declined     +-----------+--> cancelled
#
# Only the driver walks accepted -> completed. Reaching a terminal state
# releases the driver back into the available pool; without that a driver
# stayed 'enroute' forever after finishing and was never matched again.
DISPATCH_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "assigned": ("accepted", "declined", "cancelled"),
    "accepted": ("enroute", "arrived", "completed", "cancelled"),
    "enroute": ("arrived", "completed", "cancelled"),
    "arrived": ("completed", "cancelled"),
    "declined": (),
    "completed": (),
    "cancelled": (),
}

# Dispatch states in which the driver is committed to a job.
BUSY_DISPATCH_STATES = ("assigned", "accepted", "enroute", "arrived")

# Terminal states — the driver is free again.
TERMINAL_DISPATCH_STATES = ("declined", "completed", "cancelled")

# Dispatch status -> the status the linked ServiceRequest should take.
REQUEST_STATUS_FOR_DISPATCH: dict[str, str] = {
    "accepted": "enroute",
    "enroute": "enroute",
    "arrived": "in_progress",
    "completed": "completed",
    "cancelled": "cancelled",
    "declined": "pending",
}


def can_transition(current: str, target: str) -> bool:
    """Whether a dispatch may move from ``current`` to ``target``."""
    return target in DISPATCH_TRANSITIONS.get(current, ())


def apply_dispatch_status(dispatch, request, driver_profile, target: str) -> None:
    """Move a dispatch to ``target``, syncing the request and the driver.

    Kept in one place so every caller agrees on what a status means: the
    request follows the dispatch, and the driver is released the moment the
    job reaches a terminal state.
    """
    dispatch.status = target

    request_status = REQUEST_STATUS_FOR_DISPATCH.get(target)
    if request is not None and request_status is not None:
        request.status = request_status

    if driver_profile is not None:
        if target in TERMINAL_DISPATCH_STATES:
            driver_profile.current_status = 'available'
        else:
            driver_profile.current_status = 'enroute'


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


def dispatch_to_read(
    dispatch: Dispatch,
    driver: User = None,
    driver_profile: Driver = None,
    request: ServiceRequest = None,
) -> DispatchRead:
    """Serialize a Dispatch, denormalizing driver and request display fields."""
    return DispatchRead(
        id=dispatch.id,
        request_id=dispatch.request_id,
        driver_id=dispatch.driver_id,
        status=dispatch.status,
        distance_km=dispatch.distance_km,
        eta_minutes=dispatch.eta_minutes,
        price=float(dispatch.price) if dispatch.price is not None else None,
        currency=CURRENCY,
        created_at=dispatch.created_at,
        responded_at=dispatch.responded_at,
        expires_at=dispatch.expires_at,
        extension_count=dispatch.extension_count or 0,
        driver_name=(driver.email if driver else None),
        driver_email=(driver.email if driver else None),
        driver_lat=(driver_profile.current_lat if driver_profile else None),
        driver_lng=(driver_profile.current_lng if driver_profile else None),
        request_location=(request.location if request else None),
        request_description=(request.description if request else None),
        request_service_type=(request.service_type if request else None),
        request_vehicle_type=(request.vehicle_type if request else None),
        request_lat=(request.latitude if request else None),
        request_lng=(request.longitude if request else None),
    )


async def expire_stale_offers(session: AsyncSession) -> list[Dispatch]:
    """Lapse offers the driver never answered, freeing everyone involved.

    Swept lazily — on matching and on reading a driver's job list — rather
    than by a background scheduler. That keeps expiry deterministic and
    testable, needs no extra process, and behaves correctly with several API
    instances running. The tradeoff is that an offer only lapses once some
    request touches these paths; in practice a waiting client is polling, so
    it does.

    Returns the dispatches that were expired, so callers can re-offer them.
    """
    now = datetime.utcnow()
    stale = (
        await session.execute(
            select(Dispatch).where(
                and_(
                    Dispatch.status == "assigned",
                    Dispatch.expires_at.is_not(None),
                    Dispatch.expires_at < now,
                )
            )
        )
    ).scalars().all()

    if not stale:
        return []

    for dispatch in stale:
        request = await session.get(ServiceRequest, dispatch.request_id)
        driver_profile = (
            await session.execute(
                select(Driver).where(Driver.user_id == dispatch.driver_id)
            )
        ).scalar_one_or_none()
        # Treated as a decline: the driver is released, the request returns
        # to pending, and the row stays as a record of who was tried.
        apply_dispatch_status(dispatch, request, driver_profile, "declined")
        dispatch.responded_at = now
        logger.info(
            "dispatch %s expired unanswered (driver %s, request %s)",
            dispatch.id,
            dispatch.driver_id,
            dispatch.request_id,
        )

    await session.commit()
    return list(stale)


async def drivers_already_tried(session: AsyncSession, request_id: int) -> set[int]:
    """Driver ids that already declined or lapsed on this request.

    Excluding them is what turns the ranked candidate list into a real
    fallback chain instead of re-offering to the same driver forever.
    """
    rows = (
        await session.execute(
            select(Dispatch.driver_id).where(
                and_(
                    Dispatch.request_id == request_id,
                    Dispatch.status == "declined",
                )
            )
        )
    ).scalars().all()
    return set(rows)


async def match_request(session: AsyncSession, request: ServiceRequest):
    """Find the nearest available driver for a request and create a Dispatch.

    Returns (dispatch, drivers, candidates) where ``drivers`` is the raw
    (Driver, User) list and ``candidates`` is the ranked schema list. Raises
    ``LookupError`` when no driver is available or the request has no coords.
    """
    if request.latitude is None or request.longitude is None:
        raise LookupError("Request has no coordinates; cannot dispatch.")

    all_drivers = await list_available_drivers(session)

    # Never re-offer to someone who already said no (or let it lapse) on this
    # exact request — otherwise the 'next candidate' is the same candidate.
    tried = await drivers_already_tried(session, request.id)
    if tried:
        all_drivers = [(d, u) for d, u in all_drivers if u.id not in tried]

    if not all_drivers:
        raise LookupError(
            "No drivers are currently available."
            if not tried
            else "No further drivers available; every nearby driver has already been tried."
        )

    ranked = rank_candidates(all_drivers, request.latitude, request.longitude)
    top = ranked[0]
    driver_row, driver_user = top["driver"], top["user"]

    price = calculate_price(request.service_type, request.vehicle_type, top["distance_km"])

    timeout_seconds = await get_int(session, OFFER_TIMEOUT)
    dispatch = Dispatch(
        request_id=request.id,
        driver_id=driver_user.id,
        status="assigned",
        distance_km=top["distance_km"],
        eta_minutes=top["eta_minutes"],
        price=price,
        expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds),
    )
    session.add(dispatch)
    request.status = "assigned"
    await session.commit()
    await session.refresh(dispatch)

    candidates = [_candidate_schema(r) for r in ranked]
    return dispatch, driver_row, driver_user, candidates
