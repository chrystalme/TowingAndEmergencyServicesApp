"""Driver availability + live position endpoints (REST heartbeat).

Drivers come online, set their position, and flip between available/enroute.
The WebSocket variant in ``ws.py`` offers the same upsert for streaming updates;
this REST surface is the canonical, testable path.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user, may_drive
from ..core.database import get_async_session
from ..models import Driver, User
from ..schemas import DriverRead, DriverUpdate

router = APIRouter(prefix="/drivers", tags=["drivers"])


def _require_driver(user: User) -> None:
    """Refuse callers who are not permissioned to drive.

    This endpoint puts someone into the live dispatch pool, so real clients
    can be routed to them. It previously accepted any authenticated user AND
    promoted them to the driver role on the way in, which meant a commuter
    could become a dispatchable tow van by tapping a button. Hiding the
    button in the app would not have fixed it: anyone with curl was one
    request away from receiving jobs.
    """
    if not may_drive(user):
        raise HTTPException(
            status_code=403,
            detail="Your account is not approved to drive. An administrator grants the driver role.",
        )


async def _upsert_driver(session: AsyncSession, user: User, data: DriverUpdate) -> Driver:
    """Fetch-or-create the current user's driver profile and apply updates."""
    result = await session.execute(select(Driver).where(Driver.user_id == user.id))
    driver = result.scalar_one_or_none()

    if driver is None:
        driver = Driver(user_id=user.id)
        session.add(driver)

    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(driver, field, value)

    # Any explicit availability/position update refreshes the timestamp.
    driver.last_position_at = datetime.utcnow()

    # Deliberately does NOT touch user.role. Going online is an action a
    # driver takes; it is not how someone becomes one.

    await session.commit()
    await session.refresh(driver)
    return driver


@router.get("/me", response_model=DriverRead)
async def get_my_driver_profile(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Driver:
    _require_driver(user)
    result = await session.execute(select(Driver).where(Driver.user_id == user.id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver profile not set up")
    return driver


@router.put("/me", response_model=DriverRead)
async def set_driver_availability(
    data: DriverUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Driver:
    _require_driver(user)
    if data.model_dump(exclude_unset=True) == {}:
        raise HTTPException(status_code=422, detail="Nothing to update")
    return await _upsert_driver(session, user, data)


@router.post("/me/position", response_model=DriverRead)
async def update_position(
    data: DriverUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Driver:
    """Lightweight position heartbeat; also sets online/status when provided."""
    _require_driver(user)
    if data.current_lat is None and data.current_lng is None and not data.is_online and not data.current_status:
        raise HTTPException(status_code=422, detail="Provide at least coordinates or availability")
    return await _upsert_driver(session, user, data)