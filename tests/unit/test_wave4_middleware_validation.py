"""Wave 4 — request ID middleware, input validation, /auth/refresh, /health upgrade."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

_TEST_SECRET = "wave4-test-secret-x"
_TEST_API_KEY = "wave4-test-api-key-x"


@contextmanager
def _client_ctx(extra_env: dict | None = None):
    """Client with JWT enforcement enabled (GUPPY_JWT_SECRET set)."""
    env = {"GUPPY_JWT_SECRET": _TEST_SECRET, "GUPPY_API_KEY": _TEST_API_KEY}
    if extra_env:
        env.update(extra_env)
    with patch.dict(os.environ, env):
        from api.app import app
        yield TestClient(app)


@contextmanager
def _noauth_client_ctx():
    """Client with JWT enforcement disabled (dev-bypass mode)."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": "", "GUPPY_API_KEY": ""}):
        from api.app import app
        yield TestClient(app)


# ── X-Request-ID middleware ───────────────────────────────────────────────────


def test_response_contains_request_id_header() -> None:
    with _client_ctx() as client:
        resp = client.get("/health")
    assert "x-request-id" in resp.headers


def test_request_id_echoed_when_provided() -> None:
    custom_id = "test-req-id-abc123"
    with _client_ctx() as client:
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("x-request-id") == custom_id


def test_request_id_generated_when_absent() -> None:
    with _client_ctx() as client:
        resp1 = client.get("/health")
        resp2 = client.get("/health")
    id1 = resp1.headers.get("x-request-id", "")
    id2 = resp2.headers.get("x-request-id", "")
    assert id1 and id2
    assert id1 != id2  # each request gets a unique ID


# ── /health upgrade ───────────────────────────────────────────────────────────


def test_health_returns_version() -> None:
    with _client_ctx() as client:
        resp = client.get("/health")
    body = resp.json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert body["version"] != ""


def test_health_returns_uptime() -> None:
    with _client_ctx() as client:
        resp = client.get("/health")
    body = resp.json()
    assert "uptime_seconds" in body
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0


# ── Input validation ──────────────────────────────────────────────────────────
# These use the noauth client so Pydantic validation fires before auth.


def test_chat_rejects_empty_message() -> None:
    with _noauth_client_ctx() as client:
        resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_rejects_message_over_4000_chars() -> None:
    with _noauth_client_ctx() as client:
        resp = client.post("/chat", json={"message": "x" * 4001})
    assert resp.status_code == 422


def test_chat_accepts_message_at_4000_chars() -> None:
    with _noauth_client_ctx() as client:
        resp = client.post("/chat", json={"message": "x" * 4000})
    assert resp.status_code == 200


def test_chat_rejects_history_over_50_items() -> None:
    history = [{"role": "user", "content": "hi"} for _ in range(51)]
    with _noauth_client_ctx() as client:
        resp = client.post("/chat", json={"message": "hello", "history": history})
    assert resp.status_code == 422


def test_chat_accepts_history_at_50_items() -> None:
    history = [{"role": "user", "content": "hi"} for _ in range(50)]
    with _noauth_client_ctx() as client:
        resp = client.post("/chat", json={"message": "hello", "history": history})
    assert resp.status_code == 200


# ── POST /auth/refresh ────────────────────────────────────────────────────────


def test_refresh_returns_new_valid_token() -> None:
    with _client_ctx() as client:
        from api.auth import create_access_token
        token = create_access_token("test-user")
        resp = client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["schema_version"] == 1
    assert len(body["access_token"]) > 20


def test_refresh_without_token_returns_401() -> None:
    with _client_ctx() as client:
        resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_refresh_with_invalid_token_returns_401() -> None:
    with _client_ctx() as client:
        resp = client.post(
            "/auth/refresh",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
    assert resp.status_code == 401
