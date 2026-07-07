"""Vehicle CRUD router with JWT authentication."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import current_active_user
from ..core.database import get_async_session
from ..models import User, Vehicle
from ..schemas import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    data: VehicleCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Vehicle:
    vehicle = Vehicle(**data.model_dump(), owner_id=user.id)
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


@router.get("", response_model=List[VehicleRead])
async def list_vehicles(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> List[Vehicle]:
    result = await session.execute(select(Vehicle).where(Vehicle.owner_id == user.id))
    return result.scalars().all()


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> None:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await session.delete(vehicle)
    await session.commit()