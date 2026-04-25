"""Vercel-native FastAPI application shell.

This module is the cloud-side backend for Guppy AI. It has NO dependency on
the local desktop runtime, voice hardware, Qt UI, or daemon.

Only pure AI inference and supporting auth surfaces live here.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth_refresh import router as auth_refresh_router
from api.routes.auth_token import router as auth_token_router
from api.routes.catalog import router as catalog_router
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.history import router as history_router
from api.routes.settings import router as settings_router
from api.routes.workspaces import router as workspaces_router

logger = logging.getLogger(__name__)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("GUPPY_CORS_ORIGINS", "*").split(",")
    if o.strip()
]

_APP_VERSION = "1.0.0"
_STARTUP_TIME = time.time()


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Startup probe — log AI provider availability."""
    providers: list[str] = []
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")

    if providers:
        logger.info("BE-TR01 startup: AI providers available: %s", providers)
    else:
        logger.warning("BE-TR01 startup: no AI provider keys configured")

    yield
    logger.info("BE-TR01 shutdown")


app = FastAPI(
    title="Guppy AI Backend",
    version=_APP_VERSION,
    description="Cloud AI inference backend — schema_version 1",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next) -> Response:
    """Attach a request ID to every response for tracing."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


app.include_router(auth_token_router, prefix="/auth/token", tags=["auth"])
app.include_router(auth_refresh_router, prefix="/auth/refresh", tags=["auth"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])  # alias for web UI
app.include_router(health_router, tags=["health"])
app.include_router(catalog_router)
app.include_router(workspaces_router)
app.include_router(settings_router)
app.include_router(history_router)


# ---------------------------------------------------------------------------
# Auth extras — signup / verify (cloud stubs: return tokens directly)
# ---------------------------------------------------------------------------
_auth_extras = APIRouter(tags=["auth"])


@_auth_extras.post("/auth/signup")
async def auth_signup(request: Request) -> dict:
    body = await request.json()
    token = str(uuid.uuid4())
    return {"access_token": token, "token_type": "bearer", "email": body.get("email", "")}


@_auth_extras.post("/auth/verify")
async def auth_verify(request: Request) -> dict:
    return {"ok": True, "verified": True}


app.include_router(_auth_extras)


# ---------------------------------------------------------------------------
# Desktop-only stubs — return graceful empty / 503 rather than 404
# ---------------------------------------------------------------------------
_desktop_stubs = APIRouter(tags=["desktop-stubs"])


@_desktop_stubs.get("/logs/recent")
async def logs_recent() -> dict:
    return {"logs": [], "total": 0}


@_desktop_stubs.get("/metrics")
async def metrics() -> dict:
    return {"uptime_seconds": round(time.time() - _STARTUP_TIME, 1), "requests": 0}


@_desktop_stubs.get("/telemetry/report")
async def telemetry_report() -> dict:
    return {"events": [], "total": 0}


@_desktop_stubs.get("/repair-token/refresh")
async def repair_token_refresh() -> dict:
    return {"available": False, "reason": "desktop-only"}


@_desktop_stubs.post("/api/models/pull")
async def models_pull() -> dict:
    return {"available": False, "reason": "desktop-only"}


@_desktop_stubs.post("/api/voices/test")
async def voices_test() -> dict:
    return {"available": False, "reason": "desktop-only"}


app.include_router(_desktop_stubs)
