"""Cloud API client — routes chat requests to the Guppy Vercel backend.

Handles JWT acquisition, token refresh, and chat requests over HTTPS.
This is the **only** file in the local runtime that is allowed to call the
cloud API surface.  All other modules must go through ``CloudChatClient``.

Environment variables
---------------------
GUPPY_CLOUD_URL      Base URL of the deployed backend, e.g.
                     ``https://guppy.vercel.app``.  Required for cloud routing.
GUPPY_API_KEY        API key used to exchange for a JWT via ``POST /auth/token``.
GUPPY_CLOUD_TIMEOUT  HTTP timeout in seconds (default: 20).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20.0
_TOKEN_REFRESH_MARGIN = 300  # seconds before expiry to proactively refresh


def _base_url() -> str:
    url = os.environ.get("GUPPY_CLOUD_URL", "").rstrip("/")
    if not url:
        raise EnvironmentError(
            "GUPPY_CLOUD_URL is not set.  Set it to the deployed backend base URL "
            "(e.g. https://guppy.vercel.app) to use cloud routing."
        )
    return url


def _timeout() -> float:
    raw = os.environ.get("GUPPY_CLOUD_TIMEOUT", "")
    try:
        return float(raw) if raw else _DEFAULT_TIMEOUT
    except ValueError:
        return _DEFAULT_TIMEOUT


class CloudChatClient:
    """Thread-safe HTTP client for the Guppy cloud backend.

    Manages JWT lifecycle (acquisition + proactive refresh) so callers can
    just call :meth:`chat` without worrying about auth.

    Usage::

        client = CloudChatClient()
        reply, model, latency_ms = client.chat("Hello!", history=[])
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_exp: float = 0.0  # Unix timestamp

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _acquire_token(self) -> str:
        """Exchange GUPPY_API_KEY for a JWT.  Raises on failure."""
        api_key = os.environ.get("GUPPY_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "GUPPY_API_KEY is not set.  Provide the cloud API key to authenticate."
            )
        url = f"{_base_url()}/auth/token"
        resp = httpx.post(
            url,
            json={"api_key": api_key},
            timeout=_timeout(),
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Cloud auth failed: {resp.status_code} {resp.text[:200]}"
            )
        body: dict[str, Any] = resp.json()
        token: str = body["access_token"]
        # Decode expiry from JWT payload without full verification (we trust our
        # own server) so we know when to refresh.
        try:
            import base64
            import json as _json

            payload_b64 = token.split(".")[1]
            # Pad to a multiple of 4 characters for base64 decoding
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            self._token_exp = float(payload.get("exp", 0))
        except Exception:
            # If we can't parse expiry, treat as 1-hour token
            self._token_exp = time.time() + 3600
        self._token = token
        logger.debug("Cloud JWT acquired; expires at %s", self._token_exp)
        return token

    def _refresh_token(self) -> str:
        """Exchange the current JWT for a fresh one via /auth/refresh."""
        assert self._token is not None
        url = f"{_base_url()}/auth/refresh"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=_timeout(),
        )
        if resp.status_code != 200:
            # Refresh failed — re-acquire from scratch
            logger.warning(
                "Cloud JWT refresh failed (%s); re-acquiring from API key.",
                resp.status_code,
            )
            return self._acquire_token()
        body: dict[str, Any] = resp.json()
        token: str = body["access_token"]
        try:
            import base64
            import json as _json

            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            self._token_exp = float(payload.get("exp", 0))
        except Exception:
            self._token_exp = time.time() + 3600
        self._token = token
        logger.debug("Cloud JWT refreshed; expires at %s", self._token_exp)
        return token

    def _get_valid_token(self) -> str:
        """Return a valid JWT, acquiring or refreshing as needed (thread-safe)."""
        with self._lock:
            now = time.time()
            if self._token is None:
                return self._acquire_token()
            if now >= self._token_exp - _TOKEN_REFRESH_MARGIN:
                return self._refresh_token()
            return self._token

    def invalidate_token(self) -> None:
        """Force re-acquisition on the next call (e.g. after a 401 response)."""
        with self._lock:
            self._token = None
            self._token_exp = 0.0

    # ── Chat ──────────────────────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        *,
        history: list[dict[str, str]] | None = None,
        mode: str | None = None,
        persona: str | None = None,
        turnstile_token: str | None = None,
        retried: bool = False,
    ) -> tuple[str, str, int]:
        """Send a chat message to the cloud backend.

        Parameters
        ----------
        message:
            The user's message text (1–4000 chars).
        history:
            Optional prior turns: ``[{"role": "user"|"assistant", "content": "..."}]``.
            Maximum 50 items.
        mode:
            One of ``"auto"``, ``"precise"``, ``"creative"`` (or ``None``).
        persona:
            One of ``"guppy"``, ``"merlin"`` (or ``None`` for default).
        turnstile_token:
            Cloudflare Turnstile token if available.
        retried:
            Internal flag — do not pass. Used to prevent infinite re-auth loops.

        Returns
        -------
        tuple[str, str, int]
            ``(reply_text, model_name, latency_ms)``
        """
        token = self._get_valid_token()
        payload: dict[str, Any] = {"message": message}
        if history:
            payload["history"] = history
        if mode:
            payload["mode"] = mode
        if persona:
            payload["persona"] = persona
        if turnstile_token:
            payload["turnstile_token"] = turnstile_token

        url = f"{_base_url()}/chat"
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=_timeout(),
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise RuntimeError(f"Cloud chat request failed: {exc}") from exc

        if resp.status_code == 401 and not retried:
            # Token was rejected — force re-auth and retry once
            logger.warning("Cloud 401 — invalidating token and retrying")
            self.invalidate_token()
            return self.chat(
                message,
                history=history,
                mode=mode,
                persona=persona,
                turnstile_token=turnstile_token,
                retried=True,
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Cloud chat error: {resp.status_code} {resp.text[:300]}"
            )

        body: dict[str, Any] = resp.json()
        reply: str = body.get("reply", "")
        model: str = body.get("model", "cloud")
        latency_ms: int = int(body.get("latency_ms", 0))
        return reply, model, latency_ms


# ── Module-level singleton ─────────────────────────────────────────────────────

_client: CloudChatClient | None = None
_client_lock = threading.Lock()


def get_cloud_client() -> CloudChatClient:
    """Return the module-level singleton ``CloudChatClient``."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = CloudChatClient()
    return _client


def cloud_chat(
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    mode: str | None = None,
    persona: str | None = None,
) -> tuple[str, str, int]:
    """Module-level convenience wrapper around the singleton client.

    Returns ``(reply_text, model_name, latency_ms)``.
    """
    return get_cloud_client().chat(message, history=history, mode=mode, persona=persona)
