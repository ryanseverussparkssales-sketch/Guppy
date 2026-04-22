"""Health probe routes — GET /health."""
from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter()

_SCHEMA_VERSION = 1


@router.get("/health")
async def health() -> dict:
    """Liveness probe. Returns AI provider availability flags."""
    return {
        "status": "ok",
        "schema_version": _SCHEMA_VERSION,
        "providers": {
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        },
    }
