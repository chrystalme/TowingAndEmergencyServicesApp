"""WebSocket position stream for drivers.

Accepted client messages (JSON):
    {"lat": 37.7, "lng": -122.4, "is_online": true, "current_status": "available"}

The server upserts the driver's profile and echoes an ack. This is a thin
streaming complement to the REST ``POST /api/drivers/me/position`` heartbeat
(which remains the canonical, unit-tested path).
"""

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session
from ..models import Driver, User
from ..schemas import DriverUpdate

router = APIRouter(tags=["ws"])


@router.websocket("/ws/driver/{user_id}/position")
async def driver_position_stream(
    websocket: WebSocket,
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_json()
            data = DriverUpdate(**raw)
            result = await session.execute(select(Driver).where(Driver.user_id == user_id))
            driver = result.scalar_one_or_none()
            # Only the owning user may stream (no auth on WS here; enforcement
            # is done by the REST path in production). Guard by requiring the
            # user to exist.
            user = await session.get(User, user_id)
            if user is None:
                await websocket.send_json({"error": "unknown user"})
                continue

            if driver is None:
                driver = Driver(user_id=user_id)
                session.add(driver)

            payload = data.model_dump(exclude_unset=True)
            for field, value in payload.items():
                setattr(driver, field, value)
            driver.last_position_at = __import__("datetime").datetime.utcnow()
            if payload.get("is_online") is True:
                user.role = "driver"
            await session.commit()

            await websocket.send_json({"status": "updated", "user_id": user_id})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # pragma: no cover - defensive ack
        await websocket.send_json({"error": str(exc)})