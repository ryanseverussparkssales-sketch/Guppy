"""Runtime readiness fetch and mapping helpers for launcher/API seams."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .contracts import RuntimeHealthSnapshot, StartupReadinessSnapshot


def summarize_startup_readiness(
    snapshot: Mapping[str, Any] | StartupReadinessSnapshot | None,
) -> str:
    typed = (
        snapshot
        if isinstance(snapshot, StartupReadinessSnapshot)
        else StartupReadinessSnapshot.from_mapping(snapshot)
    )
    parts: list[str] = []
    if typed.overall and typed.overall != "UNKNOWN":
        parts.append(f"startup {typed.overall.lower()}")
    local_runtime = typed.local_runtime
    if local_runtime.state and local_runtime.state != "UNKNOWN":
        parts.append(f"local runtime {local_runtime.state.lower()}")
    if local_runtime.chat_ready:
        parts.append("chat ready")
    elif local_runtime.chat_state and local_runtime.chat_state != "UNKNOWN":
        parts.append(f"chat {local_runtime.chat_state.lower()}")
    if local_runtime.chat_detail:
        parts.append(local_runtime.chat_detail)
    deduped: list[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    return " | ".join(deduped)


def fetch_startup_readiness(
    fetch_json: Callable[..., Any],
    *,
    timeout: float = 1.5,
    deep: bool = False,
    unauthorized_error: Callable[[str], bool] | None = None,
) -> tuple[str, str, dict[str, object]]:
    path = "/startup/check?deep=true" if deep else "/startup/check"
    try:
        payload = fetch_json(
            path,
            method="GET",
            timeout=timeout,
            retry_auth_on_401=True,
            auth_retry_reason="startup_check",
        )
        snapshot = dict(payload) if isinstance(payload, Mapping) else {}
        return "reachable", summarize_startup_readiness(snapshot), snapshot
    except Exception as exc:
        detail = str(exc)
        if "404" in detail:
            try:
                fallback = fetch_json(
                    "/status",
                    method="GET",
                    timeout=timeout,
                    retry_auth_on_401=True,
                    auth_retry_reason="startup_check_status_fallback",
                )
                startup = fallback.get("startup_readiness", {}) if isinstance(fallback, Mapping) else {}
                snapshot = dict(startup) if isinstance(startup, Mapping) else {}
                return "reachable", summarize_startup_readiness(snapshot), snapshot
            except Exception as fallback_error:
                detail = str(fallback_error)
        if unauthorized_error is not None and unauthorized_error(detail):
            return "auth_failed", detail, {}
        return "unreachable", detail, {}


def build_runtime_health_snapshot(
    api_status: Mapping[str, Any] | None,
    launcher_status: Mapping[str, Any] | None = None,
    *,
    voice_tts_backend: str = "",
    voice_stt_backend: str = "",
) -> RuntimeHealthSnapshot:
    api_payload = dict(api_status) if isinstance(api_status, Mapping) else {}
    launcher_payload = dict(launcher_status) if isinstance(launcher_status, Mapping) else {}
    startup = api_payload.get("startup_readiness", launcher_payload.get("startup_readiness", {}))
    local_runtime = api_payload.get("local_runtime", {})
    payload = {
        "startup_readiness": startup if isinstance(startup, Mapping) else {},
        "local_runtime": local_runtime if isinstance(local_runtime, Mapping) else {},
        "resource_envelope": launcher_payload.get("resource_envelope", {}),
        "voice_status": api_payload.get("voice_status", {}),
        "voice_tts_backend": voice_tts_backend or str(api_payload.get("voice_tts_backend", "") or ""),
        "voice_stt_backend": voice_stt_backend or str(api_payload.get("voice_stt_backend", "") or ""),
        "daemon_available": bool(api_payload.get("daemon_available", False)),
    }
    return RuntimeHealthSnapshot.from_mapping(payload)


def build_runtime_health_view_payload(
    runtime_health: RuntimeHealthSnapshot,
    *,
    status: str = "",
    voice_binding: str = "",
    route_evidence: str = "",
) -> dict[str, object]:
    return {
        "status": str(status or runtime_health.overall or "unknown"),
        "startup_readiness": runtime_health.startup_readiness.metadata,
        "local_runtime": runtime_health.local_runtime.metadata,
        "voice_tts_backend": runtime_health.voice_tts_backend,
        "voice_stt_backend": runtime_health.voice_stt_backend,
        "voice_binding": str(voice_binding or "").strip(),
        "route_evidence": str(route_evidence or "").strip(),
        "resource_envelope": dict(runtime_health.resource_envelope),
    }
