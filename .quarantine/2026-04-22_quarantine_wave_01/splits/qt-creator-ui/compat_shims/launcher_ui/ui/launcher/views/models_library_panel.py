from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import tokens as T
from .models_sections import _ColumnHeader, _ModelCard, build_models_loadout_section


@dataclass(slots=True)
class ModelsLibraryPanel:
    summary_frame: QFrame
    summary_label: QLabel
    search_input: QLineEdit
    hint_label: QLabel
    loadout_frame: QFrame
    loadout_status_label: QLabel
    loadout_inputs: dict[str, object]
    apply_loadout_button: QPushButton
    spawn_main_button: QPushButton
    spawn_subs_button: QPushButton
    spawn_all_button: QPushButton
    loadout_help_label: QLabel
    scroll: QScrollArea
    grid: QGridLayout
    local_header: _ColumnHeader
    cloud_header: _ColumnHeader
    local_host: QWidget
    local_layout: QVBoxLayout
    local_sections: dict[str, QWidget]
    local_section_layouts: dict[str, QVBoxLayout]
    local_section_cards: dict[str, list[_ModelCard]]
    local_placeholder: QLabel
    cloud_host: QWidget
    cloud_layout: QVBoxLayout
    cloud_cards: list[_ModelCard]


def build_models_library_panel(
    *,
    loadout_fields: list[tuple[str, str]],
    cloud_models: list[dict[str, str]],
    on_search_changed: Callable[[], None],
    on_loadout_changed: Callable[[str, str], None],
    on_apply_loadout: Callable[[], None],
    on_spawn_main: Callable[[], None],
    on_spawn_subs: Callable[[], None],
    on_spawn_all: Callable[[], None],
    on_model_selected: Callable[[str], None],
) -> ModelsLibraryPanel:
    summary_frame = QFrame()
    summary_frame.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
    library_shell = QVBoxLayout(summary_frame)
    library_shell.setContentsMargins(28, 14, 28, 14)
    library_shell.setSpacing(8)

    summary_label = QLabel("")
    summary_label.setWordWrap(True)
    summary_label.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 10px;"
    )

    search_row = QHBoxLayout()
    search_row.setSpacing(10)
    search_input = QLineEdit()
    search_input.setPlaceholderText("Search local and cloud models")
    search_input.setMinimumWidth(320)
    search_input.setStyleSheet(
        f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
        f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
    )
    search_input.textChanged.connect(lambda _=None: on_search_changed())
    hint_label = QLabel("")
    hint_label.setWordWrap(True)
    hint_label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
    search_row.addWidget(search_input)
    search_row.addWidget(hint_label, stretch=1)

    library_shell.addWidget(summary_label)
    library_shell.addLayout(search_row)

    loadout_section = build_models_loadout_section(
        loadout_fields=loadout_fields,
        on_loadout_changed=on_loadout_changed,
        on_apply_loadout=on_apply_loadout,
        on_spawn_main=on_spawn_main,
        on_spawn_subs=on_spawn_subs,
        on_spawn_all=on_spawn_all,
    )
    library_shell.addWidget(loadout_section.frame)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    content = QWidget()
    content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    grid = QGridLayout(content)
    grid.setContentsMargins(28, 24, 28, 24)
    grid.setSpacing(16)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)

    local_header = _ColumnHeader("ON THIS PC")
    cloud_header = _ColumnHeader("CLOUD OPTIONS")
    grid.addWidget(local_header, 0, 0)
    grid.addWidget(cloud_header, 0, 1)

    local_host = QWidget()
    local_layout = QVBoxLayout(local_host)
    local_layout.setContentsMargins(0, 0, 0, 0)
    local_layout.setSpacing(16)
    local_sections: dict[str, QWidget] = {}
    local_section_layouts: dict[str, QVBoxLayout] = {}
    local_section_cards: dict[str, list[_ModelCard]] = {
        "recommended": [],
        "installed": [],
        "advanced": [],
    }
    for key, title, subtitle in [
        ("recommended", "RECOMMENDED", "Start here for the best everyday fit on this PC."),
        ("installed", "INSTALLED ON THIS PC", "Other local models you can still use this session."),
        ("advanced", "ADVANCED / EXPERIMENTAL", "More specialized or heavier picks when you want to explore."),
    ]:
        section = QFrame()
        section.setStyleSheet(
            f"background-color: {T.BG1}; border: 1px solid {T.PRIMARY if key == 'recommended' else T.BORDER};"
        )
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(14, 12, 14, 14)
        section_layout.setSpacing(10)
        header = _ColumnHeader(title)
        if key == "recommended":
            header.setStyleSheet(
                f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
                f"font-weight: bold; letter-spacing: 2px; border-bottom: 1px solid {T.PRIMARY}; padding-bottom: 4px;"
            )
        section_layout.addWidget(header)
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setWordWrap(True)
        subtitle_lbl.setStyleSheet(
            f"color: {T.TEXT if key == 'recommended' else T.DIM}; font-family: '{T.FF_BODY}'; "
            f"font-size: {T.FS_SMALL}pt;"
        )
        section_layout.addWidget(subtitle_lbl)
        cards_host = QWidget()
        cards_layout = QVBoxLayout(cards_host)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)
        section_layout.addWidget(cards_host)
        local_sections[key] = section
        local_section_layouts[key] = cards_layout
        local_layout.addWidget(section)
        section.setVisible(False)

    cloud_cards: list[_ModelCard] = []
    cloud_host = QWidget()
    cloud_layout = QVBoxLayout(cloud_host)
    cloud_layout.setContentsMargins(0, 0, 0, 0)
    cloud_layout.setSpacing(16)
    for model in cloud_models:
        card = _ModelCard(model["name"], model["display"], model["tier"], model["context"], model["note"])
        card.set_active.connect(on_model_selected)
        cloud_cards.append(card)
        cloud_layout.addWidget(card)
    cloud_layout.addStretch(1)

    local_placeholder = QLabel("Fetching local models...")
    local_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    local_placeholder.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; "
        f"letter-spacing: 1px; padding: 24px;"
    )
    local_layout.addWidget(local_placeholder)
    local_layout.addStretch(1)

    grid.addWidget(local_host, 1, 0)
    grid.addWidget(cloud_host, 1, 1)
    scroll.setWidget(content)

    return ModelsLibraryPanel(
        summary_frame=summary_frame,
        summary_label=summary_label,
        search_input=search_input,
        hint_label=hint_label,
        loadout_frame=loadout_section.frame,
        loadout_status_label=loadout_section.status_label,
        loadout_inputs=loadout_section.inputs,
        apply_loadout_button=loadout_section.apply_button,
        spawn_main_button=loadout_section.spawn_main_button,
        spawn_subs_button=loadout_section.spawn_subs_button,
        spawn_all_button=loadout_section.spawn_all_button,
        loadout_help_label=loadout_section.help_label,
        scroll=scroll,
        grid=grid,
        local_header=local_header,
        cloud_header=cloud_header,
        local_host=local_host,
        local_layout=local_layout,
        local_sections=local_sections,
        local_section_layouts=local_section_layouts,
        local_section_cards=local_section_cards,
        local_placeholder=local_placeholder,
        cloud_host=cloud_host,
        cloud_layout=cloud_layout,
        cloud_cards=cloud_cards,
    )
