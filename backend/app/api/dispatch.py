"""Dispatch endpoints: find / match the nearest driver to a situation.

Flow:
1. ``GET /dispatch/available`` — any (authenticated) caller can preview the
   nearest available drivers for a coordinate (no assignment created).
2. ``POST /dispatch`` — the requester triggers a match for a pending request;
   the top candidate is assigned (Dispatch created) and priced server-side.
3. ``POST /dispatch/{id}/respond`` — the matched driver accepts or declines.
4. ``GET /service-requests/{id}/dispatch`` — the requester views the live
   assignment (driver + ETA + price + driver position).
"""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import Dispatch, Driver, ServiceRequest, User
from ..schemas import DispatchMatchResponse, DispatchRead, DriverCandidate
from ..services.dispatch import (
    BUSY_DISPATCH_STATES,
    DISPATCH_TRANSITIONS,
    apply_dispatch_status,
    can_transition,
    dispatch_to_read,
    expire_stale_offers,
    list_available_drivers,
    match_request,
    rank_candidates,
    _candidate_schema,
)
from ..services.runtime_settings import (
    MAX_EXTENSIONS,
    OFFER_EXTENSION,
    get_int,
)

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


class MatchIn(BaseModel):
    request_id: int


class RespondIn(BaseModel):
    status: str  # accepted | declined


