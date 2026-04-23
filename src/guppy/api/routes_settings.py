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
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.guppy.api.server_context import ServerContext


class SettingsDB:
    """SQLite-based settings and credentials storage."""

    def __init__(self, db_path: str = "settings.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            # Credentials table (encrypted in production - using plaintext for now)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    provider TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Settings table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Initialize default active provider
            conn.execute(
                """
                INSERT OR IGNORE INTO settings (key, value, updated_at)
                VALUES ('active_provider', 'local', ?)
                """,
                (datetime.utcnow().isoformat(),),
            )

            conn.commit()

    def store_credential(self, provider: str, api_key: str) -> Dict[str, Any]:
        """Store API credentials for a provider."""
        if not api_key.strip():
            raise ValueError("api_key cannot be empty")

        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO credentials (provider, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider, api_key.strip(), now, now),
            )
            conn.commit()

        return {"provider": provider, "configured": True, "updated_at": now}

    def get_credential(self, provider: str) -> Optional[str]:
        """Get API key for a provider (returns actual key, don't expose to frontend)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT api_key FROM credentials WHERE provider = ?", (provider,)).fetchone()
            return row[0] if row else None

    def get_credentials_status(self) -> Dict[str, Any]:
        """Get credential status for all providers (safe: no keys returned)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT provider, updated_at FROM credentials").fetchall()

        return {
            "anthropic": {"configured": any(r["provider"] == "anthropic" for r in rows)},
            "openai": {"configured": any(r["provider"] == "openai" for r in rows)},
            "google": {"configured": any(r["provider"] == "google" for r in rows)},
        }

    def delete_credential(self, provider: str) -> bool:
        """Delete credentials for a provider."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM credentials WHERE provider = ?", (provider,))
            conn.commit()
        return True

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_setting(self, key: str, value: str) -> Dict[str, Any]:
        """Set a setting value."""
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
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
        valid_providers = ["local", "anthropic", "openai", "google"]
        if provider not in valid_providers:
            raise ValueError(f"invalid provider: {provider}")
        return self.set_setting("active_provider", provider)


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
        }

    @router.put("")
    async def update_settings(
        payload: Dict[str, Any],
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Bulk-update settings (theme, language, etc)."""
        del user_id
        if "active_provider" in payload:
            _settings_db.set_active_provider(payload["active_provider"], payload.get("active_model", ""))
        return {"ok": True}

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

        valid_providers = ["anthropic", "openai", "google"]
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
