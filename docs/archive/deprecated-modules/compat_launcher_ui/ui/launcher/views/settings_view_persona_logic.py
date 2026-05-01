"""
settings_view_persona_logic.py
Persona editor logic for SettingsView — extracted from settings_view.py.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.guppy.experience_config import (
    ensure_personalization_scaffold,
    list_model_ids,
    load_persona_config_with_diagnostics,
    load_provider_registry,
    personalization_backend_available,
    save_persona_config,
    validate_persona_config,
)
from src.guppy.experience_config.personalization_defaults import DEFAULT_ASSISTANT_NAME, DEFAULT_PERSONA_CONFIG
from src.guppy.launcher_application.settings_persona_presenter import (
    build_assignment_summary_text,
    build_persona_preview_text,
)
from .settings_view_sections import _MODEL_BINDING_OPTIONS

_PERSONALIZATION_BACKEND = personalization_backend_available()
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def deepcopy_json(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


def slugify(raw: str) -> str:
    normalized = _SLUG_RE.sub("_", (raw or "").strip().lower()).strip("_")
    return normalized[:40] or "persona"


def load_model_binding_options(view) -> None:
    options = list_model_ids(load_provider_registry())
    current = view._model_binding_cb.currentText().strip()
    view._model_binding_cb.blockSignals(True)
    view._model_binding_cb.clear()
    view._model_binding_cb.addItems(options or list(_MODEL_BINDING_OPTIONS))
    if current:
        index = view._model_binding_cb.findText(current)
        if index >= 0:
            view._model_binding_cb.setCurrentIndex(index)
    view._model_binding_cb.blockSignals(False)


def set_persona_controls_enabled(view, enabled: bool) -> None:
    for widget in [
        view._persona_picker,
        view._new_persona_btn,
        view._delete_persona_btn,
        view._persona_name,
        view._scope_cb,
        view._model_binding_cb,
        view._tone_cb,
        view._verbosity_cb,
        view._style_cb,
        view._teaching_toggle,
        view._socratic_slider,
        view._example_slider,
        view._global_persona_cb,
        view._system_prompt,
    ]:
        widget.setEnabled(enabled)


def persona_items(view) -> list[dict[str, Any]]:
    personas = view._persona_config.get("personas", [])
    return [item for item in personas if isinstance(item, dict)]


def refresh_persona_lists(view, select_id: str = "") -> None:
    personas = persona_items(view)
    if not personas:
        view._persona_config = deepcopy_json(DEFAULT_PERSONA_CONFIG)
        personas = persona_items(view)

    target = select_id or str(personas[0].get("id", "main_guppy"))
    view._persona_picker.blockSignals(True)
    view._global_persona_cb.blockSignals(True)
    view._persona_picker.clear()
    view._global_persona_cb.clear()

    for persona in personas:
        persona_id = str(persona.get("id", "")).strip()
        name = str(persona.get("name", persona_id)).strip() or persona_id
        scope = str(persona.get("scope", "global")).strip().upper()
        label = f"{name} [{scope}]"
        view._persona_picker.addItem(label, persona_id)
        view._global_persona_cb.addItem(name, persona_id)

    picker_index = max(0, view._persona_picker.findData(target))
    view._persona_picker.setCurrentIndex(picker_index)
    global_target = str(view._persona_config.get("assignments", {}).get("global", "") or target)
    global_index = view._global_persona_cb.findData(global_target)
    view._global_persona_cb.setCurrentIndex(max(0, global_index))
    view._persona_picker.blockSignals(False)
    view._global_persona_cb.blockSignals(False)
    view._current_persona_id = str(view._persona_picker.currentData() or target)
    populate_persona_form(view)


def selected_persona(view) -> dict[str, Any]:
    for p in persona_items(view):
        if str(p.get("id", "")).strip() == view._current_persona_id:
            return p
    return persona_items(view)[0]


def populate_persona_form(view) -> None:
    persona = selected_persona(view)
    traits = persona.get("traits", {}) if isinstance(persona.get("traits"), dict) else {}
    teaching = persona.get("teaching", {}) if isinstance(persona.get("teaching"), dict) else {}

    view._loading_persona = True
    view._persona_name.setText(str(persona.get("name", "")))
    view._scope_cb.setCurrentText(str(persona.get("scope", "global")).upper())
    model_name = str(persona.get("model", _MODEL_BINDING_OPTIONS[0]))
    if model_name not in _MODEL_BINDING_OPTIONS:
        model_name = _MODEL_BINDING_OPTIONS[0]
    model_index = view._model_binding_cb.findText(model_name)
    view._model_binding_cb.setCurrentIndex(max(0, model_index))
    view._tone_cb.setCurrentText(str(traits.get("tone", "butler")).upper())
    view._verbosity_cb.setCurrentText(str(traits.get("verbosity", "medium")).upper())
    view._style_cb.setCurrentText(str(traits.get("response_style", "direct")).upper())
    view._teaching_toggle.setChecked(bool(teaching.get("enabled", True)))
    view._socratic_slider.setValue(int(teaching.get("socratic_bias", 35) or 35))
    view._example_slider.setValue(int(teaching.get("example_bias", 60) or 60))
    view._system_prompt.setPlainText(str(persona.get("system_prompt", "")))
    view._loading_persona = False
    on_scope_changed(view, view._scope_cb.currentText())
    refresh_assignment_summary(view)
    refresh_preview(view)


def refresh_assignment_summary(view) -> None:
    mapping = view._persona_config.get("assignments", {}).get("by_model", {})
    view._assignment_summary_lbl.setText(build_assignment_summary_text(persona_items(view), mapping))


def on_persona_selected(view, _index: int) -> None:
    view._current_persona_id = str(view._persona_picker.currentData() or view._current_persona_id)
    populate_persona_form(view)


def on_scope_changed(view, text: str) -> None:
    model_scope = (text or "GLOBAL").strip().upper() == "MODEL"
    view._model_binding_cb.setEnabled(model_scope and _PERSONALIZATION_BACKEND)
    refresh_preview(view)


def next_persona_id(view, base_name: str) -> str:
    base = slugify(base_name)
    existing = {str(item.get("id", "")).strip() for item in persona_items(view)}
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def create_persona(view) -> None:
    if not _PERSONALIZATION_BACKEND:
        return
    name = f"Custom Assistant {len(persona_items(view)) + 1}"
    persona_id = next_persona_id(view, name)
    view._persona_config.setdefault("personas", []).append(
        {
            "id": persona_id,
            "name": name,
            "scope": "global",
            "system_prompt": "You are Guppy. Stay explicit, bounded, and practical.",
            "traits": {
                "tone": "coach",
                "verbosity": "medium",
                "response_style": "structured",
            },
            "teaching": {
                "enabled": True,
                "socratic_bias": 50,
                "example_bias": 50,
            },
        }
    )
    refresh_persona_lists(view, persona_id)
    view._persona_status_lbl.setText(f"Draft assistant persona created: {name}")


def delete_persona(view) -> None:
    personas = persona_items(view)
    if len(personas) <= 1:
        view._persona_status_lbl.setText("At least one persona must remain.")
        return
    keep = [item for item in personas if str(item.get("id", "")).strip() != view._current_persona_id]
    view._persona_config["personas"] = keep
    assignments = view._persona_config.setdefault("assignments", {"global": keep[0]["id"], "by_model": {}})
    by_model = assignments.get("by_model", {}) if isinstance(assignments.get("by_model"), dict) else {}
    assignments["by_model"] = {model: pid for model, pid in by_model.items() if pid != view._current_persona_id}
    if assignments.get("global") == view._current_persona_id:
        assignments["global"] = str(keep[0].get("id", "main_guppy"))
    view._persona_config["default_persona_id"] = assignments["global"]
    refresh_persona_lists(view, str(keep[0].get("id", "main_guppy")))
    view._persona_status_lbl.setText("Assistant persona removed from draft config")


def build_persona_config(view) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = deepcopy_json(view._persona_config)
    personas = cfg.get("personas", []) if isinstance(cfg.get("personas"), list) else []
    persona_id = view._current_persona_id or next_persona_id(view, view._persona_name.text().strip())
    name = view._persona_name.text().strip()
    if not name:
        raise ValueError("Assistant name is required")
    scope = view._scope_cb.currentText().strip().lower()
    model_name = view._model_binding_cb.currentText().strip()
    if scope == "model" and not model_name:
        raise ValueError("Model scope requires a model binding")

    existing_persona = next(
        (item for item in personas if isinstance(item, dict) and str(item.get("id", "")).strip() == persona_id),
        {},
    )
    preserved = {
        key: value
        for key, value in existing_persona.items()
        if key not in {"id", "name", "scope", "model", "system_prompt", "traits", "teaching"}
    }

    persona = {
        **preserved,
        "id": persona_id,
        "name": name,
        "scope": scope,
        "system_prompt": view._system_prompt.toPlainText().strip() or "You are Guppy. Be concise, dependable, and practical.",
        "traits": {
            "tone": view._tone_cb.currentText().strip().lower(),
            "verbosity": view._verbosity_cb.currentText().strip().lower(),
            "response_style": view._style_cb.currentText().strip().lower(),
        },
        "teaching": {
            "enabled": view._teaching_toggle.isChecked(),
            "socratic_bias": int(view._socratic_slider.value()),
            "example_bias": int(view._example_slider.value()),
        },
    }
    if scope == "model":
        persona["model"] = model_name

    replaced = False
    for index, item in enumerate(personas):
        if isinstance(item, dict) and str(item.get("id", "")).strip() == persona_id:
            personas[index] = persona
            replaced = True
            break
    if not replaced:
        personas.append(persona)
    cfg["personas"] = personas

    assignments = cfg.setdefault("assignments", {"global": persona_id, "by_model": {}})
    if not isinstance(assignments.get("by_model"), dict):
        assignments["by_model"] = {}
    assignments["by_model"] = {
        model: assigned_persona
        for model, assigned_persona in assignments["by_model"].items()
        if assigned_persona != persona_id
    }
    if scope == "model":
        assignments["by_model"][model_name] = persona_id

    global_persona_id = str(view._global_persona_cb.currentData() or persona_id).strip() or persona_id
    if global_persona_id not in {str(item.get("id", "")).strip() for item in personas if isinstance(item, dict)}:
        global_persona_id = persona_id
    assignments["global"] = global_persona_id
    cfg["default_persona_id"] = global_persona_id
    return cfg, persona


def refresh_preview(view) -> None:
    if view._loading_persona:
        return
    prompt = view._system_prompt.toPlainText().strip() or "You are Guppy. Be concise, dependable, and practical."
    view._preview_lbl.setText(
        build_persona_preview_text(
            persona_name=view._persona_name.text(),
            scope=view._scope_cb.currentText(),
            model_text=view._model_binding_cb.currentText(),
            tone=view._tone_cb.currentText(),
            verbosity=view._verbosity_cb.currentText(),
            style=view._style_cb.currentText(),
            teaching_enabled=view._teaching_toggle.isChecked(),
            socratic_bias=view._socratic_slider.value(),
            example_bias=view._example_slider.value(),
            prompt=prompt,
        )
    )


def load_persona_settings(view) -> None:
    if not _PERSONALIZATION_BACKEND:
        set_persona_controls_enabled(view, False)
        view._persona_status_lbl.setText("Assistant & Persona Builder unavailable: personalization backend not loaded.")
        refresh_preview(view)
        return

    try:
        ensure_personalization_scaffold()
        load_model_binding_options(view)
        config, diagnostics = load_persona_config_with_diagnostics()
    except Exception as exc:
        set_persona_controls_enabled(view, False)
        view._persona_status_lbl.setText(f"Assistant & Persona Builder failed to load: {exc}")
        refresh_preview(view)
        return

    if isinstance(config, dict):
        view._persona_config = config
    view._persona_diag_lbl.setText(
        "Persona config healthy" if not diagnostics else "Config notes: " + " | ".join(diagnostics)
    )
    select_id = str(
        view._persona_config.get("default_persona_id")
        or view._persona_config.get("assignments", {}).get("global", "main_guppy")
    )
    refresh_persona_lists(view, select_id)
    view._persona_status_lbl.setText("Assistant & Persona Builder ready")
