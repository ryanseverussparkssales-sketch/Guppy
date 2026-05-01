from __future__ import annotations

from typing import Any

from .. import tokens as T
from src.guppy.launcher_application.models_presenter import (
    build_models_provider_readiness_state,
)

from .models_runtime_workers import ModelHealthCheckThread, OllamaModelOpThread


def toggle_model_ops_panel(owner: Any) -> None:
    visible = not owner._ops_panel.isVisible()
    owner._ops_panel.setVisible(visible)
    owner._ops_toggle_btn.setText(
        "HIDE MODEL HEALTH + READINESS" if visible else "MODEL HEALTH + READINESS"
    )


def set_ops_status(
    owner: Any,
    text: str,
    ok: bool = True,
    *,
    tone: str | None = None,
) -> None:
    color = owner._tone_color(
        tone or ("success" if ok else "error"),
        default=T.GREEN if ok else T.ERROR,
    )
    owner._ops_status_lbl.setText(text)
    owner._ops_status_lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
    )


def check_model_health(owner: Any) -> None:
    if owner._health_thread is not None and owner._health_thread.isRunning():
        set_ops_status(owner, "Health check already running", ok=False)
        return
    set_ops_status(owner, "Checking provider and model health...", ok=True)
    owner._store_runtime_endpoint_for_backend(
        owner._local_runtime_backend,
        owner._lemonade_base_url_input.text().strip(),
    )
    owner._health_thread = ModelHealthCheckThread(
        owner._runtime_endpoint_for_backend(owner._local_runtime_backend),
        owner,
    )
    owner._health_thread.finished.connect(owner._on_health_checked)
    owner._health_thread.start()


def on_health_checked(owner: Any, payload: dict[str, str]) -> None:
    state = build_models_provider_readiness_state(
        payload,
        active_backend=owner._local_runtime_backend,
    )
    set_ops_status(owner, state.text, ok=state.tone != "error", tone=state.tone)


def run_model_op(owner: Any, operation: str) -> None:
    if owner._model_op_thread is not None and owner._model_op_thread.isRunning():
        set_ops_status(owner, "Model operation already running", ok=False)
        return
    model_name = owner._ops_model_input.text().strip()
    if not model_name:
        set_ops_status(owner, "Enter a model id first", ok=False)
        return
    action = "download" if operation == "pull" else "uninstall"
    set_ops_status(owner, f"Running {action} for {model_name}...", ok=True)
    owner._model_op_thread = OllamaModelOpThread(operation, model_name, owner)
    owner._model_op_thread.finished.connect(owner._on_model_op_finished)
    owner._model_op_thread.start()


def on_model_op_finished(owner: Any, payload: dict[str, Any]) -> None:
    ok = bool(payload.get("ok", False))
    summary = str(payload.get("summary", "") or "completed").strip()
    set_ops_status(owner, summary, ok=ok)
    if ok:
        owner._refresh()
