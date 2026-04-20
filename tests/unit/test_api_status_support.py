from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.guppy.api import services_runtime
from src.guppy.api.status_support import build_startup_check_response, build_status_response


def _fake_owner(**overrides):
    owner = SimpleNamespace(
        GUPPY_MEMORY_AVAILABLE=True,
        GUPPY_VOICE_AVAILABLE=True,
        GUPPY_DAEMON_AVAILABLE=True,
        _VOICE_TTS_BACKEND="kokoro",
        _VOICE_STT_BACKEND="whisper",
        _VOICE_BACKEND_DETAILS=["kokoro local", "whisper local"],
        _read_daemon_runtime_status=lambda: {"state": "READY", "detail": "daemon online", "available": True},
        _startup_readiness_cached_or_unknown=lambda: {"overall": "READY", "checks": {"auth": {"state": "READY"}}},
        _build_local_runtime_status=lambda: {"state": "READY", "backend": "ollama", "chat_ready": True},
        _read_resource_envelope_status=lambda: {"cpu": "steady"},
        _startup_readiness_snapshot=lambda: {"overall": "READY", "checks": {"daemon": {"state": "READY"}}},
        _startup_readiness_cache_expired=lambda: False,
        _trigger_startup_readiness_refresh=lambda: None,
    )
    for key, value in overrides.items():
        setattr(owner, key, value)
    return owner


def test_build_runtime_status_payload_keeps_launcher_visible_shape() -> None:
    owner = _fake_owner()

    payload = services_runtime.build_runtime_status_payload(
        owner,
        context={"workspace": "builder-collab"},
        timestamp="2026-04-19T21:00:00+00:00",
    )

    assert payload["status"] == "healthy"
    assert payload["timestamp"] == "2026-04-19T21:00:00+00:00"
    assert payload["context"] == {"workspace": "builder-collab"}
    assert payload["voice_tts_backend"] == "kokoro"
    assert payload["voice_stt_backend"] == "whisper"
    assert payload["voice_status"]["details"] == ["kokoro local", "whisper local"]
    assert payload["daemon_runtime"]["state"] == "READY"
    assert payload["startup_readiness"]["overall"] == "READY"
    assert payload["local_runtime"]["backend"] == "ollama"
    assert payload["resource_envelope"] == {"cpu": "steady"}


def test_build_runtime_status_payload_marks_partial_startup_as_degraded() -> None:
    owner = _fake_owner(
        _startup_readiness_cached_or_unknown=lambda: {"overall": "PARTIAL", "checks": {"auth": {"state": "READY"}}},
        _build_local_runtime_status=lambda: {"state": "PARTIAL", "backend": "lemonade", "chat_ready": False},
    )

    payload = services_runtime.build_runtime_status_payload(owner)

    assert payload["status"] == "degraded"


def test_build_status_response_uses_cache_before_reloading_window_context() -> None:
    calls: list[str] = []

    def read_window_context() -> dict[str, str]:
        calls.append("read")
        return {"workspace": "ops-lab"}

    owner = _fake_owner()
    ctx = SimpleNamespace(
        owner=owner,
        guppy_core_available=True,
        status_cache={"payload": None, "expires_at": 0.0},
        status_cache_ttl_seconds=30.0,
        status_include_window_context=True,
        guppy_daemon_available=True,
        read_window_context=read_window_context,
    )

    first = asyncio.run(build_status_response(ctx))
    second = asyncio.run(build_status_response(ctx))

    assert first["context"] == {"workspace": "ops-lab"}
    assert second == first
    assert calls == ["read"]


def test_build_startup_check_response_triggers_refresh_for_unknown_cached_snapshot() -> None:
    refreshed: list[str] = []
    owner = _fake_owner(
        _startup_readiness_cached_or_unknown=lambda: {"overall": "UNKNOWN", "checks": {}},
        _trigger_startup_readiness_refresh=lambda: refreshed.append("refresh"),
    )
    ctx = SimpleNamespace(owner=owner)

    payload = asyncio.run(build_startup_check_response(ctx, deep=False))

    assert payload["overall"] == "UNKNOWN"
    assert refreshed == ["refresh"]


def test_build_startup_check_response_uses_snapshot_for_deep_reads() -> None:
    owner = _fake_owner(
        _startup_readiness_snapshot=lambda: {"overall": "PARTIAL", "checks": {"local_runtime": {"state": "PARTIAL"}}}
    )
    ctx = SimpleNamespace(owner=owner)

    payload = asyncio.run(build_startup_check_response(ctx, deep=True))

    assert payload["overall"] == "PARTIAL"
    assert payload["checks"]["local_runtime"]["state"] == "PARTIAL"