@router.get("/available", response_model=List[DriverCandidate])
async def nearby_drivers(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[DriverCandidate]:
    """Preview the nearest available drivers for a location (no assignment)."""
    all_drivers = await list_available_drivers(session)
    ranked = rank_candidates(all_drivers, lat, lng)
    return [_candidate_schema(r) for r in ranked]


@router.get("/mine", response_model=List[DispatchRead])
async def my_dispatches(
    active_only: bool = Query(True, description="Only jobs still needing the driver"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[DispatchRead]:
    """Jobs assigned to the calling driver, newest first.

    Without this a driver had no way to discover what they had been matched to:
    ``/dispatch/{id}/respond`` needs an id, and ``/service-requests/{id}`` is
    scoped to the requester and admins, so the driver could not read either. The
    response therefore carries enough of the linked request (location,
    description, service/vehicle type, coordinates) to accept or decline
    without a second call.
    """
    # Lapse anything the driver sat on before showing them the list, so a
    # stale offer is never presented as still actionable.
    await expire_stale_offers(session)

    stmt = (
        select(Dispatch, ServiceRequest)
        .join(ServiceRequest, ServiceRequest.id == Dispatch.request_id)
        .where(Dispatch.driver_id == user.id)
        .order_by(Dispatch.id.desc())
    )
    if active_only:
        stmt = stmt.where(Dispatch.status.in_(BUSY_DISPATCH_STATES))

    rows = (await session.execute(stmt)).all()
    driver_profile = (
        await session.execute(select(Driver).where(Driver.user_id == user.id))
    ).scalar_one_or_none()
    return [
        dispatch_to_read(dispatch, user, driver_profile, request)
        for dispatch, request in rows
    ]


@router.get("/request/{request_id}", response_model=DispatchRead)
async def get_request_dispatch(
    request_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DispatchRead:
    """The requester's view of their assignment (driver, ETA, price, position)."""
    request = await session.get(ServiceRequest, request_id)
    if not request or request.user_id != user.id:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Newest first: a declined request gets re-dispatched, so several rows can
    # share a request_id and the caller wants the current attempt, not whichever
    # one the database happened to return.
    result = await session.execute(
        select(Dispatch)
        .where(Dispatch.request_id == request_id)
        .order_by(Dispatch.id.desc())
    )
    dispatch = result.scalars().first()
    if dispatch is None:
        raise HTTPException(status_code=404, detail="No dispatch for this request")

    driver = await session.get(User, dispatch.driver_id)
    driver_profile = (
        await session.execute(select(Driver).where(Driver.user_id == dispatch.driver_id))
    ).scalar_one_or_none()
    return dispatch_to_read(dispatch, driver, driver_profile, request)


@router.post("", response_model=DispatchMatchResponse, status_code=status.HTTP_201_CREATED)
async def create_dispatch(
    data: MatchIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DispatchMatchResponse:
    """Match the nearest available driver to a pending request (idempotently)."""
    # An offer that has run out must lapse before we decide anything: it
    # frees the held driver and returns the request to 'pending', which is
    # what makes re-dispatch possible at all.
    await expire_stale_offers(session)

    request = await session.get(ServiceRequest, data.request_id)
    if not request or request.user_id != user.id:
        raise HTTPException(status_code=404, detail="Service request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail=f"Cannot dispatch a request with status '{request.status}'")

    # Belt-and-braces against inconsistent state: if a live assignment already
    # exists, refuse rather than stacking a second one on the same request.
    live = (
        await session.execute(
            select(Dispatch).where(
                Dispatch.request_id == request.id,
                Dispatch.status.in_(BUSY_DISPATCH_STATES),
            )
        )
    ).scalars().first()
    if live is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Request already has a live dispatch (id={live.id}, status='{live.status}')",
        )

    try:
        dispatch, driver_profile, driver_user, candidates = await match_request(session, request)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Hold the matched driver so another request can't grab them mid-assignment.
    driver_profile.current_status = "enroute"
    await session.commit()

    return DispatchMatchResponse(
        dispatch=dispatch_to_read(dispatch, driver_user, driver_profile),
        request_status=request.status,
        candidates=candidates,
    )


class ExtendIn(BaseModel):
    seconds: int | None = None  # defaults to the configured extension


class StatusIn(BaseModel):
    status: str  # enroute | arrived | completed | cancelled


@router.post("/{dispatch_id}/extend", response_model=DispatchRead)
async def extend_offer(
    dispatch_id: int,
    data: ExtendIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DispatchRead:
    """Buy the assigned driver more time before their offer lapses.

    A driver who is mid-decision should not lose the job to a timer, but a
    client should not wait forever either — so extensions are capped, and
    both the cap and the amount of time granted are runtime settings.
    """
    dispatch = await session.get(Dispatch, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    if dispatch.driver_id != user.id:
        raise HTTPException(status_code=403, detail="Not your dispatch to extend")
    if dispatch.status != "assigned":
        raise HTTPException(
            status_code=409,
            detail=f"Only an unanswered offer can be extended (this one is '{dispatch.status}')",
        )

    max_extensions = await get_int(session, MAX_EXTENSIONS)
    if dispatch.extension_count >= max_extensions:
        raise HTTPException(
            status_code=409,
            detail=f"This offer has already been extended {dispatch.extension_count} time(s); the limit is {max_extensions}",
        )

    granted = data.seconds or await get_int(session, OFFER_EXTENSION)
    try:
        granted = OFFER_EXTENSION.clamp_or_raise(int(granted))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Extend from now rather than from the old deadline: a driver who taps
    # extend with two seconds left should get the full window.
    base = max(dispatch.expires_at or datetime.utcnow(), datetime.utcnow())
    dispatch.expires_at = base + timedelta(seconds=granted)
    dispatch.extension_count += 1
    await session.commit()
    await session.refresh(dispatch)

    request = await session.get(ServiceRequest, dispatch.request_id)
    driver_profile = (
        await session.execute(select(Driver).where(Driver.user_id == user.id))
    ).scalar_one_or_none()
    return dispatch_to_read(dispatch, user, driver_profile, request)


@router.post("/{dispatch_id}/status", response_model=DispatchRead)
async def advance_dispatch(
    dispatch_id: int,
    data: StatusIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DispatchRead:
    """Move an accepted job along: enroute, arrived, completed, cancelled.

    Previously nothing could write these states, so a job stopped at
    'accepted' and its driver stayed 'enroute' permanently — every completed
    job removed a driver from the pool for good. Completing (or cancelling)
    now releases them.

    The assigned driver may advance the job; the requester may only cancel.
    """
    dispatch = await session.get(Dispatch, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    request = await session.get(ServiceRequest, dispatch.request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Linked service request not found")

    is_driver = dispatch.driver_id == user.id
    is_requester = request.user_id == user.id
    if not (is_driver or is_requester):
        raise HTTPException(status_code=404, detail="Dispatch not found")
    if is_requester and not is_driver and data.status != "cancelled":
        raise HTTPException(
            status_code=403,
            detail="Only the assigned driver can advance this job; you may cancel it",
        )

    if not can_transition(dispatch.status, data.status):
        allowed = DISPATCH_TRANSITIONS.get(dispatch.status, ())
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot move a '{dispatch.status}' dispatch to '{data.status}'. "
                f"Allowed: {list(allowed) or 'none (terminal)'}"
            ),
        )

    driver_profile = (
        await session.execute(select(Driver).where(Driver.user_id == dispatch.driver_id))
    ).scalar_one_or_none()

    apply_dispatch_status(dispatch, request, driver_profile, data.status)
    await session.commit()
    await session.refresh(dispatch)

    driver_user = await session.get(User, dispatch.driver_id)
    return dispatch_to_read(dispatch, driver_user, driver_profile, request)


@router.post("/{dispatch_id}/respond", response_model=DispatchRead)
async def respond_to_dispatch(
    dispatch_id: int,
    data: RespondIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DispatchRead:
    """The assigned driver accepts or declines the job."""
    dispatch = await session.get(Dispatch, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    if dispatch.driver_id != user.id:
        raise HTTPException(status_code=403, detail="Not your dispatch to respond to")
    if dispatch.status not in ("assigned",):
        raise HTTPException(status_code=409, detail=f"Dispatch already '{dispatch.status}'")

    request = await session.get(ServiceRequest, dispatch.request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Linked service request not found")
    driver_profile = (
        await session.execute(select(Driver).where(Driver.user_id == user.id))
    ).scalar_one_or_none()

    if data.status not in ("accepted", "declined"):
        raise HTTPException(status_code=422, detail="status must be 'accepted' or 'declined'")

    apply_dispatch_status(dispatch, request, driver_profile, data.status)

    dispatch.responded_at = __import__("datetime").datetime.utcnow()
    await session.commit()
    await session.refresh(dispatch)
    return dispatch_to_read(dispatch, user, driver_profile, request)