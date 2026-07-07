"""EmergencyLog CRUD router with JWT authentication."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import EmergencyLog, User
from ..schemas import EmergencyLogCreate, EmergencyLogRead, EmergencyLogUpdate

router = APIRouter(prefix="/emergency-logs", tags=["emergency-logs"])


@router.post("", response_model=EmergencyLogRead, status_code=status.HTTP_201_CREATED)
async def create_emergency_log(
    data: EmergencyLogCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> EmergencyLog:
    log = EmergencyLog(**data.model_dump(), reporter_id=user.id)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.get("", response_model=List[EmergencyLogRead])
async def list_emergency_logs(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[EmergencyLog]:
    result = await session.execute(
        select(EmergencyLog).where(EmergencyLog.reporter_id == user.id)
    )
    return result.scalars().all()


@router.get("/{log_id}", response_model=EmergencyLogRead)
async def get_emergency_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> EmergencyLog:
    log = await session.get(EmergencyLog, log_id)
    if not log or log.reporter_id != user.id:
        raise HTTPException(status_code=404, detail="Emergency log not found")
    return log


@router.patch("/{log_id}", response_model=EmergencyLogRead)
async def update_emergency_log(
    log_id: int,
    data: EmergencyLogUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> EmergencyLog:
    log = await session.get(EmergencyLog, log_id)
    if not log or log.reporter_id != user.id:
        raise HTTPException(status_code=404, detail="Emergency log not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    await session.commit()
    await session.refresh(log)
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emergency_log(
    log_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    log = await session.get(EmergencyLog, log_id)
    if not log or log.reporter_id != user.id:
        raise HTTPException(status_code=404, detail="Emergency log not found")
    await session.delete(log)
    await session.commit()