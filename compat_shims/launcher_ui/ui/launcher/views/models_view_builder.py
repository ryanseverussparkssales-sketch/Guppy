"""
models_view_builder.py
UI construction for ModelsView — separated to keep the view class under the 550-line cap.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import tokens as T
from .models_library_panel import build_models_library_panel
from .models_presenter import (
    build_models_active_identity_text,
    build_models_library_hint_text,
    build_models_route_preview_hint_text,
    build_models_runtime_identity_text,
)
from .models_sections import build_models_route_section, build_models_runtime_section


def build_models_ui(
    owner: Any,
    *,
    loadout_fields: list[tuple[str, str]],
    cloud_models: list[dict[str, str]],
    lemonade_role_fields: list[tuple[str, str]],
    default_lemonade_base_url: str,
    mix_route_fields: list[tuple[str, str]],
    route_modes: list[str],
) -> None:
    root = QVBoxLayout(owner)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    topbar = QFrame()
    topbar.setObjectName("models_topbar")
    topbar.setFixedHeight(52)
    topbar.setStyleSheet(f"QFrame#models_topbar {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}")
    tb = QHBoxLayout(topbar)
    tb.setContentsMargins(28, 0, 28, 0)
    owner._title_lbl = QLabel("MODELS")
    owner._title_lbl.setStyleSheet(
        f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
    )
    owner._active_lbl = QLabel(build_models_active_identity_text(owner._active_model))
    owner._active_lbl.setStyleSheet(
        f"color: {T.ACCENT_ORANGE}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
    )
    owner._active_runtime_lbl = QLabel(build_models_runtime_identity_text(owner._local_runtime_backend))
    owner._active_runtime_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
    )
    owner._refresh_btn = QPushButton("REFRESH")
    owner._refresh_btn.setFixedHeight(28)
    owner._refresh_btn.setToolTip("Reload the local model list and runtime readiness from the selected backend")
    owner._refresh_btn.clicked.connect(owner._refresh)
    tb.addWidget(owner._title_lbl)
    tb.addStretch()
    tb.addWidget(owner._active_lbl)
    tb.addSpacing(16)
    tb.addWidget(owner._active_runtime_lbl)
    tb.addSpacing(16)
    tb.addWidget(owner._refresh_btn)
    root.addWidget(topbar)

    library_panel = build_models_library_panel(
        loadout_fields=loadout_fields,
        cloud_models=cloud_models,
        on_search_changed=owner._apply_library_filter,
        on_loadout_changed=owner._on_loadout_changed,
        on_apply_loadout=owner._apply_model_loadout,
        on_spawn_main=lambda: owner._spawn_loadout_models(include_main=True, include_subs=False),
        on_spawn_subs=lambda: owner._spawn_loadout_models(include_main=False, include_subs=True),
        on_spawn_all=lambda: owner._spawn_loadout_models(include_main=True, include_subs=True),
        on_model_selected=owner._on_model_selected,
    )
    owner._library_summary_frame = library_panel.summary_frame
    owner._library_summary_lbl = library_panel.summary_label
    owner._library_search = library_panel.search_input
    owner._library_hint_lbl = library_panel.hint_label
    owner._loadout_frame = library_panel.loadout_frame
    owner._loadout_status_lbl = library_panel.loadout_status_label
    owner._loadout_inputs = library_panel.loadout_inputs
    owner._apply_loadout_btn = library_panel.apply_loadout_button
    owner._spawn_main_btn = library_panel.spawn_main_button
    owner._spawn_subs_btn = library_panel.spawn_subs_button
    owner._spawn_all_btn = library_panel.spawn_all_button
    owner._loadout_help_lbl = library_panel.loadout_help_label
    owner._library_scroll = library_panel.scroll
    owner._grid = library_panel.grid
    owner._local_header = library_panel.local_header
    owner._cloud_header = library_panel.cloud_header
    owner._local_host = library_panel.local_host
    owner._local_layout = library_panel.local_layout
    owner._local_sections = library_panel.local_sections
    owner._local_section_layouts = library_panel.local_section_layouts
    owner._local_section_cards = library_panel.local_section_cards
    owner._local_placeholder = library_panel.local_placeholder
    owner._cloud_host = library_panel.cloud_host
    owner._cloud_layout = library_panel.cloud_layout
    owner._cloud_cards = library_panel.cloud_cards
    owner._library_hint_lbl.setText(build_models_library_hint_text())
    root.addWidget(owner._library_summary_frame)

    runtime_section = build_models_runtime_section(
        lemonade_role_fields=lemonade_role_fields,
        default_lemonade_base_url=default_lemonade_base_url,
        on_runtime_backend_changed=owner._on_runtime_backend_changed,
        on_save_runtime_settings=owner._save_runtime_settings,
        on_set_selected_runtime_role=owner._set_selected_runtime_role,
        on_refresh_runtime_library=owner._refresh_runtime_library,
    )
    owner._runtime_bar = runtime_section.frame
    owner._runtime_backend_cb = runtime_section.backend_combo
    owner._runtime_endpoint_lbl = runtime_section.endpoint_label
    owner._lemonade_base_url_input = runtime_section.lemonade_base_url_input
    owner._save_runtime_btn = runtime_section.save_button
    owner._lemonade_role_inputs = runtime_section.lemonade_role_inputs
    owner._runtime_library_frame = runtime_section.runtime_library_frame
    owner._runtime_library_title = runtime_section.runtime_library_title
    owner._runtime_library_target_lbl = runtime_section.runtime_library_target_label
    owner._runtime_library_search = runtime_section.runtime_library_search
    owner._runtime_library_summary_lbl = runtime_section.runtime_library_summary_label
    owner._runtime_library_host = runtime_section.runtime_library_host
    owner._runtime_library_grid = runtime_section.runtime_library_grid
    owner._runtime_summary_lbl = runtime_section.runtime_summary_label
    owner._runtime_policy_lbl = runtime_section.runtime_policy_label
    owner._runtime_live_lbl = runtime_section.runtime_live_label
    owner._runtime_status_lbl = runtime_section.runtime_status_label
    root.addWidget(owner._runtime_bar)

    route_section = build_models_route_section(
        mix_route_fields=mix_route_fields,
        route_modes=route_modes,
        on_route_changed=owner._refresh_route_summary,
        on_apply_routes=owner._apply_routes,
        on_apply_mix=owner._apply_mixed_loadout,
        on_toggle_ops=owner._toggle_model_ops_panel,
        on_download=lambda: owner._run_ollama_model_op("pull"),
        on_uninstall=lambda: owner._run_ollama_model_op("rm"),
        on_check_health=owner._check_model_health,
        on_route_mode_changed=lambda _text: owner._refresh_route_preview(),
        on_route_input_changed=lambda _text: owner._refresh_route_preview(),
    )
    owner._route_bar = route_section.frame
    owner._simple_route_cb = route_section.simple_route_combo
    owner._complex_route_cb = route_section.complex_route_combo
    owner._teaching_route_cb = route_section.teaching_route_combo
    owner._fallback_chain_input = route_section.fallback_chain_input
    owner._apply_routes_btn = route_section.apply_routes_button
    owner._mix_status_lbl = route_section.mix_status_label
    owner._mix_route_inputs = route_section.mix_route_inputs
    owner._apply_mix_btn = route_section.apply_mix_button
    owner._ops_toggle_btn = route_section.ops_toggle_button
    owner._ops_panel = route_section.ops_panel
    owner._ops_model_input = route_section.ops_model_input
    owner._ops_download_btn = route_section.ops_download_button
    owner._ops_uninstall_btn = route_section.ops_uninstall_button
    owner._ops_health_btn = route_section.ops_health_button
    owner._ops_status_lbl = route_section.ops_status_label
    owner._route_status_lbl = route_section.route_status_label
    owner._route_summary_lbl = route_section.route_summary_label
    owner._route_evidence_lbl = route_section.route_evidence_label
    owner._route_mode_cb = route_section.route_mode_combo
    owner._route_input = route_section.route_input
    owner._route_preview_lbl = route_section.route_preview_label
    owner._route_preview_lbl.setText(build_models_route_preview_hint_text())
    root.addWidget(owner._route_bar)

    root.addWidget(owner._library_scroll)
