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
from src.guppy.inference.local_client import (
    active_backend,
    list_local_models,
    probe_backends,
    _BACKEND_DEFAULT_MODELS,
)

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

_COHERE_MODELS = [
    {"id": "command-a-03-2025",      "name": "Command A",       "tier": "powerful"},
    {"id": "command-r-plus-08-2024", "name": "Command R+",      "tier": "smart"},
    {"id": "command-r-08-2024",      "name": "Command R",       "tier": "smart"},
    {"id": "command-light",          "name": "Command Light",   "tier": "fast"},
    {"id": "aya-23-35b",             "name": "Aya 23 35B",      "tier": "smart"},
    {"id": "aya-23-8b",              "name": "Aya 23 8B",       "tier": "fast"},
]

_MISTRAL_MODELS = [
    {"id": "mistral-large-latest",   "name": "Mistral Large",   "tier": "powerful"},
    {"id": "mistral-small-latest",   "name": "Mistral Small",   "tier": "smart"},
    {"id": "codestral-latest",       "name": "Codestral",       "tier": "smart"},
    {"id": "open-mistral-nemo",      "name": "Mistral Nemo",    "tier": "fast"},
    {"id": "pixtral-12b-2409",       "name": "Pixtral 12B",     "tier": "smart"},
    {"id": "open-mixtral-8x22b",     "name": "Mixtral 8x22B",   "tier": "powerful"},
]

_VALID_CLOUD_PROVIDERS = {"anthropic", "openai", "google", "cohere", "mistral"}
_PROVIDER_MODEL_IDS = {
    "anthropic": {m["id"] for m in _ANTHROPIC_MODELS},
    "openai":    {m["id"] for m in _OPENAI_MODELS},
    "google":    {m["id"] for m in _GOOGLE_MODELS},
    "cohere":    {m["id"] for m in _COHERE_MODELS},
    "mistral":   {m["id"] for m in _MISTRAL_MODELS},
}

# Display metadata for local models: display name + capability tags
# Covers both Ollama model IDs and LM Studio model IDs (key field from /api/v1/models)
_LOCAL_MODEL_METADATA: Dict[str, Dict[str, Any]] = {
    # Ollama guppy models
    "guppy:latest":          {"display": "Guppy",        "tags": ["stable", "conversational"]},
    "guppy-fast:latest":     {"display": "Guppy Fast",   "tags": ["fast"]},
    "guppy-vision:latest":   {"display": "Guppy Vision", "tags": ["vision", "fast"]},
    "guppy-vision-pro:latest": {"display": "Guppy Vision Pro", "tags": ["vision"]},
    "guppy-code:latest":     {"display": "Guppy Code",   "tags": ["coding"]},
    "guppy-teach:latest":    {"display": "Guppy Teach",  "tags": ["conversational"]},
    "vault-scraper:latest":  {"display": "Vault Scraper", "tags": ["specialized"]},
    # Ollama base models
    "qwen2.5:7b":            {"display": "Qwen 7B",       "tags": ["fast"]},
    "qwen2.5:32b":           {"display": "Qwen 32B",      "tags": ["stable", "conversational"]},
    "qwen2.5:72b":           {"display": "Qwen 72B",      "tags": ["powerful"]},
    "qwen2.5-coder:14b":     {"display": "Qwen Coder 14B", "tags": ["coding"]},
    "qwen3:8b":              {"display": "Qwen3 8B",      "tags": ["fast", "reasoning"]},
    "gemma3:12b":            {"display": "Gemma3 12B",    "tags": ["conversational", "coding"]},
    "nomic-embed-text:latest": {"display": "Nomic Embed", "tags": ["embeddings"]},
    # LM Studio models — IDs returned by /api/v1/models (key field)
    "qwen/qwen3.6-27b":            {"display": "Qwen3 27B",       "tags": ["stable", "conversational", "reasoning"]},
    "qwen/qwen3.5-9b":             {"display": "Qwen3.5 9B",      "tags": ["fast", "reasoning"]},
    "qwen/qwen3-coder-next":       {"display": "Qwen3 Coder",     "tags": ["coding", "reasoning"]},
    "nvidia/nemotron-3-nano":      {"display": "Nemotron Nano",   "tags": ["fast", "reasoning"]},
    "google/gemma-4-26b-a4b":      {"display": "Gemma 4 26B",     "tags": ["fast", "reasoning", "vision"]},
    "gemma-3-4b-it":               {"display": "Gemma 3 4B",      "tags": ["fast"]},
    "text-embedding-nomic-embed-text-v1.5": {"display": "Nomic Embed v1.5", "tags": ["embeddings"]},
    # llama.cpp (ROCm/HIP) — served via OpenAI-compatible endpoints, one server per model
    "gemma-4-heretic-ara":  {"display": "Gemma 4 E4B Heretic ARA",    "tags": ["vision", "fast", "uncensored"]},
    "qwen3-35b-uncensored": {"display": "Qwen3 35B MoE (Uncensored)", "tags": ["powerful", "reasoning", "uncensored"]},
    "assistant-pepe-8b":    {"display": "Assistant Pepe 8B",          "tags": ["fast", "uncensored"]},
}

