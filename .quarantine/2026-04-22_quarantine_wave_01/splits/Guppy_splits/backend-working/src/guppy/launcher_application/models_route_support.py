from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def route_targets_from_registry(registry: dict[str, Any]) -> list[str]:
    options: list[str] = []
    providers = registry.get("providers", []) if isinstance(registry, dict) else []
    for provider in providers if isinstance(providers, list) else []:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("id")
        models = provider.get("models", [])
        if not isinstance(provider_id, str) or not isinstance(models, list):
            continue
        for model in models:
            model_id = model.get("id") if isinstance(model, dict) else None
            if isinstance(model_id, str) and model_id:
                options.append(f"{provider_id}/{model_id}")
    return sorted(set(options))


def parse_fallback_chain(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def latest_runtime_latency(runtime_dir: Path) -> str:
    try:
        payload = json.loads((runtime_dir / "guppy.status").read_text(encoding="utf-8"))
    except Exception:
        return ""
    latency = str(payload.get("last_latency_ms", "") or "").strip()
    return "" if not latency or latency in {"-", "â€”"} else f"{latency} ms"
