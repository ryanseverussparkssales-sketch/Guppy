from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY

from .. import tokens as T
from .assistant_first_run_banner import FirstRunBanner


def build_assistant_shell(
    owner,
    *,
    label_factory: Callable[[str, str, int, bool], QLabel],
    dropdown_factory: Callable[[list[str]], object],
    hero_subtitle_for_workspace: Callable[[str], str],
) -> None:
    root = QVBoxLayout(owner)
    root.setContentsMargins(18, 14, 18, 14)
    root.setSpacing(10)

    owner._identity_frame = QFrame()
    owner._identity_frame.setObjectName("home_identity")
    owner._identity_frame.setStyleSheet(
        "QFrame#home_identity { background-color: rgba(255,255,255,0.54); border: 1px solid rgba(214,197,174,0.42); border-radius: 18px; }"
    )
    identity_row = QHBoxLayout(owner._identity_frame)
    identity_row.setContentsMargins(14, 10, 14, 10)
    identity_row.setSpacing(10)
    owner._identity_workspace_chip = QLabel("WORKSPACE / GUPPY-PRIMARY")
    owner._identity_workspace_chip.setStyleSheet(
        f"color: {T.SECONDARY}; background: rgba(47,111,122,0.10); border: 1px solid rgba(214,197,174,0.40);"
        f" border-radius: 12px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner._identity_mode_chip = QLabel("AUTO / LIGHT")
    owner._identity_mode_chip.setStyleSheet(
        f"color: {T.TERTIARY}; background: rgba(70,98,199,0.10); border: 1px solid rgba(214,197,174,0.40);"
        f" border-radius: 12px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    owner._identity_note = QLabel("Ask one clear question and send it.")
    owner._identity_note.setWordWrap(True)
    owner._identity_note.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    owner._identity_details_btn = QPushButton("DETAILS")
    owner._identity_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._identity_details_btn.setToolTip("Show or hide workspace details, attached sources, and saved output")
    owner._identity_details_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(0,106,106,0.46); color: {T.ACCENT_TEAL}; background: #ffffff; }}"
    )
    owner._identity_details_btn.clicked.connect(owner._toggle_workspace_details)
    identity_row.addWidget(owner._identity_workspace_chip)
    identity_row.addWidget(owner._identity_mode_chip)
    identity_row.addWidget(owner._identity_note, stretch=1)
    identity_row.addWidget(owner._identity_details_btn)
    owner._purpose_lbl = QLabel("HOME - Ask one clear thing. Attach Library sources only when they help.")
    owner._purpose_lbl.setObjectName("hub-purpose")
    owner._purpose_lbl.setWordWrap(True)
    owner._purpose_lbl.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    root.addWidget(owner._purpose_lbl)
    root.addWidget(owner._identity_frame)

    owner._first_run_frame = FirstRunBanner(owner)
    owner._first_run_frame.settings_requested.connect(lambda: owner.first_run_action_requested.emit("settings"))
    owner._first_run_frame.models_requested.connect(lambda: owner.first_run_action_requested.emit("models"))
    owner._first_run_frame.focus_input_requested.connect(lambda: owner._input.setFocus(Qt.FocusReason.OtherFocusReason))
    owner._first_run_summary = owner._first_run_frame._summary_lbl
    owner._first_run_install_chip = owner._first_run_frame._install_chip
    root.addWidget(owner._first_run_frame)

    owner._hero_title = QLabel("Start with one ask.")
    owner._hero_subtitle = QLabel(hero_subtitle_for_workspace("user_instance"))
    owner._rec_chip = QLabel("RECOMMENDED / STANDARD")
    owner._instance_chip = QLabel("WORKSPACE / GUPPY-PRIMARY")
    owner._background_chip = QLabel("READY")
    owner._entry_hint = QLabel("Primary action: type one short request and press Send.")
    owner._background_event = QLabel("Latest activity: workspace ready", owner)
    owner._background_event.setVisible(False)
    owner._workspace_summary = QLabel("Active workspace: Daily assistant workspace. General help, chat, and quick tasks.", owner)
    owner._workspace_summary.setVisible(False)
    owner._runtime_facts = QLabel("Ready now: Standard profile, Guppy model, Edge voice.", owner)
    owner._runtime_facts.setVisible(False)
    owner._route_facts = QLabel("Next reply: waiting for your next message.", owner)
    owner._route_facts.setVisible(False)
    owner._recovery_summary = QLabel("System health: stable", owner)
    owner._recovery_summary.setVisible(False)
    owner._context_bar = QFrame()
    owner._context_bar.setObjectName("home_context_bar")
    owner._context_bar.setStyleSheet(
        f"QFrame#home_context_bar {{ background-color: rgba(255,255,255,0.62); border: 1px solid rgba(214,197,174,0.44); border-radius: 18px; }}"
    )
    context_bar_layout = QVBoxLayout(owner._context_bar)
    context_bar_layout.setContentsMargins(12, 10, 12, 10)
    context_bar_layout.setSpacing(6)
    for widget in (
        owner._background_event,
        owner._workspace_summary,
    ):
        widget.setWordWrap(True)
        widget.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        context_bar_layout.addWidget(widget)
    owner._context_details_btn = QPushButton("DETAILS")
    owner._context_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._context_details_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(0,106,106,0.46); color: {T.ACCENT_TEAL}; background: #ffffff; }}"
    )
    owner._context_details_btn.clicked.connect(owner._toggle_context_details)
    owner._context_details_btn.setVisible(False)
    context_bar_layout.addWidget(owner._context_details_btn, alignment=Qt.AlignmentFlag.AlignLeft)
    owner._context_details_host = QFrame()
    owner._context_details_host.setVisible(False)
    details_layout = QVBoxLayout(owner._context_details_host)
    details_layout.setContentsMargins(0, 0, 0, 0)
    details_layout.setSpacing(4)
    for widget in (
        owner._runtime_facts,
        owner._route_facts,
        owner._recovery_summary,
    ):
        widget.setWordWrap(True)
        widget.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        details_layout.addWidget(widget)
    context_bar_layout.addWidget(owner._context_details_host)
    owner._context_details_visible = False
    owner._context_bar.setVisible(False)

    owner._starter_summary = QLabel(owner._base_starter_summary)
    owner._starter_summary.setWordWrap(True)
    owner._starter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    owner._starter_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    owner._starter_summary.setVisible(False)
    owner._starter_row = QHBoxLayout()
    owner._starter_row.setSpacing(8)
    for starter_id, title, mode, prompt in owner._starter_templates():
        btn = QPushButton(title)
        btn.setToolTip(prompt)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
            f" border-radius: 11px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background: rgba(242,202,80,0.05); }}"
        )
        btn.clicked.connect(lambda _=False, sid=starter_id: owner._load_starter_by_id(sid))
        owner._starter_buttons[starter_id] = btn
        owner._starter_row.addWidget(btn)
    owner._starter_row.addStretch()
    owner._refresh_starter_buttons()

    hero = QFrame()
    hero.setObjectName("home_hero")
    hero.setStyleSheet(
        f"QFrame#home_hero {{ background-color: rgba(255,255,255,0.48); border: 1px solid rgba(214,197,174,0.40); border-radius: 22px; }}"
    )
    hero_layout = QVBoxLayout(hero)
    hero_layout.setContentsMargins(18, 16, 18, 14)
    hero_layout.setSpacing(10)

    hero_top = QHBoxLayout()
    hero_top.setSpacing(14)
    hero_text = QVBoxLayout()
    hero_text.setSpacing(4)
    owner._hero_title.setStyleSheet(
        f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 20pt; font-weight: 700;"
    )
    owner._hero_subtitle.setWordWrap(True)
    owner._hero_subtitle.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    hero_text.addWidget(owner._hero_title)
    hero_text.addWidget(owner._hero_subtitle)
    hero_top.addLayout(hero_text, stretch=1)
    hero_layout.addLayout(hero_top)

    chip_row = QHBoxLayout()
    chip_row.setSpacing(8)
    for chip, bg, fg in (
        (owner._rec_chip, "rgba(0,106,106,0.10)", T.ACCENT_TEAL),
        (owner._instance_chip, "rgba(255,109,0,0.10)", T.ACCENT_ORANGE),
        (owner._background_chip, "rgba(0,200,83,0.10)", T.STATUS_SUCCESS),
    ):
        chip.setStyleSheet(
            f"color: {fg}; background: {bg}; border: 1px solid {T.BORDER_SOFT};"
            f" border-radius: 4px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        chip_row.addWidget(chip)
    owner._rec_chip.hide()
    owner._background_chip.hide()
    chip_row.addStretch()
    hero_layout.addLayout(chip_row)

    owner._entry_hint.setWordWrap(True)
    owner._entry_hint.setStyleSheet(
        f"color: {T.ACCENT_TEAL}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    hero_layout.addWidget(owner._entry_hint)
    hero_layout.addWidget(owner._context_bar)
    root.addWidget(hero)
    hero.hide()

    owner._workspace_details_strip = QFrame()
    owner._workspace_details_strip.setObjectName("workspace_details_strip")
    owner._workspace_details_strip.setStyleSheet(
        "QFrame#workspace_details_strip { background-color: rgba(255,255,255,0.48); border: 1px solid rgba(214,197,174,0.36); border-radius: 18px; }"
    )
    details_strip_layout = QHBoxLayout(owner._workspace_details_strip)
    details_strip_layout.setContentsMargins(14, 10, 14, 10)
    details_strip_layout.setSpacing(10)
    owner._workspace_details_summary = QLabel("")
    owner._workspace_details_summary.setWordWrap(True)
    owner._workspace_details_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
    )
    owner._workspace_details_btn = QPushButton("DETAILS")
    owner._workspace_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._workspace_details_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(0,106,106,0.46); color: {T.ACCENT_TEAL}; background: #ffffff; }}"
    )
    owner._workspace_details_btn.clicked.connect(owner._toggle_workspace_details)
    details_strip_layout.addWidget(owner._workspace_details_summary, stretch=1)
    details_strip_layout.addWidget(owner._workspace_details_btn)
    root.addWidget(owner._workspace_details_strip)
    owner._workspace_details_strip.hide()

    owner._workspace_details_host = QFrame()
    workspace_details_layout = QVBoxLayout(owner._workspace_details_host)
    workspace_details_layout.setContentsMargins(0, 0, 0, 0)
    workspace_details_layout.setSpacing(10)

    owner._workspace_dock = QFrame()
    owner._workspace_dock.setObjectName("workspace_dock")
    owner._workspace_dock.setStyleSheet(
        "QFrame#workspace_dock { background-color: rgba(255,255,255,0.56); border: 1px solid rgba(214,197,174,0.42); border-radius: 24px; }"
    )
    dock_layout = QHBoxLayout(owner._workspace_dock)
    dock_layout.setContentsMargins(14, 14, 14, 14)
    dock_layout.setSpacing(12)
    owner._files_context_lbl = QLabel("")
    owner._study_context_lbl = QLabel("")
    owner._coding_context_lbl = QLabel("")
    for title, target in (
        ("FILES", owner._files_context_lbl),
        ("STUDY", owner._study_context_lbl),
        ("BUILD", owner._coding_context_lbl),
    ):
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        card_layout.addWidget(label_factory(title, T.PRIMARY, T.FS_TINY, True))
        target.setWordWrap(True)
        target.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        card_layout.addWidget(target)
        dock_layout.addWidget(card, stretch=1)
    workspace_details_layout.addWidget(owner._workspace_dock)

    owner._latest_output_host = QFrame()
    owner._latest_output_host.setObjectName("latest_output_host")
    owner._latest_output_host.setStyleSheet(
        "QFrame#latest_output_host { background-color: rgba(255,255,255,0.54); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
    )
    latest_output_layout = QHBoxLayout(owner._latest_output_host)
    latest_output_layout.setContentsMargins(14, 12, 14, 12)
    latest_output_layout.setSpacing(12)
    latest_output_text = QVBoxLayout()
    latest_output_text.setSpacing(4)
    owner._latest_output_title = label_factory("LATEST SAVED OUTPUT", T.PRIMARY, T.FS_TINY, True)
    owner._latest_output_summary = QLabel("")
    owner._latest_output_summary.setWordWrap(True)
    owner._latest_output_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    latest_output_text.addWidget(owner._latest_output_title)
    latest_output_text.addWidget(owner._latest_output_summary)
    latest_output_layout.addLayout(latest_output_text, stretch=1)
    owner._latest_output_library_btn = QPushButton("IN LIBRARY")
    owner._latest_output_library_btn.setToolTip("Open this saved output in the Library view")
    owner._latest_output_attach_btn = QPushButton("ATTACH NOW")
    owner._latest_output_attach_btn.setToolTip("Attach this saved output as context for the next reply")
    for button in (owner._latest_output_library_btn, owner._latest_output_attach_btn):
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
            f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
        )
    owner._latest_output_library_btn.clicked.connect(owner._emit_latest_saved_output_library)
    owner._latest_output_attach_btn.clicked.connect(owner._emit_latest_saved_output_attach)
    latest_output_layout.addWidget(owner._latest_output_library_btn)
    latest_output_layout.addWidget(owner._latest_output_attach_btn)
    owner._latest_output_host.setVisible(False)
    workspace_details_layout.addWidget(owner._latest_output_host)

    owner._active_context_host = QFrame()
    owner._active_context_host.setObjectName("active_context_host")
    owner._active_context_host.setStyleSheet(
        "QFrame#active_context_host { background-color: rgba(255,255,255,0.52); border: 1px solid rgba(214,197,174,0.38); border-radius: 20px; }"
    )
    active_context_layout = QVBoxLayout(owner._active_context_host)
    active_context_layout.setContentsMargins(16, 14, 16, 14)
    active_context_layout.setSpacing(10)
    active_context_top = QHBoxLayout()
    active_context_top.setSpacing(10)
    owner._active_context_title = label_factory("CURRENT SOURCES", T.PRIMARY, T.FS_TINY, True)
    active_context_top.addWidget(owner._active_context_title)
    active_context_top.addStretch()
    owner._active_context_clear_btn = QPushButton("CLEAR SOURCES")
    owner._active_context_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_clear_btn.setToolTip("Remove all currently attached sources")
    owner._active_context_clear_btn.setAccessibleName("Clear attached sources")
    owner._active_context_clear_btn.setAccessibleDescription("Clears all active context sources")
    owner._active_context_clear_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.ERROR}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(200,75,68,0.42); background: #ffffff; }}"
    )
    owner._active_context_clear_btn.clicked.connect(owner.active_context_clear_requested.emit)
    owner._active_context_refresh_btn = QPushButton("REFRESH SAVED SOURCE")
    owner._active_context_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_refresh_btn.setToolTip("Refresh the primary saved source using the latest assistant reply")
    owner._active_context_refresh_btn.setAccessibleName("Refresh saved source")
    owner._active_context_refresh_btn.setAccessibleDescription("Refreshes the primary saved source")
    owner._active_context_refresh_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
    )
    owner._active_context_refresh_btn.clicked.connect(owner._emit_active_context_refresh_requested)
    owner._active_context_refresh_btn.setVisible(False)
    owner._active_context_pin_default_btn = QPushButton("PIN PRIMARY")
    owner._active_context_pin_default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_pin_default_btn.setToolTip("Pin the primary source as this workspace default")
    owner._active_context_pin_default_btn.setAccessibleName("Pin default source")
    owner._active_context_pin_default_btn.setAccessibleDescription("Pins the primary source for this workspace")
    owner._active_context_pin_default_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.SECONDARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(47,111,122,0.42); background: #ffffff; }}"
    )
    owner._active_context_pin_default_btn.clicked.connect(owner._emit_active_context_default_requested)
    owner._active_context_pin_default_btn.setVisible(False)
    owner._active_context_swap_btn = QPushButton("MAKE PRIMARY SOURCE")
    owner._active_context_swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._active_context_swap_btn.setToolTip("Promote another attached source to primary")
    owner._active_context_swap_btn.setAccessibleName("Make primary source")
    owner._active_context_swap_btn.setAccessibleDescription("Promotes a non-primary source to primary")
    owner._active_context_swap_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
    )
    owner._active_context_swap_btn.clicked.connect(owner._emit_active_context_swap_requested)
    owner._active_context_swap_btn.setVisible(False)
    active_context_top.addWidget(owner._active_context_refresh_btn)
    active_context_top.addWidget(owner._active_context_pin_default_btn)
    active_context_top.addWidget(owner._active_context_swap_btn)
    active_context_top.addWidget(owner._active_context_clear_btn)
    active_context_layout.addLayout(active_context_top)
    owner._active_context_summary = QLabel("No Library sources attached yet. Open Library and use USE IN CHAT to ground the next reply.")
    owner._active_context_summary.setWordWrap(True)
    owner._active_context_summary.setStyleSheet(
        f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
    )
    active_context_layout.addWidget(owner._active_context_summary)
    owner._active_context_row = QHBoxLayout()
    owner._active_context_row.setSpacing(10)
    active_context_layout.addLayout(owner._active_context_row)
    owner._active_context_host.setVisible(False)
    owner._last_context_notice = ""
    owner._focused_context_title = ""
    owner._previewed_context_title = ""
    owner._default_context_source_title = ""
    workspace_details_layout.addWidget(owner._active_context_host)
    root.addWidget(owner._workspace_details_host)

    transcript = QFrame()
    transcript.setObjectName("chat_surface")
    transcript.setStyleSheet(
        f"QFrame#chat_surface {{ background-color: rgba(255,255,255,0.58); border: 1px solid rgba(214,197,174,0.50); border-radius: 30px; }}"
    )
    tcol = QVBoxLayout(transcript)
    tcol.setContentsMargins(20, 18, 20, 18)
    tcol.setSpacing(14)

    transcript_hdr = QHBoxLayout()
    transcript_hdr.setSpacing(8)
    transcript_hdr.addWidget(label_factory("CONVERSATION", T.DIM, T.FS_TINY, True))
    owner._grounding_chip = QLabel("")
    owner._grounding_chip.setVisible(False)
    owner._grounding_chip.setStyleSheet(
        f"color: {T.TERTIARY}; background: rgba(70,98,199,0.12); border: 1px solid rgba(214,197,174,0.40);"
        f" border-radius: 12px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    transcript_hdr.addWidget(owner._grounding_chip)
    owner._status_strip = QLabel("READY")
    owner._status_strip.setStyleSheet(
        f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    transcript_hdr.addStretch()
    transcript_hdr.addWidget(owner._status_strip)
    tcol.addLayout(transcript_hdr)

    owner._chat_scroll = QScrollArea()
    owner._chat_scroll.setWidgetResizable(True)
    owner._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    owner._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    owner._chat_content = QFrame()
    owner._chat_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    owner._chat_layout = QVBoxLayout(owner._chat_content)
    owner._chat_layout.setContentsMargins(10, 6, 10, 6)
    owner._chat_layout.setSpacing(20)
    owner._empty_state = owner._build_empty_state()
    owner._chat_layout.addWidget(owner._empty_state)
    owner._chat_layout.addStretch()
    owner._chat_scroll.setWidget(owner._chat_content)
    tcol.addWidget(owner._chat_scroll, stretch=1)
    root.addWidget(transcript, stretch=1)

    composer = QFrame()
    composer.setObjectName("chat_composer")
    composer.setStyleSheet(
        f"QFrame#chat_composer {{ background-color: rgba(255,255,255,0.64); border: 1px solid rgba(214,197,174,0.46); border-radius: 30px; }}"
    )
    composer_col = QVBoxLayout(composer)
    composer_col.setContentsMargins(16, 14, 16, 12)
    composer_col.setSpacing(10)

    starter_summary_row = QHBoxLayout()
    starter_summary_row.setSpacing(10)
    starter_summary_row.addWidget(owner._starter_summary, stretch=1)
    owner._starters_btn = QPushButton("PROMPTS")
    owner._starters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    owner._starters_btn.setToolTip("Show or hide ready-made prompt suggestions for this workspace")
    owner._starters_btn.setStyleSheet(
        f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
        f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: rgba(0,106,106,0.46); color: {T.ACCENT_TEAL}; background: #ffffff; }}"
    )
    owner._starters_btn.clicked.connect(owner._toggle_starters)
    starter_summary_row.addWidget(owner._starters_btn)
    composer_col.addLayout(starter_summary_row)
    owner._starter_buttons_host = QFrame()
    starter_strip = QHBoxLayout(owner._starter_buttons_host)
    starter_strip.setContentsMargins(0, 0, 0, 0)
    starter_strip.setSpacing(10)
    starter_strip.addLayout(owner._starter_row, stretch=1)
    composer_col.addWidget(owner._starter_buttons_host)

    owner._launcher_panel = QFrame()
    owner._launcher_panel.setObjectName("launcher_panel")
    owner._launcher_panel.setStyleSheet(
        f"QFrame#launcher_panel {{ background-color: rgba(244,239,231,0.88); border: 1px solid rgba(214,197,174,0.66); border-radius: 18px; }}"
    )
    launcher_panel_col = QVBoxLayout(owner._launcher_panel)
    launcher_panel_col.setContentsMargins(14, 12, 14, 12)
    launcher_panel_col.setSpacing(10)

    controls = QHBoxLayout()
    controls.setSpacing(10)
    for header, opts, cb_attr in [
        ("MODE", list(LAUNCHER_MODES_DISPLAY), "_cb_mode"),
        ("PERSONA", ["GUPPY"], "_cb_persona"),
        ("PROFILE", ["LIGHT", "STANDARD", "POWER"], "_cb_profile"),
    ]:
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(label_factory(header))
        cb = dropdown_factory(opts)
        cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
            f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
        setattr(owner, cb_attr, cb)
        col.addWidget(cb)
        controls.addLayout(col)
    controls.addStretch()
    launcher_panel_col.addLayout(controls)
    composer_col.addWidget(owner._launcher_panel)
    owner._launcher_panel.setVisible(False)

    input_shell = QFrame()
    input_shell.setObjectName("composer_shell")
    input_shell.setStyleSheet(
        f"QFrame#composer_shell {{ background-color: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.46); border-radius: 30px; }}"
    )
    input_row = QHBoxLayout(input_shell)
    input_row.setContentsMargins(16, 8, 8, 8)
    input_row.setSpacing(8)

    owner._input = QLineEdit()
    owner._input.setPlaceholderText(owner._base_input_placeholder)
    owner._input.setStyleSheet(
        f"QLineEdit {{ background: transparent; border: none; color: {T.TEXT};"
        f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; padding: 2px 0; }}"
    )
    owner._input.returnPressed.connect(owner._submit)
    input_row.addWidget(owner._input, stretch=1)

    owner._mic_btn = QPushButton("\u25cf")
    owner._mic_btn.setFixedSize(32, 32)
    owner._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
    owner._mic_btn.setStyleSheet(
        f"QPushButton {{ border: 1px solid rgba(205,181,154,0.34); border-radius: 16px; background: rgba(255,250,243,0.92); color: {T.PRIMARY}; font-size: 10pt; }}"
        f"QPushButton:hover {{ border-color: rgba(255,107,61,0.55); background: #ffffff; }}"
    )
    owner._mic_btn.clicked.connect(owner.mic_requested.emit)

    owner._cancel_btn = QPushButton("\u25a0")
    owner._cancel_btn.setFixedSize(32, 32)
    owner._cancel_btn.setEnabled(False)
    owner._cancel_btn.setToolTip("Cancel the in-flight request")
    owner._cancel_btn.setStyleSheet(
        f"QPushButton {{ border: 1px solid rgba(200,75,68,0.42); border-radius: 16px; background: rgba(255,250,243,0.80); color: {T.ERROR}; font-size: 8pt; }}"
        f"QPushButton:hover {{ background: rgba(200,75,68,0.10); }}"
    )
    owner._cancel_btn.clicked.connect(owner.cancel_requested.emit)

    owner._send_btn = QPushButton("\u25b6")
    owner._send_btn.setFixedSize(36, 36)
    owner._send_btn.setToolTip("Send your message to the assistant")
    owner._send_btn.setStyleSheet(
        f"QPushButton {{ border: none; border-radius: 18px; background: {T.PRIMARY}; color: {T.BG}; font-size: 10pt; }}"
        f"QPushButton:hover {{ background: {T.PRIMARY_DIM}; }}"
    )
    owner._send_btn.clicked.connect(owner._submit)

    input_row.addWidget(owner._mic_btn)
    input_row.addWidget(owner._cancel_btn)
    input_row.addWidget(owner._send_btn)
    composer_col.addWidget(input_shell)

    footer = QHBoxLayout()
    footer.setSpacing(8)
    owner._session_strip = label_factory("SESSION: --")
    owner._session_strip.setStyleSheet(
        f"color: rgba(115,96,79,0.72); font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
    )
    footer.addWidget(owner._session_strip)
    footer.addStretch()
    composer_col.addLayout(footer)
    root.addWidget(composer)

    owner._cb_mode.currentTextChanged.connect(owner._emit_context_changed)
    owner._cb_persona.currentTextChanged.connect(owner._emit_context_changed)
    owner._cb_mode.currentTextChanged.connect(owner._sync_launcher_summary)
    owner._cb_persona.currentTextChanged.connect(owner._sync_launcher_summary)
    owner._cb_profile.currentTextChanged.connect(owner._sync_launcher_summary)
    owner.set_persona_options([("GUPPY", "guppy")], selected="guppy")
    owner._sync_launcher_summary()
    owner._refresh_resource_context()
    owner._refresh_empty_state()
    owner._sync_context_bar_visibility()
    owner._refresh_composer_guidance()
    owner._update_workspace_details_visibility()
    owner._update_starter_visibility()
    owner._apply_density_mode(owner.width())
    owner._launcher_panel.setVisible(False)
    owner._identity_details_btn.setVisible(False)
    owner._workspace_details_strip.setVisible(False)
    owner._workspace_details_host.setVisible(False)
