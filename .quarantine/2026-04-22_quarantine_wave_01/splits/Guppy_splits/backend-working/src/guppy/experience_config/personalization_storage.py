"""Normalization, persistence, and validation helpers for personalization config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.guppy.experience_config.personalization_defaults import (
    DEFAULT_PERSONA_CONFIG,
    DEFAULT_PROVIDER_REGISTRY,
    DEFAULT_VOICE_BINDINGS,
    MAIN_GUPPY_PERSONA_ID,
    MAIN_GUPPY_PROFILE_SUMMARY,
)

try:
    from utils.safe_io import write_json_atomic

    _ATOMIC_IO = True
except Exception:
    _ATOMIC_IO = False

    def write_json_atomic(_path: Path, _data: dict[str, Any]) -> bool:
        return False


def deepcopy_json(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


def unique_strings_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def normalize_persona_config(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = deepcopy_json(data) if isinstance(data, dict) else deepcopy_json(DEFAULT_PERSONA_CONFIG)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    personas = cfg.get("personas")
    if not isinstance(personas, list) or not personas:
        notes.append("personas must be a non-empty list; reset to defaults")
        cfg["personas"] = deepcopy_json(DEFAULT_PERSONA_CONFIG)["personas"]
    else:
        cleaned: list[dict[str, Any]] = []
        dropped = 0
        for persona in personas:
            if not isinstance(persona, dict):
                dropped += 1
                continue
            if not isinstance(persona.get("id"), str) or not persona.get("id"):
                dropped += 1
                continue
            if not isinstance(persona.get("traits"), dict):
                notes.append(f"persona {persona.get('id')} traits missing or invalid; reset to defaults")
                persona["traits"] = {
                    "tone": "butler",
                    "verbosity": "medium",
                    "response_style": "direct",
                }
            if not isinstance(persona.get("teaching"), dict):
                notes.append(f"persona {persona.get('id')} teaching block missing or invalid; reset to defaults")
                persona["teaching"] = {
                    "enabled": True,
                    "socratic_bias": 35,
                    "example_bias": 60,
                }
            profile_summary = persona.get("profile_summary")
            if profile_summary is not None and not isinstance(profile_summary, str):
                notes.append(f"persona {persona.get('id')} profile_summary must be a string; dropped invalid value")
                persona.pop("profile_summary", None)
            if persona.get("id") == MAIN_GUPPY_PERSONA_ID and not str(persona.get("profile_summary", "") or "").strip():
                persona["profile_summary"] = MAIN_GUPPY_PROFILE_SUMMARY
            cleaned.append(persona)
        if dropped:
            notes.append(f"ignored {dropped} invalid persona entries")
        cfg["personas"] = cleaned or deepcopy_json(DEFAULT_PERSONA_CONFIG)["personas"]

    assignments = cfg.get("assignments")
    if not isinstance(assignments, dict):
        notes.append("assignments must be an object; reset to defaults")
        assignments = {}
    if not isinstance(assignments.get("by_model"), dict):
        notes.append("assignments.by_model must be an object; reset to empty mapping")
        assignments["by_model"] = {}
    persona_ids = {p.get("id") for p in cfg["personas"] if isinstance(p, dict)}
    if assignments.get("global") not in persona_ids:
        notes.append("assignments.global did not reference a valid persona; reset to first persona")
        assignments["global"] = cfg["personas"][0].get("id")
    cfg["assignments"] = assignments

    if not isinstance(cfg.get("default_persona_id"), str) or cfg.get("default_persona_id") not in persona_ids:
        notes.append("default_persona_id did not reference a valid persona; reset to global assignment")
        cfg["default_persona_id"] = assignments.get("global")

    if not isinstance(cfg.get("version"), int):
        notes.append("version must be an integer; reset to 1")
        cfg["version"] = 1

    return cfg


def normalize_provider_registry(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = deepcopy_json(data) if isinstance(data, dict) else deepcopy_json(DEFAULT_PROVIDER_REGISTRY)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    providers = cfg.get("providers")
    if not isinstance(providers, list) or not providers:
        notes.append("providers must be a non-empty list; reset to defaults")
        cfg["providers"] = deepcopy_json(DEFAULT_PROVIDER_REGISTRY)["providers"]
    else:
        cleaned_providers: list[dict[str, Any]] = []
        dropped_providers = 0
        for provider in providers:
            if not isinstance(provider, dict):
                dropped_providers += 1
                continue
            pid = provider.get("id")
            models = provider.get("models")
            if not isinstance(pid, str) or not pid or not isinstance(models, list) or not models:
                dropped_providers += 1
                continue
            cleaned_models: list[dict[str, Any]] = []
            dropped_models = 0
            for model in models:
                if not isinstance(model, dict):
                    dropped_models += 1
                    continue
                mid = model.get("id")
                if not isinstance(mid, str) or not mid:
                    dropped_models += 1
                    continue
                cleaned_models.append(model)
            if not cleaned_models:
                dropped_providers += 1
                continue
            if dropped_models:
                notes.append(f"provider {pid} ignored {dropped_models} invalid model entries")
            provider["models"] = cleaned_models
            valid_tiers = {"core", "supported_optional", "experimental"}
            tier = provider.get("provider_tier")
            if tier not in valid_tiers:
                auth_env = str(provider.get("auth_env") or "").strip()
                api_base = str(provider.get("api_base") or "").strip()
                local_hosts = ("127.0.0.1", "localhost", "::1")
                is_local = not auth_env and any(host in api_base for host in local_hosts)
                provider["provider_tier"] = "core" if is_local else "supported_optional"
                if tier is not None:
                    notes.append(
                        f"provider {pid} had invalid provider_tier {tier!r}; defaulted to {provider['provider_tier']!r}"
                    )
            cleaned_providers.append(provider)
        if dropped_providers:
            notes.append(f"ignored {dropped_providers} invalid provider entries")
        cfg["providers"] = cleaned_providers or deepcopy_json(DEFAULT_PROVIDER_REGISTRY)["providers"]

    route_keys: set[str] = set()
    for provider in cfg["providers"]:
        if not isinstance(provider, dict):
            continue
        pid = provider.get("id")
        models = provider.get("models", [])
        if not isinstance(pid, str) or not isinstance(models, list):
            continue
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("id"), str):
                route_keys.add(f"{pid}/{model['id']}")

    defaults = deepcopy_json(DEFAULT_PROVIDER_REGISTRY)
    default_routes = defaults.get("routes") if isinstance(defaults.get("routes"), dict) else {}
    routes: dict[str, Any] = cfg.get("routes") if isinstance(cfg.get("routes"), dict) else {}
    if not isinstance(cfg.get("routes"), dict):
        notes.append("routes must be an object; reset to defaults")
    for key in ("simple", "complex", "teaching"):
        if routes.get(key) not in route_keys:
            notes.append(f"routes.{key} did not reference a valid provider/model; reset to default")
            routes[key] = default_routes.get(key)
    fallback_chain = routes.get("fallback_chain")
    if not isinstance(fallback_chain, list) or not fallback_chain:
        notes.append("routes.fallback_chain must be a non-empty list; reset to defaults")
        routes["fallback_chain"] = list(default_routes.get("fallback_chain", []))
    else:
        cleaned_fallback = [
            target for target in fallback_chain if isinstance(target, str) and (target in route_keys or target == "local/guppy")
        ]
        if len(cleaned_fallback) != len(fallback_chain):
            notes.append("routes.fallback_chain ignored invalid targets")
        routes["fallback_chain"] = cleaned_fallback or list(default_routes.get("fallback_chain", []))
    cfg["routes"] = routes

    if cfg.get("default_route") not in route_keys:
        notes.append("default_route did not reference a valid provider/model; reset to simple route")
        cfg["default_route"] = routes.get("simple", defaults["default_route"])
    if not isinstance(cfg.get("version"), int):
        notes.append("version must be an integer; reset to 1")
        cfg["version"] = 1
    return cfg


def normalize_voice_bindings(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = deepcopy_json(data) if isinstance(data, dict) else deepcopy_json(DEFAULT_VOICE_BINDINGS)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    defaults = cfg.get("defaults")
    if not isinstance(defaults, dict):
        notes.append("defaults must be an object; reset to defaults")
        defaults = deepcopy_json(DEFAULT_VOICE_BINDINGS["defaults"])
    if not str(defaults.get("engine", "") or "").strip():
        notes.append("defaults.engine is required; reset to default engine")
        defaults["engine"] = DEFAULT_VOICE_BINDINGS["defaults"]["engine"]
    if not str(defaults.get("voice_id", "") or "").strip():
        notes.append("defaults.voice_id is required; reset to default voice")
        defaults["voice_id"] = DEFAULT_VOICE_BINDINGS["defaults"]["voice_id"]
    cfg["defaults"] = defaults

    bindings = cfg.get("bindings")
    if not isinstance(bindings, dict):
        notes.append("bindings must be an object; reset to defaults")
        bindings = {"by_model": {}, "by_persona": {}}
    for key in ("by_model", "by_persona"):
        if not isinstance(bindings.get(key), dict):
            notes.append(f"bindings.{key} must be an object; reset to empty mapping")
            bindings[key] = {}
    cfg["bindings"] = bindings

    if not isinstance(cfg.get("imports"), list):
        notes.append("imports must be a list; reset to empty list")
        cfg["imports"] = []
    if not isinstance(cfg.get("version"), int):
        notes.append("version must be an integer; reset to 1")
        cfg["version"] = 1
    return cfg


def load_json_with_diagnostics(
    path: Path,
    fallback: dict[str, Any],
    *,
    normalizer: Callable[[Any, list[str] | None], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    diagnostics: list[str] = []
    fallback_copy = deepcopy_json(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback_copy, diagnostics
    except Exception as exc:
        diagnostics.append(f"invalid JSON ({type(exc).__name__}); reset to defaults")
        return fallback_copy, diagnostics

    if normalizer is not None:
        normalized = normalizer(data, diagnostics)
        if isinstance(normalized, dict):
            return normalized, diagnostics
    if isinstance(data, dict):
        return deepcopy_json(data), diagnostics

    diagnostics.append("root must be an object; reset to defaults")
    return fallback_copy, diagnostics


def read_json(
    path: Path,
    fallback: dict[str, Any],
    *,
    normalizer: Callable[[Any, list[str] | None], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data, _diagnostics = load_json_with_diagnostics(path, fallback, normalizer=normalizer)
    return data


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _ATOMIC_IO:
        if not write_json_atomic(path, data):
            raise OSError(f"Failed to write config atomically: {path}")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_persona_config(path: Path) -> dict[str, Any]:
    return read_json(path, DEFAULT_PERSONA_CONFIG, normalizer=normalize_persona_config)


def load_provider_registry(path: Path) -> dict[str, Any]:
    return read_json(path, DEFAULT_PROVIDER_REGISTRY, normalizer=normalize_provider_registry)


def load_voice_bindings(path: Path) -> dict[str, Any]:
    return read_json(path, DEFAULT_VOICE_BINDINGS, normalizer=normalize_voice_bindings)


def load_persona_config_with_diagnostics(path: Path) -> tuple[dict[str, Any], list[str]]:
    return load_json_with_diagnostics(path, DEFAULT_PERSONA_CONFIG, normalizer=normalize_persona_config)


def load_provider_registry_with_diagnostics(path: Path) -> tuple[dict[str, Any], list[str]]:
    return load_json_with_diagnostics(path, DEFAULT_PROVIDER_REGISTRY, normalizer=normalize_provider_registry)


def load_voice_bindings_with_diagnostics(path: Path) -> tuple[dict[str, Any], list[str]]:
    return load_json_with_diagnostics(path, DEFAULT_VOICE_BINDINGS, normalizer=normalize_voice_bindings)


def save_persona_config(path: Path, data: dict[str, Any]) -> Path:
    return write_json(path, normalize_persona_config(data))


def save_provider_registry(path: Path, data: dict[str, Any]) -> Path:
    return write_json(path, normalize_provider_registry(data))


def save_voice_bindings(path: Path, data: dict[str, Any]) -> Path:
    return write_json(path, normalize_voice_bindings(data))


def validate_persona_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["persona config must be an object"]
    personas = data.get("personas")
    if not isinstance(personas, list) or not personas:
        errors.append("personas must be a non-empty list")
        return errors
    ids = set()
    for idx, persona in enumerate(personas):
        if not isinstance(persona, dict):
            errors.append(f"personas[{idx}] must be an object")
            continue
        pid = persona.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"personas[{idx}].id is required")
            continue
        ids.add(pid)
        if persona.get("profile_summary") is not None and not isinstance(persona.get("profile_summary"), str):
            errors.append(f"personas[{idx}].profile_summary must be a string when present")
        scope = persona.get("scope")
        if scope not in {"global", "model"}:
            errors.append(f"personas[{idx}].scope must be global or model")
        if scope == "model" and not persona.get("model"):
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
    if not isinstance(data.get("imports", []), list):
        errors.append("imports must be a list")
    return errors


def ensure_personalization_scaffold(persona_path: Path, provider_path: Path, voice_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if not persona_path.exists():
        paths["persona"] = save_persona_config(persona_path, DEFAULT_PERSONA_CONFIG)
    else:
        paths["persona"] = save_persona_config(persona_path, load_persona_config(persona_path))
    if not provider_path.exists():
        paths["providers"] = save_provider_registry(provider_path, DEFAULT_PROVIDER_REGISTRY)
    else:
        paths["providers"] = save_provider_registry(provider_path, load_provider_registry(provider_path))
    if not voice_path.exists():
        paths["voice"] = save_voice_bindings(voice_path, DEFAULT_VOICE_BINDINGS)
    else:
        paths["voice"] = save_voice_bindings(voice_path, load_voice_bindings(voice_path))
    return paths


def validate_all_personalization_configs(persona_path: Path, provider_path: Path, voice_path: Path) -> dict[str, list[str]]:
    return {
        "persona": validate_persona_config(load_persona_config(persona_path)),
        "providers": validate_provider_registry(load_provider_registry(provider_path)),
        "voice": validate_voice_bindings(load_voice_bindings(voice_path)),
    }
