from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.guppy.paths import CONFIG_DIR

DEFAULT_LOCAL_LLM_MANIFEST = CONFIG_DIR / "local_llm" / "models.json"


def load_local_llm_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path else DEFAULT_LOCAL_LLM_MANIFEST
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def get_manifest_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "last_updated": manifest.get("last_updated"),
        "owner": manifest.get("owner"),
    }


def get_baseline_model_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = manifest.get("baseline_models") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def get_runtime_backend_baseline(manifest: dict[str, Any]) -> str:
    runtime = manifest.get("runtime") or {}
    return str(runtime.get("baseline_backend") or "ollama").strip() or "ollama"


def get_memory_backend_baseline(manifest: dict[str, Any]) -> str:
    memory = manifest.get("memory") or {}
    return str(memory.get("baseline_backend") or "semantic-sqlite").strip() or "semantic-sqlite"


def get_memory_directory_plan(manifest: dict[str, Any]) -> dict[str, str]:
    memory = manifest.get("memory") or {}
    plan = memory.get("directory_plan") or {}
    return {str(key): str(value) for key, value in plan.items()}


def get_manifest_artifact_path(
    manifest: dict[str, Any],
    key: str,
    default: str | Path | None = None,
) -> Path:
    runtime = manifest.get("runtime") or {}
    paths = runtime.get("artifact_paths") or {}
    raw = paths.get(key)
    if raw:
        return Path(str(raw))
    if default is not None:
        return Path(default)
    raise KeyError(f"artifact path not found: {key}")
