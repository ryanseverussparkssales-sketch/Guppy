from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox

from src.guppy.experience_config import (
    ensure_personalization_scaffold,
    list_model_ids,
    list_persona_choices,
    load_persona_config,
    load_provider_registry,
    load_voice_bindings,
    save_voice_bindings,
    validate_voice_bindings,
)
from src.guppy.launcher_application.voice_catalog_support import build_bindings_summary_text


def set_combo_options(combo: QComboBox, options: list[tuple[str, str]], *, selected: str = "") -> None:
    target = str(selected or combo.currentData() or combo.currentText()).strip().lower()
    combo.blockSignals(True)
    combo.clear()
    for label, value in options:
        combo.addItem(label, value)
    index = 0
    for idx in range(combo.count()):
        if str(combo.itemData(idx) or "").strip().lower() == target:
            index = idx
            break
    combo.setCurrentIndex(index)
    combo.blockSignals(False)


def load_assignment_options(view: Any) -> None:
    personas = list_persona_choices(load_persona_config())
    persona_options = [(item["name"], item["id"]) for item in personas]
    set_combo_options(view._persona_cb, persona_options, selected=str(view._persona_cb.currentData() or "guppy"))

    model_options = [(model_id, model_id) for model_id in list_model_ids(load_provider_registry())]
    set_combo_options(
        view._model_cb,
        model_options,
        selected=str(view._model_cb.currentData() or view._model_cb.currentText()),
    )


def refresh_bindings_summary(view: Any) -> None:
    view._bindings_summary_lbl.setText(
        build_bindings_summary_text(
            view._voice_bindings,
            default_choice=view._default_lbl.text().replace("DEFAULT VOICE: ", "").strip(),
        )
    )


def emit_bindings_changed(view: Any) -> None:
    view.bindings_changed.emit(dict(view._voice_bindings))


def load_voice_bindings_state(view: Any, *, backend_available: bool) -> None:
    if not backend_available:
        view._assign_status.setText("voice bindings backend unavailable")
        return
    try:
        ensure_personalization_scaffold()
        data = load_voice_bindings()
        if isinstance(data, dict):
            view._voice_bindings = data
        defaults = view._voice_bindings.get("defaults", {})
        if isinstance(defaults, dict):
            view._active_engine = str(defaults.get("engine", view._active_engine))
            view._active_voice = str(defaults.get("voice_id", view._active_voice))
        idx = view._engine_cb.findText(view._active_engine)
        if idx >= 0:
            view._engine_cb.setCurrentIndex(idx)
        view._assign_status.setText("Voice choices loaded.")
        view._update_default_label()
        view._active_lbl.setText(
            f"ACTIVE VOICE: {view._describe_voice_choice(view._active_engine, view._active_voice)}"
        )
        refresh_bindings_summary(view)
        view._refresh_voice_evidence()
    except Exception as error:
        view._assign_status.setText(f"load failed: {error}")


def save_voice_bindings_state(view: Any, *, backend_available: bool) -> bool:
    if not backend_available:
        view._assign_status.setText("voice bindings backend unavailable")
        return False
    try:
        errors = validate_voice_bindings(view._voice_bindings)
        if errors:
            view._assign_status.setText(f"invalid bindings: {errors[0]}")
            return False
        save_voice_bindings(view._voice_bindings)
        refresh_bindings_summary(view)
        emit_bindings_changed(view)
        return True
    except Exception as error:
        view._assign_status.setText(f"save failed: {error}")
        return False


def save_default_voice(view: Any, *, backend_available: bool) -> bool:
    valid, reason = view._validate_engine_selection(view._active_engine, view._active_voice)
    if not valid:
        view._assign_status.setText(reason)
        return False
    view._voice_bindings.setdefault("defaults", {})
    view._voice_bindings["defaults"] = {
        "engine": view._active_engine,
        "voice_id": view._active_voice,
    }
    if save_voice_bindings_state(view, backend_available=backend_available):
        view._assign_status.setText(
            f"Default voice saved: {view._describe_voice_choice(view._active_engine, view._active_voice)}"
        )
        view._update_default_label()
        return True
    return False


def assign_persona_voice(view: Any, *, backend_available: bool) -> None:
    valid, reason = view._validate_engine_selection(view._active_engine, view._active_voice)
    if not valid:
        view._assign_status.setText(reason)
        return
    persona = str(view._persona_cb.currentData() or view._persona_cb.currentText()).strip().lower()
    view._voice_bindings.setdefault("bindings", {})
    view._voice_bindings["bindings"].setdefault("by_persona", {})
    view._voice_bindings["bindings"]["by_persona"][persona] = {
        "engine": view._active_engine,
        "voice_id": view._active_voice,
    }
    if save_voice_bindings_state(view, backend_available=backend_available):
        view._assign_status.setText(
            f"Persona {persona} now uses {view._describe_voice_choice(view._active_engine, view._active_voice)}."
        )


def assign_model_voice(view: Any, *, backend_available: bool) -> None:
    valid, reason = view._validate_engine_selection(view._active_engine, view._active_voice)
    if not valid:
        view._assign_status.setText(reason)
        return
    model = str(view._model_cb.currentData() or view._model_cb.currentText()).strip()
    view._voice_bindings.setdefault("bindings", {})
    view._voice_bindings["bindings"].setdefault("by_model", {})
    view._voice_bindings["bindings"]["by_model"][model] = {
        "engine": view._active_engine,
        "voice_id": view._active_voice,
    }
    if save_voice_bindings_state(view, backend_available=backend_available):
        view._assign_status.setText(
            f"Model {model} now uses {view._describe_voice_choice(view._active_engine, view._active_voice)}."
        )


def import_voice(view: Any, *, backend_available: bool) -> None:
    engine = view._import_engine_cb.currentText().strip()
    voice_id = view._import_voice_id.text().strip()
    label = view._import_label.text().strip()
    if not engine or not voice_id:
        view._assign_status.setText("import requires engine and voice id")
        return
    imports = view._voice_bindings.setdefault("imports", [])
    if not isinstance(imports, list):
        imports = []
        view._voice_bindings["imports"] = imports
    imports = [
        item
        for item in imports
        if not (
            isinstance(item, dict)
            and str(item.get("engine", "")).strip() == engine
            and str(item.get("voice_id", "")).strip() == voice_id
        )
    ]
    imports.append(
        {
            "engine": engine,
            "voice_id": voice_id,
            "label": label or voice_id,
            "language": "Imported",
            "gender": "Custom",
        }
    )
    view._voice_bindings["imports"] = imports
    if save_voice_bindings_state(view, backend_available=backend_available):
        view._assign_status.setText(f"Imported {voice_id} into {engine}.")
        view._import_voice_id.clear()
        view._import_label.clear()
        if view._active_engine == engine:
            view._populate_voices(engine)
