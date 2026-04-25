"""Centralised runtime configuration via pydantic-settings.

All env vars Guppy reads are declared here. Load once at startup:
    from src.guppy.config import settings

Individual modules can import settings instead of calling os.environ directly.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GuppySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Auth ──────────────────────────────────────────────────────────────────
    guppy_jwt_secret: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret used to sign JWT tokens. Must be overridden in production.",
    )
    turnstile_secret: str = Field(
        default="dev-turnstile-secret",
        description="Cloudflare Turnstile secret key.",
    )

    # ── Runtime mode ─────────────────────────────────────────────────────────
    guppy_dev_mode: bool = Field(default=False, description="Enable dev endpoints and verbose logging.")
    guppy_default_mode: Literal["local", "cloud"] = Field(
        default="local",
        description="Default inference backend: local (Ollama) or cloud (Anthropic).",
    )
    guppy_local_runtime_backend: Literal["ollama", "lmstudio", "lemonade", "vllm", "auto"] = Field(
        default="ollama",
        description="Local inference backend.",
    )
    guppy_runtime_profile: Literal["standard", "power"] = Field(default="standard")

    # ── API server ────────────────────────────────────────────────────────────
    guppy_api_port: int = Field(default=8081, ge=1024, le=65535)
    guppy_api_owns_daemon: bool = Field(default=False)
    guppy_api_reload: bool = Field(default=False, description="Enable uvicorn auto-reload (dev only).")

    # ── Models ────────────────────────────────────────────────────────────────
    ollama_model: str = Field(default="guppy")
    ollama_fast_model: str = Field(default="guppy-fast")
    ollama_teach_model: str = Field(default="guppy-teach")
    ollama_code_model: str = Field(default="guppy-code")
    ollama_vault_model: str = Field(default="vault-scraper")

    # ── Feature flags ─────────────────────────────────────────────────────────
    guppy_haiku_boost: bool = Field(default=False)
    guppy_semantic_classifier: bool = Field(default=True)
    guppy_router_mode: str = Field(default="auto")
    guppy_tool_budget: int = Field(default=6, ge=0)
    guppy_whisper_model: str = Field(default="large-v3")

    # ── SQLite ────────────────────────────────────────────────────────────────
    guppy_sqlite_timeout_seconds: float = Field(default=10.0)
    guppy_sqlite_busy_timeout_ms: int = Field(default=5000)
    guppy_sqlite_sync_mode: Literal["FULL", "NORMAL", "OFF"] = Field(default="NORMAL")

    # ── Storage ───────────────────────────────────────────────────────────────
    guppy_user_data_dir: str = Field(default="")

    # ── External APIs ─────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    spotify_client_id: str = Field(default="")
    spotify_client_secret: str = Field(default="")
    weather_units: Literal["imperial", "metric"] = Field(default="imperial")


# Singleton — import this everywhere instead of os.environ
settings = GuppySettings()
