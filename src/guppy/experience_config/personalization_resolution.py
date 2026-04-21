"""Persona and voice resolution helpers."""

from __future__ import annotations

from typing import Any

from src.guppy.experience_config.personalization_defaults import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_PERSONA_CONFIG,
    DEFAULT_VOICE_BINDINGS,
    LOCAL_MODEL_IDS,
)
from src.guppy.experience_config.personalization_storage import deepcopy_json, unique_strings_in_order


def list_model_ids(provider_registry: dict[str, Any] | None = None, *, include_local: bool = True) -> list[str]:
    registry = provider_registry if isinstance(provider_registry, dict) else {}
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
    return unique_strings_in_order(model_ids)


def list_persona_choices(persona_config: dict[str, Any] | None = None) -> list[dict[str, str]]:
    cfg = persona_config if isinstance(persona_config, dict) else deepcopy_json(DEFAULT_PERSONA_CONFIG)
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
            "id": DEFAULT_PERSONA_CONFIG["personas"][0]["id"],
            "name": DEFAULT_ASSISTANT_NAME,
            "scope": "global",
            "model": "",
            "label": f"{DEFAULT_ASSISTANT_NAME} [GLOBAL]",
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
    cfg = persona_config if isinstance(persona_config, dict) else deepcopy_json(DEFAULT_PERSONA_CONFIG)
    by_id, by_name = _persona_lookup_maps(cfg)
    requested_key = str(requested_persona or "").strip().lower()
    if requested_key:
        explicit = by_id.get(requested_key) or by_name.get(requested_key)
        if isinstance(explicit, dict):
            return deepcopy_json(explicit)

    assignments = cfg.get("assignments", {}) if isinstance(cfg, dict) else {}
    by_model = assignments.get("by_model", {}) if isinstance(assignments, dict) else {}
    if isinstance(by_model, dict):
        model_key = str(model_id or "").strip()
        if model_key:
            persona_id = str(by_model.get(model_key, "") or "").strip().lower()
            model_persona = by_id.get(persona_id)
            if isinstance(model_persona, dict):
                return deepcopy_json(model_persona)

    global_id = ""
    if isinstance(assignments, dict):
        global_id = str(assignments.get("global", "") or "").strip().lower()
    if not global_id:
        global_id = str(cfg.get("default_persona_id", "") or "").strip().lower()
    resolved = by_id.get(global_id)
    if isinstance(resolved, dict):
        return deepcopy_json(resolved)

    personas = cfg.get("personas", []) if isinstance(cfg, dict) else []
    for persona in personas:
        if isinstance(persona, dict):
            return deepcopy_json(persona)
    return deepcopy_json(DEFAULT_PERSONA_CONFIG["personas"][0])


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
            if line:
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
    bindings = voice_bindings if isinstance(voice_bindings, dict) else deepcopy_json(DEFAULT_VOICE_BINDINGS)
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
