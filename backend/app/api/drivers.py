"""Driver availability + live position endpoints (REST heartbeat).

Drivers come online, set their position, and flip between available/enroute.
The WebSocket variant in ``ws.py`` offers the same upsert for streaming updates;
this REST surface is the canonical, testable path.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import Driver, User
from ..schemas import DriverRead, DriverUpdate
from .tracking_ws import publish_driver_position

router = APIRouter(prefix="/drivers", tags=["drivers"])


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

    # Going online as a driver implies the driver role.
    if payload.get("is_online") is True:
        user.role = "driver"

    await session.commit()
    await session.refresh(driver)

    # Fan the new position out to anyone tracking this driver's live jobs.
    # Positions only ever enter the system here, so the tracking socket can
    # stay strictly read-only.
    await publish_driver_position(
        session, user.id, driver.current_lat, driver.current_lng
    )
    return driver


@router.get("/me", response_model=DriverRead)
async def get_my_driver_profile(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Driver:
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
    if data.current_lat is None and data.current_lng is None and not data.is_online and not data.current_status:
        raise HTTPException(status_code=422, detail="Provide at least coordinates or availability")
    return await _upsert_driver(session, user, data)