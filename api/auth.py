"""Cloud-safe authentication — JWT verification, Turnstile, and rate limiting.

No imports from the local runtime (src.guppy.*, utils.*, etc.).
All config is read from environment variables.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_RATE_LIMIT_RPM = 60
_RATE_WINDOW_SEC = 60.0

_PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "replace-me",
    "your-secret-key-change-in-production",
    "your-turnstile-secret",
}


# ── Config helpers ─────────────────────────────────────────────────────────────

def _jwt_secret() -> str:
    return os.environ.get("GUPPY_JWT_SECRET", "").strip()


def _turnstile_secret() -> str:
    return os.environ.get("GUPPY_TURNSTILE_SECRET", "").strip()


def _is_placeholder(value: str) -> bool:
    return value.lower() in _PLACEHOLDER_VALUES


# ── JWT ────────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """FastAPI dependency — returns ``user_id`` from a valid JWT.

    When ``GUPPY_JWT_SECRET`` is not configured (dev/test), returns
    ``"dev-user"`` and logs a warning so callers know auth is bypassed.
    """
    secret = _jwt_secret()
    if _is_placeholder(secret):
        logger.warning("GUPPY_JWT_SECRET not set — auth bypassed (dev mode)")
        return "dev-user"

    if not credentials:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            detail={"code": "auth_missing_bearer", "message": "Authentication required"},
        )

    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[ALGORITHM])
        sub: str | None = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=401,
                detail={"code": "auth_invalid_payload", "message": "Token missing subject"},
            )
        return sub
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_token_expired", "message": "Token has expired"},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_token_invalid", "message": "Invalid token"},
        )


def create_access_token(sub: str, expires_delta: timedelta | None = None) -> str:
    """Mint a signed JWT. Requires ``GUPPY_JWT_SECRET`` to be set."""
    secret = _jwt_secret()
    if _is_placeholder(secret):
        raise RuntimeError("GUPPY_JWT_SECRET is not configured")
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode({"sub": sub, "iat": now, "exp": expire}, secret, algorithm=ALGORITHM)


# ── Turnstile ─────────────────────────────────────────────────────────────────

async def verify_turnstile(token: str) -> None:
    """Verify a Cloudflare Turnstile token.  Raises ``HTTP 403`` on rejection.

    When ``GUPPY_TURNSTILE_SECRET`` is not configured this is a no-op (dev
    mode) so local and test environments work without the widget.
    """
    secret = _turnstile_secret()
    if _is_placeholder(secret):
        logger.warning("GUPPY_TURNSTILE_SECRET not set — Turnstile skipped (dev mode)")
        return

    if not token or not token.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "turnstile_missing", "message": "Turnstile token required"},
        )

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(
                TURNSTILE_VERIFY_URL,
                data={"secret": secret, "response": token},
            )
            result = resp.json()
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.error("Turnstile request failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "turnstile_unavailable",
                    "message": "Could not verify Turnstile token",
                },
            )

    if not result.get("success"):
        raise HTTPException(
            status_code=403,
            detail={"code": "turnstile_rejected", "message": "Turnstile verification failed"},
        )


# ── Rate limiting ─────────────────────────────────────────────────────────────
# In-memory sliding-window per user. Each Vercel serverless instance has its
# own dictionary — for multi-instance enforcement replace with Redis.

_rate_buckets: dict[str, deque[float]] = {}


def check_rate_limit(user_id: str) -> None:
    """Enforce 60 req/min per user.  Raises ``HTTP 429`` when exceeded."""
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SEC
    bucket = _rate_buckets.setdefault(user_id, deque())

    # Evict timestamps outside the window.
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= _RATE_LIMIT_RPM:
        raise HTTPException(
            status_code=429,
            headers={"Retry-After": "60"},
            detail={
                "code": "rate_limit_exceeded",
                "message": f"Limit: {_RATE_LIMIT_RPM} requests per minute",
            },
        )

    bucket.append(now)
