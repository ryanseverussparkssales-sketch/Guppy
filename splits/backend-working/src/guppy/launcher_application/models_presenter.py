"""Pure presentation helpers for the Models hub runtime and readiness copy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ModelsTextState:
    text: str
    tone: str = "info"


def build_models_active_identity_text(active_model: str) -> str:
    selected = str(active_model or "").strip() or "not set"
    return f"CURRENT MODEL: {selected}"


def build_models_runtime_identity_text(runtime_backend: str) -> str:
    backend = _normalized_backend(runtime_backend).upper()
    return f"LOCAL RUNTIME: {backend}"


def build_models_library_hint_text(
    *,
    query: str = "",
    local_matches: int = 0,
    cloud_matches: int = 0,
) -> str:
    if str(query or "").strip():
        return (
            f"Showing {local_matches} local and {cloud_matches} cloud matches. "
            "Open Runtime only if you want to change the local engine or route slots."
        )
    return (
        "Pick the model for this assistant session. "
        "Persona and assistant naming stay separate in Settings."
    )


def _normalized_backend(value: str) -> str:
    cleaned = str(value or "ollama").strip().lower()
    if cleaned == "lemonade":
        return "lemonade"
    if cleaned in {"lm studio", "lmstudio", "lmstudio_local"}:
        return "lmstudio"
    if cleaned in {"local harness", "local_harness", "harness"}:
        return "local_harness"
    return "ollama"


def _normalized_model_name(value: str) -> str:
    return str(value or "").strip().lower()


def _string_list(values: object, *, upper: bool = False) -> list[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, bytearray)):
        return []
    items = [str(item).strip() for item in values if str(item).strip()]
    return [item.upper() for item in items] if upper else items


def _friendly_slot_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "fast": "DAILY SLOT",
        "complex": "HEAVY SLOT",
        "teach": "TEACHING SLOT",
        "teaching": "TEACHING SLOT",
        "code": "CODING SLOT",
        "vault": "RESEARCH SLOT",
        "sub_a": "SPAWNED MODEL A",
        "sub_b": "SPAWNED MODEL B",
        "main": "MAIN MODEL",
    }.get(normalized, str(value or "").strip().upper())


def _slot_list(values: object) -> list[str]:
    return [_friendly_slot_label(item) for item in _string_list(values)]


def normalize_models_policy(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def build_models_runtime_policy_state(
    policy_payload: Mapping[str, Any] | None,
    *,
    selected_backend: str,
) -> ModelsTextState:
    policy = normalize_models_policy(policy_payload)
    if not policy:
        return ModelsTextState(
            text="Policy view unavailable. Launcher will fall back to live runtime evidence only.",
            tone="muted",
        )

    runtime_baseline = str(policy.get("runtime_baseline", "ollama") or "ollama").strip().upper()
    memory_baseline = str(policy.get("memory_baseline", "semantic-sqlite") or "semantic-sqlite").strip()
    daily = str(policy.get("daily_model_promotion_candidate", "") or "").strip()
    heavy = str(policy.get("heavy_model_candidate", "") or "").strip()
    rejected = _string_list(policy.get("daily_lane_rejected_models", []))
    challengers = _string_list(policy.get("runtime_challenger_ids", []), upper=True)
    selected = _normalized_backend(selected_backend)

    lines = [
        f"FINALIZED POLICY: runtime baseline {runtime_baseline} | daily lane candidate {daily or 'unset'} | heavy fallback {heavy or 'unset'}",
        f"Memory baseline: {memory_baseline}",
    ]
    if rejected:
        lines.append("Daily-lane rejects on this machine: " + ", ".join(rejected))
    if challengers:
        lines.append("Runtime challengers only: " + ", ".join(challengers))

    tone = "info"
    if selected != "ollama":
        lines.append(
            "Current editor selection is a challenger runtime. Save it only if you are intentionally testing the opt-in lane."
        )
        tone = "warning"

    return ModelsTextState(text="\n".join(lines), tone=tone)


def build_models_runtime_summary_text(
    *,
    editor_backend: str,
    saved_backend: str,
    available_model_names: Iterable[str],
    lemonade_mapping: Iterable[str] = (),
) -> str:
    names = [str(item).strip() for item in available_model_names if str(item).strip()]
    mapping = [str(item).strip() for item in lemonade_mapping if str(item).strip()]
    editor = _normalized_backend(editor_backend)
    saved = _normalized_backend(saved_backend)
    pending_save = editor != saved

    if editor == "lemonade":
        text = "Lemonade is opt-in for the local lane. Map the saved runtime slots to downloaded Lemonade model ids here."
        text += "\nCurrent Lemonade mapping: " + (" | ".join(mapping) if mapping else "none saved yet")
        if names:
            text += f"\nDownloaded Lemonade models visible now: {', '.join(names[:6])}"
    elif editor == "lmstudio":
        text = "LM Studio is a supported local lane. Turn on the LM Studio local server, then refresh to load models here."
        if names:
            text += f"\nVisible LM Studio models: {', '.join(names[:6])}"
        else:
            text += "\nExpected setup: LM Studio local server on http://127.0.0.1:1234/v1"
    elif editor == "local_harness":
        text = "Local Harness is the development OpenAI-compatible lane. Start the harness, then refresh to load any reported models here."
        if names:
            text += f"\nVisible harness models: {', '.join(names[:6])}"
        else:
            text += "\nExpected setup: local harness on http://127.0.0.1:8001"
    else:
        text = (
            "Ollama remains the default local runtime. Local cards reflect direct Ollama tags, "
            "and the runtime controls switch to LM Studio, Local Harness, or Lemonade when you choose those lanes."
        )
        if names:
            text += f"\nVisible Ollama tags: {', '.join(names[:6])}"

    text += f"\nSaved local lane: {saved.upper()}"
    if pending_save:
        text += f" | editor selection pending save: {editor.upper()}"
    return text


def build_models_library_summary_text(
    policy_payload: Mapping[str, Any] | None,
    *,
    active_model: str,
    local_count: int,
    advanced_count: int,
    runtime_backend: str,
) -> str:
    policy = normalize_models_policy(policy_payload)
    daily = str(policy.get("daily_model_promotion_candidate", "") or "").strip() or active_model
    heavy = str(policy.get("heavy_model_candidate", "") or "").strip() or "none set"
    selected_name = str(active_model or "unset").strip() or "unset"
    runtime_name = _normalized_backend(runtime_backend).upper()
    return (
        f"Recommended default: {daily} for everyday use. Heavier local option: {heavy} when you want a deeper local pass. "
        f"This session is using {selected_name} on {runtime_name}. "
        f"{local_count} local models are installed on this PC"
        + (f", with {advanced_count} advanced picks kept in their own section." if advanced_count else ".")
    )


def build_models_loadout_help_text(
    *,
    main_model: str,
    sub_a_model: str,
    sub_b_model: str,
) -> str:
    return (
        "Saved slots: "
        f"main assistant model -> {str(main_model or 'unset').strip() or 'unset'} | "
        f"spawned model A -> {str(sub_a_model or 'unset').strip() or 'unset'} | "
        f"spawned model B -> {str(sub_b_model or 'unset').strip() or 'unset'}. "
        "Persona stays attached separately."
    )


def build_models_route_summary_text(
    *,
    simple_target: str,
    complex_target: str,
    teaching_target: str,
    fallback_targets: Iterable[str],
    health_summary: str,
) -> tuple[str, str]:
    fallback = [str(item).strip() for item in fallback_targets if str(item).strip()]
    summary = (
        "Current route plan:\n"
        f"Simple requests start with {simple_target}.\n"
        f"Complex requests start with {complex_target}.\n"
        f"Teaching requests start with {teaching_target}.\n"
        f"If the first choice is unavailable, the launcher falls back to {', '.join(fallback) if fallback else 'the built-in defaults'}."
    )
    return summary, f"Live evidence: {health_summary}"


def friendly_models_route_name(route: str) -> str:
    value = str(route or "").strip().lower()
    return {
        "haiku": "Claude Haiku",
        "sonnet": "Claude Sonnet",
        "opus": "Claude Opus",
        "local": "the local model",
        "code": "the code specialist",
        "teaching": "the teaching route",
        "auto": "the automatic route",
        "pending": "the pending route",
    }.get(value, value.replace("-", " ").replace("_", " ").strip().title() or "the selected route")


def friendly_models_route_target(target: str) -> str:
    raw = str(target or "").strip()
    if not raw:
        return "an unset route"
    provider, sep, model = raw.partition("/")
    if sep and provider and model:
        return f"{'local' if provider.lower() == 'local' else provider.upper()} / {model}"
    return friendly_models_route_name(raw)


def build_models_route_decision_text(decision: Mapping[str, Any] | None) -> str:
    if not isinstance(decision, Mapping):
        return "Route preview unavailable."
    task_type = str(decision.get("task_type", "unknown") or "unknown").strip()
    route = str(decision.get("route", "pending") or "pending").strip()
    executor = str(decision.get("executor", "") or "").strip()
    model = str(decision.get("model", "") or "").strip()
    backup = str(decision.get("backup_model", "") or "").strip()
    reason = str(decision.get("route_reason", "") or "no explanation available").strip()
    summary = (
        f"{task_type.capitalize()} work will start with "
        f"{friendly_models_route_target(model or friendly_models_route_name(route))}."
    )
    if executor:
        summary += f" The current assistant will execute it through {executor.upper()}."
    details = ([f"Backup: {friendly_models_route_target(backup)}"] if backup else []) + [f"Why: {reason}"]
    return summary + ("\n" + " ".join(details) if details else "")


def build_models_route_evidence_text(
    decision: Mapping[str, Any] | None,
    *,
    health_summary: str,
) -> str:
    route = str((decision or {}).get("route", "pending") or "pending").strip().lower()
    if route in {"haiku", "sonnet", "opus"}:
        return f"Cloud evidence: {health_summary}"
    if route == "local":
        return f"Local evidence: {health_summary}"
    return f"Launcher evidence: {health_summary}"


def build_models_route_preview_hint_text() -> str:
    return "Route preview appears here once you type a sample request. Try the kind of question you would ask on Home."


def build_models_route_preview_text(
    decision: Mapping[str, Any] | None,
    *,
    health_summary: str,
) -> str:
    return build_models_route_decision_text(decision) + "\n" + build_models_route_evidence_text(
        decision,
        health_summary=health_summary,
    )


def model_library_section(
    model_name: str,
    *,
    policy_payload: Mapping[str, Any] | None,
    active_model: str,
) -> str:
    normalized = _normalized_model_name(model_name)
    policy = normalize_models_policy(policy_payload)
    daily = _normalized_model_name(policy.get("daily_model_promotion_candidate", ""))
    heavy = _normalized_model_name(policy.get("heavy_model_candidate", ""))
    rejected = {
        _normalized_model_name(item)
        for item in policy.get("daily_lane_rejected_models", [])
        if _normalized_model_name(item)
    }
    advanced_tokens = ("experimental", "preview", "alpha", "beta", "test", "canary")
    if normalized in rejected or any(token in normalized for token in advanced_tokens):
        return "advanced"
    if normalized in {daily, heavy}:
        return "recommended"
    if normalized == _normalized_model_name(active_model) and normalized not in rejected:
        return "recommended"
    return "installed"


def build_models_runtime_evidence_state(
    snapshot_payload: Mapping[str, Any] | None,
    *,
    editor_backend: str,
    saved_backend: str,
) -> ModelsTextState:
    snapshot = snapshot_payload if isinstance(snapshot_payload, Mapping) else {}
    runtime = snapshot.get("local_runtime", {})
    editor = _normalized_backend(editor_backend)
    saved = _normalized_backend(saved_backend)
    pending_save = editor != saved

    if not isinstance(runtime, Mapping) or not runtime:
        waiting = f"Live lane evidence: waiting for /status. Saved runtime: {saved.upper()}."
        if pending_save:
            waiting += f" Editor selection: {editor.upper()} (unsaved)."
        tone = "warning" if pending_save else "muted"
        return ModelsTextState(text=waiting, tone=tone)

    backend = _normalized_backend(str(runtime.get("backend", saved) or saved))
    state = str(runtime.get("state", "unknown") or "unknown").strip().upper()
    detail = str(runtime.get("detail", "") or "").strip()
    requested_model = str(runtime.get("requested_model", "") or "").strip()
    resolved_model = str(runtime.get("resolved_model", "") or "").strip()
    base_url = str(runtime.get("base_url", "") or "").strip()
    tool_loop = str(runtime.get("tool_loop", "") or "").strip()
    available_roles = _slot_list(runtime.get("available_roles", []))
    missing_roles = _slot_list(runtime.get("missing_roles", []))
    chat_ready = bool(runtime.get("chat_ready", False))
    chat_state = str(runtime.get("chat_state", "UNKNOWN") or "UNKNOWN").strip().upper()
    chat_detail = str(runtime.get("chat_detail", "") or "").strip()
    chat_model = str(runtime.get("chat_model", "") or resolved_model or requested_model).strip()

    lines = [
        f"LIVE LANE: {state} | server runtime {backend.upper()} | saved runtime {saved.upper()}",
    ]
    if pending_save:
        lines[0] += f" | editor selection {editor.upper()} (unsaved)"
    if backend != saved:
        lines.append("Server runtime does not match the saved launcher choice yet.")
    if detail:
        lines.append(detail)

    resolved_bits = []
    if requested_model:
        resolved_bits.append(f"requested {requested_model}")
    if resolved_model:
        resolved_bits.append(f"resolved {resolved_model}")
    if tool_loop:
        resolved_bits.append(f"tool loop {tool_loop}")
    if base_url:
        resolved_bits.append(f"endpoint {base_url}")
    if resolved_bits:
        lines.append("Live runtime details: " + " | ".join(resolved_bits))

    if chat_state != "UNKNOWN" or chat_detail or chat_model:
        harness_bits = [f"Chat harness {chat_state or ('READY' if chat_ready else 'UNKNOWN')}"]
        if chat_model:
            harness_bits.append(f"model {chat_model}")
        if chat_detail:
            harness_bits.append(chat_detail)
        lines.append(" | ".join(harness_bits))
    elif backend == "lemonade":
        lines.append("Chat harness: registry-ready evidence only; an active warm sample has not been captured yet.")

    if available_roles:
        lines.append("Available mapped roles: " + ", ".join(available_roles))
    if missing_roles:
        lines.append("Missing mapped roles: " + ", ".join(missing_roles))

    tone = "success"
    if state in {"MISSING", "ERROR", "FAILED", "OFFLINE"}:
        tone = "error"
    elif (
        state in {"PARTIAL", "UNKNOWN"}
        or pending_save
        or backend != saved
        or missing_roles
        or (backend == "ollama" and chat_state in {"UNKNOWN", "WARMING"} and not chat_ready)
    ):
        tone = "warning"

    return ModelsTextState(text="\n".join(lines), tone=tone)


def build_models_provider_readiness_state(
    payload: Mapping[str, Any] | None,
    *,
    active_backend: str,
) -> ModelsTextState:
    source = payload if isinstance(payload, Mapping) else {}
    backend = _normalized_backend(active_backend)
    active_key = "lemonade_local" if backend == "lemonade" else "ollama_local"

    def status(key: str) -> str:
        return str(source.get(key, "unknown") or "unknown").strip() or "unknown"

    def is_ready(value: str) -> bool:
        lowered = value.lower()
        return bool(value) and "offline" not in lowered and "missing api key" not in lowered and lowered != "unknown"

    ollama_local = status("ollama_local")
    lmstudio_local = status("lmstudio_local")
    lemonade_local = status("lemonade_local")
    harness = status("local_harness")
    anthropic = status("anthropic")
    openai = status("openai")
    gemini = status("gemini")
    ollama_api = status("ollama_api")

    configured_cloud = [
        label
        for label, value in (
            ("Anthropic", anthropic),
            ("OpenAI", openai),
            ("Gemini", gemini),
            ("Ollama API", ollama_api),
        )
        if is_ready(value)
    ]
    missing_cloud = [
        label
        for label, value in (
            ("Anthropic", anthropic),
            ("OpenAI", openai),
            ("Gemini", gemini),
            ("Ollama API", ollama_api),
        )
        if not is_ready(value)
    ]
    active_status = status(active_key)
    active_ready = is_ready(active_status)
    harness_ready = is_ready(harness)

    lines = [
        f"Current backend gate: {backend.upper()} {'ready' if active_ready else 'needs attention'}"
        + (f" | {active_status}" if active_status else ""),
        "Local endpoints: "
        + " | ".join(
            [
                f"Ollama {ollama_local}",
                f"LM Studio {lmstudio_local}",
                f"Lemonade {lemonade_local}",
                f"Harness {harness}",
            ]
        ),
    ]
    if configured_cloud or missing_cloud:
        cloud_bits = []
        if configured_cloud:
            cloud_bits.append("configured " + ", ".join(configured_cloud))
        if missing_cloud:
            cloud_bits.append("missing " + ", ".join(missing_cloud))
        lines.append("Provider keys: " + " | ".join(cloud_bits))
    if not harness_ready:
        lines.append("Harness note: the local benchmark and OpenAI-compatible dev lane is not ready yet.")
    if not is_ready(lmstudio_local):
        lines.append("LM Studio setup: turn on the local server in LM Studio and refresh this panel.")

    tone = "success"
    if not active_ready:
        tone = "error"
    elif not harness_ready or not configured_cloud:
        tone = "warning"

    return ModelsTextState(text="\n".join(lines), tone=tone)
