import json
from pathlib import Path
from typing import Any, Callable

try:
    from utils.safe_io import write_json_atomic
    _ATOMIC_IO = True
except Exception:
    _ATOMIC_IO = False

    def write_json_atomic(_path, _data):
        return False

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "runtime"

PERSONA_CONFIG_PATH = RUNTIME_DIR / "persona_config.json"
PROVIDER_REGISTRY_PATH = RUNTIME_DIR / "provider_registry.json"
VOICE_BINDINGS_PATH = RUNTIME_DIR / "voice_bindings.json"

MAIN_GUPPY_PERSONA_ID = "main_guppy"
MAIN_GUPPY_PROFILE_SUMMARY = (
    "- Ryan prefers concise, high-signal answers with low filler.\n"
    "- Keep the tone calm, exact, proactive, and quietly confident. Aim for a Jarvis-like feel without theatrical phrasing.\n"
    "- Preserve continuity across coding, launcher UX, automation, and workspace work so progress feels cumulative.\n"
    "- Keep Home calm and chat-first. Move heavier runtime, routing, recovery, and logs detail into App Mgmt or dedicated surfaces.\n"
    "- Never pretend an action, tool result, or state change happened unless it was actually executed."
)


DEFAULT_PERSONA_CONFIG: dict[str, Any] = {
    "version": 1,
    "default_persona_id": MAIN_GUPPY_PERSONA_ID,
    "personas": [
        {
            "id": MAIN_GUPPY_PERSONA_ID,
            "name": "Main Guppy",
            "scope": "global",
            "system_prompt": (
                "You are Main Guppy, Ryan's primary day-to-day assistant. "
                "Be calm, dependable, practical, and quietly confident. "
                "Keep the Jarvis-like feel understated and never theatrical."
            ),
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
            "profile_summary": MAIN_GUPPY_PROFILE_SUMMARY,
        }
    ],
    "assignments": {
        "global": MAIN_GUPPY_PERSONA_ID,
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
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "enabled": True,
            "api_base": "https://api.openai.com/v1",
            "auth_env": "OPENAI_API_KEY",
            "models": [
                {
                    "id": "gpt-4.1-mini",
                    "label": "GPT-4.1 Mini",
                    "enabled": True,
                    "context_window": 128000,
                    "speed_tier": "fast",
                    "tags": ["general", "cheap"],
                    "pricing": {
                        "tier": "cheap",
                    },
                },
                {
                    "id": "gpt-4.1",
                    "label": "GPT-4.1",
                    "enabled": True,
                    "context_window": 128000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {
                        "tier": "premium",
                    },
                },
            ],
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "enabled": True,
            "api_base": "https://generativelanguage.googleapis.com/v1beta",
            "auth_env": "GEMINI_API_KEY",
            "models": [
                {
                    "id": "gemini-2.0-flash",
                    "label": "Gemini 2.0 Flash",
                    "enabled": True,
                    "context_window": 1000000,
                    "speed_tier": "fast",
                    "tags": ["multimodal", "cheap"],
                    "pricing": {
                        "tier": "cheap",
                    },
                },
                {
                    "id": "gemini-2.5-pro",
                    "label": "Gemini 2.5 Pro",
                    "enabled": True,
                    "context_window": 1000000,
                    "speed_tier": "balanced",
                    "tags": ["reasoning"],
                    "pricing": {
                        "tier": "premium",
                    },
                },
            ],
        },
        {
            "id": "ollama_api",
            "name": "Ollama API (Cloud/Remote)",
            "enabled": True,
            "api_base": "https://ollama.com/api",
            "auth_env": "OLLAMA_API_KEY",
            "models": [
                {
                    "id": "llama3.1:8b",
                    "label": "Llama 3.1 8B",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["general"],
                    "pricing": {
                        "tier": "cheap",
                    },
                }
            ],
        },
        {
            "id": "lmstudio_local",
            "name": "LM Studio (Local)",
            "enabled": True,
            "api_base": "http://127.0.0.1:1234/v1",
            "auth_env": "",
            "models": [
                {
                    "id": "local-model",
                    "label": "LM Studio Active Model",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local"],
                    "pricing": {
                        "tier": "local",
                    },
                }
            ],
        },
        {
            "id": "local_harness",
            "name": "Local Harness",
            "enabled": True,
            "api_base": "http://127.0.0.1:8001",
            "auth_env": "",
            "models": [
                {
                    "id": "harness-default",
                    "label": "Harness Default",
                    "enabled": True,
                    "context_window": 0,
                    "speed_tier": "balanced",
                    "tags": ["local", "harness"],
                    "pricing": {
                        "tier": "local",
                    },
                }
            ],
        },
        {
            "id": "local",
            "name": "Ollama (Local)",
            "enabled": True,
            "api_base": "http://127.0.0.1:11434",
            "auth_env": "",
            "models": [
                {
                    "id": "guppy",
                    "label": "Guppy",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["local", "default"],
                    "pricing": {
                        "tier": "local",
                    },
                },
                {
                    "id": "guppy-fast",
                    "label": "Guppy Fast",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "fast",
                    "tags": ["local", "fast"],
                    "pricing": {
                        "tier": "local",
                    },
                },
                {
                    "id": "guppy-code",
                    "label": "Guppy Code",
                    "enabled": True,
                    "context_window": 32768,
                    "speed_tier": "balanced",
                    "tags": ["local", "code"],
                    "pricing": {
                        "tier": "local",
                    },
                },
            ],
        },
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
        "by_persona": {
            MAIN_GUPPY_PERSONA_ID: {
                "engine": "EDGE TTS",
                "voice_id": "en-GB-RyanNeural",
            }
        },
    },
    "imports": [],
}

