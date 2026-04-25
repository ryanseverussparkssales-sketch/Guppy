"""Unit tests for auth.py pure-function layer.

Covers _is_placeholder_secret, create_access_token round-trip,
get_token_expiry, _is_localhost_request, and dev-mode bypass.
Integration-level tests (full HTTP stack) live in test_wave2_auth.py.
"""
from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest


_TEST_SECRET = "unit-test-secret-key-not-for-production"


# ── _is_placeholder_secret ─────────────────────────────────────────────────────

def test_placeholder_secret_empty():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import _is_placeholder_secret
        assert _is_placeholder_secret("") is True


def test_placeholder_secret_known_values():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import _is_placeholder_secret
        assert _is_placeholder_secret("your-secret-key-change-in-production") is True
        assert _is_placeholder_secret("changeme") is True
        assert _is_placeholder_secret("replace-me") is True


def test_placeholder_secret_real_value():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import _is_placeholder_secret
        assert _is_placeholder_secret("a-real-32-char-secret-0000000000") is False


# ── create_access_token + round-trip ──────────────────────────────────────────

def test_create_and_verify_token():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        import importlib, sys
        # Reload to pick up the patched env
        for mod in list(sys.modules):
            if "guppy.api.auth" in mod:
                importlib.reload(sys.modules[mod])
                break

        from src.guppy.api.auth import create_access_token, _verify_token_credentials
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token({"sub": "test_user"})
        assert isinstance(token, str) and len(token) > 10

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user_id = _verify_token_credentials(creds)
        assert user_id == "test_user"


def test_expired_token_raises():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import create_access_token, _verify_token_credentials
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        expired = create_access_token({"sub": "user"}, expires_delta=timedelta(seconds=-1))
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired)
        with pytest.raises(HTTPException) as exc:
            _verify_token_credentials(creds)
        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "auth_token_expired"


def test_invalid_signature_raises():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import _verify_token_credentials
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt as _jwt
        from datetime import datetime, timezone

        forged = _jwt.encode(
            {"sub": "attacker", "iat": datetime.now(timezone.utc)},
            "wrong-secret",
            algorithm="HS256",
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged)
        with pytest.raises(HTTPException) as exc:
            _verify_token_credentials(creds)
        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "auth_token_invalid"


# ── get_token_expiry ──────────────────────────────────────────────────────────

def test_get_token_expiry_returns_datetime():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import create_access_token, get_token_expiry
        from datetime import datetime

        token = create_access_token({"sub": "u"}, expires_delta=timedelta(hours=1))
        expiry = get_token_expiry(token)
        assert isinstance(expiry, datetime)


def test_get_token_expiry_garbage_returns_none():
    with patch.dict(os.environ, {"GUPPY_JWT_SECRET": _TEST_SECRET}):
        from src.guppy.api.auth import get_token_expiry

        assert get_token_expiry("not.a.token") is None


# ── _is_localhost_request ─────────────────────────────────────────────────────

def _mock_request(host: str, forwarded: str | None = None) -> MagicMock:
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = host
    headers = MagicMock()
    headers.get = lambda k, d=None: (
        forwarded if forwarded and k in ("X-Forwarded-For", "CF-Connecting-IP") else d
    )
    req.headers = headers
    return req


def test_localhost_127_is_local():
    from src.guppy.api.auth import _is_localhost_request
    assert _is_localhost_request(_mock_request("127.0.0.1")) is True


def test_localhost_ipv6_is_local():
    from src.guppy.api.auth import _is_localhost_request
    assert _is_localhost_request(_mock_request("::1")) is True


def test_external_ip_is_not_local():
    from src.guppy.api.auth import _is_localhost_request
    assert _is_localhost_request(_mock_request("203.0.113.5")) is False


def test_forwarded_loopback_is_not_local():
    from src.guppy.api.auth import _is_localhost_request
    req = _mock_request("127.0.0.1", forwarded="203.0.113.5")
    assert _is_localhost_request(req) is False


# ── Dev-mode bypass ───────────────────────────────────────────────────────────

def test_dev_mode_allows_no_credentials():
    import src.guppy.api.auth as _auth_mod
    with patch.object(_auth_mod, "DEV_MODE", True), \
         patch.object(_auth_mod, "SECRET_KEY", _TEST_SECRET):
        user_id = _auth_mod._verify_token_credentials(None)
        assert user_id == "dev-user"


def test_prod_mode_rejects_no_credentials():
    from fastapi import HTTPException
    import src.guppy.api.auth as _auth_mod
    with patch.object(_auth_mod, "DEV_MODE", False), \
         patch.object(_auth_mod, "SECRET_KEY", _TEST_SECRET):
        with pytest.raises(HTTPException) as exc:
            _auth_mod._verify_token_credentials(None)
        assert exc.value.status_code == 401