# Human-readable labels for the backends status pill in the UI
_BACKEND_LABELS: Dict[str, str] = {
    "ollama":          "Ollama",
    "lmstudio":        "LM Studio",
    "lemonade":        "Lemonade",
    "local_harness":   "Local Harness",
    "llamacpp-gemma":  "Gemma 4 Heretic",
    "llamacpp-qwen3":  "Qwen3 Uncensored",
    "llamacpp-pepe":   "Pepe 8B",
}

# llama.cpp backend names (to distinguish from Ollama/LM Studio when injecting models)
_LLAMACPP_BACKENDS = {"llamacpp-gemma", "llamacpp-qwen3", "llamacpp-pepe"}


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
        "cohere":    "COHERE_API_KEY",
        "mistral":   "MISTRAL_API_KEY",
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
        "cohere":    "COHERE_MODEL",
        "mistral":   "MISTRAL_MODEL",
    }
    return os.environ.get(env_map.get(provider, ""), default).strip() or default


def _provider_status() -> Dict[str, Any]:
    configured = {p: _is_configured(p) for p in _VALID_CLOUD_PROVIDERS}

    local_backend = active_backend()
    local_liveness = probe_backends(timeout=3.0)
    # Always attempt model listing for the active backend regardless of probe result —
    # probe can fail transiently (timeout) while the backend is still functional.
    local_models_raw = list_local_models(local_backend, timeout=4.0)

    def _should_include_model(model_name: str) -> bool:
        clean_names = {"fast:latest", "code:latest", "main:latest"}
        if model_name in clean_names:
            return True
        if model_name.startswith("guppy-") or model_name == "guppy:latest":
            if any(cn in local_models_raw for cn in clean_names):
                return False
        return True

    local_models_filtered = [m for m in local_models_raw if _should_include_model(m)]
    local_models = []
    seen_model_ids: set = set()
    for m in local_models_filtered:
        # Exact match first, then prefix/substring match for long LM Studio IDs
        meta = _LOCAL_MODEL_METADATA.get(m) or next(
            (v for k, v in _LOCAL_MODEL_METADATA.items() if k in m),
            {},
        )
        # For LM Studio, make a friendly short name from the path if no metadata
        display_fallback = m.split("/")[-1].replace("-GGUF", "").replace(".gguf", "") if "/" in m else m
        local_models.append({
            "id": m,
            "name": meta.get("display", display_fallback),
            "tier": "local",
            "tags": meta.get("tags", []),
            "backend": local_backend,
        })
        seen_model_ids.add(m)

    # Inject models from alive llama.cpp servers that aren't already listed
    for backend_name in _LLAMACPP_BACKENDS:
        if not local_liveness.get(backend_name):
            continue
        canonical = _BACKEND_DEFAULT_MODELS.get(backend_name, "")
        if not canonical or canonical in seen_model_ids:
            continue
        meta = _LOCAL_MODEL_METADATA.get(canonical, {})
        local_models.append({
            "id": canonical,
            "name": meta.get("display", canonical),
            "tier": "local",
            "tags": meta.get("tags", []),
            "backend": backend_name,
        })
        seen_model_ids.add(canonical)

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
        "cohere": {
            "configured": configured["cohere"],
            "active_model": _get_active_model("cohere", "command-a-03-2025"),
            "models": _COHERE_MODELS,
        },
        "mistral": {
            "configured": configured["mistral"],
            "active_model": _get_active_model("mistral", "mistral-large-latest"),
            "models": _MISTRAL_MODELS,
        },
        "local": {
            "configured": bool(local_models_raw),
            "backend": local_backend,
            "active_model": local_active,
            "models": local_models,
            "backends": {
                name: {"alive": alive, "label": _BACKEND_LABELS.get(name, name)}
                for name, alive in local_liveness.items()
            },
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
