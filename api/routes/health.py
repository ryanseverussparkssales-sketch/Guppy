"""Health probe routes — GET /health."""
from __future__ import annotations

import os
import time

from fastapi import APIRouter

router = APIRouter()

_SCHEMA_VERSION = 1
_VERSION = "1.0.0"
_STARTUP_TIME = time.time()


@router.get("/health")
async def health() -> dict:
    """Liveness probe. Returns AI provider availability, version, and uptime."""
    return {
        "status": "ok",
        "schema_version": _SCHEMA_VERSION,
        "version": _VERSION,
        "uptime_seconds": round(time.time() - _STARTUP_TIME, 1),
        "providers": {
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        },
    }
