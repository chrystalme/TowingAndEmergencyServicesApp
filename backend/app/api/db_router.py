"""Database health endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session

router = APIRouter()

@router.get("/db-ping", tags=["monitoring"])
async def db_ping(session: AsyncSession = Depends(get_async_session)) -> dict:
    await session.execute(text("SELECT 1"))
    return {"db": "ok"}