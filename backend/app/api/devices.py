"""Device registration for push notifications.

The app posts its FCM token here after signing in, and removes it on sign-out
so the next person to use that phone does not receive the previous user's job
notifications.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import DeviceToken, User

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegisterIn(BaseModel):
    token: str = Field(..., min_length=8, max_length=4096)
    platform: str = Field("android", pattern="^(android|ios|web)$")


class DeviceRead(BaseModel):
    id: int
    platform: str
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def register_device(
    data: DeviceRegisterIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> DeviceToken:
    """Register (or re-claim) this device's push token.

    FCM tokens rotate, and the same physical phone can be handed to a different
    user. So an existing token is reassigned to whoever is signed in now rather
    than rejected — otherwise the previous owner would keep getting this phone's
    notifications.
    """
    existing = (
        await session.execute(select(DeviceToken).where(DeviceToken.token == data.token))
    ).scalar_one_or_none()

    if existing is not None:
        existing.user_id = user.id
        existing.platform = data.platform
        existing.last_seen_at = datetime.utcnow()
        await session.commit()
        await session.refresh(existing)
        return existing

    device = DeviceToken(user_id=user.id, token=data.token, platform=data.platform)
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    data: DeviceRegisterIn,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    """Drop this device's token, e.g. on sign-out."""
    device = (
        await session.execute(
            select(DeviceToken).where(
                DeviceToken.token == data.token, DeviceToken.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if device is None:
        # Already gone: nothing to do, and a 404 would make sign-out noisy.
        return
    await session.delete(device)
    await session.commit()
