from __future__ import annotations

import os
from typing import Any

from .. import tokens as T
from src.guppy.launcher_application.models_presenter import (
    build_models_library_hint_text,
    build_models_library_summary_text,
    build_models_runtime_evidence_state,
    build_models_runtime_policy_state,
    build_models_runtime_summary_text,
    model_library_section,
    normalize_models_policy,
)

_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
_DEFAULT_LOCAL_HARNESS_BASE_URL = "http://127.0.0.1:8001"


def normalize_runtime_backend(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned == "lemonade":
        return "lemonade"
    if cleaned in {"lm studio", "lmstudio", "lmstudio_local"}:
        return "lmstudio"
    if cleaned in {"local harness", "local_harness", "harness"}:
        return "local_harness"
    if cleaned in {"llamacpp-gemma", "llamacpp_gemma", "gemma-llamacpp"}:
        return "llamacpp-gemma"
    if cleaned in {"llamacpp-qwen3", "llamacpp_qwen3", "qwen3-llamacpp"}:
        return "llamacpp-qwen3"
    if cleaned in {"llamacpp-pepe", "llamacpp_pepe", "pepe-llamacpp"}:
        return "llamacpp-pepe"
    return "ollama"


def runtime_endpoint_for_backend(owner: Any, backend: str) -> str:
    normalized = normalize_runtime_backend(backend)
    if normalized == "lemonade":
        return owner._lemonade_base_url
    if normalized == "lmstudio":
        return owner._lmstudio_base_url
    if normalized == "local_harness":
        return owner._local_harness_base_url
    return "http://127.0.0.1:11434"


def store_runtime_endpoint_for_backend(owner: Any, backend: str, value: str) -> None:
    normalized = normalize_runtime_backend(backend)
    cleaned = str(value or "").strip()
    if normalized == "lemonade":
        owner._lemonade_base_url = cleaned or _DEFAULT_LEMONADE_BASE_URL
    elif normalized == "lmstudio":
        owner._lmstudio_base_url = cleaned or _DEFAULT_LMSTUDIO_BASE_URL
    elif normalized == "local_harness":
        owner._local_harness_base_url = cleaned or _DEFAULT_LOCAL_HARNESS_BASE_URL


def refresh_runtime_endpoint_input(owner: Any) -> None:
    placeholder = {
        "ollama": "http://127.0.0.1:11434",
        "lmstudio": _DEFAULT_LMSTUDIO_BASE_URL,
        "local_harness": _DEFAULT_LOCAL_HARNESS_BASE_URL,
        "lemonade": _DEFAULT_LEMONADE_BASE_URL,
    }.get(owner._local_runtime_backend, "http://127.0.0.1:11434")
    owner._runtime_endpoint_lbl.setText("RUNTIME ENDPOINT")
    owner._lemonade_base_url_input.setPlaceholderText(placeholder)
    owner._lemonade_base_url_input.setToolTip(
        f"Endpoint used for the {owner._local_runtime_backend.upper()} local runtime lane"
    )
    owner._lemonade_base_url_input.setText(runtime_endpoint_for_backend(owner, owner._local_runtime_backend))


def normalize_policy_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_models_policy(payload)


def load_local_llm_policy(owner: Any) -> dict[str, Any]:
    if not owner._local_llm_manifest_backend:
        return {}
    try:
        return normalize_policy_snapshot(owner._get_local_llm_policy_summary(owner._load_local_llm_manifest()))
    except Exception:
        return {}


def render_runtime_policy(owner: Any) -> None:
    state = build_models_runtime_policy_state(
        owner._policy_snapshot,
        selected_backend=owner._local_runtime_backend,
    )
    owner._runtime_policy_lbl.setText(state.text)
    owner._runtime_policy_lbl.setStyleSheet(
        f"color: {owner._tone_color(state.tone, default=T.TEXT)}; font-family: '{T.FF_MONO}'; "
        f"font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
    )


def refresh_runtime_summary(owner: Any, role_fields: list[tuple[str, str]]) -> None:
    mapped = [
        f"{label.lower()} -> {owner._lemonade_role_inputs[field_name].currentText().strip()}"
        for field_name, label in role_fields
        if owner._lemonade_role_inputs[field_name].currentText().strip()
    ]
    owner._runtime_summary_lbl.setText(
        build_models_runtime_summary_text(
            editor_backend=owner._local_runtime_backend,
            saved_backend=owner._saved_runtime_backend,
            available_model_names=owner._available_local_model_names(),
            lemonade_mapping=mapped,
        )
    )
    render_runtime_policy(owner)
    render_runtime_evidence(owner)
    refresh_library_summary(owner)


def refresh_library_summary(owner: Any) -> None:
    if not hasattr(owner, "_library_summary_lbl"):
        return
    owner._library_summary_lbl.setText(
        build_models_library_summary_text(
            owner._policy_snapshot,
            active_model=owner._active_model,
            local_count=len(owner._local_cards),
            advanced_count=len(owner._local_section_cards.get("advanced", [])),
            runtime_backend=owner._saved_runtime_backend,
        )
    )


def apply_library_filter(owner: Any) -> None:
    if not hasattr(owner, "_library_search"):
        return
    query = owner._library_search.text().strip().lower()
    local_matches = 0
    cloud_matches = 0
    section_matches = {key: 0 for key in owner._local_sections}
    for card in owner._local_cards:
        match = card.matches_query(query)
        card.setVisible(match)
        local_matches += int(match)
        section_matches[getattr(card, "_library_section", "installed")] += int(match)
    for card in owner._cloud_cards:
        match = card.matches_query(query)
        card.setVisible(match)
        cloud_matches += int(match)
    for key, section in owner._local_sections.items():
        section.setVisible(section_matches.get(key, 0) > 0)
    if owner._local_placeholder is not None:
        owner._local_placeholder.setVisible(not owner._local_cards)
    owner._library_hint_lbl.setText(
        build_models_library_hint_text(
            query=query,
            local_matches=local_matches,
            cloud_matches=cloud_matches,
        )
    )


def local_model_section_for(owner: Any, model_name: str) -> str:
    return model_library_section(
        model_name,
        policy_payload=owner._policy_snapshot,
        active_model=owner._active_model,
    )


def rebuild_local_sections(owner: Any) -> None:
    for key, cards in owner._local_section_cards.items():
        layout = owner._local_section_layouts.get(key)
        if layout is None:
            continue
        for card in cards:
            layout.removeWidget(card)
        owner._local_section_cards[key] = []
    for card in owner._local_cards:
        section = local_model_section_for(owner, card._model_name)
        card._library_section = section
        card.set_recommended(section == "recommended")
        owner._local_section_layouts[section].addWidget(card)
        owner._local_section_cards[section].append(card)


def render_runtime_evidence(owner: Any) -> None:
    state = build_models_runtime_evidence_state(
        owner._status_snapshot,
        editor_backend=owner._local_runtime_backend,
        saved_backend=owner._saved_runtime_backend,
    )
    owner._runtime_live_lbl.setText(state.text)
    owner._runtime_live_lbl.setStyleSheet(
        f"color: {owner._tone_color(state.tone, default=T.TEXT)}; font-family: '{T.FF_MONO}'; "
        f"font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
    )


def load_runtime_endpoint_settings(owner: Any, settings: dict[str, Any]) -> None:
    owner._lemonade_base_url = str(
        settings.get("lemonade_base_url", os.environ.get("GUPPY_LEMONADE_BASE_URL", _DEFAULT_LEMONADE_BASE_URL))
        or _DEFAULT_LEMONADE_BASE_URL
    ).strip()
    owner._lmstudio_base_url = str(
        settings.get("lmstudio_base_url", os.environ.get("GUPPY_LMSTUDIO_BASE_URL", _DEFAULT_LMSTUDIO_BASE_URL))
        or _DEFAULT_LMSTUDIO_BASE_URL
    ).strip()
    owner._local_harness_base_url = str(
        settings.get("local_harness_base_url", os.environ.get("GUPPY_LOCAL_HARNESS_BASE_URL", _DEFAULT_LOCAL_HARNESS_BASE_URL))
        or _DEFAULT_LOCAL_HARNESS_BASE_URL
    ).strip()
