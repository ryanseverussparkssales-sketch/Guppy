"""Provider status API — read-only view of configured AI providers.

GET /providers        — all providers with configured status + known models
GET /providers/models — flat list of all available models across providers
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

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
    {"id": "gemini-2.0-flash",        "name": "Gemini 2.0 Flash",      "tier": "fast"},
    {"id": "gemini-2.5-pro-preview",  "name": "Gemini 2.5 Pro",        "tier": "powerful"},
    {"id": "gemini-2.5-flash-preview","name": "Gemini 2.5 Flash",      "tier": "fast"},
]


def _provider_status() -> Dict[str, Any]:
    anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    openai_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    google_key = bool(os.environ.get("GOOGLE_API_KEY", "").strip())

    local_backend = active_backend()
    local_liveness = probe_backends(timeout=1.0)
    local_models_raw = list_local_models(local_backend, timeout=2.0) if local_liveness.get(local_backend) else []

    local_models = [{"id": m, "name": m, "tier": "local"} for m in local_models_raw]

    return {
        "anthropic": {
            "configured": anthropic_key,
            "active_model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip(),
            "models": _ANTHROPIC_MODELS if anthropic_key else [],
        },
        "openai": {
            "configured": openai_key,
            "active_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
            "models": _OPENAI_MODELS if openai_key else [],
        },
        "google": {
            "configured": google_key,
            "active_model": os.environ.get("GOOGLE_MODEL", "gemini-2.0-flash").strip(),
            "models": _GOOGLE_MODELS if google_key else [],
        },
        "local": {
            "configured": bool(local_models_raw),
            "backend": local_backend,
            "active_model": local_models_raw[0] if local_models_raw else "",
            "models": local_models,
            "backends": {name: {"alive": alive} for name, alive in local_liveness.items()},
        },
    }


def build_providers_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/providers")

    @router.get("")
    async def get_providers(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        return _provider_status()

    @router.get("/models")
    async def get_all_models(user_id: str = Depends(ctx.require_rate_limit)):
        """Flat list of every model available across all configured providers."""
        del user_id
        status = _provider_status()
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

    return router
