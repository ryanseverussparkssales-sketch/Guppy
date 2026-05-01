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
        description="Default inference backend: local llama.cpp/OpenAI-compatible runtime or cloud Anthropic.",
    )
    guppy_local_runtime_backend: Literal[
        "auto",
        "llamacpp-gemma", "llamacpp-qwen3", "llamacpp-pepe",
        "llamacpp-minicpm", "llamacpp-dispatch", "llamacpp-hermes4",
        "llamacpp-hermes3", "llamacpp-rocinante", "llamacpp-xlam",
        "llamacpp-chat", "llamacpp-phi4-mini", "local_harness",
        "ollama", "lmstudio", "lemonade", "vllm",
    ] = Field(
        default="auto",
        description="Local inference backend. Legacy values collapse to the active llama.cpp backend.",
    )
    guppy_runtime_profile: Literal["standard", "power"] = Field(default="standard")

    # ── API server ────────────────────────────────────────────────────────────
    guppy_api_port: int = Field(default=8081, ge=1024, le=65535)
    guppy_api_owns_daemon: bool = Field(default=False)
    guppy_api_reload: bool = Field(default=False, description="Enable uvicorn auto-reload (dev only).")

    # ── Models ────────────────────────────────────────────────────────────────
    # llamacpp model role defaults (resolved via model_roles registry at runtime)
    llamacpp_default_model: str = Field(default="hermes-3-8b-lorablated",  description="Default conversation model (conversation.default role)")
    llamacpp_worker_model:  str = Field(default="hermes-4-14b",            description="Workspace worker model (workspace.worker.primary role)")

    # ── llama.cpp (ROCm/HIP) model names ─────────────────────────────────────
    llamacpp_gemma_model: str = Field(default="gemma-4-heretic-ara",    description="Model ID for llamacpp-gemma server.")
    llamacpp_qwen3_model: str = Field(default="qwen3-35b-uncensored",   description="Model ID for llamacpp-qwen3 server.")
    llamacpp_pepe_model:  str = Field(default="assistant-pepe-8b",      description="Model ID for llamacpp-pepe server.")

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
