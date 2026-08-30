"""ServiceRequest CRUD router with JWT authentication.

Ordinary users see and manage only their own requests. Admin/superuser callers
see and manage every request — the full history — with each entry enriched with
the requester's identity and the matched driver's live position so the admin UI
can render a driver-vs-client map.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import Dispatch, Driver, ServiceRequest, User
from ..schemas import ServiceRequestCreate, ServiceRequestRead, ServiceRequestUpdate

router = APIRouter(prefix="/service-requests", tags=["service-requests"])

# Joined aliases so we can pull requester + driver + dispatch in one query.
Requester = aliased(User)
DriverUser = aliased(User)


def _is_admin(user: User) -> bool:
    return user.is_superuser or (user.role or "").lower() == "admin"


def _compose_read(
    sr: ServiceRequest,
    requester: Optional[User] = None,
    dispatch: Optional[Dispatch] = None,
    driver_user: Optional[User] = None,
    driver_profile: Optional[Driver] = None,
) -> ServiceRequestRead:
    """Serialize a ServiceRequest with optional requester/dispatch enrichment."""
    read = ServiceRequestRead.model_validate(sr)
    if requester is not None:
        read.requester_email = requester.email
        read.requester_name = requester.email
    if dispatch is not None:
        read.dispatch_status = dispatch.status
        read.distance_km = dispatch.distance_km
        read.eta_minutes = dispatch.eta_minutes
        read.price = float(dispatch.price) if dispatch.price is not None else None
        if driver_user is not None:
            read.driver_email = driver_user.email
        if driver_profile is not None:
            read.driver_lat = driver_profile.current_lat
            read.driver_lng = driver_profile.current_lng
    return read


def _enriched_select():
    """Base query: a request plus its requester and its CURRENT dispatch.

    A request can accumulate several dispatches — a driver declines, the
    request returns to `pending`, and the next candidate is assigned — so
    joining `Dispatch` directly on `request_id` multiplies the row out once per
    attempt. That made `one_or_none()` below raise MultipleResultsFound (a 500
    on read) and duplicated the request in the list endpoint.

    Joining through "highest dispatch id per request" instead collapses that to
    the latest attempt, which is the one clients should see, and keeps every
    earlier attempt on the table as history.
    """
    latest = (
        select(
            Dispatch.request_id.label("request_id"),
            func.max(Dispatch.id).label("dispatch_id"),
        )
        .group_by(Dispatch.request_id)
        .subquery()
    )
    return (
        select(ServiceRequest, Requester, Dispatch, DriverUser, Driver)
        .outerjoin(Requester, Requester.id == ServiceRequest.user_id)
        .outerjoin(latest, latest.c.request_id == ServiceRequest.id)
        .outerjoin(Dispatch, Dispatch.id == latest.c.dispatch_id)
        .outerjoin(DriverUser, DriverUser.id == Dispatch.driver_id)
        .outerjoin(Driver, Driver.user_id == Dispatch.driver_id)
    )


async def _query_enriched(session: AsyncSession, sr_id: int) -> ServiceRequestRead | None:
    """Fetch one request with its requester + current dispatch/driver joined in."""
    stmt = _enriched_select().where(ServiceRequest.id == sr_id)
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None
    return _compose_read(*row)


@router.post("", response_model=ServiceRequestRead, status_code=status.HTTP_201_CREATED)
async def create_service_request(
    data: ServiceRequestCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ServiceRequest:
    sr = ServiceRequest(**data.model_dump(), user_id=user.id)
    session.add(sr)
    await session.commit()
    await session.refresh(sr)
    return sr


@router.get("", response_model=List[ServiceRequestRead])
async def list_service_requests(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[ServiceRequestRead]:
    """List requests. Admins see the full history; others see only their own."""
    stmt = _enriched_select()
    if not _is_admin(user):
        stmt = stmt.where(ServiceRequest.user_id == user.id)
    stmt = stmt.order_by(ServiceRequest.created_at.desc())

    rows = (await session.execute(stmt)).all()
    return [_compose_read(*row) for row in rows]


@router.get("/{sr_id}", response_model=ServiceRequestRead)
async def get_service_request(
    sr_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ServiceRequestRead:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or (not _is_admin(user) and sr.user_id != user.id):
        raise HTTPException(status_code=404, detail="Service request not found")
    enriched = await _query_enriched(session, sr_id)
    return enriched if enriched is not None else ServiceRequestRead.model_validate(sr)


@router.patch("/{sr_id}", response_model=ServiceRequestRead)
async def update_service_request(
    sr_id: int,
    data: ServiceRequestUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ServiceRequestRead:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or (not _is_admin(user) and sr.user_id != user.id):
        raise HTTPException(status_code=404, detail="Service request not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sr, field, value)
    await session.commit()
    enriched = await _query_enriched(session, sr_id)
    return enriched if enriched is not None else ServiceRequestRead.model_validate(sr)


@router.delete("/{sr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_request(
    sr_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or (not _is_admin(user) and sr.user_id != user.id):
        raise HTTPException(status_code=404, detail="Service request not found")
    await session.delete(sr)
    await session.commit()
