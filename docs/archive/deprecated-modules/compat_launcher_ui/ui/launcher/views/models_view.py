from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton, QWidget

from src.guppy.experience_config import (
    load_runtime_settings as load_app_settings,
    personalization_backend_available,
    runtime_settings_backend_available,
    save_runtime_settings as save_app_settings,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from src.guppy.launcher_application.models_route_support import parse_fallback_chain, route_targets_from_registry
from .models_view_builder import build_models_ui
from .. import tokens as T
from .models_library_refresh_support import (
    on_local_runtime_result as library_refresh_on_local_result,
    on_model_selected as library_refresh_on_model_selected,
    refresh_local_runtime_library as library_refresh_local_runtime_library,
)
from .models_management_support import (
    apply_mixed_loadout as management_apply_mixed_loadout,
    apply_model_loadout as management_apply_model_loadout,
    apply_routes as management_apply_routes,
    load_mix_from_routes as management_load_mix_from_routes,
    load_route_config as management_load_route_config,
    on_loadout_changed as management_on_loadout_changed,
    on_spawn_finished as management_on_spawn_finished,
    refresh_loadout_help as management_refresh_loadout_help,
    refresh_loadout_inputs as management_refresh_loadout_inputs,
    refresh_mix_route_inputs as management_refresh_mix_route_inputs,
    refresh_route_preview as management_refresh_route_preview,
    refresh_route_summary as management_refresh_route_summary,
    spawn_loadout_models as management_spawn_loadout_models,
    sync_runtime_mapping_options as management_sync_runtime_mapping_options,
)
from .models_ops_support import (
    check_model_health as ops_check_model_health,
    on_health_checked as ops_on_health_checked,
    on_model_op_finished as ops_on_model_op_finished,
    run_model_op as ops_run_model_op,
    set_ops_status as ops_set_ops_status,
    toggle_model_ops_panel as ops_toggle_model_ops_panel,
)
from .models_runtime_workers import ModelWarmSpawnThread
from .models_sections import _ModelCard
from .models_runtime_support import (
    _DEFAULT_LEMONADE_BASE_URL,
    _DEFAULT_LMSTUDIO_BASE_URL,
    _DEFAULT_LOCAL_HARNESS_BASE_URL,
    apply_library_filter,
    load_local_llm_policy,
    load_runtime_endpoint_settings,
    normalize_policy_snapshot,
    normalize_runtime_backend,
    rebuild_local_sections,
    refresh_library_summary,
    refresh_runtime_endpoint_input,
    refresh_runtime_summary,
    render_runtime_evidence,
    render_runtime_policy,
    runtime_endpoint_for_backend,
    store_runtime_endpoint_for_backend,
)
from .models_runtime_settings_support import (
    load_runtime_settings as runtime_settings_load_runtime_settings,
    on_runtime_backend_changed as runtime_settings_on_runtime_backend_changed,
    save_runtime_settings as runtime_settings_save_runtime_settings,
    set_runtime_status as runtime_settings_set_runtime_status,
    runtime_settings_payload as build_runtime_settings_payload,
    update_runtime_controls as runtime_settings_update_runtime_controls,
)
from .models_runtime_library import (
    assign_runtime_model as runtime_library_assign_runtime_model,
    refresh_runtime_library as runtime_library_refresh_runtime_library,
    set_selected_runtime_role as runtime_library_set_selected_runtime_role,
)

_RUNTIME_SETTINGS_BACKEND = runtime_settings_backend_available()
_PROVIDER_BACKEND = personalization_backend_available()

try:
    from src.guppy.local_llm.manifest import get_local_llm_policy_summary, load_local_llm_manifest
    _LOCAL_LLM_MANIFEST_BACKEND = True
except Exception:
    _LOCAL_LLM_MANIFEST_BACKEND = False

    def load_local_llm_manifest():
        return {}

    def get_local_llm_policy_summary(_manifest):
        return {}
CLOUD_MODELS = [
    {"name": "claude-haiku-4-5-20251001", "display": "Claude Haiku 4.5", "context": "200K tokens", "tier": "CLOUD", "note": "Fast / cost-efficient"},
    {"name": "claude-sonnet-4-6", "display": "Claude Sonnet 4.6", "context": "200K tokens", "tier": "CLOUD", "note": "Balanced / recommended"},
    {"name": "claude-opus-4-7", "display": "Claude Opus 4.7", "context": "200K tokens", "tier": "CLOUD", "note": "Maximum intelligence"},
]
_RUNTIME = Path(__file__).resolve().parent.parent.parent.parent / "runtime"
_HEARTBEAT_FRESH_SECONDS = float(os.environ.get("GUPPY_HEARTBEAT_FRESH_SECONDS", "20") or "20")
_LEMONADE_ROLE_FIELDS = [
    ("lemonade_fast_model", "DAILY SLOT"),
    ("lemonade_complex_model", "HEAVY SLOT"),
    ("lemonade_teach_model", "TEACHING SLOT"),
    ("lemonade_code_model", "CODING SLOT"),
    ("lemonade_vault_model", "RESEARCH SLOT"),
]
_LOADOUT_FIELDS = [
    ("local_main_model", "MAIN MODEL"),
    ("local_sub_model_a", "SPAWNED MODEL A"),
    ("local_sub_model_b", "SPAWNED MODEL B"),
]
_MIX_ROUTE_FIELDS = [
    ("mix_main_route", "MAIN ROUTE"),
    ("mix_sub_route_a", "SPAWNED ROUTE A"),
    ("mix_sub_route_b", "SPAWNED ROUTE B"),
]
class ModelsView(QWidget):
    model_selected = Signal(str)
    runtime_settings_saved = Signal(dict)

    @staticmethod
    def _route_targets_from_registry(registry: dict[str, Any]) -> list[str]:
        return route_targets_from_registry(registry)

    @staticmethod
    def _parse_fallback_chain(raw: str) -> list[str]:
        return parse_fallback_chain(raw)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_cards: list[_ModelCard] = []
        self._cloud_cards: list[_ModelCard] = []
        self._active_model = (
            os.environ.get("GUPPY_LOCAL_MODEL", "") or os.environ.get("OLLAMA_MODEL", "")
        ).strip()
        self._provider_registry: dict[str, Any] = {}
        self._route_options: list[str] = []
        self._local_runtime_backend = "ollama"
        self._saved_runtime_backend = "ollama"
        self._lemonade_base_url = _DEFAULT_LEMONADE_BASE_URL
        self._lmstudio_base_url = _DEFAULT_LMSTUDIO_BASE_URL
        self._local_harness_base_url = _DEFAULT_LOCAL_HARNESS_BASE_URL
        self._local_llm_manifest_backend = _LOCAL_LLM_MANIFEST_BACKEND
        self._load_local_llm_manifest = load_local_llm_manifest
        self._get_local_llm_policy_summary = get_local_llm_policy_summary
        self._status_snapshot: dict[str, Any] = {}
        self._policy_snapshot: dict[str, Any] = self._load_local_llm_policy()
        self._lemonade_role_inputs: dict[str, QComboBox] = {}
        self._selected_runtime_role_field = "lemonade_fast_model"
        self._runtime_library_buttons: list[QPushButton] = []
        self._model_loadout: dict[str, str] = {
            "local_main_model": (
                os.environ.get("GUPPY_MAIN_MODEL", "")
                or os.environ.get("OLLAMA_MODEL", "")
                or self._active_model
            ).strip(),
            "local_sub_model_a": (
                os.environ.get("GUPPY_SUB_MODEL_A", "")
                or os.environ.get("GUPPY_LOCAL_FAST_MODEL", "")
                or self._active_model
            ).strip(),
            "local_sub_model_b": (
                os.environ.get("GUPPY_SUB_MODEL_B", "")
                or os.environ.get("GUPPY_LOCAL_CODE_MODEL", "")
                or self._active_model
            ).strip(),
        }
        self._loadout_inputs: dict[str, QComboBox] = {}
        self._loadout_spawn_thread: ModelWarmSpawnThread | None = None
        self._mix_route_inputs: dict[str, QComboBox] = {}
        self._health_thread: ModelHealthCheckThread | None = None
        self._model_op_thread: OllamaModelOpThread | None = None
        self._runtime_dir = _RUNTIME
        self._heartbeat_fresh_seconds = _HEARTBEAT_FRESH_SECONDS
        self._model_warm_spawn_thread_factory = ModelWarmSpawnThread
        self._build_ui()
        self._load_runtime_settings()
        self._load_route_config()
        if QApplication.instance() is not None:
            self._refresh()
        self._set_page_mode("library")

    def _build_ui(self) -> None:
        build_models_ui(
            self,
            loadout_fields=_LOADOUT_FIELDS,
            cloud_models=CLOUD_MODELS,
            lemonade_role_fields=_LEMONADE_ROLE_FIELDS,
            default_lemonade_base_url=_DEFAULT_LEMONADE_BASE_URL,
            mix_route_fields=_MIX_ROUTE_FIELDS,
            route_modes=list(LAUNCHER_MODES_DISPLAY),
        )

    @staticmethod
    def _normalize_runtime_backend(value: str) -> str:
        return normalize_runtime_backend(value)

    def _runtime_endpoint_for_backend(self, backend: str) -> str:
        return runtime_endpoint_for_backend(self, backend)

    def _store_runtime_endpoint_for_backend(self, backend: str, value: str) -> None:
        store_runtime_endpoint_for_backend(self, backend, value)

    def _refresh_runtime_endpoint_input(self) -> None:
        refresh_runtime_endpoint_input(self)

    @staticmethod
    def _tone_color(tone: str, *, default: str = T.TEXT) -> str:
        return {
            "success": T.STATUS_SUCCESS,
            "warning": T.STATUS_WARNING,
            "error": T.STATUS_ERROR,
            "muted": T.DIM,
            "info": default,
        }.get(str(tone or "").strip().lower(), default)

    def _set_runtime_status(self, text: str, ok: bool = True) -> None:
        runtime_settings_set_runtime_status(self, text, ok)

    def _runtime_settings_payload(self) -> dict[str, Any]:
        return build_runtime_settings_payload(self)

    def _load_runtime_settings(self) -> None:
        runtime_settings_load_runtime_settings(
            self,
            load_app_settings=load_app_settings,
            runtime_settings_backend_available=_RUNTIME_SETTINGS_BACKEND,
            normalize_runtime_backend=normalize_runtime_backend,
            load_runtime_endpoint_settings=load_runtime_endpoint_settings,
            role_fields=_LEMONADE_ROLE_FIELDS,
            loadout_fields=_LOADOUT_FIELDS,
        )

    def _update_runtime_controls(self) -> None:
        runtime_settings_update_runtime_controls(self)

    def _set_page_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower()
        runtime_mode = normalized == "runtime"
        hub_mode = normalized == "hub"
        self._runtime_bar.setVisible(runtime_mode or hub_mode)
        self._route_bar.setVisible(runtime_mode or hub_mode)
        self._library_summary_frame.setVisible(not runtime_mode or hub_mode)
        self._library_scroll.setVisible(not runtime_mode or hub_mode)
        self._refresh_library_summary()

    def _available_local_model_names(self) -> list[str]:
        return [card._model_name for card in self._local_cards]

    @staticmethod
    def _normalize_policy_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
        return normalize_policy_snapshot(payload)

    def _load_local_llm_policy(self) -> dict[str, Any]:
        return load_local_llm_policy(self)

    def _render_runtime_policy(self) -> None:
        render_runtime_policy(self)

    def _refresh_runtime_summary(self) -> None:
        refresh_runtime_summary(self, _LEMONADE_ROLE_FIELDS)

    def _refresh_library_summary(self) -> None:
        refresh_library_summary(self)

    def _apply_library_filter(self) -> None:
        apply_library_filter(self)

    def _rebuild_local_sections(self) -> None:
        rebuild_local_sections(self)

    def _render_runtime_evidence(self) -> None:
        render_runtime_evidence(self)

    @staticmethod
    def _set_combo_items_preserve_text(combo: QComboBox, options: list[str], current: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for option in options:
            combo.addItem(option)
        if current and combo.findText(current) < 0:
            combo.addItem(current)
        if current:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def _sync_runtime_mapping_options(self) -> None:
        management_sync_runtime_mapping_options(self)

    def _refresh_mix_route_inputs(self) -> None:
        management_refresh_mix_route_inputs(self)

    def _load_mix_from_routes(self) -> None:
        management_load_mix_from_routes(self)

    def _apply_mixed_loadout(self) -> None:
        management_apply_mixed_loadout(self, provider_backend_available=_PROVIDER_BACKEND)

    def _toggle_model_ops_panel(self) -> None:
        ops_toggle_model_ops_panel(self)

    def _set_ops_status(self, text: str, ok: bool = True, *, tone: str | None = None) -> None:
        ops_set_ops_status(self, text, ok, tone=tone)

    def _check_model_health(self) -> None:
        ops_check_model_health(self)

    def _on_health_checked(self, payload: dict[str, str]) -> None:
        ops_on_health_checked(self, payload)

    def _run_ollama_model_op(self, operation: str) -> None:
        ops_run_model_op(self, operation)

    def _on_model_op_finished(self, payload: dict[str, Any]) -> None:
        ops_on_model_op_finished(self, payload)

    def _refresh_loadout_inputs(self) -> None:
        management_refresh_loadout_inputs(self)

    def _on_loadout_changed(self, field_name: str, value: str) -> None:
        management_on_loadout_changed(self, field_name, value)

    def _refresh_loadout_help(self) -> None:
        management_refresh_loadout_help(self)

    def _apply_model_loadout(self) -> None:
        management_apply_model_loadout(
            self,
            runtime_settings_backend_available=_RUNTIME_SETTINGS_BACKEND,
            loadout_fields=_LOADOUT_FIELDS,
        )

    def _spawn_loadout_models(self, *, include_main: bool, include_subs: bool) -> None:
        management_spawn_loadout_models(
            self,
            include_main=include_main,
            include_subs=include_subs,
            loadout_fields=_LOADOUT_FIELDS,
        )

    def _on_spawn_finished(self, payload: dict[str, Any]) -> None:
        management_on_spawn_finished(self, payload)

    def _set_selected_runtime_role(self, field_name: str) -> None:
        runtime_library_set_selected_runtime_role(self, field_name, _LEMONADE_ROLE_FIELDS)

    def _assign_runtime_model(self, model_name: str) -> None:
        runtime_library_assign_runtime_model(self, model_name)

    def _refresh_runtime_library(self) -> None:
        runtime_library_refresh_runtime_library(self)

    def _on_runtime_backend_changed(self, text: str) -> None:
        runtime_settings_on_runtime_backend_changed(
            self,
            text,
            normalize_runtime_backend=normalize_runtime_backend,
        )

    def _save_runtime_settings(self) -> None:
        runtime_settings_save_runtime_settings(
            self,
            runtime_settings_backend_available=_RUNTIME_SETTINGS_BACKEND,
            save_app_settings=save_app_settings,
            normalize_runtime_backend=normalize_runtime_backend,
        )

    def _refresh(self) -> None:
        library_refresh_local_runtime_library(self)

    def _on_local_result(self, payload: dict[str, Any]) -> None:
        library_refresh_on_local_result(self, payload)

    def _on_model_selected(self, name: str) -> None:
        library_refresh_on_model_selected(self, name)

    def set_status_snapshot(self, payload: dict[str, Any]) -> None:
        self._status_snapshot = payload if isinstance(payload, dict) else {}
        runtime = self._status_snapshot.get("local_runtime", {}) if isinstance(self._status_snapshot, dict) else {}
        live_policy = runtime.get("policy", {}) if isinstance(runtime, dict) else {}
        if isinstance(live_policy, dict) and live_policy:
            self._policy_snapshot = live_policy
        else:
            self._policy_snapshot = self._load_local_llm_policy()
        self._render_runtime_policy()
        self._render_runtime_evidence()
        self._refresh_library_summary()

    def _load_route_config(self) -> None:
        management_load_route_config(
            self,
            provider_backend_available=_PROVIDER_BACKEND,
            runtime_dir=_RUNTIME,
            heartbeat_fresh_seconds=_HEARTBEAT_FRESH_SECONDS,
        )

    def _refresh_route_summary(self) -> None:
        management_refresh_route_summary(
            self,
            runtime_dir=_RUNTIME,
            heartbeat_fresh_seconds=_HEARTBEAT_FRESH_SECONDS,
        )

    def _refresh_route_preview(self) -> None:
        management_refresh_route_preview(
            self,
            runtime_dir=_RUNTIME,
            heartbeat_fresh_seconds=_HEARTBEAT_FRESH_SECONDS,
        )

    def _apply_routes(self) -> None:
        management_apply_routes(
            self,
            provider_backend_available=_PROVIDER_BACKEND,
            runtime_dir=_RUNTIME,
            heartbeat_fresh_seconds=_HEARTBEAT_FRESH_SECONDS,
        )
