from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api._server_fragment_models import TokenResponse, TurnstileToken
from src.guppy.api.server_context import ServerContext


def build_core_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root():
        return {"message": "Guppy API is running", "status": "healthy"}

    @router.get("/metrics")
    async def get_metrics(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        with ctx.api_metrics_lock:
            requests_total = ctx.api_metrics["requests_total"]
            avg_latency_ms = (ctx.api_metrics["latency_total_ms"] / requests_total) if requests_total else 0.0
            payload = {
                "started_at": ctx.api_metrics["started_at"],
                "requests_total": requests_total,
                "errors_total": ctx.api_metrics["errors_total"],
                "slow_requests": ctx.api_metrics["slow_requests"],
                "average_latency_ms": round(avg_latency_ms, 2),
                "path_counts": dict(ctx.api_metrics["path_counts"]),
                "status_counts": dict(ctx.api_metrics["status_counts"]),
            }

        if ctx.guppy_core_available and hasattr(ctx.core, "get_tool_health_snapshot"):
            try:
                payload["tool_runner"] = ctx.core.get_tool_health_snapshot()
            except Exception as e:
                payload["tool_runner_error"] = str(e)
        return payload

    @router.post("/auth/verify", response_model=TokenResponse)
    async def auth_verify_turnstile_token(
        request: TurnstileToken,
        _auth_limiter: str = Depends(ctx.require_auth_rate_limit),
    ):
        if not await ctx.verify_turnstile_token_auth(request.token):
            raise HTTPException(status_code=400, detail="Invalid Turnstile token")

        access_token = ctx.create_access_token(data={"sub": "guppy_user"})
        return TokenResponse(
            access_token=access_token,
            expires_in=ctx.access_token_expire_minutes * 60,
        )

    @router.get("/auth/self-check")
    async def auth_self_check(user_id: str = Depends(ctx.require_rate_limit)):
        return {
            "ok": True,
            "user_id": user_id,
            "mode": "dev" if ctx.dev_mode else "strict",
        }

    @router.get("/status")
    async def get_status(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id

        if not ctx.guppy_core_available:
            return {"status": "error", "message": "Guppy core not available"}

        try:
            now = time.time()
            if ctx.status_cache["payload"] is not None and ctx.status_cache["expires_at"] > now:
                return ctx.status_cache["payload"]

            context = {}
            if ctx.status_include_window_context and ctx.guppy_daemon_available:
                try:
                    context = await asyncio.wait_for(
                        asyncio.to_thread(ctx.read_window_context),
                        timeout=0.2,
                    )
                except Exception:
                    context = {}

            voice_tts = ctx.voice_tts_backend if ctx.guppy_voice_available else "none"
            voice_stt = ctx.voice_stt_backend if ctx.guppy_voice_available else "none"
            voice_status = {
                "available": ctx.guppy_voice_available,
                "tts_backend": voice_tts,
                "stt_backend": voice_stt,
                "details": ctx.voice_backend_details if ctx.guppy_voice_available else [],
            }

            payload = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": context,
                "memory_available": ctx.guppy_memory_available,
                "voice_available": ctx.guppy_voice_available,
                "voice_tts_backend": voice_tts,
                "voice_stt_backend": voice_stt,
                "voice_status": voice_status,
                "daemon_available": ctx.guppy_daemon_available,
                "daemon_runtime": ctx.read_daemon_runtime_status(),
                "startup_readiness": ctx.startup_readiness_cached_or_unknown(),
                "local_runtime": ctx.build_local_runtime_status(),
                "resource_envelope": ctx.read_resource_envelope_status(),
            }
            ctx.status_cache["payload"] = payload
            ctx.status_cache["expires_at"] = now + ctx.status_cache_ttl_seconds
            return payload
        except Exception as e:
            ctx.logger.error(f"Status check failed: {e}")
            ctx.log_session_event("api", "status_failed", level="error", error=str(e))
            return {"status": "error", "message": str(e)}

    @router.get("/startup/check")
    async def startup_check(deep: bool = False, user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        if deep:
            snapshot = await asyncio.to_thread(ctx.startup_readiness_snapshot)
        else:
            snapshot = ctx.startup_readiness_cached_or_unknown()
            if snapshot.get("overall") == "UNKNOWN" or ctx.startup_readiness_cache_expired():
                ctx.trigger_startup_readiness_refresh()
        ctx.log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
        return snapshot

    return router
