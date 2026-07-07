"""FastAPI application entrypoint.

- CORS middleware (allow all origins for dev; tighten in prod)
- Includes the `api_router` where feature routers will be mounted
- Provides a simple health‑check endpoint (`GET /health`)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import router as api_router

app = FastAPI(title="Towing & Emergency Services API", version="0.1.0")

# Development CORS – replace with specific origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health", tags=["monitoring"])  # pragma: no cover – trivial
async def health_check() -> dict:
    """Return a tiny JSON confirming the service is alive."""
    return {"status": "ok"}
