from __future__ import annotations

import asyncio
import time
from typing import Any

from src.guppy.api import services_runtime
from src.guppy.api.server_context import ServerContext


async def _read_optional_window_context(ctx: ServerContext) -> dict[str, Any]:
    if not ctx.status_include_window_context or not ctx.guppy_daemon_available:
        return {}
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(ctx.read_window_context),
            timeout=0.2,
        )
    except Exception:
        # Keep /status responsive even when watcher context polling stalls.
        return {}


async def build_status_response(ctx: ServerContext) -> dict[str, Any]:
    if not ctx.guppy_core_available:
        return {"status": "error", "message": "Guppy core not available"}

    now = time.time()
    cached = ctx.status_cache.get("payload")
    if cached is not None and ctx.status_cache.get("expires_at", 0.0) > now:
        return cached

    context = await _read_optional_window_context(ctx)
    payload = services_runtime.build_runtime_status_payload(
        ctx.owner,
        context=context,
    )
    ctx.status_cache["payload"] = payload
    ctx.status_cache["expires_at"] = now + ctx.status_cache_ttl_seconds
    return payload


async def build_startup_check_response(ctx: ServerContext, *, deep: bool = False) -> dict[str, Any]:
    if deep:
        return await asyncio.to_thread(services_runtime.startup_check_payload, ctx.owner, deep=True)
    return services_runtime.startup_check_payload(ctx.owner, deep=False)
