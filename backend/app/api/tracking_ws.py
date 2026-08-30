"""Authenticated WebSocket for live driver tracking.

Replaces the endpoint removed in the security pass. That one took a `user_id`
straight from the URL path and wrote whatever it was sent, so anyone could
reposition any driver. This one is the opposite shape in every way that
mattered:

* it only ever **reads** — positions still arrive over the authenticated REST
  heartbeat (``PUT /api/drivers/me``), so a socket can never move a driver;
* the caller is resolved from a JWT, never from the path;
* the path identifies a *request*, and you must be a party to it — the
  requester who filed it, or the driver currently assigned to it.

Fan-out goes through ``app.core.broker``, so a position published by whichever
API instance handled the driver's heartbeat reaches watchers connected to any
other instance. With the in-process fallback that is silently single-instance,
which is why ``REDIS_URL`` matters in production.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from ..core.auth import UserManager, get_jwt_strategy
from ..core.broker import get_broker
from ..services.push import notify_requester_of_status
from ..core.database import AsyncSessionLocal
from ..models import Dispatch, Driver, ServiceRequest, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tracking"])

# Dispatch states in which a driver is committed to a job and therefore worth
# tracking. Duplicated deliberately rather than imported so this module does not
# depend on the dispatch-lifecycle branch; unify once both have landed.
ACTIVE_DISPATCH_STATES = ("assigned", "accepted", "enroute", "arrived")

# Application-defined close codes (the 4xxx range), so a client can tell
# "log in again" apart from "you are not part of this job".
#
# These require accepting the handshake first. Closing before accept() rejects
# at the HTTP layer, which conveys only a bare 403 — the code is lost and every
# failure looks identical to the client. Accepting costs nothing here: no data
# is sent before the check, and the socket closes immediately.
WS_UNAUTHENTICATED = 4401
WS_FORBIDDEN = 4403
WS_NOT_FOUND = 4404


def channel_for(request_id: int) -> str:
    """The broker channel carrying one request's driver positions."""
    return f"request:{request_id}"


async def user_from_token(token: str, session: AsyncSession) -> Optional[User]:
    """Resolve a JWT to a user, or None.

    Browsers cannot set headers on a WebSocket handshake, so the token arrives
    as a query parameter. It is verified with exactly the same JWTStrategy the
    REST endpoints use — this is not a second, weaker auth path.

    Takes the caller's session rather than opening its own. Calling the
    get_user_db() dependency by hand would bypass FastAPI's override machinery
    and reach for a second connection pool — which is wrong in production and
    silently unauthenticates everything under test.
    """
    if not token:
        return None
    strategy = get_jwt_strategy()
    manager = UserManager(SQLAlchemyUserDatabase(session, User))
    try:
        return await strategy.read_token(token, manager)
    except Exception as exc:  # invalid, expired, or unknown user
        logger.debug("tracking socket rejected a token: %s", exc)
        return None


