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
from .tracking_ws import router as tracking_router
from .admin_settings import router as admin_settings_router
from .admin_users import router as admin_users_router

# NOTE: `.ws` is intentionally NOT imported/mounted. The driver position stream
# accepted a user_id straight from the URL path with no authentication, so any
# caller could move any driver or pull them out of the dispatch pool. No client
# uses it (web and mobile both post position via PUT /api/drivers/me), so it is
# pure attack surface. See app/api/ws.py before re-enabling it.

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

# Read-only live tracking socket (JWT in a query param; browsers cannot set
# headers on a WebSocket handshake).
router.include_router(tracking_router)
# Runtime settings (superuser only) - change dispatch behaviour without a deploy.
router.include_router(admin_settings_router)
router.include_router(admin_users_router)

# Debug endpoint
@router.get("/ping", tags=["debug"])
async def ping() -> dict:
    return {"msg": "pong"}
