from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from src.guppy.runtime_application import (
    RuntimeHealthSnapshot,
    build_runtime_health_snapshot,
    build_runtime_health_view_payload,
)

from .instance_manager_presenter import workspace_role_label


@dataclass(frozen=True, slots=True)
class LauncherStatusPollSnapshot:
    data: dict[str, Any]
    api_status: dict[str, object]
    guppy_online: bool
    guppy_load: object
    background_summary: str
    runtime_health: RuntimeHealthSnapshot
    settings_status_snapshot: dict[str, object]


def fetch_api_status(
    fetch_json: Callable[..., Any],
    *,
    timeout: float = 0.75,
) -> dict[str, object]:
    try:
        payload = fetch_json(
            "/status",
            method="GET",
            timeout=timeout,
            retry_auth_on_401=True,
            auth_retry_reason="status_poll",
        )
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def build_launcher_status_poll_snapshot(
    *,
    launcher_status: Mapping[str, Any] | None,
    api_status: Mapping[str, Any] | None,
    environment: Mapping[str, str] | None,
    active_instance_name: str,
    last_instance_snapshot: Mapping[str, Any] | None,
    embedded_online: Iterable[str] = (),
    fallback_last_query: str = "",
    voice_summary: str = "",
    route_evidence: str = "",
) -> LauncherStatusPollSnapshot:
    launcher_payload = dict(launcher_status) if isinstance(launcher_status, Mapping) else {}
    api_payload = dict(api_status) if isinstance(api_status, Mapping) else {}
    env = environment if isinstance(environment, Mapping) else {}

    embedded_names = {str(item).strip().lower() for item in embedded_online}
    launcher_online = bool(launcher_payload.get("guppy_online", False)) or ("guppy" in embedded_names)
    data = {
        "guppy_online": launcher_online,
        "profile": launcher_payload.get("runtime_profile", env.get("GUPPY_RUNTIME_PROFILE", "standard")),
        "daemon": bool(launcher_payload.get("daemon_running", False)) or launcher_online,
        "voice_engine": launcher_payload.get("tts_engine", env.get("GUPPY_TTS_ENGINE", "edge")),
        "model": launcher_payload.get("active_model", env.get("GUPPY_LOCAL_MODEL", "guppy")),
        "wake_word": launcher_payload.get("wake_word", env.get("GUPPY_WAKE_WORD_ENABLED", "false")),
        "latency": launcher_payload.get("last_latency_ms", "—"),
        "last_query": launcher_payload.get("last_query", "—"),
    }
    if data["last_query"] in {"", "—"} and fallback_last_query:
        data["last_query"] = fallback_last_query
    data["status"] = str(api_payload.get("status", "unknown") or "unknown")

    background_summary = _background_summary(
        active_instance_name=active_instance_name,
        last_instance_snapshot=last_instance_snapshot,
        guppy_online=launcher_online,
    )
    runtime_health = build_runtime_health_snapshot(
        api_payload,
        launcher_payload,
        voice_tts_backend=str(data.get("voice_engine", "edge") or "edge"),
        voice_stt_backend=str(launcher_payload.get("stt_backend", "unknown") or "unknown"),
    )
    settings_status_snapshot = build_runtime_health_view_payload(
        runtime_health,
        status=str(data.get("status", "unknown") or "unknown"),
        voice_binding=str(voice_summary or "").strip(),
        route_evidence=str(route_evidence or "").strip(),
    )
    return LauncherStatusPollSnapshot(
        data=data,
        api_status=api_payload,
        guppy_online=launcher_online,
        guppy_load=launcher_payload.get("cpu_load_pct", 0),
        background_summary=background_summary,
        runtime_health=runtime_health,
        settings_status_snapshot=settings_status_snapshot,
    )


def _background_summary(
    *,
    active_instance_name: str,
    last_instance_snapshot: Mapping[str, Any] | None,
    guppy_online: bool,
) -> str:
    snapshot = dict(last_instance_snapshot) if isinstance(last_instance_snapshot, Mapping) else {}
    items = snapshot.get("instances", [])
    active_payload = next(
        (
            item
            for item in items
            if isinstance(item, Mapping) and str(item.get("name", "")).strip() == active_instance_name
        ),
        {},
    )
    active_type = str((active_payload or {}).get("type", "user_instance") or "user_instance")
    role = workspace_role_label(active_type)
    return f"{role.upper()} {'LIVE' if guppy_online else 'OFFLINE'}"
