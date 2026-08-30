"""Admin API for runtime settings.

The point of these endpoints is that operational knobs change without a
release. Editing an environment variable on a PaaS restarts the service, so an
env var cannot be "toggled" — it can only be redeployed. Values written here
take effect on the next read, on every instance.

Superuser only: these directly change dispatch behaviour for every user.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import User
from ..services.runtime_settings import KNOBS, describe_all, get_int, set_int

router = APIRouter(prefix="/admin/settings", tags=["admin"])


class SettingRead(BaseModel):
    key: str
    value: int
    default: int
    minimum: int
    maximum: int
    source: str  # "override" | "default"
    description: str
    updated_at: Optional[str] = None


class SettingWrite(BaseModel):
    value: int


def _require_admin(user: User) -> None:
    if not (user.is_superuser or (user.role or "").lower() == "admin"):
        raise HTTPException(status_code=403, detail="Administrator access required")


@router.get("", response_model=List[SettingRead])
async def list_settings(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[SettingRead]:
    """Every knob, its effective value, and whether that came from an override."""
    _require_admin(user)
    rows = await describe_all(session)
    return [
        SettingRead(
            **{
                **row,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        )
        for row in rows
    ]


@router.put("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    data: SettingWrite,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> SettingRead:
    """Override one knob. Takes effect immediately, no redeploy."""
    _require_admin(user)

    knob = KNOBS.get(key)
    if knob is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting '{key}'. Known: {sorted(KNOBS)}",
        )

    try:
        await set_int(session, knob, data.value, user_id=user.id)
    except ValueError as exc:
        # Bounds exist so a typo cannot make offers expire instantly or never.
        raise HTTPException(status_code=422, detail=str(exc))

    effective = await get_int(session, knob)
    return SettingRead(
        key=knob.key,
        value=effective,
        default=knob.default,
        minimum=knob.minimum,
        maximum=knob.maximum,
        source="override",
        description=knob.description,
        updated_at=None,
    )
