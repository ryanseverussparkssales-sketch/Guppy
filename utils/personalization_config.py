import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "runtime"

PERSONA_CONFIG_PATH = RUNTIME_DIR / "persona_config.json"
PROVIDER_REGISTRY_PATH = RUNTIME_DIR / "provider_registry.json"
VOICE_BINDINGS_PATH = RUNTIME_DIR / "voice_bindings.json"


DEFAULT_PERSONA_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_persona_id": "guppy_global",
    "personas": [
        {
            "id": "guppy_global",
            "name": "Guppy Global",
            "scope": "global",
            "system_prompt": "You are Guppy. Be concise, dependable, and practical.",
            "traits": {
                "tone": "butler",
                "verbosity": "medium",
                "response_style": "direct",
            },
            "teaching": {
                "enabled": True,
                "socratic_bias": 35,
                "example_bias": 60,
            },
        }
    ],
    "assignments": {
        "global": "guppy_global",
        "by_model": {},
    },
}

DEFAULT_PROVIDER_REGISTRY: dict[str, Any] = {
    "version": 1,
    "default_route": "anthropic/claude-haiku-4-5-20251001",
    "providers": [
        {
            "id": "anthropic",
            "name": "Anthropic",
            "enabled": True,
            "api_base": "https://api.anthropic.com",
            "auth_env": "ANTHROPIC_API_KEY",
            "models": [
                {
                    "id": "claude-haiku-4-5-20251001",
                    "label": "Claude Haiku 4.5",
                    "enabled": True,
                    "context_window": 200000,
                    "speed_tier": "fast",
                    "tags": ["cheap", "teaching"],
                    "pricing": {
                        "tier": "cheap",
                    },
                },
                {
                    "id": "claude-sonnet-4-6",
                    "label": "Claude Sonnet 4.6",
                    "enabled": True,
                    "context_window": 200000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {
                        "tier": "premium",
                    },
                },
            ],
        }
    ],
    "routes": {
        "simple": "anthropic/claude-haiku-4-5-20251001",
        "complex": "anthropic/claude-sonnet-4-6",
        "teaching": "anthropic/claude-haiku-4-5-20251001",
        "fallback_chain": [
            "anthropic/claude-haiku-4-5-20251001",
            "anthropic/claude-sonnet-4-6",
            "local/guppy",
        ],
    },
}

DEFAULT_VOICE_BINDINGS: dict[str, Any] = {
    "version": 1,
    "defaults": {
        "engine": "EDGE TTS",
        "voice_id": "en-GB-RyanNeural",
    },
    "bindings": {
        "by_model": {},
        "by_persona": {},
    },
    "imports": [],
}


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return json.loads(json.dumps(fallback))


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_persona_config() -> dict[str, Any]:
    return _read_json(PERSONA_CONFIG_PATH, DEFAULT_PERSONA_CONFIG)


def load_provider_registry() -> dict[str, Any]:
    return _read_json(PROVIDER_REGISTRY_PATH, DEFAULT_PROVIDER_REGISTRY)


def load_voice_bindings() -> dict[str, Any]:
    return _read_json(VOICE_BINDINGS_PATH, DEFAULT_VOICE_BINDINGS)


def save_persona_config(data: dict[str, Any]) -> Path:
    return _write_json(PERSONA_CONFIG_PATH, data)


def save_provider_registry(data: dict[str, Any]) -> Path:
    return _write_json(PROVIDER_REGISTRY_PATH, data)


def save_voice_bindings(data: dict[str, Any]) -> Path:
    return _write_json(VOICE_BINDINGS_PATH, data)


