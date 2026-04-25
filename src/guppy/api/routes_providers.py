"""Provider status API — read-only view of configured AI providers.

GET  /providers                              — all providers with configured status + known models
GET  /providers/models                       — flat list of all available models across providers
POST /providers/{provider}/active-model      — set the active model for a provider
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext
from src.guppy.inference.local_client import active_backend, list_local_models, probe_backends

# Known model catalogs per provider (no discovery needed — models don't change often)
_ANTHROPIC_MODELS = [
    {"id": "claude-sonnet-4-6",          "name": "Claude Sonnet 4.6",   "tier": "smart"},
    {"id": "claude-opus-4-7",            "name": "Claude Opus 4.7",     "tier": "powerful"},
    {"id": "claude-haiku-4-5-20251001",  "name": "Claude Haiku 4.5",    "tier": "fast"},
]

_OPENAI_MODELS = [
    {"id": "gpt-4o",        "name": "GPT-4o",        "tier": "smart"},
    {"id": "gpt-4o-mini",   "name": "GPT-4o Mini",   "tier": "fast"},
    {"id": "o1",            "name": "o1",             "tier": "powerful"},
    {"id": "o1-mini",       "name": "o1 Mini",        "tier": "fast"},
    {"id": "o3-mini",       "name": "o3 Mini",        "tier": "fast"},
]

_GOOGLE_MODELS = [
    {"id": "gemini-2.0-flash",         "name": "Gemini 2.0 Flash",  "tier": "fast"},
    {"id": "gemini-2.5-pro-preview",   "name": "Gemini 2.5 Pro",    "tier": "powerful"},
    {"id": "gemini-2.5-flash-preview", "name": "Gemini 2.5 Flash",  "tier": "fast"},
]

_VALID_CLOUD_PROVIDERS = {"anthropic", "openai", "google"}
_PROVIDER_MODEL_IDS = {
    "anthropic": {m["id"] for m in _ANTHROPIC_MODELS},
    "openai":    {m["id"] for m in _OPENAI_MODELS},
    "google":    {m["id"] for m in _GOOGLE_MODELS},
}


def _get_settings_db():
    """Import lazily to avoid circular dependency at module load."""
    from src.guppy.api.routes_settings import _settings_db
    return _settings_db


def _is_configured(provider: str) -> bool:
    """Check env var first, then fall back to settings DB credential."""
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "google":    "GOOGLE_API_KEY",
    }
    env_key = env_map.get(provider, "")
    if os.environ.get(env_key, "").strip():
        return True
    try:
        return bool(_get_settings_db().get_credential(provider))
    except Exception:
        return False


def _get_active_model(provider: str, default: str) -> str:
    """Read active model from settings DB, fall back to env var, then hard default."""
    try:
        stored = _get_settings_db().get_setting(f"{provider}_active_model")
        if stored:
            return stored
    except Exception:
        pass
    env_map = {
        "anthropic": "ANTHROPIC_MODEL",
        "openai":    "OPENAI_MODEL",
        "google":    "GOOGLE_MODEL",
    }
    return os.environ.get(env_map.get(provider, ""), default).strip() or default


def _provider_status() -> Dict[str, Any]:
    configured = {p: _is_configured(p) for p in _VALID_CLOUD_PROVIDERS}

    local_backend = active_backend()
    local_liveness = probe_backends(timeout=1.0)
    local_models_raw = list_local_models(local_backend, timeout=2.0) if local_liveness.get(local_backend) else []

    def _should_include_model(model_name: str) -> bool:
        clean_names = {"fast:latest", "code:latest", "main:latest"}
        if model_name in clean_names:
            return True
        if model_name.startswith("guppy-") or model_name == "guppy:latest":
            if any(cn in local_models_raw for cn in clean_names):
                return False
        return True

    local_models_filtered = [m for m in local_models_raw if _should_include_model(m)]
    local_models = [{"id": m, "name": m, "tier": "local"} for m in local_models_filtered]

    local_active = _get_active_model("local", local_models_raw[0] if local_models_raw else "")

    return {
        "anthropic": {
            "configured": configured["anthropic"],
            "active_model": _get_active_model("anthropic", "claude-sonnet-4-6"),
            "models": _ANTHROPIC_MODELS,
        },
        "openai": {
            "configured": configured["openai"],
            "active_model": _get_active_model("openai", "gpt-4o-mini"),
            "models": _OPENAI_MODELS,
        },
        "google": {
            "configured": configured["google"],
            "active_model": _get_active_model("google", "gemini-2.0-flash"),
            "models": _GOOGLE_MODELS,
        },
        "local": {
            "configured": bool(local_models_raw),
            "backend": local_backend,
            "active_model": local_active,
            "models": local_models,
            "backends": {name: {"alive": alive} for name, alive in local_liveness.items()},
        },
    }


class ActiveModelRequest(BaseModel):
    model_id: str


def build_providers_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/providers")

    @router.get("")
    async def get_providers(_user_id: str = Depends(ctx.require_rate_limit)):
        return await asyncio.to_thread(_provider_status)

    @router.get("/models")
    async def get_all_models(_user_id: str = Depends(ctx.require_rate_limit)):
        """Flat list of every model available across all configured providers."""
        status = await asyncio.to_thread(_provider_status)
        all_models: List[Dict[str, Any]] = []
        for provider, info in status.items():
            for model in info.get("models", []):
                all_models.append({
                    "provider": provider,
                    "id": model["id"],
                    "name": model["name"],
                    "tier": model.get("tier", ""),
                    "configured": info["configured"],
                })
        return {"models": all_models, "total": len(all_models)}

    @router.post("/{provider}/active-model")
    async def set_active_model(
        provider: str,
        body: ActiveModelRequest,
        _user_id: str = Depends(ctx.require_rate_limit),
    ):
        """Persist the selected active model for a provider."""
        if provider not in {*_VALID_CLOUD_PROVIDERS, "local"}:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
        model_id = body.model_id.strip()
        if not model_id:
            raise HTTPException(status_code=422, detail="model_id required")
        # For cloud providers, validate against known catalog
        if provider in _PROVIDER_MODEL_IDS:
            if model_id not in _PROVIDER_MODEL_IDS[provider]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown model '{model_id}' for provider '{provider}'",
                )
        db = _get_settings_db()
        await asyncio.to_thread(db.set_setting, f"{provider}_active_model", model_id)
        return {"provider": provider, "active_model": model_id}

    return router
