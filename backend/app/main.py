"""FastAPI application entrypoint.

- CORS middleware driven by ``CORS_ORIGINS`` (wide open for local dev only)
- Includes the `api_router` where feature routers are mounted
- Provides a simple health-check endpoint (`GET /health`)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import router as api_router
from .core.settings import settings

app = FastAPI(title="Towing & Emergency Services API", version="0.1.0")

# CORS. Set CORS_ORIGINS to your web origin(s) in any deployed environment, e.g.
# CORS_ORIGINS=https://app.example.com,https://admin.example.com
#
# Credentials are switched off whenever origins are wildcarded: the CORS spec
# forbids "*" together with credentials, and browsers reject the combination
# outright. This API authenticates with an Authorization: Bearer header rather
# than cookies, so nothing depends on credentialed cross-origin requests.
_origins = settings.cors_origin_list
_allow_credentials = _origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["monitoring"])  # pragma: no cover - trivial
async def health_check() -> dict:
    """Return a tiny JSON confirming the service is alive."""
    return {"status": "ok"}
