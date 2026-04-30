"""Model lifecycle manager — Tranche C.

Provides:
- build_model_health_router()  →  GET /api/model-health
- Role-to-backend mapping using model_roles.py

The actual auto-start and watchdog threads live in routes_backends.py
(see _run_auto_starts and _run_watchdog).  This module is a clean API
layer on top: it reads live port status and maps it back to role names.
"""
from __future__ import annotations

import socket
import time
import logging
from typing import Literal

from fastapi import APIRouter

from src.guppy.api.server_context import ServerContext
from src.guppy.model_roles import (
    MODEL_ROLES,
    ALWAYS_ON_ROLES,
    resolve_role,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Port map — backend key → port (mirrors routes_backends._LLAMACPP_CONFIG)
# Kept here as a lightweight read-only copy so we don't create a circular dep.
# ---------------------------------------------------------------------------

_BACKEND_PORTS: dict[str, int] = {
    "llamacpp-gemma":    8080,
    "llamacpp-pepe":     8082,
    "llamacpp-qwen3":    8083,
    "llamacpp-minicpm":  8084,
    "llamacpp-dispatch": 8085,
    "llamacpp-hermes4":  8086,
    "llamacpp-hermes3":  8087,
    "llamacpp-rocinante":8088,
    "llamacpp-xlam":     8089,
    "llamacpp-chat":     8090,
    "llamacpp-phi4-mini":8091,
}

ModelStatus = Literal["warm", "starting", "offline"]


def _port_alive(port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_latency_ms(port: int) -> float | None:
    """Return TCP connect latency in ms, or None if unreachable."""
    t0 = time.monotonic()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            pass
        return round((time.monotonic() - t0) * 1000, 1)
    except OSError:
        return None


def get_model_health() -> dict[str, dict]:
    """Return health status for all registered roles.

    Response schema per role:
      {
        "backend":    "llamacpp-hermes3",
        "port":       8087,
        "status":     "warm" | "starting" | "offline",
        "latency_ms": 4.2 | null,
        "required":   true | false,
      }
    """
    results: dict[str, dict] = {}
    for role, backend in MODEL_ROLES.items():
        port = _BACKEND_PORTS.get(backend)
        if port is None:
            results[role] = {
                "backend": backend,
                "port": None,
                "status": "offline",
                "latency_ms": None,
                "required": role in ALWAYS_ON_ROLES,
            }
            continue
        latency = _probe_latency_ms(port)
        status: ModelStatus = "warm" if latency is not None else "offline"
        results[role] = {
            "backend": backend,
            "port": port,
            "status": status,
            "latency_ms": latency,
            "required": role in ALWAYS_ON_ROLES,
        }
    return results


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_model_health_router(ctx: ServerContext) -> APIRouter:  # noqa: ARG001
    router = APIRouter(prefix="/api", tags=["model-health"])

    @router.get("/model-health")
    async def get_health():
        """Return live health status for all model roles."""
        return get_model_health()

    return router
