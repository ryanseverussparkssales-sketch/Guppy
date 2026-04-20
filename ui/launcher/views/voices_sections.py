from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T


def build_voices_ui(owner, *, engines: dict[str, list[tuple[str, str, str]]], persona_options: list[str], model_options: list[str], preview_phrase: str) -> None:
    root = QVBoxLayout(owner)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    bar = QFrame()
    bar.setFixedHeight(64)
    bar.setObjectName("voices_topbar")
    bar.setStyleSheet(
        f"QFrame#voices_topbar {{"
        f"  background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};"
        f"}}"
    )
    bl = QHBoxLayout(bar)
    bl.setContentsMargins(28, 0, 28, 0)
    bl.setSpacing(20)
    title = QLabel("VOICE LIBRARY")
    title.setStyleSheet(
        f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
        f"font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
    )
    bl.addWidget(title)
    bl.addSpacing(24)
    engine_lbl = QLabel("ENGINE")
    engine_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
    )
    bl.addWidget(engine_lbl)
    owner._engine_cb = QComboBox()
    owner._engine_cb.addItems(list(engines.keys()))
    owner._engine_cb.setFixedWidth(180)
    owner._engine_cb.currentTextChanged.connect(owner._populate_voices)
    bl.addWidget(owner._engine_cb)
    owner._engine_status_lbl = QLabel("ENGINES: probing...")
    owner._engine_status_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    bl.addWidget(owner._engine_status_lbl)
    bl.addStretch()
    owner._default_lbl = QLabel("DEFAULT VOICE: loading...")
    owner._default_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    bl.addWidget(owner._default_lbl)
    bl.addSpacing(14)
    owner._active_lbl = QLabel(f"ACTIVE VOICE: {owner._describe_voice_choice(owner._active_engine, owner._active_voice)}")
    owner._active_lbl.setStyleSheet(
        f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
    )
    bl.addWidget(owner._active_lbl)
    owner._save_default_btn = QPushButton("SAVE AS DEFAULT")
    owner._save_default_btn.setFixedHeight(28)
    owner._save_default_btn.clicked.connect(owner._save_default_voice)
    bl.addSpacing(12)
    bl.addWidget(owner._save_default_btn)
    root.addWidget(bar)

    assign_bar = QFrame()
    assign_bar.setFixedHeight(62)
    assign_bar.setStyleSheet(
        f"QFrame {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}"
    )
    ab = QHBoxLayout(assign_bar)
    ab.setContentsMargins(28, 0, 28, 0)
    ab.setSpacing(10)
    p_lbl = QLabel("ASSIGN TO PERSONA")
    p_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    ab.addWidget(p_lbl)
    owner._persona_cb = QComboBox()
    owner._persona_cb.addItems(persona_options)
    owner._persona_cb.setFixedWidth(140)
    ab.addWidget(owner._persona_cb)
    owner._assign_persona_btn = QPushButton("ASSIGN")
    owner._assign_persona_btn.setFixedHeight(28)
    owner._assign_persona_btn.clicked.connect(owner._assign_persona_voice)
    ab.addWidget(owner._assign_persona_btn)
    ab.addSpacing(18)
    m_lbl = QLabel("ASSIGN TO MODEL")
    m_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    ab.addWidget(m_lbl)
    owner._model_cb = QComboBox()
    owner._model_cb.addItems(model_options)
    owner._model_cb.setFixedWidth(210)
    ab.addWidget(owner._model_cb)
    owner._assign_model_btn = QPushButton("ASSIGN")
    owner._assign_model_btn.setFixedHeight(28)
    owner._assign_model_btn.clicked.connect(owner._assign_model_voice)
    ab.addWidget(owner._assign_model_btn)
    ab.addStretch()
    owner._assign_status = QLabel("Voice bindings ready")
    owner._assign_status.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner.preview_status.connect(owner._assign_status.setText)
    ab.addWidget(owner._assign_status)
    root.addWidget(assign_bar)

    manage_bar = QFrame()
    manage_bar.setStyleSheet(
        f"QFrame {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}"
    )
    mb = QVBoxLayout(manage_bar)
    mb.setContentsMargins(28, 10, 28, 10)
    mb.setSpacing(8)
    preview_row = QHBoxLayout()
    preview_row.setSpacing(10)
    preview_lbl = QLabel("PREVIEW PHRASE")
    preview_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    preview_row.addWidget(preview_lbl)
    owner._preview_phrase_input = QLineEdit(preview_phrase)
    owner._preview_phrase_input.setStyleSheet(
        f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
    )
    preview_row.addWidget(owner._preview_phrase_input, stretch=1)
    owner._stop_preview_btn = QPushButton("STOP PREVIEW")
    owner._stop_preview_btn.setFixedHeight(28)
    owner._stop_preview_btn.clicked.connect(owner._cancel_preview)
    preview_row.addWidget(owner._stop_preview_btn)
    mb.addLayout(preview_row)
    import_row = QHBoxLayout()
    import_row.setSpacing(10)
    import_lbl = QLabel("IMPORT VOICE")
    import_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    import_row.addWidget(import_lbl)
    owner._import_engine_cb = QComboBox()
    owner._import_engine_cb.addItems(list(engines.keys()))
    import_row.addWidget(owner._import_engine_cb)
    owner._import_voice_id = QLineEdit()
    owner._import_voice_id.setPlaceholderText("voice id")
    owner._import_label = QLineEdit()
    owner._import_label.setPlaceholderText("display label (optional)")
    for widget in (owner._import_voice_id, owner._import_label):
        widget.setStyleSheet(
            f"QLineEdit {{ background: {T.BG1}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 4px 8px; }}"
        )
    import_row.addWidget(owner._import_voice_id)
    import_row.addWidget(owner._import_label)
    owner._import_btn = QPushButton("IMPORT")
    owner._import_btn.setFixedHeight(28)
    owner._import_btn.clicked.connect(owner._import_voice)
    import_row.addWidget(owner._import_btn)
    mb.addLayout(import_row)
    owner._bindings_summary_lbl = QLabel("Voice sources: Using the default voice for everything right now.")
    owner._bindings_summary_lbl.setWordWrap(True)
    owner._bindings_summary_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    mb.addWidget(owner._bindings_summary_lbl)
    owner._voice_evidence_lbl = QLabel("Voice readiness appears here once Guppy loads bindings and engine status.")
    owner._voice_evidence_lbl.setWordWrap(True)
    owner._voice_evidence_lbl.setStyleSheet(
        f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
        f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    mb.addWidget(owner._voice_evidence_lbl)
    root.addWidget(manage_bar)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    owner._list_widget = QWidget()
    owner._list_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    owner._list_layout = QVBoxLayout(owner._list_widget)
    owner._list_layout.setContentsMargins(28, 20, 28, 24)
    owner._list_layout.setSpacing(6)
    owner._list_layout.addStretch()
    scroll.setWidget(owner._list_widget)
    root.addWidget(scroll, stretch=1)
