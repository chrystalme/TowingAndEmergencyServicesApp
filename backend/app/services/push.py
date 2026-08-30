"""Push notifications via Firebase Cloud Messaging.

The WebSocket covers the case where the app is open. This covers the case that
actually matters for a tow: the phone is in a pocket, screen off, and the driver
has just arrived. A socket cannot deliver that — the OS suspends it within
seconds of backgrounding — so it has to go through FCM/APNs.

Configuration is a single environment variable, ``FIREBASE_CREDENTIALS_JSON``,
holding the service-account JSON. That keeps the secret out of the repository
and works identically on Railway and in local compose.

**Push is optional.** With no credentials the app runs normally and simply skips
sending, which is what lets the test suite and a bare local run work without a
Firebase project. That is a deliberate difference from the JWT guard: a missing
push config degrades a feature, it does not make the service unsafe.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..models import DeviceToken

logger = logging.getLogger(__name__)

_app = None
_init_attempted = False


def _firebase_app():
    """The initialized Firebase app, or None when push is not configured.

    Initialization is attempted once. A bad credential should log loudly and
    then stop being retried on every notification.
    """
    global _app, _init_attempted
    if _init_attempted:
        return _app
    _init_attempted = True

    raw = (settings.FIREBASE_CREDENTIALS_JSON or "").strip()
    if not raw:
        logger.info("push: FIREBASE_CREDENTIALS_JSON not set; notifications disabled")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(json.loads(raw))
        _app = firebase_admin.initialize_app(cred, name="towassist-push")
        logger.info("push: Firebase initialized")
    except Exception as exc:
        logger.error("push: could not initialize Firebase, notifications disabled: %s", exc)
        _app = None
    return _app


def reset() -> None:
    """Forget the cached app so a configuration change takes effect.

    Initialization is deliberately once-only, which means a process that
    started without credentials would never pick them up. Tests also need
    this to pin push on or off rather than inheriting whatever the ambient
    environment happens to have configured.
    """
    global _app, _init_attempted
    _app = None
    _init_attempted = False


def is_enabled() -> bool:
    return _firebase_app() is not None


async def tokens_for_user(session: AsyncSession, user_id: int) -> list[str]:
    rows = (
        await session.execute(
            select(DeviceToken.token).where(DeviceToken.user_id == user_id)
        )
    ).scalars().all()
    return list(rows)


async def _drop_tokens(session: AsyncSession, tokens: Iterable[str]) -> None:
    """Delete tokens FCM has told us are dead.

    Uninstalls and reinstalls leave stale tokens behind. Keeping them means
    every future send wastes a call and the failure count grows forever.
    """
    dead = list(tokens)
    if not dead:
        return
    rows = (
        await session.execute(select(DeviceToken).where(DeviceToken.token.in_(dead)))
    ).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.commit()
    logger.info("push: pruned %d dead token(s)", len(rows))


async def send_to_user(
    session: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> int:
    """Notify every device a user has registered. Returns how many were sent.

    Never raises: a failed notification must not fail the request that
    triggered it. A driver accepting a job should not get a 500 because
    someone's phone token expired.
    """
    app = _firebase_app()
    if app is None:
        return 0

    tokens = await tokens_for_user(session, user_id)
    if not tokens:
        return 0

    try:
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            # Data must be all-strings; the app reads these to route the tap.
            data={k: str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(channel_id="towassist_jobs"),
            ),
        )
        # firebase-admin is synchronous: this is a blocking HTTPS round
        # trip. Called directly it would stall the event loop - and so
        # every other in-flight request - for its duration.
        response = await asyncio.to_thread(
            messaging.send_each_for_multicast, message, app=app
        )
    except Exception as exc:
        logger.warning("push: send failed for user %s: %s", user_id, exc)
        return 0

    dead = [
        tokens[i]
        for i, r in enumerate(response.responses)
        if not r.success
        and getattr(r.exception, "code", "") in ("NOT_FOUND", "INVALID_ARGUMENT",
                                                 "UNREGISTERED", "registration-token-not-registered")
    ]
    if dead:
        await _drop_tokens(session, dead)

    return response.success_count


# What each dispatch status should say to the person waiting. Statuses absent
# here are deliberately silent — a client does not need a notification that
# their request was re-offered internally.
_STATUS_COPY: dict[str, tuple[str, str]] = {
    "assigned": ("Driver dispatched", "{driver} is on the way to you"),
    "accepted": ("Driver accepted", "{driver} accepted your request"),
    "enroute": ("Driver on the way", "{driver} is driving to you"),
    "arrived": ("Driver arrived", "{driver} has arrived"),
    "completed": ("Request complete", "Your request has been completed"),
    "cancelled": ("Request cancelled", "Your request was cancelled"),
}


async def notify_requester_of_status(
    session: AsyncSession, dispatch, request, driver_email: Optional[str] = None
) -> int:
    """Push a job status change to the person who filed the request."""
    if request is None:
        return 0
    copy = _STATUS_COPY.get(dispatch.status)
    if copy is None:
        return 0

    title, body_template = copy
    return await send_to_user(
        session,
        request.user_id,
        title,
        body_template.format(driver=driver_email or "Your driver"),
        {
            "type": "dispatch_status",
            "request_id": dispatch.request_id,
            "dispatch_id": dispatch.id,
            "status": dispatch.status,
        },
    )
