"""Async HTTP health probes for each Guppy service."""
from __future__ import annotations

import asyncio
import time
import logging
from typing import Optional

import httpx

from .service_config import SERVICES

logger = logging.getLogger(__name__)


async def check_service(service_name: str, timeout: float = 3.0) -> dict:
    cfg = SERVICES.get(service_name, {})
    health_url: Optional[str] = cfg.get("health_url")

    if not health_url:
        return {
            "name":       service_name,
            "health":     "unknown",
            "latency_ms": None,
            "detail":     "No health endpoint configured",
        }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(health_url)
            latency = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code < 400:
                return {"name": service_name, "health": "up",       "latency_ms": latency, "detail": f"HTTP {resp.status_code}"}
            return     {"name": service_name, "health": "degraded", "latency_ms": latency, "detail": f"HTTP {resp.status_code}"}
    except httpx.ConnectError:
        return {"name": service_name, "health": "down", "latency_ms": None, "detail": "Connection refused"}
    except httpx.TimeoutException:
        return {"name": service_name, "health": "down", "latency_ms": None, "detail": "Timeout"}
    except Exception as exc:
        return {"name": service_name, "health": "down", "latency_ms": None, "detail": str(exc)[:120]}


async def check_all(timeout: float = 3.0) -> list[dict]:
    tasks = [check_service(name, timeout) for name in SERVICES]
    return await asyncio.gather(*tasks)
