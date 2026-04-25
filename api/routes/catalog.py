from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter

try:
    from src.guppy.inference.local_client import active_backend, list_local_models, probe_backends
except ImportError:  # cloud deployments without the desktop runtime tree
    def active_backend() -> str:  # type: ignore[misc]
        return "ollama"

    def list_local_models(_backend: str, **_kw) -> list:  # type: ignore[misc]
        return []

    def probe_backends(**_kw) -> dict:  # type: ignore[misc]
        return {}

from utils.connector_manager import connector_inventory
from utils.tool_registry import TOOLS

router = APIRouter(tags=["catalog"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _REPO_ROOT / "config"
_RUNTIME_DIR = _REPO_ROOT / "runtime"
_STARTUP_TIME = time.time()

_ANTHROPIC_MODELS = [
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "tier": "smart"},
    {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "tier": "powerful"},
    {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "tier": "fast"},
]

_OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "tier": "smart"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "tier": "fast"},
    {"id": "o1", "name": "o1", "tier": "powerful"},
    {"id": "o1-mini", "name": "o1 Mini", "tier": "fast"},
    {"id": "o3-mini", "name": "o3 Mini", "tier": "fast"},
]

_GOOGLE_MODELS = [
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "tier": "fast"},
    {"id": "gemini-2.5-pro-preview", "name": "Gemini 2.5 Pro", "tier": "powerful"},
    {"id": "gemini-2.5-flash-preview", "name": "Gemini 2.5 Flash", "tier": "fast"},
]


def _safe_local_models(backend: str) -> list[str]:
    try:
        return list_local_models(backend, timeout=2.0)
    except Exception:
        return []


def _providers_payload() -> dict[str, Any]:
    anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    openai_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    google_key = bool(os.environ.get("GOOGLE_API_KEY", "").strip())

    backend = active_backend()
    backends = probe_backends(timeout=1.0)
    local_models_raw = _safe_local_models(backend) if backends.get(backend) else []
    local_models = [{"id": model, "name": model, "tier": "local"} for model in local_models_raw]

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
            "backend": backend,
            "active_model": local_models_raw[0] if local_models_raw else "",
            "models": local_models,
            "backends": {name: {"alive": alive} for name, alive in backends.items()},
        },
    }


def _model_capabilities(provider: str) -> dict[str, bool]:
    return {
        "chat": True,
        "completion": True,
        "functionCalling": provider in {"openai", "anthropic", "local"},
        "vision": provider in {"openai", "google"},
        "embedding": False,
        "streaming": True,
    }


def _flat_models_payload() -> list[dict[str, Any]]:
    providers = _providers_payload()
    models: list[dict[str, Any]] = []
    for provider_name, info in providers.items():
        configured = bool(info.get("configured", False))
        for model in info.get("models", []):
            model_id = str(model.get("id", "") or "").strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": str(model.get("name", model_id) or model_id),
                    "provider": "local" if provider_name == "local" else provider_name,
                    "type": "llm",
                    "description": f"{provider_name.title()} model ({str(model.get('tier', 'general') or 'general')}).",
                    "parameters": "",
                    "contextLength": 0,
                    "isAvailable": configured,
                    "size": 0,
                    "capabilities": _model_capabilities(provider_name),
                }
            )
    return models


def _normalize_instance_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"running", "active", "busy"}:
        return "running"
    if normalized in {"starting"}:
        return "starting"
    if normalized in {"error", "failed"}:
        return "error"
    return "stopped"


def _instance_snapshot_payload() -> dict[str, Any]:
    import json

    def _load(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}

    config = _load(_CONFIG_DIR / "instances.json")
    state = _load(_RUNTIME_DIR / "instance_state.json")
    raw_items = config.get("instances", []) if isinstance(config, dict) else []
    state_items = state.get("instances", {}) if isinstance(state, dict) else {}
    active = str(
        config.get("active_instance", state.get("active_instance", "guppy-primary"))
        if isinstance(config, dict)
        else "guppy-primary"
    ).strip() or "guppy-primary"

    items: list[dict[str, Any]] = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        runtime = state_items.get(name, {}) if isinstance(state_items, dict) else {}
        items.append({
            "name": name,
            "description": str(item.get("description", "")).strip(),
            "mode": str(item.get("mode", "auto") or "auto"),
            "persona": str(item.get("persona", "guppy") or "guppy"),
            "type": str(item.get("type", "user_instance") or "user_instance"),
            "created_at": item.get("created_at"),
            "enabled": bool(item.get("enabled", True)),
            "status": str(runtime.get("status", "idle") or "idle"),
            "last_message": str(runtime.get("last_message", "") or ""),
            "last_updated": runtime.get("last_updated"),
            "message_count": int(runtime.get("message_count", 0) or 0),
            "model_currently_using": str(
                runtime.get("model_currently_using", item.get("mode", "auto")) or "auto"
            ),
        })

    if not items:
        items = [{
            "name": "guppy-primary",
            "description": "Primary foreground assistant instance",
            "mode": "auto",
            "persona": "guppy",
            "type": "user_instance",
            "created_at": None,
            "enabled": True,
            "status": "active",
            "last_message": "",
            "last_updated": None,
            "message_count": 0,
            "model_currently_using": "auto",
        }]
        active = "guppy-primary"

    active_runtime = sum(
        1 for i in items if str(i.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
    )
    return {
        "version": int(config.get("version", 1) or 1) if isinstance(config, dict) else 1,
        "active_instance": active,
        "instances": items,
        "limits": {
            "configured": len(items),
            "max_configured": 5,
            "active_runtime": active_runtime,
            "max_active_runtime": 2,
        },
        "warnings": [],
    }


def _flat_instances_payload() -> list[dict[str, Any]]:
    snapshot = _instance_snapshot_payload()
    rows = snapshot.get("instances", []) if isinstance(snapshot, dict) else []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "") or "").strip()
        if not name:
            continue
        model_name = str(row.get("model_currently_using", row.get("mode", "auto")) or "auto")
        items.append(
            {
                "id": name,
                "name": name,
                "status": _normalize_instance_status(str(row.get("status", "idle") or "idle")),
                "modelId": model_name,
                "modelName": model_name,
                "createdAt": str(row.get("created_at", "") or ""),
                "lastActive": str(row.get("last_updated", "") or ""),
                "metrics": {
                    "cpuUsage": 0,
                    "memoryUsage": 0,
                    "memoryTotal": 0,
                    "requestCount": int(row.get("message_count", 0) or 0),
                    "avgResponseTime": 0,
                },
                "config": {
                    "maxTokens": 0,
                    "temperature": 0,
                    "topP": 0,
                    "enabledTools": [],
                },
                "description": str(row.get("description", "") or ""),
                "type": str(row.get("type", "") or ""),
                "mode": str(row.get("mode", "auto") or "auto"),
                "persona": str(row.get("persona", "guppy") or "guppy"),
                "enabled": bool(row.get("enabled", True)),
            }
        )
    return items


