"""
ui/launcher/views/assistant_view.py
Home chat surface with a calmer, messenger-style launcher layout.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.home_presenter import (
    build_home_workspace_copy,
    build_home_starter_state,
    build_home_welcome_message,
    build_home_workspace_state,
    home_workspace_starter_templates,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY
from .. import tokens as T
from .assistant_context import (
    active_context_titles as context_active_context_titles,
    build_composer_guidance as context_build_composer_guidance,
    build_grounding_cue as context_build_grounding_cue,
    context_aware_starter_prompt as context_context_aware_starter_prompt,
    context_aware_starter_title as context_context_aware_starter_title,
    format_active_context_summary as context_format_active_context_summary,
    normalize_context_items as context_normalize_context_items,
    refresh_resource_context as context_refresh_resource_context,
    set_background_event as context_set_background_event,
    set_background_status as context_set_background_status,
    set_recovery_summary as context_set_recovery_summary,
    set_route_preview as context_set_route_preview,
    set_runtime_facts as context_set_runtime_facts,
    sync_context_bar_visibility as context_sync_context_bar_visibility,
    toggle_context_details as context_toggle_context_details,
)


def _lbl(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}';"
        f"font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return lbl


def _dropdown(options: list[str]) -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    return cb


def _hero_subtitle_for_workspace(workspace_type: str) -> str:
    key = str(workspace_type or "").strip().lower()
    return {
        "builder_instance": "Plan, review, or build here. Starters are optional.",
        "read_only_instance": "Inspect files, notes, and saved context here. Starters are optional.",
        "admin_instance": "Use this workspace for setup and recovery. Starters are optional.",
    }.get(key, "Start with the next clear ask. Starters are optional.")


class AssistantView(QWidget):
    command_submitted = Signal(str)
    cancel_requested = Signal()
    mic_requested = Signal()
    starter_requested = Signal(str, str)
    settings_changed = Signal(dict)
    chat_context_changed = Signal(str, str)
    launcher_summary_changed = Signal(str)
    active_context_clear_requested = Signal()
    active_context_remove_requested = Signal(str)
    active_context_focus_requested = Signal(str)
    active_context_default_requested = Signal(str)
    active_context_library_requested = Signal(str)
    active_context_refresh_requested = Signal(str, bool)
    assistant_reply_library_requested = Signal(str, bool)
    assistant_reply_artifact_requested = Signal(str)
    latest_saved_output_attach_requested = Signal(str, str)
    latest_saved_output_library_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        initial_copy = build_home_workspace_copy("user_instance")
        self._request_in_flight_ui = False
        self._mic_capture_active = False
        self._workspace_name = "guppy-primary"
        self._workspace_type = "user_instance"
        self._workspace_role = initial_copy.role_label
        self._workspace_purpose = initial_copy.purpose
        self._starter_buttons: dict[str, QPushButton] = {}
        self._conversation_history: list[dict[str, str]] = []
        self._active_context_items: list[dict[str, str]] = []
        self._empty_state_title_text = initial_copy.onboarding_title
        self._empty_state_subtitle_text = initial_copy.onboarding_subtitle
        self._empty_state_recipe_text = initial_copy.onboarding_recipe
        self._base_empty_state_title = initial_copy.onboarding_title
        self._base_empty_state_subtitle = initial_copy.onboarding_subtitle
        self._base_empty_state_recipe = initial_copy.onboarding_recipe
        self._base_starter_summary = initial_copy.starter_summary
        self._base_input_placeholder = initial_copy.input_placeholder
        self._latest_saved_output: dict[str, str] = {}
        self._latest_assistant_reply_text = ""
        self._swap_source_target_title = ""
        self._workspace_details_expanded = False
        self._starters_expanded = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        self._identity_frame = QFrame()
        self._identity_frame.setObjectName("home_identity")
        self._identity_frame.setStyleSheet(
            "QFrame#home_identity { background-color: rgba(255,255,255,0.54); border: 1px solid rgba(214,197,174,0.42); border-radius: 18px; }"
        )
        identity_row = QHBoxLayout(self._identity_frame)
        identity_row.setContentsMargins(12, 8, 12, 8)
        identity_row.setSpacing(8)
        self._identity_workspace_chip = QLabel("WORKSPACE · GUPPY-PRIMARY")
        self._identity_workspace_chip.setStyleSheet(
            f"color: {T.SECONDARY}; background: rgba(47,111,122,0.10); border: 1px solid rgba(214,197,174,0.40);"
            f" border-radius: 12px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._identity_mode_chip = QLabel("AUTO / LIGHT")
        self._identity_mode_chip.setStyleSheet(
            f"color: {T.TERTIARY}; background: rgba(70,98,199,0.10); border: 1px solid rgba(214,197,174,0.40);"
            f" border-radius: 12px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._identity_note = QLabel("Ask one clear question and send it.")
        self._identity_note.setWordWrap(True)
        self._identity_note.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        self._identity_details_btn = QPushButton("DETAILS")
        self._identity_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._identity_details_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.46); color: {T.TERTIARY}; background: #ffffff; }}"
        )
        self._identity_details_btn.clicked.connect(self._toggle_workspace_details)
        identity_row.addWidget(self._identity_workspace_chip)
        identity_row.addWidget(self._identity_mode_chip)
        identity_row.addWidget(self._identity_note, stretch=1)
        identity_row.addWidget(self._identity_details_btn)
        root.addWidget(self._identity_frame)

        self._hero_title = QLabel("Start with one ask.")
        self._hero_subtitle = QLabel(_hero_subtitle_for_workspace("user_instance"))
        self._rec_chip = QLabel("RECOMMENDED / STANDARD")
        self._instance_chip = QLabel("WORKSPACE / GUPPY-PRIMARY")
        self._background_chip = QLabel("READY")
        self._entry_hint = QLabel("Primary action: type one short request and press Send.")
        self._background_event = QLabel("Latest activity: workspace ready", self)
        self._background_event.setVisible(False)
        self._workspace_summary = QLabel("Active workspace: Daily assistant workspace. General help, chat, and quick tasks.", self)
        self._workspace_summary.setVisible(False)
        self._runtime_facts = QLabel("Ready now: Standard profile, Guppy model, Edge voice.", self)
        self._runtime_facts.setVisible(False)
        self._route_facts = QLabel("Next reply: waiting for your next message.", self)
        self._route_facts.setVisible(False)
        self._recovery_summary = QLabel("System health: stable", self)
        self._recovery_summary.setVisible(False)
        self._context_bar = QFrame()
        self._context_bar.setObjectName("home_context_bar")
        self._context_bar.setStyleSheet(
            f"QFrame#home_context_bar {{ background-color: rgba(255,255,255,0.62); border: 1px solid rgba(214,197,174,0.44); border-radius: 18px; }}"
        )
        context_bar_layout = QVBoxLayout(self._context_bar)
        context_bar_layout.setContentsMargins(12, 9, 12, 9)
        context_bar_layout.setSpacing(4)
        for widget in (
            self._background_event,
            self._workspace_summary,
        ):
            widget.setWordWrap(True)
            widget.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            context_bar_layout.addWidget(widget)
        self._context_details_btn = QPushButton("DETAILS")
        self._context_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._context_details_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.46); color: {T.TERTIARY}; background: #ffffff; }}"
        )
        self._context_details_btn.clicked.connect(self._toggle_context_details)
        self._context_details_btn.setVisible(False)
        context_bar_layout.addWidget(self._context_details_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self._context_details_host = QWidget()
        self._context_details_host.setVisible(False)
        details_layout = QVBoxLayout(self._context_details_host)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)
        for widget in (
            self._runtime_facts,
            self._route_facts,
            self._recovery_summary,
        ):
            widget.setWordWrap(True)
            widget.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            details_layout.addWidget(widget)
        context_bar_layout.addWidget(self._context_details_host)
        self._context_details_visible = False
        self._context_bar.setVisible(False)

        self._starter_summary = QLabel(self._base_starter_summary)
        self._starter_summary.setWordWrap(True)
        self._starter_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._starter_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        self._starter_summary.setVisible(False)
        self._starter_row = QHBoxLayout()
        self._starter_row.setSpacing(8)
        for starter_id, title, mode, prompt in self._starter_templates():
            btn = QPushButton(title)
            btn.setToolTip(prompt)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
                f" border-radius: 11px; padding: 5px 9px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; background: rgba(242,202,80,0.05); }}"
            )
            btn.clicked.connect(lambda _=False, sid=starter_id: self._load_starter_by_id(sid))
            self._starter_buttons[starter_id] = btn
            self._starter_row.addWidget(btn)
        self._starter_row.addStretch()
        self._refresh_starter_buttons()

        hero = QFrame()
        hero.setObjectName("home_hero")
        hero.setStyleSheet(
            f"QFrame#home_hero {{ background-color: rgba(255,255,255,0.48); border: 1px solid rgba(214,197,174,0.40); border-radius: 22px; }}"
        )
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 12)
        hero_layout.setSpacing(8)

        hero_top = QHBoxLayout()
        hero_top.setSpacing(12)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        self._hero_title.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 20pt; font-weight: 700;"
        )
        self._hero_subtitle.setWordWrap(True)
        self._hero_subtitle.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        hero_text.addWidget(self._hero_title)
        hero_text.addWidget(self._hero_subtitle)
        hero_top.addLayout(hero_text, stretch=1)
        hero_layout.addLayout(hero_top)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for chip, bg, fg in (
            (self._rec_chip, "rgba(70,98,199,0.10)", T.TERTIARY),
            (self._instance_chip, "rgba(47,111,122,0.10)", T.SECONDARY),
            (self._background_chip, "rgba(44,123,89,0.10)", T.GREEN),
        ):
            chip.setStyleSheet(
                f"color: {fg}; background: {bg}; border: 1px solid rgba(214,197,174,0.40);"
                f" border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            chip_row.addWidget(chip)
        self._rec_chip.hide()
        self._background_chip.hide()
        chip_row.addStretch()
        hero_layout.addLayout(chip_row)

        self._entry_hint.setWordWrap(True)
        self._entry_hint.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        hero_layout.addWidget(self._entry_hint)
        hero_layout.addWidget(self._context_bar)
        root.addWidget(hero)
        hero.hide()

        self._workspace_details_strip = QFrame()
        self._workspace_details_strip.setObjectName("workspace_details_strip")
        self._workspace_details_strip.setStyleSheet(
            "QFrame#workspace_details_strip { background-color: rgba(255,255,255,0.48); border: 1px solid rgba(214,197,174,0.36); border-radius: 18px; }"
        )
        details_strip_layout = QHBoxLayout(self._workspace_details_strip)
        details_strip_layout.setContentsMargins(12, 8, 12, 8)
        details_strip_layout.setSpacing(8)
        self._workspace_details_summary = QLabel("")
        self._workspace_details_summary.setWordWrap(True)
        self._workspace_details_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
        )
        self._workspace_details_btn = QPushButton("DETAILS")
        self._workspace_details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._workspace_details_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.46); color: {T.TERTIARY}; background: #ffffff; }}"
        )
        self._workspace_details_btn.clicked.connect(self._toggle_workspace_details)
        details_strip_layout.addWidget(self._workspace_details_summary, stretch=1)
        details_strip_layout.addWidget(self._workspace_details_btn)
        root.addWidget(self._workspace_details_strip)
        self._workspace_details_strip.hide()

        self._workspace_details_host = QWidget()
        workspace_details_layout = QVBoxLayout(self._workspace_details_host)
        workspace_details_layout.setContentsMargins(0, 0, 0, 0)
        workspace_details_layout.setSpacing(10)

        self._workspace_dock = QFrame()
        self._workspace_dock.setObjectName("workspace_dock")
        self._workspace_dock.setStyleSheet(
            "QFrame#workspace_dock { background-color: rgba(255,255,255,0.56); border: 1px solid rgba(214,197,174,0.42); border-radius: 24px; }"
        )
        dock_layout = QHBoxLayout(self._workspace_dock)
        dock_layout.setContentsMargins(12, 12, 12, 12)
        dock_layout.setSpacing(10)
        self._files_context_lbl = QLabel("")
        self._study_context_lbl = QLabel("")
        self._coding_context_lbl = QLabel("")
        for title, target in (
            ("FILES", self._files_context_lbl),
            ("STUDY", self._study_context_lbl),
            ("BUILD", self._coding_context_lbl),
        ):
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: rgba(255,255,255,0.72); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)
            card_layout.addWidget(_lbl(title, T.PRIMARY, T.FS_TINY, True))
            target.setWordWrap(True)
            target.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
            )
            card_layout.addWidget(target)
            dock_layout.addWidget(card, stretch=1)
        workspace_details_layout.addWidget(self._workspace_dock)

        self._latest_output_host = QFrame()
        self._latest_output_host.setObjectName("latest_output_host")
        self._latest_output_host.setStyleSheet(
            "QFrame#latest_output_host { background-color: rgba(255,255,255,0.54); border: 1px solid rgba(214,197,174,0.40); border-radius: 18px; }"
        )
        latest_output_layout = QHBoxLayout(self._latest_output_host)
        latest_output_layout.setContentsMargins(12, 10, 12, 10)
        latest_output_layout.setSpacing(10)
        latest_output_text = QVBoxLayout()
        latest_output_text.setSpacing(4)
        self._latest_output_title = _lbl("LATEST SAVED OUTPUT", T.PRIMARY, T.FS_TINY, True)
        self._latest_output_summary = QLabel("")
        self._latest_output_summary.setWordWrap(True)
        self._latest_output_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        latest_output_text.addWidget(self._latest_output_title)
        latest_output_text.addWidget(self._latest_output_summary)
        latest_output_layout.addLayout(latest_output_text, stretch=1)
        self._latest_output_library_btn = QPushButton("IN LIBRARY")
        self._latest_output_attach_btn = QPushButton("ATTACH NOW")
        for button in (self._latest_output_library_btn, self._latest_output_attach_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
                f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
            )
        self._latest_output_library_btn.clicked.connect(self._emit_latest_saved_output_library)
        self._latest_output_attach_btn.clicked.connect(self._emit_latest_saved_output_attach)
        latest_output_layout.addWidget(self._latest_output_library_btn)
        latest_output_layout.addWidget(self._latest_output_attach_btn)
        self._latest_output_host.setVisible(False)
        workspace_details_layout.addWidget(self._latest_output_host)

        self._active_context_host = QFrame()
        self._active_context_host.setObjectName("active_context_host")
        self._active_context_host.setStyleSheet(
            "QFrame#active_context_host { background-color: rgba(255,255,255,0.52); border: 1px solid rgba(214,197,174,0.38); border-radius: 20px; }"
        )
        active_context_layout = QVBoxLayout(self._active_context_host)
        active_context_layout.setContentsMargins(12, 10, 12, 10)
        active_context_layout.setSpacing(8)
        active_context_top = QHBoxLayout()
        active_context_top.setSpacing(8)
        self._active_context_title = _lbl("CURRENT SOURCES", T.PRIMARY, T.FS_TINY, True)
        active_context_top.addWidget(self._active_context_title)
        active_context_top.addStretch()
        self._active_context_clear_btn = QPushButton("CLEAR SOURCES")
        self._active_context_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_context_clear_btn.setToolTip("Remove all currently attached sources")
        self._active_context_clear_btn.setAccessibleName("Clear attached sources")
        self._active_context_clear_btn.setAccessibleDescription("Clears all active context sources")
        self._active_context_clear_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.ERROR}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(200,75,68,0.42); background: #ffffff; }}"
        )
        self._active_context_clear_btn.clicked.connect(self.active_context_clear_requested.emit)
        self._active_context_refresh_btn = QPushButton("REFRESH SAVED SOURCE")
        self._active_context_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_context_refresh_btn.setToolTip("Refresh the primary saved source using the latest assistant reply")
        self._active_context_refresh_btn.setAccessibleName("Refresh saved source")
        self._active_context_refresh_btn.setAccessibleDescription("Refreshes the primary saved source")
        self._active_context_refresh_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
        )
        self._active_context_refresh_btn.clicked.connect(self._emit_active_context_refresh_requested)
        self._active_context_refresh_btn.setVisible(False)
        self._active_context_pin_default_btn = QPushButton("PIN PRIMARY")
        self._active_context_pin_default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_context_pin_default_btn.setToolTip("Pin the primary source as this workspace default")
        self._active_context_pin_default_btn.setAccessibleName("Pin default source")
        self._active_context_pin_default_btn.setAccessibleDescription("Pins the primary source for this workspace")
        self._active_context_pin_default_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.SECONDARY}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(47,111,122,0.42); background: #ffffff; }}"
        )
        self._active_context_pin_default_btn.clicked.connect(self._emit_active_context_default_requested)
        self._active_context_pin_default_btn.setVisible(False)
        self._active_context_swap_btn = QPushButton("MAKE PRIMARY SOURCE")
        self._active_context_swap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_context_swap_btn.setToolTip("Promote another attached source to primary")
        self._active_context_swap_btn.setAccessibleName("Make primary source")
        self._active_context_swap_btn.setAccessibleDescription("Promotes a non-primary source to primary")
        self._active_context_swap_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
        )
        self._active_context_swap_btn.clicked.connect(self._emit_active_context_swap_requested)
        self._active_context_swap_btn.setVisible(False)
        active_context_top.addWidget(self._active_context_refresh_btn)
        active_context_top.addWidget(self._active_context_pin_default_btn)
        active_context_top.addWidget(self._active_context_swap_btn)
        active_context_top.addWidget(self._active_context_clear_btn)
        active_context_layout.addLayout(active_context_top)
        self._active_context_summary = QLabel("No Library sources attached yet. Open Library and use USE IN CHAT to ground the next reply.")
        self._active_context_summary.setWordWrap(True)
        self._active_context_summary.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        active_context_layout.addWidget(self._active_context_summary)
        self._active_context_row = QHBoxLayout()
        self._active_context_row.setSpacing(8)
        active_context_layout.addLayout(self._active_context_row)
        self._active_context_host.setVisible(False)
        self._last_context_notice = ""
        self._focused_context_title = ""
        self._previewed_context_title = ""
        self._default_context_source_title = ""
        workspace_details_layout.addWidget(self._active_context_host)
        root.addWidget(self._workspace_details_host)

        transcript = QFrame()
        transcript.setObjectName("chat_surface")
        transcript.setStyleSheet(
            f"QFrame#chat_surface {{ background-color: rgba(255,255,255,0.58); border: 1px solid rgba(214,197,174,0.50); border-radius: 30px; }}"
        )
        tcol = QVBoxLayout(transcript)
        tcol.setContentsMargins(18, 16, 18, 16)
        tcol.setSpacing(12)

        transcript_hdr = QHBoxLayout()
        transcript_hdr.setSpacing(8)
        transcript_hdr.addWidget(_lbl("CONVERSATION", T.DIM, T.FS_TINY, True))
        self._grounding_chip = QLabel("")
        self._grounding_chip.setVisible(False)
        self._grounding_chip.setStyleSheet(
            f"color: {T.TERTIARY}; background: rgba(70,98,199,0.12); border: 1px solid rgba(214,197,174,0.40);"
            f" border-radius: 12px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        transcript_hdr.addWidget(self._grounding_chip)
        self._status_strip = QLabel("READY")
        self._status_strip.setStyleSheet(
            f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        transcript_hdr.addStretch()
        transcript_hdr.addWidget(self._status_strip)
        tcol.addLayout(transcript_hdr)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._chat_content = QWidget()
        self._chat_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._chat_layout = QVBoxLayout(self._chat_content)
        self._chat_layout.setContentsMargins(10, 6, 10, 6)
        self._chat_layout.setSpacing(20)
        self._empty_state = self._build_empty_state()
        self._chat_layout.addWidget(self._empty_state)
        self._chat_layout.addStretch()
        self._chat_scroll.setWidget(self._chat_content)
        tcol.addWidget(self._chat_scroll, stretch=1)
        root.addWidget(transcript, stretch=1)

        composer = QFrame()
        composer.setObjectName("chat_composer")
        composer.setStyleSheet(
            f"QFrame#chat_composer {{ background-color: rgba(255,255,255,0.64); border: 1px solid rgba(214,197,174,0.46); border-radius: 30px; }}"
        )
        composer_col = QVBoxLayout(composer)
        composer_col.setContentsMargins(14, 12, 14, 10)
        composer_col.setSpacing(8)

        starter_summary_row = QHBoxLayout()
        starter_summary_row.setSpacing(8)
        starter_summary_row.addWidget(self._starter_summary, stretch=1)
        self._starters_btn = QPushButton("STARTERS")
        self._starters_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._starters_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
            f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: rgba(70,98,199,0.46); color: {T.TERTIARY}; background: #ffffff; }}"
        )
        self._starters_btn.clicked.connect(self._toggle_starters)
        starter_summary_row.addWidget(self._starters_btn)
        composer_col.addLayout(starter_summary_row)
        self._starter_buttons_host = QWidget()
        starter_strip = QHBoxLayout(self._starter_buttons_host)
        starter_strip.setContentsMargins(0, 0, 0, 0)
        starter_strip.setSpacing(8)
        starter_strip.addLayout(self._starter_row, stretch=1)
        composer_col.addWidget(self._starter_buttons_host)

        self._launcher_panel = QFrame()
        self._launcher_panel.setObjectName("launcher_panel")
        self._launcher_panel.setStyleSheet(
            f"QFrame#launcher_panel {{ background-color: rgba(244,239,231,0.88); border: 1px solid rgba(214,197,174,0.66); border-radius: 18px; }}"
        )
        launcher_panel_col = QVBoxLayout(self._launcher_panel)
        launcher_panel_col.setContentsMargins(12, 10, 12, 10)
        launcher_panel_col.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        for header, opts, cb_attr in [
            ("MODE", list(LAUNCHER_MODES_DISPLAY), "_cb_mode"),
            ("PERSONA", ["GUPPY"], "_cb_persona"),
            ("PROFILE", ["LIGHT", "STANDARD", "POWER"], "_cb_profile"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_lbl(header))
            cb = _dropdown(opts)
            cb.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; color: {T.TEXT}; border: 1px solid {T.BORDER};"
                f" border-radius: 10px; padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            )
            setattr(self, cb_attr, cb)
            col.addWidget(cb)
            controls.addLayout(col)
        controls.addStretch()
        launcher_panel_col.addLayout(controls)
        composer_col.addWidget(self._launcher_panel)
        self._launcher_panel.setVisible(False)

        input_shell = QFrame()
        input_shell.setObjectName("composer_shell")
        input_shell.setStyleSheet(
            f"QFrame#composer_shell {{ background-color: rgba(255,255,255,0.90); border: 1px solid rgba(214,197,174,0.46); border-radius: 30px; }}"
        )
        input_row = QHBoxLayout(input_shell)
        input_row.setContentsMargins(16, 7, 7, 7)
        input_row.setSpacing(7)

        self._input = QLineEdit()
        self._input.setPlaceholderText(self._base_input_placeholder)
        self._input.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {T.TEXT};"
            f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; padding: 2px 0; }}"
        )
        self._input.returnPressed.connect(self._submit)
        input_row.addWidget(self._input, stretch=1)

        self._mic_btn = QPushButton("\u25cf")
        self._mic_btn.setFixedSize(32, 32)
        self._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
        self._mic_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(205,181,154,0.34); border-radius: 16px; background: rgba(255,250,243,0.92); color: {T.PRIMARY}; font-size: 10pt; }}"
            f"QPushButton:hover {{ border-color: rgba(255,107,61,0.55); background: #ffffff; }}"
        )
        self._mic_btn.clicked.connect(self.mic_requested.emit)

        self._cancel_btn = QPushButton("\u25a0")
        self._cancel_btn.setFixedSize(32, 32)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setToolTip("Cancel the in-flight request")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid rgba(200,75,68,0.42); border-radius: 16px; background: rgba(255,250,243,0.80); color: {T.ERROR}; font-size: 8pt; }}"
            f"QPushButton:hover {{ background: rgba(200,75,68,0.10); }}"
        )
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        self._send_btn = QPushButton("\u25b6")
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setStyleSheet(
            f"QPushButton {{ border: none; border-radius: 18px; background: {T.PRIMARY}; color: {T.BG}; font-size: 10pt; }}"
            f"QPushButton:hover {{ background: {T.PRIMARY_DIM}; }}"
        )
        self._send_btn.clicked.connect(self._submit)

        input_row.addWidget(self._mic_btn)
        input_row.addWidget(self._cancel_btn)
        input_row.addWidget(self._send_btn)
        composer_col.addWidget(input_shell)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._session_strip = _lbl("SESSION: --")
        self._session_strip.setStyleSheet(
            f"color: rgba(115,96,79,0.72); font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        footer.addWidget(self._session_strip)
        footer.addStretch()
        composer_col.addLayout(footer)
        root.addWidget(composer)

        self._cb_mode.currentTextChanged.connect(self._emit_context_changed)
        self._cb_persona.currentTextChanged.connect(self._emit_context_changed)
        self._cb_mode.currentTextChanged.connect(self._sync_launcher_summary)
        self._cb_persona.currentTextChanged.connect(self._sync_launcher_summary)
        self._cb_profile.currentTextChanged.connect(self._sync_launcher_summary)
        self.set_persona_options([("GUPPY", "guppy")], selected="guppy")
        self._sync_launcher_summary()
        self._refresh_resource_context()
        self._refresh_empty_state()
        self._sync_context_bar_visibility()
        self._refresh_composer_guidance()
        self._update_workspace_details_visibility()
        self._update_starter_visibility()

    def _sync_context_bar_visibility(self) -> None:
        context_sync_context_bar_visibility(self)

    def _toggle_context_details(self) -> None:
        context_toggle_context_details(self)

    def _toggle_workspace_details(self) -> None:
        self._workspace_details_expanded = not self._workspace_details_expanded
        self._update_workspace_details_visibility()

    def _toggle_starters(self) -> None:
        self._starters_expanded = not self._starters_expanded
        self._update_starter_visibility()

    def _update_workspace_details_visibility(self) -> None:
        has_saved_output = bool(self._latest_saved_output)
        has_sources = bool(self._active_context_items)
        summary = "Files and saved context are tucked away here."
        if has_sources and has_saved_output:
            summary = "Attached sources and saved output are available here."
        elif has_sources:
            summary = "Attached sources are available here."
        elif has_saved_output:
            summary = "Saved output is available here."
        self._workspace_details_summary.setText(summary)
        self._workspace_details_btn.setText("HIDE DETAILS" if self._workspace_details_expanded else "DETAILS")
        self._identity_details_btn.setText("HIDE DETAILS" if self._workspace_details_expanded else "DETAILS")
        self._workspace_details_host.setVisible(self._workspace_details_expanded)

    def _update_starter_visibility(self) -> None:
        self._starter_buttons_host.setVisible(self._starters_expanded)
        self._starters_btn.setText("HIDE STARTERS" if self._starters_expanded else "STARTERS")

    def _build_empty_state(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("empty_state")
        frame.setStyleSheet(
            f"QFrame#empty_state {{ background-color: rgba(255,250,243,0.78); border: 1px solid rgba(205,181,154,0.55); border-radius: 28px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        self._empty_state_title_lbl = QLabel(self._empty_state_title_text)
        self._empty_state_title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_title_lbl.setStyleSheet(
            f"color: {T.INK}; font-family: '{T.FF_HEAD}'; font-size: 25pt; font-weight: 700;"
        )
        layout.addWidget(self._empty_state_title_lbl)

        self._empty_state_subtitle_lbl = QLabel(self._empty_state_subtitle_text)
        self._empty_state_subtitle_lbl.setWordWrap(True)
        self._empty_state_subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_subtitle_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt;"
        )
        layout.addWidget(self._empty_state_subtitle_lbl)
        self._empty_state_recipe_lbl = QLabel(self._empty_state_recipe_text)
        self._empty_state_recipe_lbl.setWordWrap(True)
        self._empty_state_recipe_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._empty_state_recipe_lbl.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        layout.addWidget(self._empty_state_recipe_lbl)
        return frame

    def _refresh_empty_state(self) -> None:
        has_history = any(item.get("role") in {"user", "assistant"} for item in self._conversation_history)
        self._empty_state.setVisible(not has_history)

    def _refresh_empty_state_copy(self) -> None:
        state = build_home_workspace_state(
            self._workspace_name,
            workspace_type=self._workspace_type,
            description=self._workspace_purpose,
            mode=self.selected_mode(),
            persona=self.selected_persona(),
            voice="default",
            last_message="",
        )
        self._base_empty_state_title = state.onboarding_title
        self._base_empty_state_subtitle = state.onboarding_subtitle
        self._base_empty_state_recipe = state.onboarding_recipe
        self._refresh_empty_state_guidance()

    def _refresh_empty_state_guidance(self) -> None:
        title = self._base_empty_state_title
        subtitle = self._base_empty_state_subtitle
        recipe = self._base_empty_state_recipe
        titles = self._active_context_titles()
        if titles:
            joined = ", ".join(titles)
            subtitle = f"{subtitle} Library sources are already attached: {joined}."
            recipe = f"{recipe} Or ask the next thing using these attached sources: {joined}."
        self._empty_state_title_text = title
        self._empty_state_subtitle_text = subtitle
        self._empty_state_recipe_text = recipe
        if hasattr(self, "_empty_state_title_lbl"):
            self._empty_state_title_lbl.setText(title)
        if hasattr(self, "_empty_state_subtitle_lbl"):
            self._empty_state_subtitle_lbl.setText(subtitle)
        if hasattr(self, "_empty_state_recipe_lbl"):
            self._empty_state_recipe_lbl.setText(recipe)

    def _refresh_resource_context(self) -> None:
        context_refresh_resource_context(self)

    def _add_message(self, text: str, role: str) -> None:
        row_host = QWidget()
        row = QHBoxLayout(row_host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        if role == "system":
            pill = QLabel(text)
            pill.setWordWrap(True)
            pill.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            pill.setStyleSheet(
                f"color: {T.DIM}; background-color: rgba(244,239,231,0.84); border: 1px solid rgba(214,197,174,0.62);"
                f"border-radius: 14px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            )
            row.addStretch()
            row.addWidget(pill)
            row.addStretch()
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, row_host)
            QTimer.singleShot(0, self._scroll_to_bottom)
            return

        bubble = QFrame()
        bubble.setObjectName(f"bubble_{role}")
        bubble_bg = T.TERTIARY if role == "user" else "rgba(255,255,255,0.84)"
        bubble_fg = T.BG if role == "user" else T.TEXT
        if role == "user":
            radius = "24px 24px 8px 24px"
            border = "none"
        else:
            radius = "24px 24px 24px 8px"
            border = f"1px solid rgba(205,181,154,0.38)"
        bubble.setStyleSheet(
            f"QFrame#bubble_{role} {{ background-color: {bubble_bg}; border: {border}; border-top-left-radius: 24px; border-top-right-radius: 24px; border-bottom-left-radius: { '8px' if role == 'assistant' else '24px' }; border-bottom-right-radius: { '8px' if role == 'user' else '24px' }; }}"
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 11)
        bubble_layout.setSpacing(4)

        speaker = _lbl(
            "YOU" if role == "user" else "GUPPY",
            color="rgba(255,250,243,0.88)" if role == "user" else T.PRIMARY,
            size=T.FS_TINY,
            bold=True,
        )
        bubble_layout.addWidget(speaker)

        if role == "assistant":
            body = QTextBrowser()
            body.setOpenExternalLinks(False)
            body.setReadOnly(True)
            body.setUndoRedoEnabled(False)
            body.setMarkdown(text)
            body.setFrameStyle(0)
            body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            body.setStyleSheet(
                f"QTextBrowser {{ background: transparent; color: {bubble_fg}; border: none;"
                f" font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em; padding: 0; }}"
            )
            body.document().setDocumentMargin(0)
            body.document().adjustSize()
            body_height = max(36, min(260, int(body.document().size().height()) + 10))
            body.setFixedHeight(body_height)
            bubble_layout.addWidget(body)
            actions = QHBoxLayout()
            actions.setSpacing(6)
            actions.addStretch()
            for icon_label, hover_text, attach_next in (
                ("\u267b", "Save this reply to Library", False),
                ("\U0001F4CE", "Attach this reply as source for the next turn", True),
            ):
                action_btn = QPushButton(icon_label)
                action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                action_btn.setToolTip(hover_text)
                action_btn.setFixedSize(28, 24)
                action_btn.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
                    f" border-radius: 9px; padding: 0; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                    f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
                )
                action_btn.clicked.connect(
                    lambda _=False, content=text, should_attach=attach_next: self.assistant_reply_library_requested.emit(content, should_attach)
                )
                actions.addWidget(action_btn)
            artifact_btn = QPushButton("\u2B22")
            artifact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            artifact_btn.setToolTip("Save this reply as an artifact")
            artifact_btn.setFixedSize(28, 24)
            artifact_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.PRIMARY}; border: 1px solid rgba(214,197,174,0.44);"
                f" border-radius: 9px; padding: 0; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: rgba(242,202,80,0.62); background: #ffffff; }}"
            )
            artifact_btn.clicked.connect(
                lambda _=False, content=text: self.assistant_reply_artifact_requested.emit(content)
            )
            actions.addWidget(artifact_btn)
            bubble_layout.addLayout(actions)
        else:
            body = QLabel(text)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body.setStyleSheet(
                f"color: {bubble_fg}; background: transparent; border: none;"
                f"font-family: '{T.FF_BODY}'; font-size: {T.FS_LABEL}pt; line-height: 1.4em;"
            )
            bubble_layout.addWidget(body)

        bubble.setMaximumWidth(488 if role == "assistant" else 320)
        if role == "user":
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, row_host)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_transcript_widgets(self) -> None:
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue
            nested = item.layout()
            if nested is None:
                continue
            while nested.count():
                nested_item = nested.takeAt(0)
                if nested_item is None:
                    continue
                nested_widget = nested_item.widget()
                if nested_widget is not None:
                    nested_widget.deleteLater()

    def add_user_message(self, text: str) -> None:
        self._add_message(text, "user")
        self._conversation_history.append({"role": "user", "content": text})
        self._refresh_resource_context()
        self._refresh_empty_state()

    def add_assistant_message(self, text: str) -> None:
        self._add_message(text, "assistant")
        self._conversation_history.append({"role": "assistant", "content": text})
        self._latest_assistant_reply_text = str(text or "").strip()
        self._refresh_resource_context()
        self._refresh_empty_state()

    def add_system_message(self, text: str) -> None:
        self._add_message(text, "system")
        self._conversation_history.append({"role": "system", "content": text})

    def ensure_welcome_message(self) -> None:
        if any(item.get("role") in {"user", "assistant"} for item in self._conversation_history):
            return
        self.add_assistant_message(
            build_home_welcome_message(
                self._workspace_type,
                description=self._workspace_purpose,
            )
        )

    def toggle_launcher_panel(self) -> None:
        self._launcher_panel.setVisible(not self._launcher_panel.isVisible())
        self._sync_launcher_summary()

    def _sync_launcher_summary(self, _text: str = "") -> None:
        mode = self._cb_mode.currentText().strip().upper() or "AUTO"
        persona = self._cb_persona.currentText().strip().upper() or "GUPPY"
        profile = self._cb_profile.currentText().strip().upper() or "LIGHT"
        suffix = "OPEN" if self._launcher_panel.isVisible() else "EDIT"
        self._identity_mode_chip.setText(f"{mode} / {profile}")
        self.launcher_summary_changed.emit(f"{mode} / {persona} / {profile} [{suffix}]")

    def activate_agent(self, agent: str) -> None:
        del agent
        self._cb_persona.setCurrentIndex(0)
        self._status_strip.setText("ACTIVE AGENT · GUPPY")
        self.set_background_event("Active agent switched to GUPPY")

    def _submit(self) -> None:
        if not self._input.isEnabled():
            return
        text = self._input.text().strip()
        if text:
            self.command_submitted.emit(text)
            self._input.clear()

    def set_recommendation(self, profile: str) -> None:
        self._rec_chip.setText(f"RECOMMENDED · {profile.upper()}")

    def apply_settings(self, settings: dict) -> None:
        modes = {"auto": 0, "claude": 1, "ollama": 2, "local": 3, "code": 4, "teaching": 5}
        self._cb_mode.setCurrentIndex(modes.get(settings.get("default_mode", "auto"), 0))
        profiles = {"light": 0, "standard": 1, "power": 2}
        self._cb_profile.setCurrentIndex(profiles.get(settings.get("runtime_profile", "standard"), 1))

    def selected_mode(self) -> str:
        mode = self._cb_mode.currentText().strip().lower()
        return mode or "auto"

    def selected_persona(self) -> str:
        persona = str(self._cb_persona.currentData() or self._cb_persona.currentText()).strip().lower()
        return persona or "guppy"

    def set_persona_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._cb_persona.currentData() or self._cb_persona.currentText()).strip().lower()
        normalized = [
            (str(label).strip() or str(value).strip(), str(value).strip())
            for label, value in options
            if str(value).strip()
        ]
        if not normalized:
            normalized = [("GUPPY", "guppy")]
        self._cb_persona.blockSignals(True)
        self._cb_persona.clear()
        for label, value in normalized:
            self._cb_persona.addItem(label, value)
        target_index = 0
        for idx in range(self._cb_persona.count()):
            if str(self._cb_persona.itemData(idx) or "").strip().lower() == target:
                target_index = idx
                break
        self._cb_persona.setCurrentIndex(target_index)
        self._cb_persona.blockSignals(False)

    def set_route_preview(
        self,
        *,
        task_type: str = "unknown",
        route: str = "pending",
        model: str = "",
        backup_model: str = "",
        reason: str = "",
        evidence: str = "",
    ) -> None:
        context_set_route_preview(
            self,
            task_type=task_type,
            route=route,
            model=model,
            backup_model=backup_model,
            reason=reason,
            evidence=evidence,
        )

    def set_input_text(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def _starter_templates(self) -> list[tuple[str, str, str, str]]:
        return [
            (item.starter_id, item.title, item.mode, item.prompt)
            for item in home_workspace_starter_templates(self._workspace_type)
        ]

    def _active_context_titles(self, limit: int = 2) -> list[str]:
        return context_active_context_titles(self._active_context_items, limit)

    def _context_aware_starter_title(self, starter_id: str, title: str) -> str:
        return context_context_aware_starter_title(self._active_context_items, starter_id, title)

    def _context_aware_starter_prompt(self, prompt: str) -> str:
        return context_context_aware_starter_prompt(self._active_context_items, prompt)

    def _refresh_starter_buttons(self) -> None:
        for index, (starter_id, title, mode, prompt) in enumerate(self._starter_templates()):
            button = self._starter_buttons.get(starter_id)
            if button is None:
                continue
            button.setText(self._context_aware_starter_title(starter_id, title))
            button.setToolTip(self._context_aware_starter_prompt(prompt))
            button.setStyleSheet(self._starter_button_style(primary=index == 0))

    def _load_starter_by_id(self, starter_id: str) -> None:
        starter = build_home_starter_state(self._workspace_type, starter_id)
        titles = self._active_context_titles()
        if titles:
            starter = type(starter)(
                starter_id=starter.starter_id,
                label=self._context_aware_starter_title(starter.starter_id, starter.label),
                mode=starter.mode,
                prompt=self._context_aware_starter_prompt(starter.prompt),
                background_event=f"{starter.background_event} Attached sources ready: {', '.join(titles)}.",
                starter_summary=f"{starter.starter_summary} Attached sources: {', '.join(titles)}.",
                status=starter.status,
            )
        self._load_starter(starter)

    def _load_starter(self, starter) -> None:
        self.set_input_text(starter.prompt)
        self.set_chat_context(starter.mode, self.selected_persona())
        self.set_background_event(starter.background_event)
        self._base_starter_summary = starter.starter_summary
        self._refresh_composer_guidance()
        self.set_status(starter.status)
        self._starters_expanded = False
        self._update_starter_visibility()
        self.starter_requested.emit(starter.starter_id, starter.prompt)

    def set_status(self, text: str) -> None:
        status = (text or "Ready").strip().upper()
        self._status_strip.setText(status)
        color = T.PRIMARY
        if "ERROR" in status:
            color = T.ERROR
        elif "READY" in status:
            color = T.GREEN
        self._status_strip.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )

    def set_active_instance(
        self,
        instance: str,
        *,
        workspace_type: str = "user_instance",
        description: str = "",
        mode: str = "auto",
        persona: str = "guppy",
        voice: str = "default",
        last_message: str = "",
    ) -> None:
        name = (instance or "guppy-primary").strip() or "guppy-primary"
        if name != self._workspace_name:
            self.set_active_context_items([])
            self.clear_latest_saved_output()
        state = build_home_workspace_state(
            name,
            workspace_type=workspace_type,
            description=description,
            mode=mode,
            persona=persona,
            voice=voice,
            last_message=last_message,
        )
        self._workspace_name = name
        self._workspace_type = (workspace_type or "user_instance").strip().lower() or "user_instance"
        self._workspace_role = state.role_label
        self._workspace_purpose = state.purpose
        self.set_chat_context(mode, persona)
        self._refresh_empty_state_copy()
        self._refresh_starter_buttons()
        self._base_starter_summary = state.starter_summary
        self._base_input_placeholder = state.input_placeholder
        self._refresh_composer_guidance()
        self._instance_chip.setText(f"WORKSPACE · {name.upper()}")
        self._identity_workspace_chip.setText(f"WORKSPACE · {name.upper()}")
        self._identity_note.setText(state.entry_hint)
        self._workspace_summary.setText(state.workspace_summary)
        self._workspace_summary.setVisible(True)
        self._hero_subtitle.setText(_hero_subtitle_for_workspace(self._workspace_type))
        self._entry_hint.setText(state.entry_hint)
        self._refresh_resource_context()
        self._sync_context_bar_visibility()

    def set_background_status(self, text: str, healthy: bool = True) -> None:
        context_set_background_status(self, text, healthy=healthy)

    def set_background_event(self, text: str) -> None:
        context_set_background_event(self, text)

    def set_runtime_facts(
        self,
        *,
        profile: str = "standard",
        model: str = "guppy",
        voice: str = "edge",
        latency: str = "-",
        last_query: str = "-",
    ) -> None:
        context_set_runtime_facts(
            self,
            profile=profile,
            model=model,
            voice=voice,
            latency=latency,
            last_query=last_query,
        )

    def set_recovery_summary(self, text: str, healthy: bool = True) -> None:
        context_set_recovery_summary(self, text, healthy=healthy)

    def set_request_in_flight(self, in_flight: bool) -> None:
        self._request_in_flight_ui = in_flight
        self._input.setEnabled(not in_flight)
        self._send_btn.setEnabled(not in_flight)
        self._cancel_btn.setEnabled(in_flight)
        self._mic_btn.setEnabled(self._mic_capture_active or not in_flight)

    def set_mic_capture_state(self, listening: bool) -> None:
        self._mic_capture_active = listening
        if listening:
            self._mic_btn.setText("\u25c9")
            self._mic_btn.setToolTip("Listening now. Click to stop capture.")
            self._status_strip.setText("LISTENING")
            self._mic_btn.setEnabled(True)
            return
        self._mic_btn.setText("\u25cf")
        self._mic_btn.setToolTip("Push to talk. Click again while listening to stop capture.")
        self._mic_btn.setEnabled(not self._request_in_flight_ui)

    def set_session_id(self, session_id: str) -> None:
        sid = (session_id or "").strip()
        suffix = sid[-8:] if sid else "--"
        self._session_strip.setText(f"SESSION: {suffix}")

    def reset_live_history(self) -> None:
        self._conversation_history.clear()
        self._latest_assistant_reply_text = ""
        self._refresh_empty_state()

    def clear_transcript(self) -> None:
        self._clear_transcript_widgets()
        self.reset_live_history()

    def restore_history(self, history: list[dict[str, str]]) -> None:
        self.clear_transcript()
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            if role == "user":
                self.add_user_message(content)
            elif role == "assistant":
                self.add_assistant_message(content)
        self._refresh_resource_context()
        self._refresh_empty_state()

    def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        trimmed = self._conversation_history[-max(0, limit):]
        return [dict(item) for item in trimmed if item.get("role") in {"user", "assistant"}]

    def set_chat_context(self, mode: str, persona: str) -> None:
        mode_key = (mode or "").strip().lower()
        persona_key = (persona or "").strip().lower()

        for idx in range(self._cb_mode.count()):
            if self._cb_mode.itemText(idx).strip().lower() == mode_key:
                self._cb_mode.setCurrentIndex(idx)
                break

        for idx in range(self._cb_persona.count()):
            option_key = str(self._cb_persona.itemData(idx) or self._cb_persona.itemText(idx)).strip().lower()
            if option_key == persona_key:
                self._cb_persona.setCurrentIndex(idx)
                break
        self._refresh_resource_context()

    def chat_context(self) -> tuple[str, str]:
        return self.selected_mode(), self.selected_persona()

    def set_resource_context(self, *, files: str, study: str, coding: str) -> None:
        self._files_context_lbl.setText(files)
        self._study_context_lbl.setText(study)
        self._coding_context_lbl.setText(coding)

    def set_latest_saved_output(self, *, title: str, summary: str, source_label: str = "Saved reply artifact") -> None:
        title_text = str(title or "").strip()
        summary_text = str(summary or "").strip()
        if not title_text:
            self.clear_latest_saved_output()
            return
        self._latest_saved_output = {
            "title": title_text,
            "summary": summary_text,
            "source_label": str(source_label or "Saved reply artifact").strip() or "Saved reply artifact",
        }
        self._latest_output_title.setText(str(self._latest_saved_output["source_label"]).upper())
        self._latest_output_summary.setText(
            f"{title_text}. {summary_text}" if summary_text else title_text
        )
        self._latest_output_host.setVisible(True)
        self._update_workspace_details_visibility()

    def clear_latest_saved_output(self) -> None:
        self._latest_saved_output = {}
        self._latest_output_summary.setText("")
        self._latest_output_host.setVisible(False)
        self._update_workspace_details_visibility()

    def _emit_latest_saved_output_attach(self) -> None:
        if not self._latest_saved_output:
            return
        self.latest_saved_output_attach_requested.emit(
            str(self._latest_saved_output.get("title", "")),
            str(self._latest_saved_output.get("summary", "")),
        )

    def _emit_latest_saved_output_library(self) -> None:
        if not self._latest_saved_output:
            return
        self.latest_saved_output_library_requested.emit(str(self._latest_saved_output.get("title", "")))

    def set_active_context_items(self, items: list[dict[str, str]]) -> None:
        self._active_context_items = context_normalize_context_items(items)
        while self._active_context_row.count():
            row_item = self._active_context_row.takeAt(0)
            if row_item is None:
                continue
            widget = row_item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if not self._active_context_items:
            self._last_context_notice = ""
            self._focused_context_title = ""
            self._previewed_context_title = ""
            self._swap_source_target_title = ""
            self._active_context_refresh_btn.setVisible(False)
            self._active_context_pin_default_btn.setVisible(False)
            self._active_context_swap_btn.setVisible(False)
            self._active_context_host.setVisible(False)
            self._refresh_grounding_cue()
            self._refresh_starter_buttons()
            self._refresh_composer_guidance()
            self._refresh_empty_state_guidance()
            self._update_workspace_details_visibility()
            return
        primary_title = self._active_context_items[0]["title"]
        previous_focus = self._focused_context_title
        self._focused_context_title = primary_title
        primary_origin = str(self._active_context_items[0].get("origin", "") or "").strip().lower()
        saved_origins = {"assistant_reply", "assistant_reply_artifact"}
        self._swap_source_target_title = ""
        if primary_origin in saved_origins:
            for item in self._active_context_items[1:]:
                item_origin = str(item.get("origin", "") or "").strip().lower()
                if item_origin not in saved_origins and str(item.get("title", "") or "").strip():
                    self._swap_source_target_title = str(item.get("title", "") or "").strip()
                    break
        self._active_context_refresh_btn.setVisible(bool(primary_origin in saved_origins and self._latest_assistant_reply_text))
        self._active_context_pin_default_btn.setVisible(bool(primary_title))
        pinned_default = primary_title == self._default_context_source_title
        self._active_context_pin_default_btn.setText("DEFAULT PINNED" if pinned_default else "PIN PRIMARY")
        self._active_context_pin_default_btn.setEnabled(not pinned_default)
        self._active_context_pin_default_btn.setToolTip(
            "This source is already the workspace default"
            if pinned_default
            else "Pin the primary source as this workspace default"
        )
        self._active_context_swap_btn.setVisible(bool(self._swap_source_target_title))
        self._active_context_swap_btn.setText("MAKE PRIMARY SOURCE")
        available_titles = {item["title"] for item in self._active_context_items}
        if previous_focus != primary_title or self._previewed_context_title not in available_titles:
            self._previewed_context_title = primary_title
        self._active_context_summary.setText(context_format_active_context_summary(self._active_context_items))
        for item in self._active_context_items:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background-color: rgba(255,250,243,0.92); border: 1px solid rgba(214,197,174,0.52); border-radius: 14px; }"
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(4)
            top = QHBoxLayout()
            top.setSpacing(6)
            if item["title"] == primary_title:
                top.addWidget(_lbl("PRIMARY", T.PRIMARY, T.FS_TINY, True))
            if item["title"] == self._default_context_source_title:
                top.addWidget(_lbl("DEFAULT", T.SECONDARY, T.FS_TINY, True))
            kind_lbl = _lbl(item["kind"], T.SECONDARY, T.FS_TINY, True)
            top.addWidget(kind_lbl)
            if item.get("origin") in {"assistant_reply", "assistant_reply_artifact"}:
                source_lbl = _lbl(
                    str(item.get("source_label") or "SAVED SOURCE").upper(),
                    T.PRIMARY,
                    T.FS_TINY,
                    True,
                )
                top.addWidget(source_lbl)
            top.addStretch()
            preview_btn = QPushButton("HIDE" if item["title"] == self._previewed_context_title else "PREVIEW")
            preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            preview_btn.setFixedHeight(20)
            preview_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.44);"
                f" border-radius: 10px; padding: 0 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: rgba(205,181,154,0.62); background: #ffffff; }}"
            )
            preview_btn.clicked.connect(
                lambda _=False, title=item["title"]: self._toggle_active_context_preview(title)
            )
            top.addWidget(preview_btn)
            if item["title"] != primary_title:
                focus_btn = QPushButton("MAKE PRIMARY")
                focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                focus_btn.setFixedHeight(20)
                focus_btn.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
                    f" border-radius: 10px; padding: 0 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                    f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); color: {T.TERTIARY}; background: #ffffff; }}"
                )
                focus_btn.clicked.connect(
                    lambda _=False, title=item["title"]: self.active_context_focus_requested.emit(title)
                )
                top.addWidget(focus_btn)
            if item["title"] == primary_title:
                library_btn = QPushButton("OPEN IN LIBRARY")
                library_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                library_btn.setFixedHeight(20)
                library_btn.setStyleSheet(
                    f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.TERTIARY}; border: 1px solid rgba(214,197,174,0.44);"
                    f" border-radius: 10px; padding: 0 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                    f"QPushButton:hover {{ border-color: rgba(70,98,199,0.42); background: #ffffff; }}"
                )
                library_btn.clicked.connect(
                    lambda _=False, title=item["title"]: self.active_context_library_requested.emit(title)
                )
                top.addWidget(library_btn)
            remove_btn = QPushButton("REMOVE")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setFixedHeight(20)
            remove_btn.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.44);"
                f" border-radius: 10px; padding: 0 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: rgba(200,75,68,0.42); color: {T.ERROR}; }}"
            )
            remove_btn.clicked.connect(
                lambda _=False, title=item["title"]: self.active_context_remove_requested.emit(title)
            )
            top.addWidget(remove_btn)
            layout.addLayout(top)
            title_lbl = QLabel(item["title"])
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(
                f"color: {T.INK}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; font-weight: 600;"
            )
            layout.addWidget(title_lbl)
            if item["detail"]:
                detail_lbl = QLabel(item["detail"])
                detail_lbl.setWordWrap(True)
                detail_lbl.setToolTip(item["detail"])
                detail_lbl.setStyleSheet(
                    f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_TINY}pt;"
                )
                detail_lbl.setVisible(item["title"] == self._previewed_context_title)
                layout.addWidget(detail_lbl)
            self._active_context_row.addWidget(card)
        self._active_context_row.addStretch()
        self._active_context_host.setVisible(True)
        self._refresh_grounding_cue()
        self._refresh_starter_buttons()
        self._refresh_composer_guidance()
        self._refresh_empty_state_guidance()
        self._update_workspace_details_visibility()

    def _toggle_active_context_preview(self, title: str) -> None:
        title_text = str(title or "").strip()
        if not title_text:
            return
        self._previewed_context_title = "" if self._previewed_context_title == title_text else title_text
        self.set_active_context_items(self._active_context_items)

    def _emit_active_context_refresh_requested(self) -> None:
        if not self._active_context_items:
            return
        latest_reply = str(self._latest_assistant_reply_text or "").strip()
        if not latest_reply:
            return
        origin = str(self._active_context_items[0].get("origin", "") or "").strip().lower()
        self.active_context_refresh_requested.emit(latest_reply, origin == "assistant_reply_artifact")

    def _emit_active_context_swap_requested(self) -> None:
        title = str(self._swap_source_target_title or "").strip()
        if not title:
            return
        self.active_context_focus_requested.emit(title)

    def _emit_active_context_default_requested(self) -> None:
        if not self._active_context_items:
            return
        primary_title = str(self._active_context_items[0].get("title", "") or "").strip()
        if not primary_title:
            return
        self.active_context_default_requested.emit(primary_title)

    def set_default_context_source(self, title: str) -> None:
        self._default_context_source_title = str(title or "").strip()
        if self._active_context_items:
            self.set_active_context_items(self._active_context_items)

    def note_active_context_submission(self, text: str) -> None:
        notice = str(text or "").strip()
        if not notice:
            return
        self._last_context_notice = notice
        if self._active_context_items:
            self._active_context_summary.setText(
                context_format_active_context_summary(self._active_context_items, used_for_latest_reply=True)
            )
            self._active_context_host.setVisible(True)
            self._update_workspace_details_visibility()
        self._refresh_grounding_cue()
        self._refresh_composer_guidance()
        self.add_system_message(notice)

    def _refresh_grounding_cue(self) -> None:
        if not self._active_context_items:
            self._grounding_chip.clear()
            self._grounding_chip.setToolTip("")
            self._grounding_chip.setVisible(False)
            return
        label, tooltip = context_build_grounding_cue(self._active_context_items[0])
        self._grounding_chip.setText(label)
        self._grounding_chip.setToolTip(tooltip)
        self._grounding_chip.setVisible(True)

    def _refresh_composer_guidance(self) -> None:
        placeholder, starter_summary = context_build_composer_guidance(
            self._base_input_placeholder,
            self._base_starter_summary,
            self._active_context_items,
        )
        self._input.setPlaceholderText(placeholder)
        self._starter_summary.setText(starter_summary)

    def _emit_context_changed(self, _text: str) -> None:
        self.chat_context_changed.emit(self.selected_mode(), self.selected_persona())

    @staticmethod
    def _starter_button_style(primary: bool = False) -> str:
        border = T.PRIMARY if primary else T.BORDER
        color = T.PRIMARY if primary else T.TEXT
        background = "rgba(242,202,80,0.10)" if primary else T.BG0
        return (
            f"QPushButton {{ background: {background}; color: {color}; border: 1px solid {border};"
            f" border-radius: 13px; padding: 6px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.TERTIARY}; color: {T.INK}; background: rgba(70,98,199,0.08); }}"
        )