def validate_persona_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["persona config must be an object"]

    personas = data.get("personas")
    if not isinstance(personas, list) or not personas:
        errors.append("personas must be a non-empty list")
        return errors

    ids = set()
    for idx, p in enumerate(personas):
        if not isinstance(p, dict):
            errors.append(f"personas[{idx}] must be an object")
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"personas[{idx}].id is required")
            continue
        ids.add(pid)
        scope = p.get("scope")
        if scope not in {"global", "model"}:
            errors.append(f"personas[{idx}].scope must be global or model")
        if scope == "model" and not p.get("model"):
            errors.append(f"personas[{idx}].model is required for scope=model")

    assignments = data.get("assignments", {})
    global_id = assignments.get("global") if isinstance(assignments, dict) else None
    if global_id not in ids:
        errors.append("assignments.global must reference a defined persona id")

    by_model = assignments.get("by_model", {}) if isinstance(assignments, dict) else {}
    if isinstance(by_model, dict):
        for model_key, persona_id in by_model.items():
            if not isinstance(model_key, str) or not model_key:
                errors.append("assignments.by_model keys must be non-empty strings")
            if persona_id not in ids:
                errors.append(f"assignments.by_model[{model_key}] must reference a defined persona id")
    else:
        errors.append("assignments.by_model must be an object")

    return errors


def validate_provider_registry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["provider registry must be an object"]

    providers = data.get("providers")
    if not isinstance(providers, list) or not providers:
        return ["providers must be a non-empty list"]

    route_keys: set[str] = set()
    for pidx, provider in enumerate(providers):
        if not isinstance(provider, dict):
            errors.append(f"providers[{pidx}] must be an object")
            continue
        provider_id = provider.get("id")
        models = provider.get("models")
        if not isinstance(provider_id, str) or not provider_id:
            errors.append(f"providers[{pidx}].id is required")
            continue
        if not isinstance(models, list) or not models:
            errors.append(f"providers[{pidx}].models must be non-empty")
            continue
        for midx, model in enumerate(models):
            if not isinstance(model, dict):
                errors.append(f"providers[{pidx}].models[{midx}] must be an object")
                continue
            model_id = model.get("id")
            if not isinstance(model_id, str) or not model_id:
                errors.append(f"providers[{pidx}].models[{midx}].id is required")
                continue
            route_keys.add(f"{provider_id}/{model_id}")

    routes = data.get("routes", {})
    if not isinstance(routes, dict):
        return errors + ["routes must be an object"]

    for key in ("simple", "complex", "teaching"):
        target = routes.get(key)
        if target not in route_keys:
            errors.append(f"routes.{key} must reference provider/model from registry")

    fallback_chain = routes.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain:
        errors.append("routes.fallback_chain must be a non-empty list")
    else:
        for idx, target in enumerate(fallback_chain):
            if target not in route_keys and target != "local/guppy":
                errors.append(f"routes.fallback_chain[{idx}] invalid target: {target}")

    return errors


def validate_voice_bindings(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["voice bindings must be an object"]

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict) or not defaults.get("engine") or not defaults.get("voice_id"):
        errors.append("defaults.engine and defaults.voice_id are required")

    bindings = data.get("bindings", {})
    if not isinstance(bindings, dict):
        errors.append("bindings must be an object")
        return errors

    for binding_key in ("by_model", "by_persona"):
        mapping = bindings.get(binding_key, {})
        if not isinstance(mapping, dict):
            errors.append(f"bindings.{binding_key} must be an object")
            continue
        for key, item in mapping.items():
            if not isinstance(item, dict):
                errors.append(f"bindings.{binding_key}[{key}] must be an object")
                continue
            if not item.get("engine") or not item.get("voice_id"):
                errors.append(f"bindings.{binding_key}[{key}] requires engine and voice_id")

    imports = data.get("imports", [])
    if not isinstance(imports, list):
        errors.append("imports must be a list")

    return errors


def ensure_personalization_scaffold() -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if not PERSONA_CONFIG_PATH.exists():
        paths["persona"] = save_persona_config(DEFAULT_PERSONA_CONFIG)
    if not PROVIDER_REGISTRY_PATH.exists():
        paths["providers"] = save_provider_registry(DEFAULT_PROVIDER_REGISTRY)
    if not VOICE_BINDINGS_PATH.exists():
        paths["voice"] = save_voice_bindings(DEFAULT_VOICE_BINDINGS)
    return paths


def validate_all_personalization_configs() -> dict[str, list[str]]:
    persona = load_persona_config()
    providers = load_provider_registry()
    voice = load_voice_bindings()
    return {
        "persona": validate_persona_config(persona),
        "providers": validate_provider_registry(providers),
        "voice": validate_voice_bindings(voice),
    }
