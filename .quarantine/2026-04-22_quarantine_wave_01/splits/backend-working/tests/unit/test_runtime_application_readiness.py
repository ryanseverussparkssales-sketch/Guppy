from __future__ import annotations

from src.guppy.runtime_application import (
    build_local_bearer_token,
    build_runtime_health_snapshot,
    build_runtime_health_view_payload,
    fetch_startup_readiness,
    summarize_startup_readiness,
)


def test_summarize_startup_readiness_uses_typed_local_runtime_details() -> None:
    summary = summarize_startup_readiness(
        {
            "overall": "partial",
            "checks": {
                "local_runtime": {
                    "state": "READY",
                    "chat_ready": False,
                    "chat_state": "warming",
                    "chat_detail": "chat lane warming",
                }
            },
        }
    )

    assert summary == "startup partial | local runtime ready | chat warming | chat lane warming"


def test_fetch_startup_readiness_falls_back_to_status_payload() -> None:
    calls: list[str] = []

    def fake_fetch(path: str, **_kwargs):
        calls.append(path)
        if path == "/startup/check?deep=true":
            raise RuntimeError("404 not found")
        return {
            "startup_readiness": {
                "overall": "READY",
                "checks": {
                    "local_runtime": {
                        "state": "READY",
                        "chat_ready": True,
                    }
                },
            }
        }

    state, detail, snapshot = fetch_startup_readiness(fake_fetch, deep=True)

    assert calls == ["/startup/check?deep=true", "/status"]
    assert state == "reachable"
    assert detail == "startup ready | local runtime ready | chat ready"
    assert snapshot["overall"] == "READY"


def test_fetch_startup_readiness_reports_auth_failed_when_checker_matches() -> None:
    def fake_fetch(_path: str, **_kwargs):
        raise RuntimeError("401 unauthorized")

    state, detail, snapshot = fetch_startup_readiness(
        fake_fetch,
        unauthorized_error=lambda message: "401" in message,
    )

    assert state == "auth_failed"
    assert "401 unauthorized" in detail
    assert snapshot == {}


def test_build_local_bearer_token_prefers_environment_token() -> None:
    token, token_source = build_local_bearer_token(env={"GUPPY_API_BEARER_TOKEN": " env-token "})

    assert token == "env-token"
    assert token_source == "env_bearer_token"


def test_build_local_bearer_token_uses_runtime_jwt_helper_when_available() -> None:
    token, token_source = build_local_bearer_token(
        env={},
        create_token=lambda claims: f"token-for-{claims['sub']}",
    )

    assert token == "token-for-launcher_local"
    assert token_source == "jwt_helper"


def test_build_runtime_health_snapshot_preserves_startup_precedence_and_view_payload() -> None:
    runtime = build_runtime_health_snapshot(
        {
            "startup_readiness": {
                "overall": "missing",
                "checks": {
                    "local_runtime": {
                        "state": "partial",
                        "backend": "Ollama",
                        "chat_state": "warming",
                    }
                },
            },
            "local_runtime": {
                "state": "READY",
                "backend": "Ollama",
                "available_roles": ["fast", "complex", ""],
                "missing_roles": {"vision", "vision"},
            },
        },
        {"resource_envelope": {"state": "READY"}},
        voice_tts_backend="edge",
        voice_stt_backend="whisper",
    )
    payload = build_runtime_health_view_payload(
        runtime,
        status="degraded",
        voice_binding="EDGE TTS",
        route_evidence="route: local",
    )

    assert runtime.overall == "MISSING"
    assert runtime.local_runtime.state == "READY"
    assert runtime.local_runtime.backend == "ollama"
    assert runtime.local_runtime.available_roles == ("fast", "complex")
    assert runtime.local_runtime.missing_roles == ("vision",)
    assert payload["status"] == "degraded"
    assert payload["voice_binding"] == "EDGE TTS"
    assert payload["route_evidence"] == "route: local"
    assert payload["voice_tts_backend"] == "edge"
    assert payload["voice_stt_backend"] == "whisper"
