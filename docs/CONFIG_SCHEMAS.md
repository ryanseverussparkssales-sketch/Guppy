# Personalization Config Schemas

This document defines the scaffolded config contracts for the personalization track:

- Persona Editor (global and per-model personas)
- Freemium provider/model registry
- Voice bindings and imports

Schema files:

- docs/schemas/persona.schema.json
- docs/schemas/provider_registry.schema.json
- docs/schemas/voice_binding.schema.json

Runtime config files (scaffold targets):

- runtime/persona_config.json
- runtime/provider_registry.json
- runtime/voice_bindings.json

## Persona config

Purpose:
- Define persona behavior blocks and assign them globally or by model.

Core fields:
- version
- default_persona_id
- personas[]
  - id, name, scope (global|model), model (required when scope=model)
  - system_prompt
  - traits: tone, verbosity, response_style
  - teaching: enabled, socratic_bias, example_bias
- assignments
  - global
  - by_model mapping

## Provider registry

Purpose:
- Define selectable providers/models and routing defaults for simple/complex/teaching tasks.

Core fields:
- version
- default_route
- providers[]
  - id, name, enabled, api_base, auth_env
  - models[]
    - id, label, enabled, context_window, speed_tier, tags, pricing
- routes
  - simple, complex, teaching
  - fallback_chain[]

## Voice bindings

Purpose:
- Bind specific voices to models/personas and hold imported voice metadata.

Core fields:
- version
- defaults: engine, voice_id
- bindings
  - by_model
  - by_persona
- imports[]
  - id, engine, label, source, sample_rate_hz, language, license, enabled

## Loader and validator scaffold

See:
- utils/personalization_config.py

Key functions:
- ensure_personalization_scaffold()
- load_persona_config()
- load_provider_registry()
- load_voice_bindings()
- validate_persona_config(...)
- validate_provider_registry(...)
- validate_voice_bindings(...)
- validate_all_personalization_configs()

Notes:
- Validation is intentionally lightweight and stdlib-only in this scaffold.
- This is enough to begin UI and API integration without schema ambiguity.
