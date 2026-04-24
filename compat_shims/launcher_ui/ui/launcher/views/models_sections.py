from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .. import tokens as T
from .models_panel_support import _ColumnHeader, _ModelCard, _fmt_size  # noqa: F401 – re-exported for consumers


@dataclass(slots=True)
class ModelsLoadoutSection:
    frame: QFrame
    status_label: QLabel
    inputs: dict[str, QComboBox]
    apply_button: QPushButton
    spawn_main_button: QPushButton
    spawn_subs_button: QPushButton
    spawn_all_button: QPushButton
    help_label: QLabel


@dataclass(slots=True)
class ModelsRuntimeSection:
    frame: QFrame
    backend_combo: QComboBox
    endpoint_label: QLabel
    lemonade_base_url_input: QLineEdit
    save_button: QPushButton
    lemonade_role_inputs: dict[str, QComboBox]
    runtime_library_frame: QFrame
    runtime_library_title: QLabel
    runtime_library_target_label: QLabel
    runtime_library_search: QLineEdit
    runtime_library_summary_label: QLabel
    runtime_library_host: QWidget
    runtime_library_grid: QGridLayout
    runtime_summary_label: QLabel
    runtime_policy_label: QLabel
    runtime_live_label: QLabel
    runtime_status_label: QLabel


@dataclass(slots=True)
class ModelsRouteSection:
    frame: QFrame
    simple_route_combo: QComboBox
    complex_route_combo: QComboBox
    teaching_route_combo: QComboBox
    fallback_chain_input: QLineEdit
    apply_routes_button: QPushButton
    mix_status_label: QLabel
    mix_route_inputs: dict[str, QComboBox]
    apply_mix_button: QPushButton
    ops_toggle_button: QPushButton
    ops_panel: QFrame
    ops_model_input: QLineEdit
    ops_download_button: QPushButton
    ops_uninstall_button: QPushButton
    ops_health_button: QPushButton
    ops_status_label: QLabel
    route_status_label: QLabel
    route_summary_label: QLabel
    route_evidence_label: QLabel
    route_mode_combo: QComboBox
    route_input: QLineEdit
    route_preview_label: QLabel


def build_models_loadout_section(
    *,
    loadout_fields: list[tuple[str, str]],
    on_loadout_changed: Callable[[str, str], None],
    on_apply_loadout: Callable[[], None],
    on_spawn_main: Callable[[], None],
    on_spawn_subs: Callable[[], None],
    on_spawn_all: Callable[[], None],
) -> ModelsLoadoutSection:
    frame = QFrame()
    frame.setStyleSheet(f"background-color: {T.BG1}; border: 1px solid {T.BORDER};")
    loadout_layout = QVBoxLayout(frame)
    loadout_layout.setContentsMargins(10, 10, 10, 10)
    loadout_layout.setSpacing(8)

    loadout_header = QHBoxLayout()
    loadout_title = QLabel("LOCAL MODEL LOADOUT (MAIN + 2 SPAWNED MODELS)")
    loadout_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
    status_label = QLabel("Set the main assistant model and two spawned secondary models")
    status_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    loadout_header.addWidget(loadout_title)
    loadout_header.addStretch()
    loadout_header.addWidget(status_label)
    loadout_layout.addLayout(loadout_header)

    inputs: dict[str, QComboBox] = {}
    loadout_grid = QGridLayout()
    loadout_grid.setHorizontalSpacing(10)
    loadout_grid.setVerticalSpacing(8)
    for index, (field_name, field_label) in enumerate(loadout_fields):
        label = QLabel(field_label)
        label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMinimumWidth(240)
        combo.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 4px 6px;")
        combo.currentTextChanged.connect(lambda value, target=field_name: on_loadout_changed(target, value))
        loadout_grid.addWidget(label, index, 0)
        loadout_grid.addWidget(combo, index, 1)
        inputs[field_name] = combo
    loadout_layout.addLayout(loadout_grid)

    loadout_buttons = QHBoxLayout()
    apply_button = QPushButton("APPLY LOADOUT")
    apply_button.setFixedHeight(28)
    apply_button.setToolTip("Save and apply the current main and sub model loadout configuration")
    apply_button.clicked.connect(on_apply_loadout)
    spawn_main_button = QPushButton("SPAWN MAIN")
    spawn_main_button.setFixedHeight(28)
    spawn_main_button.setToolTip("Start the main model on the local runtime engine")
    spawn_main_button.clicked.connect(on_spawn_main)
    spawn_subs_button = QPushButton("SPAWN SUBS")
    spawn_subs_button.setFixedHeight(28)
    spawn_subs_button.setToolTip("Start sub-agent models A and B on the local runtime engine")
    spawn_subs_button.clicked.connect(on_spawn_subs)
    spawn_all_button = QPushButton("SPAWN ALL")
    spawn_all_button.setFixedHeight(28)
    spawn_all_button.setToolTip("Start the main model and both sub-agent models on the local runtime engine")
    spawn_all_button.clicked.connect(on_spawn_all)
    loadout_buttons.addWidget(apply_button)
    loadout_buttons.addWidget(spawn_main_button)
    loadout_buttons.addWidget(spawn_subs_button)
    loadout_buttons.addWidget(spawn_all_button)
    loadout_buttons.addStretch()
    loadout_layout.addLayout(loadout_buttons)

    help_label = QLabel("")
    help_label.setWordWrap(True)
    help_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    loadout_layout.addWidget(help_label)

    return ModelsLoadoutSection(
        frame=frame,
        status_label=status_label,
        inputs=inputs,
        apply_button=apply_button,
        spawn_main_button=spawn_main_button,
        spawn_subs_button=spawn_subs_button,
        spawn_all_button=spawn_all_button,
        help_label=help_label,
    )


