from fastapi import APIRouter

from ..core.auth import (
    auth_router,
    register_router,
    reset_password_router,
    verify_router,
    users_router,
)
from .db_router import router as db_router
from .service_requests import router as service_requests_router
from .vehicles import router as vehicles_router
from .emergency_logs import router as emergency_logs_router
from .drivers import router as drivers_router
from .dispatch import router as dispatch_router
from .ws import router as ws_router

router = APIRouter()

# Authentication routes
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])
router.include_router(register_router, prefix="/auth", tags=["auth"])
router.include_router(reset_password_router, prefix="/auth", tags=["auth"])
router.include_router(verify_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])

# Monitoring routes
router.include_router(db_router, tags=["monitoring"])

# Resource CRUD routes (auth-protected)
router.include_router(service_requests_router)
router.include_router(vehicles_router)
router.include_router(emergency_logs_router)

# Dispatch / routing routes
router.include_router(drivers_router)
router.include_router(dispatch_router)
router.include_router(ws_router)

# Debug endpoint
@router.get("/ping", tags=["debug"])
async def ping() -> dict:
    return {"msg": "pong"}