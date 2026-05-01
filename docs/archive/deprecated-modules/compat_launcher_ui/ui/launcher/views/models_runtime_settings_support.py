from __future__ import annotations

import os
from typing import Any

from src.guppy.experience_config import apply_runtime_settings_to_env as apply_settings_to_env
from src.guppy.launcher_application.models_presenter import build_models_runtime_identity_text

from .. import tokens as T


def set_runtime_status(owner: Any, text: str, ok: bool = True) -> None:
    color = T.STATUS_SUCCESS if ok else T.STATUS_ERROR
    owner._runtime_status_lbl.setText(text)
    owner._runtime_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )


def runtime_settings_payload(owner: Any) -> dict[str, Any]:
    return {
        "local_runtime_backend": owner._local_runtime_backend,
        "lemonade_base_url": owner._lemonade_base_url,
        "lmstudio_base_url": owner._lmstudio_base_url,
        "local_harness_base_url": owner._local_harness_base_url,
        **{key: combo.currentText().strip() for key, combo in owner._lemonade_role_inputs.items()},
    }


def load_runtime_settings(
    owner: Any,
    *,
    load_app_settings,
    runtime_settings_backend_available: bool,
    normalize_runtime_backend,
    load_runtime_endpoint_settings,
    role_fields: list[tuple[str, str]],
    loadout_fields: list[tuple[str, str]],
) -> None:
    settings = load_app_settings() if runtime_settings_backend_available else {}
    owner._local_runtime_backend = normalize_runtime_backend(
        str(
            settings.get(
                "local_runtime_backend",
                os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama"),
            )
        )
    )
    owner._saved_runtime_backend = owner._local_runtime_backend
    owner._runtime_backend_cb.blockSignals(True)
    owner._runtime_backend_cb.setCurrentText(owner._local_runtime_backend.upper())
    owner._runtime_backend_cb.blockSignals(False)
    load_runtime_endpoint_settings(owner, settings)
    for field_name, _label in role_fields:
        combo = owner._lemonade_role_inputs[field_name]
        value = str(
            settings.get(field_name, os.environ.get(f"GUPPY_{field_name.upper()}", "")) or ""
        ).strip()
        combo.clear()
        if value:
            combo.addItem(value)
            combo.setCurrentText(value)
    for field_name, _label in loadout_fields:
        value = str(settings.get(field_name, owner._model_loadout.get(field_name, "")) or "").strip()
        if value:
            owner._model_loadout[field_name] = value
    update_runtime_controls(owner)
    owner._refresh_loadout_inputs()
    owner._refresh_loadout_help()


def update_runtime_controls(owner: Any) -> None:
    owner._active_runtime_lbl.setText(
        build_models_runtime_identity_text(owner._local_runtime_backend)
    )
    owner._refresh_runtime_endpoint_input()
    owner._lemonade_base_url_input.setEnabled(True)
    for combo in owner._lemonade_role_inputs.values():
        combo.setEnabled(owner._local_runtime_backend == "lemonade")
    owner._runtime_library_frame.setVisible(
        owner._local_runtime_backend in {"lemonade", "lmstudio", "local_harness"}
    )
    owner._refresh_runtime_summary()
    owner._refresh_runtime_library()


def on_runtime_backend_changed(owner: Any, text: str, *, normalize_runtime_backend) -> None:
    owner._store_runtime_endpoint_for_backend(
        owner._local_runtime_backend,
        owner._lemonade_base_url_input.text().strip(),
    )
    owner._local_runtime_backend = normalize_runtime_backend(text)
    update_runtime_controls(owner)
    owner._refresh()


def save_runtime_settings(
    owner: Any,
    *,
    runtime_settings_backend_available: bool,
    save_app_settings,
    normalize_runtime_backend,
) -> None:
    if not runtime_settings_backend_available:
        set_runtime_status(owner, "Runtime settings backend unavailable", ok=False)
        return
    try:
        owner._store_runtime_endpoint_for_backend(
            owner._local_runtime_backend,
            owner._lemonade_base_url_input.text().strip(),
        )
        payload = runtime_settings_payload(owner)
        save_app_settings(payload)
        merged = apply_settings_to_env(payload)
        owner._local_runtime_backend = normalize_runtime_backend(
            str(merged.get("local_runtime_backend", owner._local_runtime_backend))
        )
        owner._saved_runtime_backend = owner._local_runtime_backend
        update_runtime_controls(owner)
        set_runtime_status(
            owner,
            f"Saved local runtime: {owner._local_runtime_backend.upper()}",
            ok=True,
        )
        owner.runtime_settings_saved.emit(dict(merged))
    except Exception as exc:
        set_runtime_status(owner, f"Runtime save failed: {exc}", ok=False)
