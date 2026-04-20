from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .. import tokens as T


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
    loadout_title = QLabel("LOCAL LOADOUT (MAIN + 2 SUB MODELS)")
    loadout_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
    status_label = QLabel("Set a main model and two spawnable sub models")
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
    backend_combo.addItems(["OLLAMA", "LEMONADE"])
    backend_combo.setFixedWidth(160)
    backend_combo.currentTextChanged.connect(on_runtime_backend_changed)
    row.addWidget(backend_combo)
    row.addWidget(QLabel("LEMONADE ENDPOINT"))
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
    runtime_library_title = QLabel("LEMONADE MODEL PICKER")
    runtime_library_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
    runtime_library_target_label = QLabel("Assigning to FAST")
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