def _tool_category(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("search", "news", "weather", "fetch_url")):
        return "search"
    if any(token in lowered for token in ("file", "directory", "patch")):
        return "file"
    if any(token in lowered for token in ("command", "application", "mouse", "keyboard", "screen", "screenshot")):
        return "system"
    if any(token in lowered for token in ("gmail", "calendar", "spotify", "youtube", "weather", "news")):
        return "api"
    if any(token in lowered for token in ("memory", "task", "contact", "pipeline", "remember", "recall")):
        return "database"
    return "code"


def _flat_tools_payload() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool in TOOLS:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("name", "") or "").strip()
        if not tool_id:
            continue
        items.append(
            {
                "id": tool_id,
                "name": tool_id.replace("_", " ").title(),
                "description": str(tool.get("description", "") or "").strip(),
                "category": _tool_category(tool_id),
                "isEnabled": True,
                "parameters": tool.get("input_schema", {}),
                "type": "builtin",
            }
        )
    return items


def _status_payload() -> dict[str, Any]:
    providers = _providers_payload()
    local = providers["local"]
    local_models = [str(item.get("id", "") or "") for item in local.get("models", []) if isinstance(item, dict)]
    local_ready = bool(local_models) and any(
        bool(item.get("alive", False)) for item in local.get("backends", {}).values()
    )
    health = "healthy" if local_ready or providers["anthropic"]["configured"] or providers["openai"]["configured"] else "degraded"
    return {
        "health": health,
        "status": health,
        "message": "Catalog endpoints aligned with launcher inventories.",
        "uptime_seconds": round(time.time() - _STARTUP_TIME, 1),
        "resources": {"gpuMemory": None},
        "memory_available": True,
        "voice_available": False,
        "daemon_available": False,
        "guppy_core_available": True,
        "startup_readiness": {
            "overall": "ready" if health == "healthy" else "degraded",
            "checks": {
                "api": {"state": "ready", "detail": "FastAPI shell responding."},
                "local_runtime": {
                    "state": "ready" if local_ready else "missing",
                    "detail": (
                        f"{local.get('backend', 'local')} available with {len(local_models)} model(s)."
                        if local_ready
                        else "No local runtime models detected."
                    ),
                },
            },
        },
        "local_runtime": {
            "state": "ready" if local_ready else "missing",
            "backend": str(local.get("backend", "local") or "local"),
            "chat_ready": local_ready,
            "models": local_models,
        },
        "providers": {
            "openai": bool(providers["openai"]["configured"]),
            "anthropic": bool(providers["anthropic"]["configured"]),
            "google": bool(providers["google"]["configured"]),
        },
    }


@router.get("/")
async def root_status() -> dict[str, Any]:
    return _status_payload()


@router.get("/status")
@router.get("/api/status")
async def status() -> dict[str, Any]:
    return _status_payload()


@router.get("/providers")
@router.get("/api/providers")
async def providers() -> dict[str, Any]:
    return _providers_payload()


@router.get("/providers/models")
@router.get("/api/providers/models")
async def provider_models() -> dict[str, Any]:
    models = _flat_models_payload()
    return {"models": models, "total": len(models)}


@router.get("/api/models")
async def models() -> list[dict[str, Any]]:
    return _flat_models_payload()


@router.get("/tools")
@router.get("/api/tools")
async def tools() -> list[dict[str, Any]]:
    return _flat_tools_payload()


@router.get("/instances")
async def instances_snapshot() -> dict[str, Any]:
    return _instance_snapshot_payload()


@router.get("/api/instances")
async def instances() -> list[dict[str, Any]]:
    return _flat_instances_payload()


@router.get("/connectors")
@router.get("/api/connectors")
async def connectors() -> dict[str, Any]:
    return {"connectors": connector_inventory()}