def build_models_runtime_section(
    *,
    lemonade_role_fields: list[tuple[str, str]],
    default_lemonade_base_url: str,
    on_runtime_backend_changed: Callable[[str], None],
    on_save_runtime_settings: Callable[[], None],
    on_set_selected_runtime_role: Callable[[str], None],
    on_refresh_runtime_library: Callable[[], None],
) -> ModelsRuntimeSection:
    frame = QFrame()
    frame.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(28, 12, 28, 12)
    layout.setSpacing(8)

    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(QLabel("LOCAL RUNTIME"))
    backend_combo = QComboBox()
    backend_combo.addItems(["OLLAMA", "LM STUDIO", "LOCAL HARNESS", "LEMONADE"])
    backend_combo.setFixedWidth(160)
    backend_combo.currentTextChanged.connect(on_runtime_backend_changed)
    row.addWidget(backend_combo)
    endpoint_label = QLabel("RUNTIME ENDPOINT")
    row.addWidget(endpoint_label)
    lemonade_base_url_input = QLineEdit()
    lemonade_base_url_input.setPlaceholderText(default_lemonade_base_url)
    lemonade_base_url_input.setMinimumWidth(280)
    lemonade_base_url_input.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
    save_button = QPushButton("SAVE RUNTIME")
    save_button.setFixedHeight(28)
    save_button.setToolTip("Save current runtime settings including base URL and model role assignments")
    save_button.clicked.connect(on_save_runtime_settings)
    row.addWidget(lemonade_base_url_input)
    row.addWidget(save_button)
    row.addStretch()
    layout.addLayout(row)

    lemonade_role_inputs: dict[str, QComboBox] = {}
    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(8)
    for index, (field_name, label_text) in enumerate(lemonade_role_fields):
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMinimumWidth(220)
        combo.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 4px 6px;")
        combo.currentTextChanged.connect(lambda _=None, target_field=field_name: on_set_selected_runtime_role(target_field))
        grid.addWidget(label, index // 3, (index % 3) * 2)
        grid.addWidget(combo, index // 3, (index % 3) * 2 + 1)
        lemonade_role_inputs[field_name] = combo
    layout.addLayout(grid)

    runtime_library_frame = QFrame()
    runtime_library_frame.setStyleSheet(f"background-color: {T.BG1}; border: 1px solid {T.BORDER};")
    library_layout = QVBoxLayout(runtime_library_frame)
    library_layout.setContentsMargins(10, 10, 10, 10)
    library_layout.setSpacing(8)
    library_hdr = QHBoxLayout()
    runtime_library_title = QLabel("LOCAL RUNTIME MODEL PICKER")
    runtime_library_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
    runtime_library_target_label = QLabel("Assigning to DAILY SLOT")
    runtime_library_target_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    library_hdr.addWidget(runtime_library_title)
    library_hdr.addStretch()
    library_hdr.addWidget(runtime_library_target_label)
    library_layout.addLayout(library_hdr)
    runtime_library_search = QLineEdit()
    runtime_library_search.setPlaceholderText("Search downloaded models...")
    runtime_library_search.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
    runtime_library_search.textChanged.connect(lambda _=None: on_refresh_runtime_library())
    library_layout.addWidget(runtime_library_search)
    runtime_library_summary_label = QLabel("")
    runtime_library_summary_label.setWordWrap(True)
    runtime_library_summary_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    library_layout.addWidget(runtime_library_summary_label)
    runtime_library_host = QWidget()
    runtime_library_grid = QGridLayout(runtime_library_host)
    runtime_library_grid.setContentsMargins(0, 0, 0, 0)
    runtime_library_grid.setHorizontalSpacing(8)
    runtime_library_grid.setVerticalSpacing(8)
    library_layout.addWidget(runtime_library_host)
    layout.addWidget(runtime_library_frame)

    runtime_summary_label = QLabel("")
    runtime_summary_label.setWordWrap(True)
    runtime_summary_label.setStyleSheet(f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
    runtime_policy_label = QLabel("")
    runtime_policy_label.setWordWrap(True)
    runtime_policy_label.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
    runtime_live_label = QLabel("Live lane evidence will appear here after the next /status poll.")
    runtime_live_label.setWordWrap(True)
    runtime_live_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
    runtime_status_label = QLabel("Local runtime controls ready")
    runtime_status_label.setWordWrap(True)
    runtime_status_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
    layout.addWidget(runtime_summary_label)
    layout.addWidget(runtime_policy_label)
    layout.addWidget(runtime_live_label)
    layout.addWidget(runtime_status_label)

    return ModelsRuntimeSection(
        frame=frame,
        backend_combo=backend_combo,
        endpoint_label=endpoint_label,
        lemonade_base_url_input=lemonade_base_url_input,
        save_button=save_button,
        lemonade_role_inputs=lemonade_role_inputs,
        runtime_library_frame=runtime_library_frame,
        runtime_library_title=runtime_library_title,
        runtime_library_target_label=runtime_library_target_label,
        runtime_library_search=runtime_library_search,
        runtime_library_summary_label=runtime_library_summary_label,
        runtime_library_host=runtime_library_host,
        runtime_library_grid=runtime_library_grid,
        runtime_summary_label=runtime_summary_label,
        runtime_policy_label=runtime_policy_label,
        runtime_live_label=runtime_live_label,
        runtime_status_label=runtime_status_label,
    )


def build_models_route_section(
    *,
    mix_route_fields: list[tuple[str, str]],
    route_modes: list[str],
    on_route_changed: Callable[[], None],
    on_apply_routes: Callable[[], None],
    on_apply_mix: Callable[[], None],
    on_toggle_ops: Callable[[], None],
    on_download: Callable[[], None],
    on_uninstall: Callable[[], None],
    on_check_health: Callable[[], None],
    on_route_mode_changed: Callable[[str], None],
    on_route_input_changed: Callable[[str], None],
) -> ModelsRouteSection:
    frame = QFrame()
    frame.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(28, 10, 28, 10)
    layout.setSpacing(8)

    route_row = QHBoxLayout()
    route_row.setSpacing(10)

    def _task_combo(label_text: str) -> QComboBox:
        route_row.addWidget(QLabel(label_text))
        combo = QComboBox()
        combo.setFixedWidth(300)
        combo.currentTextChanged.connect(lambda _=None: on_route_changed())
        route_row.addWidget(combo)
        return combo

    simple_route_combo = _task_combo("TASK: SIMPLE")
    complex_route_combo = _task_combo("TASK: COMPLEX")
    teaching_route_combo = _task_combo("TASK: TEACHING")
    route_row.addStretch()
    layout.addLayout(route_row)

    fallback_row = QHBoxLayout()
    fallback_row.setSpacing(10)
    fallback_row.addWidget(QLabel("FALLBACK CHAIN"))
    fallback_chain_input = QLineEdit("")
    fallback_chain_input.textChanged.connect(lambda _=None: on_route_changed())
    fallback_chain_input.setMinimumWidth(620)
    fallback_chain_input.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
    )
    apply_routes_button = QPushButton("APPLY ROUTES")
    apply_routes_button.setFixedHeight(28)
    apply_routes_button.setToolTip("Save the current task-to-model route assignments and fallback chain")
    apply_routes_button.clicked.connect(on_apply_routes)
    fallback_row.addWidget(fallback_chain_input)
    fallback_row.addWidget(apply_routes_button)
    fallback_row.addStretch()
    layout.addLayout(fallback_row)

    mix_routes_frame = QFrame()
    mix_routes_frame.setStyleSheet(f"background-color: {T.BG1}; border: 1px solid {T.BORDER};")
    mix_layout = QVBoxLayout(mix_routes_frame)
    mix_layout.setContentsMargins(10, 10, 10, 10)
    mix_layout.setSpacing(8)
    mix_header = QHBoxLayout()
    mix_title = QLabel("MIXED ROUTE LOADOUT")
    mix_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
    mix_status_label = QLabel("Mix local, cloud, and API providers by route target")
    mix_status_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    mix_header.addWidget(mix_title)
    mix_header.addStretch()
    mix_header.addWidget(mix_status_label)
    mix_layout.addLayout(mix_header)
    mix_grid = QGridLayout()
    mix_grid.setHorizontalSpacing(10)
    mix_grid.setVerticalSpacing(8)
    mix_route_inputs: dict[str, QComboBox] = {}
    for index, (field_name, label_text) in enumerate(mix_route_fields):
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMinimumWidth(320)
        combo.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
            f"background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 4px 6px;"
        )
        mix_grid.addWidget(label, index, 0)
        mix_grid.addWidget(combo, index, 1)
        mix_route_inputs[field_name] = combo
    mix_layout.addLayout(mix_grid)
    mix_actions = QHBoxLayout()
    apply_mix_button = QPushButton("APPLY MIX")
    apply_mix_button.setFixedHeight(28)
    apply_mix_button.setToolTip("Save the mixed route assignments for the main assistant and spawned models")
    apply_mix_button.clicked.connect(on_apply_mix)
    mix_actions.addWidget(apply_mix_button)
    mix_actions.addStretch()
    mix_layout.addLayout(mix_actions)
    layout.addWidget(mix_routes_frame)

    ops_toggle_button = QPushButton("MODEL HEALTH + READINESS")
    ops_toggle_button.setFixedHeight(28)
    ops_toggle_button.setToolTip("Show or hide local runtime health, download, and uninstall controls")
    ops_toggle_button.clicked.connect(on_toggle_ops)
    layout.addWidget(ops_toggle_button)

    ops_panel = QFrame()
    ops_panel.setVisible(False)
    ops_panel.setStyleSheet(f"background-color: {T.BG1}; border: 1px solid {T.BORDER};")
    ops_layout = QVBoxLayout(ops_panel)
    ops_layout.setContentsMargins(10, 10, 10, 10)
    ops_layout.setSpacing(8)
    endpoints_lbl = QLabel(
        "Runtime readiness lives here, but provider accounts and API-key storage stay unified in Settings. "
        "Hidden endpoints remain environment-driven: LM Studio (GUPPY_LMSTUDIO_BASE_URL), local harness (GUPPY_LOCAL_HARNESS_BASE_URL), and any cloud-provider API keys."
    )
    endpoints_lbl.setWordWrap(True)
    endpoints_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    ops_layout.addWidget(endpoints_lbl)
    connector_note_lbl = QLabel(
        "Connector lane: Ollama install/uninstall and warm-spawn are live here. "
        "LM Studio is discovery/readiness-only today. Local harness is a development and benchmark lane. "
        "Hugging Face local is planned behind the harness/OpenAI-compatible adapter path before it becomes a saved runtime backend."
    )
    connector_note_lbl.setWordWrap(True)
    connector_note_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    ops_layout.addWidget(connector_note_lbl)
    ops_row = QHBoxLayout()
    ops_row.setSpacing(8)
    ops_model_input = QLineEdit()
    ops_model_input.setPlaceholderText("model id e.g. llama3.2:3b")
    ops_model_input.setMinimumWidth(260)
    ops_model_input.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
    )
    ops_download_button = QPushButton("DOWNLOAD")
    ops_download_button.setFixedHeight(28)
    ops_download_button.setToolTip("Download this model to the local Ollama runtime (ollama pull)")
    ops_download_button.clicked.connect(on_download)
    ops_uninstall_button = QPushButton("UNINSTALL")
    ops_uninstall_button.setFixedHeight(28)
    ops_uninstall_button.setToolTip("Remove this model from the local Ollama runtime (ollama rm)")
    ops_uninstall_button.clicked.connect(on_uninstall)
    ops_health_button = QPushButton("CHECK HEALTH")
    ops_health_button.setFixedHeight(28)
    ops_health_button.setToolTip("Run a quick health check against the active local runtime")
    ops_health_button.clicked.connect(on_check_health)
    ops_row.addWidget(ops_model_input)
    ops_row.addWidget(ops_download_button)
    ops_row.addWidget(ops_uninstall_button)
    ops_row.addWidget(ops_health_button)
    ops_row.addStretch()
    ops_layout.addLayout(ops_row)
    ops_status_label = QLabel("Health and provider readiness are hidden by default")
    ops_status_label.setWordWrap(True)
    ops_status_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    ops_layout.addWidget(ops_status_label)
    layout.addWidget(ops_panel)

    route_status_label = QLabel("Route strategy ready")
    route_status_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
    route_summary_label = QLabel("")
    route_summary_label.setWordWrap(True)
    route_summary_label.setStyleSheet(
        f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
    )
    route_evidence_label = QLabel("")
    route_evidence_label.setWordWrap(True)
    route_evidence_label.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
    )
    layout.addWidget(route_status_label)
    layout.addWidget(route_summary_label)
    layout.addWidget(route_evidence_label)

    preview_row = QHBoxLayout()
    preview_row.setSpacing(10)
    preview_row.addWidget(QLabel("WHY THIS MODEL WAS CHOSEN"))
    route_mode_combo = QComboBox()
    route_mode_combo.addItems(route_modes)
    route_mode_combo.setFixedWidth(150)
    route_mode_combo.currentTextChanged.connect(on_route_mode_changed)
    route_input = QLineEdit()
    route_input.setPlaceholderText("Type a sample request to preview task classification and route choice")
    route_input.textChanged.connect(on_route_input_changed)
    route_input.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
    )
    preview_row.addWidget(route_mode_combo)
    preview_row.addWidget(route_input, stretch=1)
    layout.addLayout(preview_row)

    route_preview_label = QLabel("")
    route_preview_label.setWordWrap(True)
    route_preview_label.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
    )
    layout.addWidget(route_preview_label)

    return ModelsRouteSection(
        frame=frame,
        simple_route_combo=simple_route_combo,
        complex_route_combo=complex_route_combo,
        teaching_route_combo=teaching_route_combo,
        fallback_chain_input=fallback_chain_input,
        apply_routes_button=apply_routes_button,
        mix_status_label=mix_status_label,
        mix_route_inputs=mix_route_inputs,
        apply_mix_button=apply_mix_button,
        ops_toggle_button=ops_toggle_button,
        ops_panel=ops_panel,
        ops_model_input=ops_model_input,
        ops_download_button=ops_download_button,
        ops_uninstall_button=ops_uninstall_button,
        ops_health_button=ops_health_button,
        ops_status_label=ops_status_label,
        route_status_label=route_status_label,
        route_summary_label=route_summary_label,
        route_evidence_label=route_evidence_label,
        route_mode_combo=route_mode_combo,
        route_input=route_input,
        route_preview_label=route_preview_label,
    )
