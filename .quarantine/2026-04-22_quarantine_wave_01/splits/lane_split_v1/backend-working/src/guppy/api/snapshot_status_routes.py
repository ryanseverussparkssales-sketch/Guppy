from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import Depends, HTTPException


def build_status_support_context(owner: Any) -> SimpleNamespace:
    return owner.snapshot_status_context_support.build_status_support_context(
        memory_available=owner.GUPPY_MEMORY_AVAILABLE,
        voice_available=owner.GUPPY_VOICE_AVAILABLE,
        daemon_available=owner.GUPPY_DAEMON_AVAILABLE,
        voice_tts_backend=owner._VOICE_TTS_BACKEND,
        voice_stt_backend=owner._VOICE_STT_BACKEND,
        voice_backend_details=owner._VOICE_BACKEND_DETAILS,
        read_daemon_runtime_status=owner._read_daemon_runtime_status,
        startup_readiness_cached_or_unknown=owner._startup_readiness_cached_or_unknown,
        build_local_runtime_status=owner._build_local_runtime_status,
        read_resource_envelope_status=owner._read_resource_envelope_status,
        startup_readiness_snapshot=owner._startup_readiness_snapshot,
        startup_readiness_cache_expired=owner._startup_readiness_cache_expired,
        trigger_startup_readiness_refresh=owner._trigger_startup_readiness_refresh,
        guppy_core_available=owner.GUPPY_CORE_AVAILABLE,
        status_cache=owner._status_cache,
        status_cache_ttl_seconds=owner.STATUS_CACHE_TTL_SECONDS,
        status_include_window_context=owner.STATUS_INCLUDE_WINDOW_CONTEXT,
        read_window_context=owner._read_window_context,
    )


def register_status_routes(app: Any, owner: Any) -> None:
    @app.get("/metrics")
    async def get_metrics(user_id: str = Depends(owner.require_rate_limit)):
        del user_id
        return owner.snapshot_status_context_support.build_metrics_payload(
            api_metrics=owner._api_metrics,
            api_metrics_lock=owner._api_metrics_lock,
            guppy_core_available=owner.GUPPY_CORE_AVAILABLE,
            core_module=owner.core,
        )

    @app.post("/auth/verify", response_model=owner.TokenResponse)
    async def auth_verify_turnstile_token(
        request: owner.TurnstileToken,
        _auth_limiter: str = Depends(owner.require_auth_rate_limit),
    ):
        if not await owner.verify_turnstile_token_auth(request.token):
            raise HTTPException(status_code=400, detail="Invalid Turnstile token")

        access_token = owner.create_access_token(data={"sub": "guppy_user"})
        return owner.TokenResponse(
            access_token=access_token,
            expires_in=owner.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @app.get("/auth/self-check")
    async def auth_self_check(user_id: str = Depends(owner.require_rate_limit)):
        del user_id
        return {
            "ok": True,
            "user_id": user_id,
            "mode": "dev" if owner.DEV_MODE else "strict",
        }

    @app.get("/status")
    async def get_status(user_id: str = Depends(owner.require_rate_limit)):
        del user_id
        try:
            return await owner.build_status_response(build_status_support_context(owner))
        except Exception as exc:
            owner.logger.error(f"Status check failed: {exc}")
            owner.log_session_event("api", "status_failed", level="error", error=str(exc))
            return {"status": "error", "message": str(exc)}

    @app.get("/startup/check")
    async def startup_check(deep: bool = False, user_id: str = Depends(owner.require_rate_limit)):
        del user_id
        snapshot = await owner.build_startup_check_response(build_status_support_context(owner), deep=deep)
        owner.log_session_event("api", "startup_check", level="info", overall=snapshot.get("overall", "unknown"))
        return snapshot