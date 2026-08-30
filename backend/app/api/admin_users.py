"""Admin API for user roles.

Driving is a permissioned role, not something a user assigns themselves.
Granting it is the approval step for a tow van operator — the point at which
someone has been vetted enough to receive real clients — so it lives behind an
administrator.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ASSIGNABLE_ROLES, current_active_user, is_admin
from ..core.database import get_async_session
from ..models import Driver, User

router = APIRouter(prefix="/admin/users", tags=["admin"])


class AdminUserRead(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_superuser: bool
    is_online: Optional[bool] = None
    current_status: Optional[str] = None


class RoleWrite(BaseModel):
    role: str


def _require_admin(user: User) -> None:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Administrator access required")


@router.get("", response_model=List[AdminUserRead])
async def list_users(
    role: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[AdminUserRead]:
    """Users, optionally filtered by role, with their live driver state."""
    _require_admin(user)

    stmt = select(User, Driver).outerjoin(Driver, Driver.user_id == User.id).order_by(User.id)
    if role:
        stmt = stmt.where(User.role == role)

    return [
        AdminUserRead(
            id=u.id,
            email=u.email,
            role=u.role or "commuter",
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            is_online=(d.is_online if d else None),
            current_status=(d.current_status if d else None),
        )
        for u, d in (await session.execute(stmt)).all()
    ]


@router.put("/{user_id}/role", response_model=AdminUserRead)
async def set_user_role(
    user_id: int,
    data: RoleWrite,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AdminUserRead:
    """Grant or revoke a role. Granting `driver` is the approval step.

    Revoking takes the user out of the dispatch pool immediately rather than
    waiting for them to notice — otherwise a driver whose approval was pulled
    keeps receiving jobs until they next go offline.
    """
    _require_admin(user)

    role = (data.role or "").strip().lower()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown role '{data.role}'. Allowed: {list(ASSIGNABLE_ROLES)}",
        )

    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    target.role = role

    profile = (
        await session.execute(select(Driver).where(Driver.user_id == user_id))
    ).scalar_one_or_none()

    if role not in ("driver", "company", "admin") and profile is not None:
        profile.is_online = False
        profile.current_status = "off_duty"

    await session.commit()

    return AdminUserRead(
        id=target.id,
        email=target.email,
        role=target.role,
        is_active=target.is_active,
        is_superuser=target.is_superuser,
        is_online=(profile.is_online if profile else None),
        current_status=(profile.current_status if profile else None),
    )
