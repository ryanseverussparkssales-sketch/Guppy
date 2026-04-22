"""Wave 2 — auth enforcement and rate-limit tests.

These run against the cloud FastAPI app with ``GUPPY_JWT_SECRET`` set so
that the auth dependency is fully active (not bypassed).
"""
from __future__ import annotations

import os
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────────

_TEST_SECRET = "test-secret-key-for-unit-tests-only"


def _make_token(sub: str = "user-1", expires_delta: timedelta | None = None) -> str:
    """Mint a real signed JWT using the test secret."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.auth import create_access_token

        return create_access_token(sub, expires_delta=expires_delta)


def _client_with_secret():
    """Return a TestClient with JWT enforcement active."""
    # Patch env before importing app so the auth dependency sees the secret.
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.app import app

        return TestClient(app, raise_server_exceptions=True)


# ── JWT enforcement ────────────────────────────────────────────────────────────


def test_chat_requires_bearer_when_secret_set() -> None:
    """POST /chat with no Authorization header → 401."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.app import app

        client = TestClient(app)
        resp = client.post("/chat", json={"message": "hello", "history": []})
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "auth_missing_bearer"


def test_chat_rejects_invalid_signature() -> None:
    """POST /chat with a JWT signed with wrong key → 401."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.auth import create_access_token

        bad_token = create_access_token.__wrapped__("user-1") if hasattr(
            create_access_token, "__wrapped__"
        ) else None

    # Mint a token with a *different* secret.
    from datetime import datetime, timezone
    from jose import jwt as _jwt

    forged = _jwt.encode(
        {"sub": "attacker", "iat": datetime.now(timezone.utc)},
        "wrong-secret",
        algorithm="HS256",
    )

    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.app import app

        client = TestClient(app)
        resp = client.post(
            "/chat",
            json={"message": "hello", "history": []},
            headers={"Authorization": f"Bearer {forged}"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "auth_token_invalid"


def test_chat_rejects_expired_token() -> None:
    """POST /chat with an expired JWT → 401 auth_token_expired."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.auth import create_access_token

        expired = create_access_token("user-1", expires_delta=timedelta(seconds=-1))

        from api.app import app

        client = TestClient(app)
        resp = client.post(
            "/chat",
            json={"message": "hello", "history": []},
            headers={"Authorization": f"Bearer {expired}"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "auth_token_expired"


def test_chat_accepts_valid_token() -> None:
    """POST /chat with a valid signed JWT → 200."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.auth import create_access_token
        from api.app import app

        token = create_access_token("user-1")
        client = TestClient(app)
        resp = client.post(
            "/chat",
            json={"message": "hello", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 1
    assert isinstance(body["reply"], str)


def test_stream_requires_bearer_when_secret_set() -> None:
    """POST /chat/stream with no Authorization header → 401."""
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from api.app import app

        client = TestClient(app)
        resp = client.post("/chat/stream", json={"message": "hi", "history": []})
    assert resp.status_code == 401


# ── Rate limiting ──────────────────────────────────────────────────────────────


def test_rate_limit_enforced_at_61st_request() -> None:
    """The 61st request from the same user within one minute → 429."""
    from api.auth import _rate_buckets, check_rate_limit

    # Isolate this user bucket.
    test_user = "__rate_test_user__"
    _rate_buckets.pop(test_user, None)

    # Fill the bucket to the limit (60 requests).
    for _ in range(60):
        check_rate_limit(test_user)

    # The 61st call must raise 429.
    with pytest.raises(Exception) as exc_info:
        check_rate_limit(test_user)

    # FastAPI HTTPException or starlette HTTPException — status_code 429.
    assert exc_info.value.status_code == 429

    # Cleanup.
    _rate_buckets.pop(test_user, None)


def test_rate_limit_resets_after_window() -> None:
    """After the window expires the counter resets and requests succeed."""
    from api.auth import _RATE_WINDOW_SEC, _rate_buckets, check_rate_limit

    test_user = "__rate_reset_user__"
    _rate_buckets.pop(test_user, None)

    # Inject 60 stale timestamps just outside the window.
    old_ts = time.monotonic() - _RATE_WINDOW_SEC - 1.0
    from collections import deque

    _rate_buckets[test_user] = deque([old_ts] * 60)

    # Should succeed — stale entries are evicted first.
    check_rate_limit(test_user)

    _rate_buckets.pop(test_user, None)
