from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from src.guppy.experience_config import (
    load_runtime_settings as load_app_settings,
    personalization_backend_available,
    runtime_settings_backend_available,
    save_runtime_settings as save_app_settings,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from src.guppy.launcher_application.models_route_support import parse_fallback_chain, route_targets_from_registry
from src.guppy.launcher_application.models_presenter import (
    build_models_active_identity_text,
    build_models_library_hint_text,
    build_models_route_preview_hint_text,
    build_models_runtime_identity_text,
)
from .. import tokens as T
from .models_library_panel import build_models_library_panel
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
from .models_sections import _ModelCard, build_models_route_section, build_models_runtime_section
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
    {"name": "claude-opus-4", "display": "Claude Opus 4", "context": "200K tokens", "tier": "CLOUD", "note": "Maximum intelligence"},
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
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("models_topbar")
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(f"QFrame#models_topbar {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(28, 0, 28, 0)
        self._title_lbl = QLabel("MODELS")
        self._title_lbl.setStyleSheet(
            f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
        )
        self._active_lbl = QLabel(build_models_active_identity_text(self._active_model))
        self._active_lbl.setStyleSheet(
            f"color: {T.ACCENT_ORANGE}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        self._active_runtime_lbl = QLabel(build_models_runtime_identity_text(self._local_runtime_backend))
        self._active_runtime_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setToolTip("Reload the local model list and runtime readiness from the selected backend")
        self._refresh_btn.clicked.connect(self._refresh)
        tb.addWidget(self._title_lbl)
        tb.addStretch()
        tb.addWidget(self._active_lbl)
        tb.addSpacing(16)
        tb.addWidget(self._active_runtime_lbl)
        tb.addSpacing(16)
        tb.addWidget(self._refresh_btn)
        root.addWidget(topbar)

        library_panel = build_models_library_panel(
            loadout_fields=_LOADOUT_FIELDS,
            cloud_models=CLOUD_MODELS,
            on_search_changed=self._apply_library_filter,
            on_loadout_changed=self._on_loadout_changed,
            on_apply_loadout=self._apply_model_loadout,
            on_spawn_main=lambda: self._spawn_loadout_models(include_main=True, include_subs=False),
            on_spawn_subs=lambda: self._spawn_loadout_models(include_main=False, include_subs=True),
            on_spawn_all=lambda: self._spawn_loadout_models(include_main=True, include_subs=True),
            on_model_selected=self._on_model_selected,
        )
        self._library_summary_frame = library_panel.summary_frame
        self._library_summary_lbl = library_panel.summary_label
        self._library_search = library_panel.search_input
        self._library_hint_lbl = library_panel.hint_label
        self._loadout_frame = library_panel.loadout_frame
        self._loadout_status_lbl = library_panel.loadout_status_label
        self._loadout_inputs = library_panel.loadout_inputs
        self._apply_loadout_btn = library_panel.apply_loadout_button
        self._spawn_main_btn = library_panel.spawn_main_button
        self._spawn_subs_btn = library_panel.spawn_subs_button
        self._spawn_all_btn = library_panel.spawn_all_button
        self._loadout_help_lbl = library_panel.loadout_help_label
        self._library_scroll = library_panel.scroll
        self._grid = library_panel.grid
        self._local_header = library_panel.local_header
        self._cloud_header = library_panel.cloud_header
        self._local_host = library_panel.local_host
        self._local_layout = library_panel.local_layout
        self._local_sections = library_panel.local_sections
        self._local_section_layouts = library_panel.local_section_layouts
        self._local_section_cards = library_panel.local_section_cards
        self._local_placeholder = library_panel.local_placeholder
        self._cloud_host = library_panel.cloud_host
        self._cloud_layout = library_panel.cloud_layout
        self._cloud_cards = library_panel.cloud_cards
        self._library_hint_lbl.setText(build_models_library_hint_text())
        root.addWidget(self._library_summary_frame)

        runtime_section = build_models_runtime_section(
            lemonade_role_fields=_LEMONADE_ROLE_FIELDS,
            default_lemonade_base_url=_DEFAULT_LEMONADE_BASE_URL,
            on_runtime_backend_changed=self._on_runtime_backend_changed,
            on_save_runtime_settings=self._save_runtime_settings,
            on_set_selected_runtime_role=self._set_selected_runtime_role,
            on_refresh_runtime_library=self._refresh_runtime_library,
        )
        self._runtime_bar = runtime_section.frame
        self._runtime_backend_cb = runtime_section.backend_combo
        self._runtime_endpoint_lbl = runtime_section.endpoint_label
        self._lemonade_base_url_input = runtime_section.lemonade_base_url_input
        self._save_runtime_btn = runtime_section.save_button
        self._lemonade_role_inputs = runtime_section.lemonade_role_inputs
        self._runtime_library_frame = runtime_section.runtime_library_frame
        self._runtime_library_title = runtime_section.runtime_library_title
        self._runtime_library_target_lbl = runtime_section.runtime_library_target_label
        self._runtime_library_search = runtime_section.runtime_library_search
        self._runtime_library_summary_lbl = runtime_section.runtime_library_summary_label
        self._runtime_library_host = runtime_section.runtime_library_host
        self._runtime_library_grid = runtime_section.runtime_library_grid
        self._runtime_summary_lbl = runtime_section.runtime_summary_label
        self._runtime_policy_lbl = runtime_section.runtime_policy_label
        self._runtime_live_lbl = runtime_section.runtime_live_label
        self._runtime_status_lbl = runtime_section.runtime_status_label
        root.addWidget(self._runtime_bar)

        route_section = build_models_route_section(
            mix_route_fields=_MIX_ROUTE_FIELDS,
            route_modes=list(LAUNCHER_MODES_DISPLAY),
            on_route_changed=self._refresh_route_summary,
            on_apply_routes=self._apply_routes,
            on_apply_mix=self._apply_mixed_loadout,
            on_toggle_ops=self._toggle_model_ops_panel,
            on_download=lambda: self._run_ollama_model_op("pull"),
            on_uninstall=lambda: self._run_ollama_model_op("rm"),
            on_check_health=self._check_model_health,
            on_route_mode_changed=lambda _text: self._refresh_route_preview(),
            on_route_input_changed=lambda _text: self._refresh_route_preview(),
        )
        self._route_bar = route_section.frame
        self._simple_route_cb = route_section.simple_route_combo
        self._complex_route_cb = route_section.complex_route_combo
        self._teaching_route_cb = route_section.teaching_route_combo
        self._fallback_chain_input = route_section.fallback_chain_input
        self._apply_routes_btn = route_section.apply_routes_button
        self._mix_status_lbl = route_section.mix_status_label
        self._mix_route_inputs = route_section.mix_route_inputs
        self._apply_mix_btn = route_section.apply_mix_button
        self._ops_toggle_btn = route_section.ops_toggle_button
        self._ops_panel = route_section.ops_panel
        self._ops_model_input = route_section.ops_model_input
        self._ops_download_btn = route_section.ops_download_button
        self._ops_uninstall_btn = route_section.ops_uninstall_button
        self._ops_health_btn = route_section.ops_health_button
        self._ops_status_lbl = route_section.ops_status_label
        self._route_status_lbl = route_section.route_status_label
        self._route_summary_lbl = route_section.route_summary_label
        self._route_evidence_lbl = route_section.route_evidence_label
        self._route_mode_cb = route_section.route_mode_combo
        self._route_input = route_section.route_input
        self._route_preview_lbl = route_section.route_preview_label
        self._route_preview_lbl.setText(build_models_route_preview_hint_text())
        root.addWidget(self._route_bar)

        root.addWidget(self._library_scroll)

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
