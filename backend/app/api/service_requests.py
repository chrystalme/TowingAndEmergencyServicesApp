"""ServiceRequest CRUD router with JWT authentication."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import ServiceRequest, User
from ..schemas import ServiceRequestCreate, ServiceRequestRead, ServiceRequestUpdate

router = APIRouter(prefix="/service-requests", tags=["service-requests"])


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
) -> List[ServiceRequest]:
    result = await session.execute(
        select(ServiceRequest).where(ServiceRequest.user_id == user.id)
    )
    return result.scalars().all()


@router.get("/{sr_id}", response_model=ServiceRequestRead)
async def get_service_request(
    sr_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ServiceRequest:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or sr.user_id != user.id:
        raise HTTPException(status_code=404, detail="Service request not found")
    return sr


@router.patch("/{sr_id}", response_model=ServiceRequestRead)
async def update_service_request(
    sr_id: int,
    data: ServiceRequestUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> ServiceRequest:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or sr.user_id != user.id:
        raise HTTPException(status_code=404, detail="Service request not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sr, field, value)
    await session.commit()
    await session.refresh(sr)
    return sr


@router.delete("/{sr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_request(
    sr_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    sr = await session.get(ServiceRequest, sr_id)
    if not sr or sr.user_id != user.id:
        raise HTTPException(status_code=404, detail="Service request not found")
    await session.delete(sr)
    await session.commit()