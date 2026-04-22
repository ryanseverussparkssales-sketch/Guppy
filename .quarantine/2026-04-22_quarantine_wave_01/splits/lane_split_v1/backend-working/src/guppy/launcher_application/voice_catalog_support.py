"""Pure support helpers for voice catalog readiness and summary text."""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Callable, Mapping


EngineCapabilities = dict[str, dict[str, str]]
SpecFinder = Callable[[str], object | None]


def build_engine_capabilities(
    engines: Mapping[str, object],
    *,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    spec_finder: SpecFinder | None = None,
) -> EngineCapabilities:
    capabilities: EngineCapabilities = {}
    for engine in engines.keys():
        ok, reason = engine_capability(
            str(engine),
            env=env,
            platform_name=platform_name,
            spec_finder=spec_finder,
        )
        capabilities[str(engine)] = {"ok": "1" if ok else "0", "reason": reason}
    return capabilities


def engine_capability(
    engine: str,
    *,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    spec_finder: SpecFinder | None = None,
) -> tuple[bool, str]:
    env_map = env if env is not None else os.environ
    active_platform = platform_name or sys.platform
    finder = spec_finder or importlib.util.find_spec

    if engine == "EDGE TTS":
        ok = finder("edge_tts") is not None
        return ok, "edge-tts installed" if ok else "missing edge-tts"
    if engine == "KOKORO":
        ok = finder("kokoro") is not None or finder("kokoro_onnx") is not None
        return ok, "kokoro runtime detected" if ok else "kokoro runtime missing"
    if engine == "WINDOWS SAPI":
        if not str(active_platform).startswith("win"):
            return False, "Windows only"
        ok = finder("pyttsx3") is not None
        return ok, "pyttsx3 available" if ok else "missing pyttsx3"
    if engine == "ELEVENLABS":
        api_key = str(env_map.get("ELEVENLABS_API_KEY", "") or "").strip()
        return bool(api_key), "API key present" if api_key else "missing ELEVENLABS_API_KEY"
    return False, "unknown engine"


def engine_is_available(
    engine_capabilities: Mapping[str, Mapping[str, str]],
    engine: str,
) -> tuple[bool, str]:
    info = engine_capabilities.get(engine, {})
    ok = str(info.get("ok", "") or "") == "1"
    return ok, str(info.get("reason", "") or "")


def build_engine_status_summary(
    engines: Mapping[str, object],
    engine_capabilities: Mapping[str, Mapping[str, str]],
) -> str:
    parts: list[str] = []
    for engine in engines.keys():
        ok, _ = engine_is_available(engine_capabilities, str(engine))
        parts.append(f"{engine}:{'READY' if ok else 'UNAVAILABLE'}")
    return "ENGINES: " + " | ".join(parts)


def build_bindings_summary_text(
    voice_bindings: Mapping[str, object] | None,
    *,
    default_choice: str,
) -> str:
    bindings = voice_bindings.get("bindings", {}) if isinstance(voice_bindings, Mapping) else {}
    by_persona = bindings.get("by_persona", {}) if isinstance(bindings.get("by_persona"), Mapping) else {}
    by_model = bindings.get("by_model", {}) if isinstance(bindings.get("by_model"), Mapping) else {}
    imports = voice_bindings.get("imports", []) if isinstance(voice_bindings, Mapping) else []
    parts = [
        f"Default: {default_choice.strip() or 'unset'}",
        f"Persona bindings: {len(by_persona)}",
        f"Model bindings: {len(by_model)}",
        f"Imports: {len(imports) if isinstance(imports, list) else 0}",
    ]
    return "Voice sources: " + " | ".join(parts)


def build_voice_evidence_text(
    *,
    active_engine: str,
    active_voice: str,
    default_choice: str,
    describe_voice_choice: Callable[[str, str], str],
    voice_bindings: Mapping[str, object] | None,
    engine_capabilities: Mapping[str, Mapping[str, str]],
) -> str:
    ok, reason = engine_is_available(engine_capabilities, active_engine)
    readiness = "ready" if ok else f"needs attention ({reason})"
    bindings = voice_bindings.get("bindings", {}) if isinstance(voice_bindings, Mapping) else {}
    by_persona = bindings.get("by_persona", {}) if isinstance(bindings.get("by_persona"), Mapping) else {}
    by_model = bindings.get("by_model", {}) if isinstance(bindings.get("by_model"), Mapping) else {}
    return (
        f"Ready now: selected voice {describe_voice_choice(active_engine, active_voice)} is {readiness}. "
        f"Default runtime voice stays {default_choice.strip() or 'unset'}. "
        f"Live bindings: {len(by_persona)} persona, {len(by_model)} model."
    )
