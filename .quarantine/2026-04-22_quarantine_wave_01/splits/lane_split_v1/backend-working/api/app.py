"""Vercel-native FastAPI application shell.

This module is the cloud-side backend for Guppy AI. It has NO dependency on
the local desktop runtime, voice hardware, Qt UI, or daemon.

Only pure AI inference and supporting auth surfaces live here.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router

logger = logging.getLogger(__name__)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("GUPPY_CORS_ORIGINS", "*").split(",")
    if o.strip()
]


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
    version="1.0.0",
    description="Cloud AI inference backend — schema_version 1",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(health_router, tags=["health"])
