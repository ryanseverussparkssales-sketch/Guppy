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

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth_refresh import router as auth_refresh_router
from api.routes.auth_token import router as auth_token_router
from api.routes.chat import router as chat_router
from api.routes.health import router as health_router

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
app.include_router(health_router, tags=["health"])