async def _may_watch(
    session: AsyncSession, user: User, request_id: int
) -> tuple[bool, Optional[ServiceRequest]]:
    """Whether this user is a party to this request."""
    request = await session.get(ServiceRequest, request_id)
    if request is None:
        return False, None
    if request.user_id == user.id:
        return True, request

    assigned = (
        await session.execute(
            select(Dispatch.id)
            .where(
                Dispatch.request_id == request_id,
                Dispatch.driver_id == user.id,
                Dispatch.status.in_(ACTIVE_DISPATCH_STATES),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return assigned is not None, request


async def current_driver_position(
    session: AsyncSession, request_id: int
) -> Optional[dict]:
    """The assigned driver's last known position, if there is one.

    Sent immediately on connect so a watcher sees the truck straight away
    instead of a blank map until the driver's next heartbeat.
    """
    row = (
        await session.execute(
            select(Dispatch, Driver)
            .join(Driver, Driver.user_id == Dispatch.driver_id)
            .where(
                Dispatch.request_id == request_id,
                Dispatch.status.in_(ACTIVE_DISPATCH_STATES),
            )
            .order_by(Dispatch.id.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    dispatch, driver = row
    if driver.current_lat is None or driver.current_lng is None:
        return None
    return {
        "type": "driver_position",
        "request_id": request_id,
        "driver_id": dispatch.driver_id,
        "lat": driver.current_lat,
        "lng": driver.current_lng,
        "dispatch_status": dispatch.status,
        "at": (driver.last_position_at or datetime.utcnow()).isoformat(),
    }


@router.websocket("/ws/track/{request_id}")
async def track_request(
    websocket: WebSocket,
    request_id: int,
    token: str = "",
) -> None:
    """Stream the assigned driver's position for one request.

    Connect with ``/api/ws/track/{request_id}?token=<jwt>``. Read-only: any
    frame the client sends is ignored, so this cannot be used to move a driver.
    """
    # Accept first so a refusal can carry a reason. Nothing is sent until the
    # checks below pass.
    await websocket.accept()

    # The session is opened here and released before the streaming loop,
    # rather than injected with Depends(get_async_session).
    #
    # A dependency lives as long as the connection it was injected into. On a
    # socket a client keeps open while they wait for a tow, that meant one
    # pooled connection and one OPEN TRANSACTION held for the whole watch -
    # and a transaction holds its locks for as long as it lives. Two of these,
    # left over from a QA run, blocked a migration's ALTER TABLE until the
    # deploy timed out and rolled back.
    #
    # Every query this endpoint needs happens up front, so nothing is lost by
    # closing the session before the part that waits.
    async with AsyncSessionLocal() as session:
        user = await user_from_token(token, session)
        if user is None:
            await websocket.close(code=WS_UNAUTHENTICATED)
            return

        allowed, request = await _may_watch(session, user, request_id)
        if request is None:
            await websocket.close(code=WS_NOT_FOUND)
            return
        if not allowed:
            await websocket.close(code=WS_FORBIDDEN)
            return

        snapshot = await current_driver_position(session, request_id)

    # No session held from here on: the loop below can run for hours.
    if snapshot is not None:
        await websocket.send_json(snapshot)

    broker = get_broker()
    subscription = broker.subscribe(channel_for(request_id))
    try:
        async for event in subscription:
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("tracking socket for request %s failed: %s", request_id, exc)
    finally:
        await subscription.aclose()


async def publish_dispatch_status(
    dispatch, request=None, driver_email: Optional[str] = None, session=None
) -> None:
    """Broadcast a job's status change to whoever is watching that request.

    The socket previously carried only driver_position, so a client watching a
    tow learned where the van was but never that it had accepted, arrived, or
    finished — the events they actually care about. Position without status is
    a moving dot with no story.
    """
    broker = get_broker()
    await broker.publish(
        channel_for(dispatch.request_id),
        {
            "type": "dispatch_status",
            "request_id": dispatch.request_id,
            "dispatch_id": dispatch.id,
            "status": dispatch.status,
            "request_status": getattr(request, "status", None),
            "driver_id": dispatch.driver_id,
            "driver_email": driver_email,
            "eta_minutes": dispatch.eta_minutes,
            "price": float(dispatch.price) if dispatch.price is not None else None,
            "at": datetime.utcnow().isoformat(),
        },
    )

    # Same event, second channel. The socket only reaches a foregrounded app;
    # a client whose phone is in their pocket waiting for a tow needs FCM.
    if session is not None:
        await notify_requester_of_status(session, dispatch, request, driver_email)


async def publish_driver_position(
    session: AsyncSession, driver_user_id: int, lat: Optional[float], lng: Optional[float]
) -> int:
    """Fan a driver's new position out to everyone watching their live jobs.

    Called from the REST heartbeat so there is exactly one way a position
    enters the system. Returns how many channels were published to, which makes
    the behaviour assertable in tests.
    """
    if lat is None or lng is None:
        return 0

    request_ids = (
        await session.execute(
            select(Dispatch.request_id).where(
                Dispatch.driver_id == driver_user_id,
                Dispatch.status.in_(ACTIVE_DISPATCH_STATES),
            )
        )
    ).scalars().all()
    if not request_ids:
        return 0

    broker = get_broker()
    now = datetime.utcnow().isoformat()
    for request_id in set(request_ids):
        await broker.publish(
            channel_for(request_id),
            {
                "type": "driver_position",
                "request_id": request_id,
                "driver_id": driver_user_id,
                "lat": lat,
                "lng": lng,
                "at": now,
            },
        )
    return len(set(request_ids))
