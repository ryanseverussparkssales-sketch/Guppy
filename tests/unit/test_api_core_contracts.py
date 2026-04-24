from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from src.guppy.api import server as guppy_api


@contextmanager
def _rate_limit_override() -> Any:
    app = guppy_api.app
    app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "contract-user"
    try:
        yield app
    finally:
        app.dependency_overrides.pop(guppy_api.require_rate_limit, None)


@contextmanager
def _seed_status_cache(payload: dict[str, Any]) -> Any:
    cache = guppy_api._server_context.status_cache
    original_payload = cache.get("payload")
    original_expires_at = cache.get("expires_at", 0.0)
    try:
        cache["payload"] = payload
        cache["expires_at"] = time.time() + 30.0
        yield
    finally:
        cache["payload"] = original_payload
        cache["expires_at"] = original_expires_at


@contextmanager
def _seed_startup_check_cache(payload: dict[str, Any]) -> Any:
    cache = guppy_api._runtime_state.startup_check_cache
    original_payload = cache.get("payload")
    original_expires_at = cache.get("expires_at", 0.0)
    try:
        cache["payload"] = payload
        cache["expires_at"] = time.time() + 30.0
        yield
    finally:
        cache["payload"] = original_payload
        cache["expires_at"] = original_expires_at


def test_contract_get_root_baseline_fields() -> None:
    with _rate_limit_override() as app:
        client = TestClient(app)
        response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("message"), str)
    assert isinstance(payload.get("status"), str)


def test_contract_get_status_baseline_fields() -> None:
    cached_status = {
        "status": "healthy",
        "timestamp": "2026-04-21T00:00:00+00:00",
        "context": {"workspace": "contract-tests"},
        "memory_available": True,
        "voice_available": True,
        "voice_tts_backend": "kokoro",
        "voice_stt_backend": "whisper",
        "voice_status": {
            "available": True,
            "tts_backend": "kokoro",
            "stt_backend": "whisper",
            "details": ["kokoro local", "whisper local"],
        },
        "daemon_available": True,
        "daemon_runtime": {"state": "READY", "detail": "daemon online", "available": True},
        "startup_readiness": {
            "overall": "READY",
            "checks": {"auth": {"state": "READY", "detail": "strict auth secrets configured"}},
        },
        "local_runtime": {
            "state": "READY",
            "backend": "ollama",
            "chat_ready": True,
            "chat_state": "READY",
            "chat_detail": "chat lane warmed",
        },
        "resource_envelope": {"cpu": "steady"},
    }

    with _rate_limit_override() as app, _seed_status_cache(cached_status):
        client = TestClient(app)
        response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("status"), str)
    assert isinstance(payload.get("timestamp"), str)
    assert isinstance(payload.get("context"), dict)
    assert isinstance(payload.get("memory_available"), bool)
    assert isinstance(payload.get("voice_available"), bool)
    assert isinstance(payload.get("daemon_available"), bool)
    assert isinstance(payload.get("startup_readiness"), dict)
    assert isinstance(payload.get("local_runtime"), dict)
    assert isinstance(payload.get("resource_envelope"), dict)


def test_contract_get_startup_check_baseline_fields() -> None:
    cached_startup = {
        "overall": "READY",
        "checks": {
            "auth": {"state": "READY", "detail": "strict auth secrets configured"},
            "daemon": {"state": "READY", "detail": "daemon online"},
            "local_runtime": {"state": "READY", "detail": "local runtime warmed"},
        },
    }

    with _rate_limit_override() as app, _seed_startup_check_cache(cached_startup):
        client = TestClient(app)
        response = client.get("/startup/check")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("overall"), str)
    assert isinstance(payload.get("checks"), dict)
    checks = payload["checks"]
    assert isinstance(checks.get("auth"), dict)
    assert isinstance(checks["auth"].get("state"), str)
    assert isinstance(checks["auth"].get("detail"), str)


def test_contract_post_chat_error_envelope_shape() -> None:
    with _rate_limit_override() as app:
        client = TestClient(app)
        response = client.post("/chat", json={})

    assert response.status_code >= 400
    payload = response.json()
    assert isinstance(payload, dict)
    assert "detail" in payload

    detail = payload["detail"]
    assert isinstance(detail, (list, dict, str))
    if isinstance(detail, list):
        assert detail
        first_error = detail[0]
        assert isinstance(first_error, dict)
        assert isinstance(first_error.get("loc"), list)
        assert isinstance(first_error.get("msg"), str)
        assert isinstance(first_error.get("type"), str)
    elif isinstance(detail, dict):
        assert isinstance(detail.get("message"), str)
        assert isinstance(detail.get("code"), str)
    else:
        assert detail.strip() != ""