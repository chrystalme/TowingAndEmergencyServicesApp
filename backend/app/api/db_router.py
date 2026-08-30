"""Dependency health endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.broker import get_broker
from ..core.database import get_async_session

router = APIRouter()

@router.get("/db-ping", tags=["monitoring"])
async def db_ping(session: AsyncSession = Depends(get_async_session)) -> dict:
    await session.execute(text("SELECT 1"))
    return {"db": "ok"}


@router.get("/broker-ping", tags=["monitoring"])
async def broker_ping() -> dict:
    """Which fan-out backend is live, and is it reachable.

    Reports the backend name so a deployment that quietly fell back to
    in-process fan-out is visible from the outside, not just in the logs.
    """
    broker = get_broker()
    try:
        ok = await broker.ping()
    except Exception as exc:  # pragma: no cover - depends on a live Redis
        return {"broker": getattr(broker, "name", "unknown"), "ok": False, "error": str(exc)[:200]}
    return {"broker": getattr(broker, "name", "unknown"), "ok": bool(ok)}