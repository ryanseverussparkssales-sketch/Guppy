"""Settings and credentials API — manage API keys, preferences, provider selection.

GET  /api/settings              — get all user settings
GET  /api/settings/credentials  — get configured provider status (safe: no keys returned)
POST /api/settings/credentials  — store API credentials { provider: string, api_key: string }
DELETE /api/settings/credentials/{provider} — remove provider credentials
GET  /api/settings/provider     — get active provider
POST /api/settings/provider     — set active provider { provider: string }
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext
from utils.db_utils import open_db as _open_db

# ── Credential encryption ──────────────────────────────────────────────────────
# Keys are encrypted with Fernet using a key derived from the JWT secret so
# they are never stored in plaintext.  If cryptography is unavailable or the
# secret is missing, encryption is skipped with a warning (legacy behaviour).

import base64
import hashlib
import logging as _logging

_enc_log = _logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken as _InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False


def _get_fernet():
    if not _FERNET_AVAILABLE:
        return None
    try:
        from src.guppy.api.auth import SECRET_KEY
        secret = (SECRET_KEY or "").strip()
        if not secret:
            return None
        # Derive a 32-byte key from the JWT secret via SHA-256, then base64url-encode.
        derived = hashlib.sha256(secret.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)
    except Exception as exc:
        _enc_log.warning("Could not build Fernet key: %s — storing credentials unencrypted", exc)
        return None


def _encrypt_key(value: str) -> str:
    f = _get_fernet()
    if not f:
        return value
    return f.encrypt(value.encode()).decode()


def _decrypt_key(value: str) -> str:
    f = _get_fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        # Value is plaintext (pre-encryption migration) — return as-is and
        # the next write will store it encrypted.
        return value


class SettingsDB:
    """SQLite-based settings and credentials storage."""

    def __init__(self, db_path: str = "settings.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        schema = """
            CREATE TABLE IF NOT EXISTS credentials (
                provider TEXT PRIMARY KEY,
                api_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """
        with _open_db(self.db_path, schema_sql=schema) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO settings (key, value, updated_at)
                VALUES ('active_provider', 'local', ?)
                """,
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()

    def store_credential(self, provider: str, api_key: str) -> Dict[str, Any]:
        """Store API credentials for a provider (encrypted at rest)."""
        if not api_key.strip():
            raise ValueError("api_key cannot be empty")

        now = datetime.now(timezone.utc).isoformat()
        encrypted = _encrypt_key(api_key.strip())
        with _open_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO credentials (provider, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider, encrypted, now, now),
            )
            conn.commit()

        return {"provider": provider, "configured": True, "updated_at": now}

    def get_credential(self, provider: str) -> Optional[str]:
        """Get API key for a provider, decrypting if needed."""
        with _open_db(self.db_path) as conn:
            row = conn.execute("SELECT api_key FROM credentials WHERE provider = ?", (provider,)).fetchone()
            if not row:
                return None
            return _decrypt_key(row[0])

    def get_credentials_status(self) -> Dict[str, Any]:
        """Get credential status for all providers (safe: no keys returned)."""
        with _open_db(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT provider, updated_at FROM credentials").fetchall()

        configured = {r["provider"] for r in rows}
        all_providers = [
            "anthropic", "openai", "google", "cohere", "mistral",
            "elevenlabs", "deepgram", "hubspot", "quo",
        ]
        return {p: {"configured": p in configured} for p in all_providers}

    def delete_credential(self, provider: str) -> bool:
        """Delete credentials for a provider."""
        with _open_db(self.db_path) as conn:
            conn.execute("DELETE FROM credentials WHERE provider = ?", (provider,))
            conn.commit()
        return True

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value."""
        with _open_db(self.db_path) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_setting(self, key: str, value: str) -> Dict[str, Any]:
        """Set a setting value."""
        now = datetime.now(timezone.utc).isoformat()
        with _open_db(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, now),
            )
            conn.commit()
        return {"key": key, "value": value, "updated_at": now}

    def get_active_provider(self) -> str:
        """Get the currently active provider."""
        return self.get_setting("active_provider") or "local"

    def set_active_provider(self, provider: str) -> Dict[str, Any]:
        """Set the active provider."""
        valid_providers = ["local", "anthropic", "openai", "google", "cohere", "mistral"]
        if provider not in valid_providers:
            raise ValueError(f"invalid provider: {provider}")
        return self.set_setting("active_provider", provider)

    def get_model_params(self) -> Dict[str, Any]:
        """Get persisted model generation parameters."""
        try:
            temperature = float(self.get_setting("temperature") or 0.8)
        except (TypeError, ValueError):
            temperature = 0.8
        try:
            max_tokens = int(self.get_setting("max_tokens") or 4096)
        except (TypeError, ValueError):
            max_tokens = 4096
        return {"temperature": temperature, "max_tokens": max_tokens}

    def set_model_params(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> None:
        """Persist model generation parameters."""
        if temperature is not None:
            self.set_setting("temperature", str(float(temperature)))
        if max_tokens is not None:
            self.set_setting("max_tokens", str(int(max_tokens)))


# Global DB instance
_settings_db = SettingsDB()


def build_settings_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/settings")

    @router.get("")
    async def get_settings(user_id: str = Depends(ctx.require_rate_limit)):
        """Get all settings and credential status."""
        del user_id
        return {
            "active_provider": _settings_db.get_active_provider(),
            "credentials": _settings_db.get_credentials_status(),
            "model_params": _settings_db.get_model_params(),
        }

    @router.put("")
    async def update_settings(
        payload: Dict[str, Any],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Bulk-update settings (active_provider, model_params, credentials)."""
        del user_id
        if "active_provider" in payload:
            _settings_db.set_active_provider(payload["active_provider"])
        model_params = payload.get("model_params") or {}
        temperature = model_params.get("temperature") if isinstance(model_params, dict) else None
        max_tokens = model_params.get("max_tokens") if isinstance(model_params, dict) else None
        if temperature is not None or max_tokens is not None:
            _settings_db.set_model_params(
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
            )
        return {
            "active_provider": _settings_db.get_active_provider(),
            "credentials": _settings_db.get_credentials_status(),
            "model_params": _settings_db.get_model_params(),
        }

    @router.get("/credentials")
    async def get_credentials_status(user_id: str = Depends(ctx.require_rate_limit)):
        """Get credential configuration status (no keys exposed)."""
        del user_id
        return _settings_db.get_credentials_status()

    @router.post("/credentials")
    async def store_credential(
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Store API credentials."""
        del user_id
        provider = payload.get("provider", "").strip().lower()
        api_key = payload.get("api_key", "").strip()

        valid_providers = [
            "anthropic", "openai", "google", "cohere", "mistral",
            "elevenlabs", "deepgram", "hubspot", "quo",
        ]
        if provider not in valid_providers:
            raise HTTPException(status_code=400, detail=f"invalid provider: {provider}")

        if not api_key:
            raise HTTPException(status_code=400, detail="api_key required")

        try:
            result = _settings_db.store_credential(provider, api_key)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/credentials/{provider}")
    async def delete_credential(provider: str, user_id: str = Depends(ctx.require_rate_limit)):
        """Delete credentials for a provider."""
        del user_id
        _settings_db.delete_credential(provider)
        return {"deleted": provider}

    @router.get("/provider")
    async def get_provider(user_id: str = Depends(ctx.require_rate_limit)):
        """Get active provider."""
        del user_id
        return {"active_provider": _settings_db.get_active_provider()}

    @router.post("/provider")
    async def set_provider(
        payload: Dict[str, str],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Set active provider."""
        del user_id
        provider = payload.get("provider", "").strip().lower()
        if not provider:
            raise HTTPException(status_code=400, detail="provider required")

        try:
            result = _settings_db.set_active_provider(provider)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router
