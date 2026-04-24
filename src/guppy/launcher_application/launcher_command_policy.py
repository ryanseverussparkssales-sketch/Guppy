"""Launcher assistant command policy and model-context helpers.

Extracted from launcher_command_flow as part of the ongoing shell decomposition.
"""
from __future__ import annotations

import os
import re


def humanize_chat_error(raw: str) -> str:
    txt = (raw or "").strip()
    low = txt.lower()
    if "still warming up" in low or "restarted" in low and "retry now" in low:
        return "The local service restarted, but the first reply is still warming up. Please retry now."
    if "http 401" in low or "unauthorized" in low or "jwt_expired" in low:
        return "Authentication expired. Please retry now."
    if "http 403" in low:
        return "This action is not permitted right now."
    if "http 429" in low:
        return "Too many requests at once. Please wait a few seconds and retry."
    if "timed out" in low or "timeout" in low:
        return "The request timed out before a response was received. Please try again."
    if "network error" in low or "connection refused" in low:
        return "Could not reach the local API service. Check that the API is running, then retry."
    if (
        "local-only mode failed" in low
        or "local-only retry failed" in low
        or "ollama" in low and ("not running" in low or "unavailable" in low or "could not contact" in low)
    ):
        return "Local model service is unavailable. Start Ollama or switch to Claude mode."
    if "ollama" in low and ("not running" in low or "unavailable" in low or "could not contact" in low):
        return "Local model service is unavailable. Start Ollama or switch to Claude mode."
    return "The assistant request failed. Please retry."


def chat_timeout_for_request(mode: str, command: str = "") -> float:
    m = (mode or "auto").strip().lower()
    base = 25.0 if m in {"claude", "auto", "teaching"} else 35.0 if m in {"local", "ollama", "code", "vault"} else 30.0
    text = (command or "").strip().lower()
    if not text:
        return base
    if any(
        token in text
        for token in (
            "diagnostic",
            "diagnose",
            "health check",
            "system check",
            "audit",
            "scan",
            "debug",
            "trace",
            "investigate",
        )
    ):
        return max(base, 60.0)
    if any(token in text for token in ("review", "triage", "analyze", "search the repo", "walk the codebase")):
        return max(base, 45.0)
    if len(text) > 220:
        return max(base, 45.0)
    return base


def required_local_model_for_mode(mode: str) -> str | None:
    m = (mode or "").strip().lower()
    if m in {"local", "ollama"}:
        return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    if m == "teaching":
        return (os.environ.get("GUPPY_LOCAL_TEACH_MODEL", "guppy-teach") or "guppy-teach").strip()
    if m == "code":
        return (os.environ.get("GUPPY_LOCAL_CODE_MODEL", "guppy-code") or "guppy-code").strip()
    if m == "vault":
        return (os.environ.get("GUPPY_LOCAL_VAULT_MODEL", "vault-scraper") or "vault-scraper").strip()
    return None


def assistant_model_id(mode: str, active_model: str = "") -> str:
    candidate = str(active_model or "").strip()
    if candidate and candidate not in {"-", "—"}:
        return candidate
    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode == "claude":
        return (
            os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
            or "claude-haiku-4-5-20251001"
        ).strip()
    required_local = required_local_model_for_mode(normalized_mode)
    if required_local:
        return required_local
    return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()


def derive_topbar_model_context(
    *,
    route_text: str,
    runtime: object,
    main_model: str = "",
    support_model: str = "",
) -> dict[str, str]:
    using_match = re.search(r"\busing\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)
    backup_match = re.search(r"\bbackup\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)
    route_match = re.search(r"\bvia\s+([A-Za-z0-9._:/-]+)", route_text, flags=re.IGNORECASE)

    normalized_main = str(main_model or getattr(runtime, "chat_model", "") or getattr(runtime, "model", "") or "").strip()
    normalized_support = str(support_model or (backup_match.group(1) if backup_match else "")).strip()
    if not normalized_main and using_match is not None:
        normalized_main = str(using_match.group(1) or "").strip()
    backend = str(getattr(runtime, "backend", "") or "").strip().lower()
    route_name = str(route_match.group(1) if route_match else "").strip().upper()
    return {
        "main_model": normalized_main,
        "support_model": normalized_support,
        "backend": backend,
        "route": route_name,
    }


def build_shell_model_loadout_summary(
    *,
    active_model: str = "",
    runtime_backend: str = "",
    settings_payload: dict[str, object] | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    settings = settings_payload if isinstance(settings_payload, dict) else {}
    env = environment if isinstance(environment, dict) else dict(os.environ)
    backend = (
        str(settings.get("local_runtime_backend", "") or "").strip()
        or str(runtime_backend or "").strip()
        or str(env.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama") or "ollama").strip()
        or "ollama"
    )
    main_model = (
        str(settings.get("local_main_model", "") or "").strip()
        or str(env.get("GUPPY_MAIN_MODEL", "") or "").strip()
        or str(active_model or "").strip()
        or str(env.get("OLLAMA_MODEL", "") or "").strip()
        or "unset"
    )
    sub_a_model = (
        str(settings.get("local_sub_model_a", "") or "").strip()
        or str(env.get("GUPPY_SUB_MODEL_A", "") or "").strip()
        or str(env.get("GUPPY_LOCAL_FAST_MODEL", "") or "").strip()
        or "unset"
    )
    sub_b_model = (
        str(settings.get("local_sub_model_b", "") or "").strip()
        or str(env.get("GUPPY_SUB_MODEL_B", "") or "").strip()
        or str(env.get("GUPPY_LOCAL_CODE_MODEL", "") or "").strip()
        or "unset"
    )
    return (
        f"MODELS / {backend.upper()} / "
        f"MAIN {main_model} / SUB A {sub_a_model} / SUB B {sub_b_model}"
    )