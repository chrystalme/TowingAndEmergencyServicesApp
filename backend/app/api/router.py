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
from .devices import router as devices_router
from .admin_settings import router as admin_settings_router
from .admin_users import router as admin_users_router

# NOTE: there is no driver-position WebSocket. app/api/ws.py used to hold one,
# left unmounted because it took a user_id straight from the URL path with no
# authentication: any caller could move any driver, pull one out of the
# dispatch pool, or - since it set `user.role = "driver"` - promote an account
# straight past the administrator approval that gates driving.
#
# It has now been deleted rather than left dormant. Unmounting made it
# unreachable, but a file that only needs one import line to become live is a
# standing invitation to whoever next needs a position stream. Clients post
# position over PUT /api/drivers/me, which is authenticated and role-gated.

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

# Push-notification device registration.
router.include_router(devices_router)
# Runtime settings (superuser only) - change dispatch behaviour without a deploy.
router.include_router(admin_settings_router)
router.include_router(admin_users_router)

# Debug endpoint
@router.get("/ping", tags=["debug"])
async def ping() -> dict:
    return {"msg": "pong"}