LOCAL_MODEL_IDS: list[str] = [
    "guppy",
    "guppy-fast",
    "guppy-code",
    "guppy-teach",
    "vault-scraper",
]


def _deepcopy_json(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


def _unique_strings_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def _normalize_persona_config(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = _deepcopy_json(data) if isinstance(data, dict) else _deepcopy_json(DEFAULT_PERSONA_CONFIG)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    personas = cfg.get("personas")
    if not isinstance(personas, list) or not personas:
        notes.append("personas must be a non-empty list; reset to defaults")
        cfg["personas"] = _deepcopy_json(DEFAULT_PERSONA_CONFIG)["personas"]
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
            traits = persona.get("traits")
            if not isinstance(traits, dict):
                notes.append(f"persona {persona.get('id')} traits missing or invalid; reset to defaults")
                persona["traits"] = {
                    "tone": "butler",
                    "verbosity": "medium",
                    "response_style": "direct",
                }
            teaching = persona.get("teaching")
            if not isinstance(teaching, dict):
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
        cfg["personas"] = cleaned or _deepcopy_json(DEFAULT_PERSONA_CONFIG)["personas"]

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


def _normalize_provider_registry(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = _deepcopy_json(data) if isinstance(data, dict) else _deepcopy_json(DEFAULT_PROVIDER_REGISTRY)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    providers = cfg.get("providers")
    if not isinstance(providers, list) or not providers:
        notes.append("providers must be a non-empty list; reset to defaults")
        cfg["providers"] = _deepcopy_json(DEFAULT_PROVIDER_REGISTRY)["providers"]
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
            cleaned_providers.append(provider)
        if dropped_providers:
            notes.append(f"ignored {dropped_providers} invalid provider entries")
        cfg["providers"] = cleaned_providers or _deepcopy_json(DEFAULT_PROVIDER_REGISTRY)["providers"]

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

    defaults = _deepcopy_json(DEFAULT_PROVIDER_REGISTRY)
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
            target
            for target in fallback_chain
            if isinstance(target, str) and (target in route_keys or target == "local/guppy")
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


def _normalize_voice_bindings(data: Any, diagnostics: list[str] | None = None) -> dict[str, Any]:
    notes = diagnostics if diagnostics is not None else []
    cfg = _deepcopy_json(data) if isinstance(data, dict) else _deepcopy_json(DEFAULT_VOICE_BINDINGS)
    if not isinstance(data, dict):
        notes.append("root must be an object; reset to defaults")

    defaults = cfg.get("defaults")
    if not isinstance(defaults, dict):
        notes.append("defaults must be an object; reset missing fields to defaults")
        defaults = {}
    if not isinstance(defaults.get("engine"), str) or not defaults.get("engine"):
        notes.append("defaults.engine missing or invalid; reset to default")
        defaults["engine"] = DEFAULT_VOICE_BINDINGS["defaults"]["engine"]
    if not isinstance(defaults.get("voice_id"), str) or not defaults.get("voice_id"):
        notes.append("defaults.voice_id missing or invalid; reset to default")
        defaults["voice_id"] = DEFAULT_VOICE_BINDINGS["defaults"]["voice_id"]
    cfg["defaults"] = defaults

    bindings = cfg.get("bindings")
    if not isinstance(bindings, dict):
        notes.append("bindings must be an object; reset to defaults")
        bindings = {}
    for key in ("by_model", "by_persona"):
        mapping = bindings.get(key)
        if not isinstance(mapping, dict):
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


def _load_json_with_diagnostics(
    path: Path,
    fallback: dict[str, Any],
    *,
    normalizer: Callable[[Any, list[str] | None], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    diagnostics: list[str] = []
    fallback_copy = _deepcopy_json(fallback)
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
        return _deepcopy_json(data), diagnostics

    diagnostics.append("root must be an object; reset to defaults")
    return fallback_copy, diagnostics


def _read_json(
    path: Path,
    fallback: dict[str, Any],
    *,
    normalizer: Callable[[Any, Any], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data, _diagnostics = _load_json_with_diagnostics(path, fallback, normalizer=normalizer)
    return data


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _ATOMIC_IO:
        if not write_json_atomic(path, data):
            raise OSError(f"Failed to write config atomically: {path}")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_persona_config() -> dict[str, Any]:
    return _read_json(
        PERSONA_CONFIG_PATH,
        DEFAULT_PERSONA_CONFIG,
        normalizer=_normalize_persona_config,
    )


def load_provider_registry() -> dict[str, Any]:
    return _read_json(
        PROVIDER_REGISTRY_PATH,
        DEFAULT_PROVIDER_REGISTRY,
        normalizer=_normalize_provider_registry,
    )


def load_voice_bindings() -> dict[str, Any]:
    return _read_json(
        VOICE_BINDINGS_PATH,
        DEFAULT_VOICE_BINDINGS,
        normalizer=_normalize_voice_bindings,
    )


def load_persona_config_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _load_json_with_diagnostics(
        PERSONA_CONFIG_PATH,
        DEFAULT_PERSONA_CONFIG,
        normalizer=_normalize_persona_config,
    )


def load_provider_registry_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _load_json_with_diagnostics(
        PROVIDER_REGISTRY_PATH,
        DEFAULT_PROVIDER_REGISTRY,
        normalizer=_normalize_provider_registry,
    )


def load_voice_bindings_with_diagnostics() -> tuple[dict[str, Any], list[str]]:
    return _load_json_with_diagnostics(
        VOICE_BINDINGS_PATH,
        DEFAULT_VOICE_BINDINGS,
        normalizer=_normalize_voice_bindings,
    )


def save_persona_config(data: dict[str, Any]) -> Path:
    return _write_json(PERSONA_CONFIG_PATH, _normalize_persona_config(data))


def save_provider_registry(data: dict[str, Any]) -> Path:
    return _write_json(PROVIDER_REGISTRY_PATH, _normalize_provider_registry(data))


def save_voice_bindings(data: dict[str, Any]) -> Path:
    return _write_json(VOICE_BINDINGS_PATH, _normalize_voice_bindings(data))


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
        profile_summary = p.get("profile_summary")
        if profile_summary is not None and not isinstance(profile_summary, str):
            errors.append(f"personas[{idx}].profile_summary must be a string when present")
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
    else:
        normalized = load_persona_config()
        paths["persona"] = save_persona_config(normalized)
    if not PROVIDER_REGISTRY_PATH.exists():
        paths["providers"] = save_provider_registry(DEFAULT_PROVIDER_REGISTRY)
    else:
        normalized = load_provider_registry()
        paths["providers"] = save_provider_registry(normalized)
    if not VOICE_BINDINGS_PATH.exists():
        paths["voice"] = save_voice_bindings(DEFAULT_VOICE_BINDINGS)
    else:
        normalized = load_voice_bindings()
        paths["voice"] = save_voice_bindings(normalized)
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


def list_model_ids(provider_registry: dict[str, Any] | None = None, *, include_local: bool = True) -> list[str]:
    registry = provider_registry if isinstance(provider_registry, dict) else load_provider_registry()
    model_ids: list[str] = list(LOCAL_MODEL_IDS) if include_local else []
    providers = registry.get("providers", []) if isinstance(registry, dict) else []
    if isinstance(providers, list):
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            models = provider.get("models", [])
            if not isinstance(models, list):
                continue
            for model in models:
                if not isinstance(model, dict):
                    continue
                model_id = str(model.get("id", "") or "").strip()
                if model_id:
                    model_ids.append(model_id)
    return _unique_strings_in_order(model_ids)


def list_persona_choices(persona_config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    cfg = persona_config if isinstance(persona_config, dict) else load_persona_config()
    personas = cfg.get("personas", []) if isinstance(cfg, dict) else []
    choices: list[dict[str, str]] = []
    if isinstance(personas, list):
        for persona in personas:
            if not isinstance(persona, dict):
                continue
            persona_id = str(persona.get("id", "") or "").strip()
            if not persona_id:
                continue
            name = str(persona.get("name", persona_id) or persona_id).strip() or persona_id
            scope = str(persona.get("scope", "global") or "global").strip().lower() or "global"
            model = str(persona.get("model", "") or "").strip()
            suffix = "GLOBAL" if scope != "model" else f"MODEL:{model or 'unbound'}"
            choices.append(
                {
                    "id": persona_id,
                    "name": name,
                    "scope": scope,
                    "model": model,
                    "label": f"{name} [{suffix}]",
                }
            )
    if choices:
        return choices
    return [
        {
            "id": MAIN_GUPPY_PERSONA_ID,
            "name": "Main Guppy",
            "scope": "global",
            "model": "",
            "label": "Main Guppy [GLOBAL]",
        }
    ]


def _persona_lookup_maps(persona_config: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for entry in list_persona_choices(persona_config):
        persona = next(
            (
                item
                for item in persona_config.get("personas", [])
                if isinstance(item, dict) and str(item.get("id", "")).strip() == entry["id"]
            ),
            None,
        )
        if not isinstance(persona, dict):
            continue
        by_id[entry["id"].lower()] = persona
        by_name[entry["name"].lower()] = persona
    return by_id, by_name


def resolve_persona_profile(
    *,
    requested_persona: str = "",
    model_id: str = "",
    persona_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = persona_config if isinstance(persona_config, dict) else load_persona_config()
    by_id, by_name = _persona_lookup_maps(cfg)
    requested_key = str(requested_persona or "").strip().lower()
    if requested_key:
        explicit = by_id.get(requested_key) or by_name.get(requested_key)
        if isinstance(explicit, dict):
            return _deepcopy_json(explicit)

    assignments = cfg.get("assignments", {}) if isinstance(cfg, dict) else {}
    by_model = assignments.get("by_model", {}) if isinstance(assignments, dict) else {}
    if isinstance(by_model, dict):
        model_key = str(model_id or "").strip()
        if model_key:
            persona_id = str(by_model.get(model_key, "") or "").strip().lower()
            model_persona = by_id.get(persona_id)
            if isinstance(model_persona, dict):
                return _deepcopy_json(model_persona)

    global_id = ""
    if isinstance(assignments, dict):
        global_id = str(assignments.get("global", "") or "").strip().lower()
    if not global_id:
        global_id = str(cfg.get("default_persona_id", "") or "").strip().lower()
    resolved = by_id.get(global_id)
    if isinstance(resolved, dict):
        return _deepcopy_json(resolved)

    personas = cfg.get("personas", []) if isinstance(cfg, dict) else []
    for persona in personas:
        if isinstance(persona, dict):
            return _deepcopy_json(persona)
    return _deepcopy_json(DEFAULT_PERSONA_CONFIG["personas"][0])


def build_persona_prompt_overlay(
    *,
    requested_persona: str = "",
    model_id: str = "",
    persona_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    persona = resolve_persona_profile(
        requested_persona=requested_persona,
        model_id=model_id,
        persona_config=persona_config,
    )
    if not isinstance(persona, dict) or not persona:
        return {}, ""

    traits = persona.get("traits", {}) if isinstance(persona.get("traits"), dict) else {}
    teaching = persona.get("teaching", {}) if isinstance(persona.get("teaching"), dict) else {}
    scope = str(persona.get("scope", "global") or "global").strip().lower() or "global"
    scope_suffix = ""
    if scope == "model":
        bound_model = str(persona.get("model", "") or "").strip()
        scope_suffix = f" bound to model {bound_model}." if bound_model else "."
    else:
        scope_suffix = "."

    lines = [
        "ACTIVE PERSONA PROFILE:",
        f"- Persona name: {str(persona.get('name', 'Guppy')).strip() or 'Guppy'}",
        f"- Scope: {scope}{scope_suffix}",
        f"- Tone: {str(traits.get('tone', 'butler') or 'butler').strip()}",
        f"- Verbosity: {str(traits.get('verbosity', 'medium') or 'medium').strip()}",
        f"- Response style: {str(traits.get('response_style', 'direct') or 'direct').strip()}",
    ]

    teaching_enabled = bool(teaching.get("enabled", True))
    socratic_bias = int(teaching.get("socratic_bias", 35) or 35)
    example_bias = int(teaching.get("example_bias", 60) or 60)
    if teaching_enabled:
        lines.append(
            f"- Teaching guidance: teaching is enabled with socratic bias {socratic_bias}/100 and example bias {example_bias}/100."
        )
    else:
        lines.append("- Teaching guidance: answer directly unless the user explicitly asks for teaching or explanation.")

    system_prompt = str(persona.get("system_prompt", "") or "").strip()
    if system_prompt:
        lines.append("- Persona prompt override:")
        lines.append(system_prompt)

    profile_summary = str(persona.get("profile_summary", "") or "").strip()
    if profile_summary:
        lines.append("- Curated long-term profile summary:")
        for raw_line in profile_summary.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lines.append(f"  {line}")

    lines.append("- Apply this persona as a style and teaching overlay while preserving tool-use honesty and safety rules.")
    return persona, "\n".join(lines)


def _mapping_lookup(mapping: dict[str, Any], key: str) -> dict[str, Any] | None:
    direct = mapping.get(key)
    if isinstance(direct, dict):
        return direct
    lowered = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key or "").strip().lower() == lowered and isinstance(value, dict):
            return value
    return None


def resolve_voice_binding(
    *,
    persona_id: str = "",
    model_id: str = "",
    voice_bindings: dict[str, Any] | None = None,
) -> dict[str, str]:
    bindings = voice_bindings if isinstance(voice_bindings, dict) else load_voice_bindings()
    defaults = bindings.get("defaults", {}) if isinstance(bindings.get("defaults"), dict) else {}
    mappings = bindings.get("bindings", {}) if isinstance(bindings.get("bindings"), dict) else {}
    by_model = mappings.get("by_model", {}) if isinstance(mappings.get("by_model"), dict) else {}
    by_persona = mappings.get("by_persona", {}) if isinstance(mappings.get("by_persona"), dict) else {}

    resolved: dict[str, Any] | None = None
    source = "default"
    model_key = str(model_id or "").strip()
    persona_key = str(persona_id or "").strip()

    if model_key:
        resolved = _mapping_lookup(by_model, model_key)
        if resolved is not None:
            source = "model"
    if resolved is None and persona_key:
        resolved = _mapping_lookup(by_persona, persona_key)
        if resolved is not None:
            source = "persona"
    if resolved is None:
        resolved = defaults if isinstance(defaults, dict) else {}

    engine = str(resolved.get("engine", defaults.get("engine", "")) or defaults.get("engine", "")).strip()
    voice_id = str(resolved.get("voice_id", defaults.get("voice_id", "")) or defaults.get("voice_id", "")).strip()
    return {
        "engine": engine or str(DEFAULT_VOICE_BINDINGS["defaults"]["engine"]),
        "voice_id": voice_id or str(DEFAULT_VOICE_BINDINGS["defaults"]["voice_id"]),
        "source": source,
    }
