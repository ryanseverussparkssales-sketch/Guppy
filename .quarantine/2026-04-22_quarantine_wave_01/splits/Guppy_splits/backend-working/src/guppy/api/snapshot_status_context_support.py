from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def build_status_support_context(
    *,
    memory_available: bool,
    voice_available: bool,
    daemon_available: bool,
    voice_tts_backend: str,
    voice_stt_backend: str,
    voice_backend_details: list[str],
    read_daemon_runtime_status,
    startup_readiness_cached_or_unknown,
    build_local_runtime_status,
    read_resource_envelope_status,
    startup_readiness_snapshot,
    startup_readiness_cache_expired,
    trigger_startup_readiness_refresh,
    guppy_core_available: bool,
    status_cache: dict[str, Any],
    status_cache_ttl_seconds: float,
    status_include_window_context: bool,
    read_window_context,
) -> SimpleNamespace:
    return SimpleNamespace(
        owner=SimpleNamespace(
            GUPPY_MEMORY_AVAILABLE=memory_available,
            GUPPY_VOICE_AVAILABLE=voice_available,
            GUPPY_DAEMON_AVAILABLE=daemon_available,
            _VOICE_TTS_BACKEND=voice_tts_backend,
            _VOICE_STT_BACKEND=voice_stt_backend,
            _VOICE_BACKEND_DETAILS=voice_backend_details,
            _read_daemon_runtime_status=read_daemon_runtime_status,
            _startup_readiness_cached_or_unknown=startup_readiness_cached_or_unknown,
            _build_local_runtime_status=build_local_runtime_status,
            _read_resource_envelope_status=read_resource_envelope_status,
            _startup_readiness_snapshot=startup_readiness_snapshot,
            _startup_readiness_cache_expired=startup_readiness_cache_expired,
            _trigger_startup_readiness_refresh=trigger_startup_readiness_refresh,
        ),
        guppy_core_available=guppy_core_available,
        status_cache=status_cache,
        status_cache_ttl_seconds=status_cache_ttl_seconds,
        status_include_window_context=status_include_window_context,
        guppy_daemon_available=daemon_available,
        read_window_context=read_window_context,
    )


def build_metrics_payload(
    *,
    api_metrics: dict[str, Any],
    api_metrics_lock,
    guppy_core_available: bool,
    core_module: Any,
) -> dict[str, Any]:
    with api_metrics_lock:
        requests_total = api_metrics["requests_total"]
        avg_latency_ms = (api_metrics["latency_total_ms"] / requests_total) if requests_total else 0.0
        payload = {
            "started_at": api_metrics["started_at"],
            "requests_total": requests_total,
            "errors_total": api_metrics["errors_total"],
            "slow_requests": api_metrics["slow_requests"],
            "average_latency_ms": round(avg_latency_ms, 2),
            "path_counts": dict(api_metrics["path_counts"]),
            "status_counts": dict(api_metrics["status_counts"]),
        }

    if guppy_core_available and hasattr(core_module, "get_tool_health_snapshot"):
        try:
            payload["tool_runner"] = core_module.get_tool_health_snapshot()
        except Exception as exc:
            payload["tool_runner_error"] = str(exc)
    return payload
