"""Pure presenter helpers for the experience-config domain.

Handles voice option building, voice binding summaries, and personalization
state assembly — all without Qt or I/O dependencies.
"""
from __future__ import annotations

import importlib.util
import os
from typing import Any


def voice_option_choices(voice_bindings: dict) -> list[tuple[str, str]]:
    """Build (label, value) pairs from a voice-bindings config dict."""
    options: list[tuple[str, str]] = [("Default", "default")]
    seen: set[str] = {"default"}

    def _add(engine: str, voice_id: str) -> None:
        value = f"{engine}:{voice_id}"
        if not engine or not voice_id or value in seen:
            return
        seen.add(value)
        options.append((f"{engine} / {voice_id}", value))

    raw = voice_bindings if isinstance(voice_bindings, dict) else {}
    defaults = raw.get("defaults", {})
    if isinstance(defaults, dict):
        _add(str(defaults.get("engine", "")).strip(), str(defaults.get("voice_id", "")).strip())

    bindings = raw.get("bindings", {})
    if isinstance(bindings, dict):
        for mapping_key in ("by_persona", "by_model"):
            mapping = bindings.get(mapping_key, {})
            if not isinstance(mapping, dict):
                continue
            for item in mapping.values():
                if isinstance(item, dict):
                    _add(str(item.get("engine", "")).strip(), str(item.get("voice_id", "")).strip())

    imports = raw.get("imports", [])
    if isinstance(imports, list):
        for item in imports:
            if isinstance(item, dict):
                _add(str(item.get("engine", "")).strip(), str(item.get("voice_id", "")).strip())

    return options


def voice_binding_summary(choice: dict[str, Any] | None) -> str:
    """Return a short human-readable readiness string for a resolved voice binding."""
    payload = choice if isinstance(choice, dict) else {}
    engine = str(payload.get("engine", "edge")).strip() or "edge"
    source = str(payload.get("source", "default")).strip().lower() or "default"
    source_label = {
        "default": "default voice",
        "persona": "persona voice",
        "model": "model voice",
    }.get(source, "voice setting")
    readiness = "ready"
    if engine.upper() == "ELEVENLABS":
        if not (os.environ.get("ELEVENLABS_API_KEY", "") or "").strip():
            readiness = "needs API key"
    elif engine.upper() == "EDGE TTS":
        try:
            readiness = "ready" if importlib.util.find_spec("edge_tts") is not None else "preview dependency missing"
        except Exception:
            readiness = "ready"
    return f"{engine} from {source_label} ({readiness})"


def build_persona_options(persona_choices: list[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Convert a list of persona-choice dicts into (label, id) option tuples."""
    return tuple(
        (item.get("name", item.get("id", "guppy")), item.get("id", "guppy"))
        for item in persona_choices
        if isinstance(item, dict)
    )
