from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.instance_manager_presenter import (
    build_connector_binding_editor_state,
    build_connector_binding_save_request,
    build_governance_editor_state,
    build_instance_manager_state,
    build_save_affordance_state,
    build_section_toggle_state,
    build_selector_state,
    build_workspace_activity_log_text,
    build_workspace_create_copy,
    build_workspace_create_form_state,
    build_workspace_create_request,
    build_connector_binding_feedback,
    build_governance_save_request,
    build_workspace_editors_state,
    connector_history_line,
    selector_label,
    workspace_recent_context,
    workspace_role_summary,
    workspace_saved_context,
)
from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label

def _workspace_saved_context(payload: dict[str, object]) -> str:
    return workspace_saved_context(payload)


def _workspace_recent_context(payload: dict[str, object]) -> str:
    return workspace_recent_context(payload)


def _workspace_role_summary(items: list[dict[str, object]]) -> str:
    return workspace_role_summary(items)


class _InstanceCard(QFrame):
    activate_requested = Signal(str)
    delete_requested = Signal(str)
    logs_requested = Signal(str)

    def __init__(self, payload: dict[str, object], active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = str(payload.get("name", "")).strip()
        self.setObjectName("instance_card")
        border = T.PRIMARY if active else T.BORDER
        self.setStyleSheet(
            f"QFrame#instance_card {{ background-color: {T.BG1}; border: 1px solid {border}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        name_lbl = QLabel(self._name.upper())
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE}pt; font-weight: bold;"
        )
        header.addWidget(name_lbl)
        workspace_type = str(payload.get("type", "user_instance") or "user_instance")
        workspace_copy = build_workspace_create_copy(workspace_type)
        header.addSpacing(8)
        header.addWidget(_mono(workspace_copy.role_label.upper(), T.DIM, T.FS_TINY, True))
        header.addStretch()
        status = str(payload.get("status", "idle") or "idle").upper()
        header.addWidget(_mono(status, T.GREEN if status in {"ACTIVE", "RUNNING"} else T.DIM, T.FS_TINY, True))
        if active:
            header.addSpacing(8)
            header.addWidget(_mono("ACTIVE", T.PRIMARY, T.FS_TINY, True))
        root.addLayout(header)

        details = [
            f"Mode: {str(payload.get('mode', 'auto')).upper()}",
            f"Persona: {str(payload.get('persona', 'guppy')).upper()}",
            f"Voice: {str(payload.get('voice', 'default')).upper()}",
            f"Role: {workspace_copy.role_label}",
        ]
        description = str(payload.get("description", "")).strip()
        details.append(f"Purpose: {description or workspace_copy.default_purpose}")
        details.append(f"Fit: {workspace_copy.collaboration_hint}")
        details.append(workspace_copy.first_run_recipe)
        details.append(_workspace_saved_context(payload))
        details.append(f"Return here for: {workspace_copy.reentry_hint}")
        details.append(_workspace_recent_context(payload))
        for line in details:
            root.addWidget(_mono(line, T.DIM, T.FS_TINY))

        actions = QHBoxLayout()
        for label, signal in (("OPEN", self.activate_requested), ("LOGS", self.logs_requested), ("DELETE", self.delete_requested)):
            button = QPushButton(label)
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            button.clicked.connect(lambda _=False, name=self._name, emitter=signal: emitter.emit(name))
            if label == "DELETE" and active:
                button.setEnabled(False)
                button.setToolTip("Switch away before deleting the active instance.")
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)


class InstanceManagerView(QWidget):
    refresh_requested = Signal()
    activate_requested = Signal(str)
    delete_requested = Signal(str)
    create_requested = Signal(dict)
    logs_requested = Signal(str)
    governance_save_requested = Signal(dict)
    connector_binding_save_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_names: set[str] = set()
        self._configured = 0
        self._max_configured = 5
        self._active_runtime = 0
        self._max_active_runtime = 2
        self._governance_by_name: dict[str, dict[str, object]] = {}
        self._connectors_by_name: dict[str, dict[str, dict[str, object]]] = {}
        self._governance_visible = False
        self._connector_bindings_visible = False
        self._last_role_copy = build_workspace_create_copy("user_instance")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        title = QLabel("Workspaces")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;"
        )
        layout.addWidget(title)
        self._status_lbl = _mono("Ready to review saved workspaces, defaults, and workspace memory.", T.DIM, T.FS_TINY)
        layout.addWidget(self._status_lbl)

        self._sections = QTabWidget()
        self._sections.setDocumentMode(True)
        self._sections.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {T.BORDER}; background: rgba(255,255,255,0.42); }}"
            f"QTabBar::tab {{ background: rgba(255,255,255,0.86); color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 8px; margin-right: 4px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QTabBar::tab:selected {{ color: {T.INK}; border-color: {T.PRIMARY}; background: rgba(242,202,80,0.14); }}"
        )
        self._overview_tab = QWidget()
        self._overview_layout = QVBoxLayout(self._overview_tab)
        self._overview_layout.setContentsMargins(10, 10, 10, 10)
        self._overview_layout.setSpacing(10)
        self._create_tab = QWidget()
        self._create_layout = QVBoxLayout(self._create_tab)
        self._create_layout.setContentsMargins(10, 10, 10, 10)
        self._create_layout.setSpacing(10)
        self._access_tab = QWidget()
        self._access_layout = QVBoxLayout(self._access_tab)
        self._access_layout.setContentsMargins(10, 10, 10, 10)
        self._access_layout.setSpacing(10)
        self._connector_tab = QWidget()
        self._connector_layout = QVBoxLayout(self._connector_tab)
        self._connector_layout.setContentsMargins(10, 10, 10, 10)
        self._connector_layout.setSpacing(10)
        self._activity_tab = QWidget()
        self._activity_layout = QVBoxLayout(self._activity_tab)
        self._activity_layout.setContentsMargins(10, 10, 10, 10)
        self._activity_layout.setSpacing(10)
        self._sections.addTab(self._overview_tab, "Overview")
        self._sections.addTab(self._create_tab, "Create")
        self._sections.addTab(self._access_tab, "Access")
        self._sections.addTab(self._connector_tab, "Connectors")
        self._sections.addTab(self._activity_tab, "Activity")
        layout.addWidget(self._sections)

        form = QFrame()
        form.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(8)
        form_layout.addWidget(_mono("WORKSPACE SETUP", T.PRIMARY, T.FS_TINY, True))
        self._preset_lbl = _mono("Preset: daily workspace defaults are ready.", T.DIM, T.FS_TINY)
        self._preset_lbl.setWordWrap(True)
        form_layout.addWidget(self._preset_lbl)
        self._recipe_lbl = _mono("First run: use MORNING BRIEF to get the workspace moving.", T.DIM, T.FS_TINY)
        self._recipe_lbl.setWordWrap(True)
        form_layout.addWidget(self._recipe_lbl)
        self._examples_lbl = _mono(build_workspace_create_copy("user_instance").example_names, T.DIM, T.FS_TINY)
        self._examples_lbl.setWordWrap(True)
        form_layout.addWidget(self._examples_lbl)

        row1 = QHBoxLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("research-desk")
        self._description = QLineEdit()
        self._description.setPlaceholderText("What this workspace helps with")
        for widget in (self._name, self._description):
            widget.setStyleSheet(
                f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        row1.addWidget(self._name)
        row1.addWidget(self._description, stretch=1)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self._mode = QComboBox()
        self._mode.addItems(["auto", "claude", "ollama", "local", "code", "teaching"])
        self._persona = QComboBox()
        self._persona.addItems(["guppy"])
        self._voice = QComboBox()
        self._voice.addItems(["default", "kokoro", "system"])
        self._type = QComboBox()
        self._type.addItems(["user_instance", "builder_instance", "read_only_instance", "admin_instance"])
        for combo in (self._mode, self._persona, self._voice, self._type):
            combo.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
            row2.addWidget(combo)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(True)
        self._enabled.setStyleSheet(
            f"QCheckBox {{ color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; }}"
        )
        save_btn = QPushButton("SAVE WORKSPACE")
        refresh_btn = QPushButton("REFRESH")
        for button in (save_btn, refresh_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
        save_btn.clicked.connect(self._emit_create)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        row3.addWidget(self._enabled)
        row3.addStretch()
        row3.addWidget(refresh_btn)
        row3.addWidget(save_btn)
        form_layout.addLayout(row3)
        layout.addWidget(form)

        collapse_row = QHBoxLayout()
        collapse_row.setSpacing(8)
        self._governance_toggle_btn = QPushButton("SHOW ACCESS RULES")
        self._connector_toggle_btn = QPushButton("SHOW CONNECTOR RULES")
        for button in (self._governance_toggle_btn, self._connector_toggle_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
        collapse_row.addWidget(self._governance_toggle_btn)
        collapse_row.addWidget(self._connector_toggle_btn)
        collapse_row.addStretch()

        self._governance_frame = QFrame()
        self._governance_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        governance_layout = QVBoxLayout(self._governance_frame)
        governance_layout.setContentsMargins(14, 12, 14, 12)
        governance_layout.setSpacing(8)
        governance_layout.addWidget(_mono("ACCESS + SAFETY", T.PRIMARY, T.FS_TINY, True))
        governance_hint = _mono(
            "Control what this workspace can do, what it can reach, and what note appears when access is limited.",
            T.DIM,
            T.FS_SMALL,
        )
        governance_hint.setWordWrap(True)
        governance_layout.addWidget(governance_hint)

        gov_row1 = QHBoxLayout()
        self._governance_workspace = QComboBox()
        self._governance_auth_mode = QComboBox()
        self._governance_auth_mode.addItems(
            ["runtime_default", "workspace_token_required", "local_only", "disabled"]
        )
        for combo in (self._governance_workspace, self._governance_auth_mode):
            combo.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        gov_row1.addWidget(self._governance_workspace, stretch=1)
        gov_row1.addWidget(self._governance_auth_mode, stretch=1)
        governance_layout.addLayout(gov_row1)

        self._governance_note = QLineEdit()
        self._governance_note.setPlaceholderText("Short note shown when something is blocked in this workspace")
        self._governance_note.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        governance_layout.addWidget(self._governance_note)

        gov_row2 = QHBoxLayout()
        gov_row3 = QHBoxLayout()
        self._tool_allow = QPlainTextEdit()
        self._tool_block = QPlainTextEdit()
        self._endpoint_allow = QPlainTextEdit()
        self._endpoint_block = QPlainTextEdit()
        for editor, placeholder in (
            (self._tool_allow, "tool allow list\none tool per line"),
            (self._tool_block, "tool block list\none tool per line"),
            (self._endpoint_allow, "endpoint allow filters\none pattern per line"),
            (self._endpoint_block, "endpoint block filters\none pattern per line"),
        ):
            editor.setPlaceholderText(placeholder)
            editor.setMinimumHeight(88)
            editor.setStyleSheet(
                f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            )
        gov_row2.addWidget(self._tool_allow)
        gov_row2.addWidget(self._tool_block)
        gov_row3.addWidget(self._endpoint_allow)
        gov_row3.addWidget(self._endpoint_block)
        governance_layout.addLayout(gov_row2)
        governance_layout.addLayout(gov_row3)

        self._governance_status = _mono("Access settings ready.", T.DIM, T.FS_TINY)
        self._governance_status.setWordWrap(True)
        governance_layout.addWidget(self._governance_status)

        gov_actions = QHBoxLayout()
        gov_actions.addStretch()
        self._governance_save_btn = QPushButton("SAVE ACCESS")
        self._governance_save_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        gov_actions.addWidget(self._governance_save_btn)
        governance_layout.addLayout(gov_actions)
        self._governance_frame.setVisible(False)
        layout.addWidget(self._governance_frame)

        self._connectors_frame = QFrame()
        self._connectors_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        connectors_layout = QVBoxLayout(self._connectors_frame)
        connectors_layout.setContentsMargins(14, 12, 14, 12)
        connectors_layout.setSpacing(8)
        connectors_layout.addWidget(_mono("CONNECTOR BINDINGS", T.PRIMARY, T.FS_TINY, True))
        connector_hint = _mono(
            "Bind this workspace to a machine-level connector account/provider, then refine allowed connector actions and endpoint scope.",
            T.DIM,
            T.FS_SMALL,
        )
        connector_hint.setWordWrap(True)
        connectors_layout.addWidget(connector_hint)

        connector_row1 = QHBoxLayout()
        self._connector_workspace = QComboBox()
        self._connector_id = QComboBox()
        for combo in (self._connector_workspace, self._connector_id):
            combo.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        connector_row1.addWidget(self._connector_workspace, stretch=1)
        connector_row1.addWidget(self._connector_id, stretch=1)
        connectors_layout.addLayout(connector_row1)

        connector_row2 = QHBoxLayout()
        self._connector_enabled = QCheckBox("Bound to this workspace")
        self._connector_enabled.setStyleSheet(
            f"QCheckBox {{ color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; }}"
        )
        self._connector_account = QComboBox()
        self._connector_provider = QComboBox()
        for widget in (self._connector_account, self._connector_provider):
            widget.setStyleSheet(
                f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            )
        connector_row2.addWidget(self._connector_enabled)
        connector_row2.addWidget(self._connector_account, stretch=1)
        connector_row2.addWidget(self._connector_provider, stretch=1)
        connectors_layout.addLayout(connector_row2)

        connector_row3 = QHBoxLayout()
        self._connector_action_allow = QPlainTextEdit()
        self._connector_action_block = QPlainTextEdit()
        self._connector_endpoint_allow = QPlainTextEdit()
        self._connector_endpoint_block = QPlainTextEdit()
        for editor, placeholder in (
            (self._connector_action_allow, "action allow list\none action per line"),
            (self._connector_action_block, "action block list\none action per line"),
            (self._connector_endpoint_allow, "connector endpoint allow filters\none pattern per line"),
            (self._connector_endpoint_block, "connector endpoint block filters\none pattern per line"),
        ):
            editor.setPlaceholderText(placeholder)
            editor.setMinimumHeight(88)
            editor.setStyleSheet(
                f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
                f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            )
        connector_row3.addWidget(self._connector_action_allow)
        connector_row3.addWidget(self._connector_action_block)
        connectors_layout.addLayout(connector_row3)

        connector_row4 = QHBoxLayout()
        connector_row4.addWidget(self._connector_endpoint_allow)
        connector_row4.addWidget(self._connector_endpoint_block)
        connectors_layout.addLayout(connector_row4)

        self._connector_note = QLineEdit()
        self._connector_note.setPlaceholderText("Operator-visible connector note for this workspace")
        self._connector_note.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        connectors_layout.addWidget(self._connector_note)

        self._connector_status = _mono("Connector binding editor ready", T.DIM, T.FS_TINY)
        self._connector_status.setWordWrap(True)
        connectors_layout.addWidget(self._connector_status)
        self._connector_validation = _mono("Binding validation will appear here after connector data loads.", T.DIM, T.FS_TINY)
        self._connector_validation.setWordWrap(True)
        connectors_layout.addWidget(self._connector_validation)
        self._connector_history = _mono("Connector history will appear here after verify/connect activity runs.", T.DIM, T.FS_TINY)
        self._connector_history.setWordWrap(True)
        connectors_layout.addWidget(self._connector_history)

        connector_actions = QHBoxLayout()
        connector_actions.addStretch()
        self._connector_save_btn = QPushButton("SAVE CONNECTOR BINDING")
        self._connector_save_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        connector_actions.addWidget(self._connector_save_btn)
        connectors_layout.addLayout(connector_actions)
        self._connectors_frame.setVisible(False)
        layout.addWidget(self._connectors_frame)

        self._summary_lbl = _mono("No workspace data loaded", T.DIM, T.FS_TINY)
        layout.addWidget(self._summary_lbl)
        self._role_mix_lbl = _mono("Role mix: Daily 0 | Builder 0 | Reference 0 | Ops 0", T.DIM, T.FS_TINY)
        self._collab_lbl = _mono("Collaboration cues appear here once workspaces load.", T.DIM, T.FS_TINY)
        self._collab_lbl.setWordWrap(True)
        self._recurring_lbl = _mono("Recurring context cues appear here once workspaces load.", T.DIM, T.FS_TINY)
        self._recurring_lbl.setWordWrap(True)
        self._empty_state_lbl = _mono(
            "Create a workspace to get started: Daily for recurring help, Builder for review loops, Reference for safe source checks, or Ops for recovery work.",
            T.DIM,
            T.FS_TINY,
        )
        self._empty_state_lbl.setWordWrap(True)
        self._limits_lbl = _mono("Configured workspaces: 0 / 5 | Live workspaces: 0 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._limits_lbl)
        layout.addWidget(self._role_mix_lbl)
        layout.addWidget(self._collab_lbl)
        layout.addWidget(self._recurring_lbl)
        layout.addWidget(self._empty_state_lbl)

        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        layout.addWidget(self._cards_host)

        logs_frame = QFrame()
        logs_frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; }}")
        logs_layout = QVBoxLayout(logs_frame)
        logs_layout.setContentsMargins(12, 10, 12, 10)
        logs_layout.setSpacing(6)
        logs_layout.addWidget(_mono("WORKSPACE ACTIVITY", T.PRIMARY, T.FS_TINY, True))
        self._logs = QPlainTextEdit()
        self._logs.setReadOnly(True)
        self._logs.setMinimumHeight(180)
        self._logs.setStyleSheet(
            f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        )
        logs_layout.addWidget(self._logs)
        layout.addWidget(logs_frame)

        # Move dense sections into tabs so only one workspace surface is visible at a time.
        for widget in (
            self._limits_lbl,
            self._summary_lbl,
            self._role_mix_lbl,
            self._collab_lbl,
            self._recurring_lbl,
            self._empty_state_lbl,
            self._cards_host,
        ):
            layout.removeWidget(widget)
            self._overview_layout.addWidget(widget)
        self._overview_layout.addStretch()

        layout.removeWidget(form)
        self._create_layout.addWidget(form)
        self._create_layout.addStretch()

        layout.removeWidget(self._governance_frame)
        _access_btn_row = QHBoxLayout()
        _access_btn_row.addWidget(self._governance_toggle_btn)
        _access_btn_row.addStretch()
        self._access_layout.addLayout(_access_btn_row)
        self._access_layout.addWidget(self._governance_frame)
        self._access_layout.addStretch()
        layout.removeWidget(self._connectors_frame)
        _conn_btn_row = QHBoxLayout()
        _conn_btn_row.addWidget(self._connector_toggle_btn)
        _conn_btn_row.addStretch()
        self._connector_layout.addLayout(_conn_btn_row)
        self._connector_layout.addWidget(self._connectors_frame)
        self._connector_layout.addStretch()

        layout.removeWidget(logs_frame)
        self._activity_layout.addWidget(logs_frame)
        self._activity_layout.addStretch()

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._name.textChanged.connect(self._sync_save_affordance)
        self._type.currentTextChanged.connect(self._apply_role_preset)
        self._governance_workspace.currentTextChanged.connect(self._load_governance_editor)
        self._connector_workspace.currentTextChanged.connect(self._load_connector_binding_editor)
        self._connector_id.currentTextChanged.connect(self._load_connector_binding_editor)
        self._connector_provider.currentIndexChanged.connect(self._refresh_connector_binding_feedback)
        self._connector_account.currentIndexChanged.connect(self._refresh_connector_binding_feedback)
        self._connector_enabled.stateChanged.connect(self._refresh_connector_binding_feedback)
        self._governance_toggle_btn.clicked.connect(self._toggle_governance_section)
        self._connector_toggle_btn.clicked.connect(self._toggle_connector_bindings_section)
        self._governance_save_btn.clicked.connect(self._emit_governance_save)
        self._connector_save_btn.clicked.connect(self._emit_connector_binding_save)
        self._save_btn = save_btn
        self._apply_role_preset(self._type.currentText())
        self._sync_save_affordance()

    def _emit_create(self) -> None:
        request = build_workspace_create_request(
            name=self._name.text(),
            description=self._description.text(),
            mode=self._mode.currentText(),
            persona=str(self._persona.currentData() or self._persona.currentText()),
            voice=str(self._voice.currentData() or self._voice.currentText()),
            workspace_type=self._type.currentText(),
            enabled=self._enabled.isChecked(),
        )
        self.create_requested.emit(request.as_payload())

    def _toggle_governance_section(self) -> None:
        state = build_section_toggle_state(
            not self._governance_visible,
            show_label="SHOW ACCESS RULES",
            hide_label="HIDE ACCESS RULES",
        )
        self._governance_visible = state.visible
        self._governance_frame.setVisible(state.visible)
        self._governance_toggle_btn.setText(state.button_label)

    def _toggle_connector_bindings_section(self) -> None:
        state = build_section_toggle_state(
            not self._connector_bindings_visible,
            show_label="SHOW CONNECTOR RULES",
            hide_label="HIDE CONNECTOR RULES",
        )
        self._connector_bindings_visible = state.visible
        self._connectors_frame.setVisible(state.visible)
        self._connector_toggle_btn.setText(state.button_label)

    @staticmethod
    def _selector_label(item: dict[str, object], *, fallback: str) -> str:
        return selector_label(item, fallback=fallback)

    @staticmethod
    def _history_line(payload: dict[str, object]) -> str:
        return connector_history_line(payload)

    def _apply_role_preset(self, workspace_type: str) -> None:
        form_state = build_workspace_create_form_state(
            workspace_type=workspace_type,
            current_description=self._description.text(),
            current_mode=self._mode.currentText(),
            previous_copy=self._last_role_copy,
        )
        copy = form_state.copy
        self._name.setPlaceholderText(copy.name_placeholder)
        self._description.setPlaceholderText(copy.description_placeholder)
        self._preset_lbl.setText(copy.preset_summary)
        self._recipe_lbl.setText(copy.first_run_recipe)
        self._examples_lbl.setText(copy.example_names)
        if form_state.description_value is not None:
            self._description.setText(form_state.description_value)
        if form_state.mode_value is not None:
            idx = self._mode.findText(form_state.mode_value)
            if idx >= 0:
                self._mode.setCurrentIndex(idx)
        self._last_role_copy = copy

    @staticmethod
    def _apply_selector(combo: QComboBox, state) -> None:
        combo.blockSignals(True)
        combo.clear()
        for option in state.options:
            combo.addItem(option)
        if state.selected_value:
            idx = combo.findText(state.selected_value)
            combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)

    def _apply_governance_editor_state(self, state) -> None:
        auth_index = max(0, self._governance_auth_mode.findText(state.auth_mode))
        self._governance_auth_mode.setCurrentIndex(auth_index)
        self._governance_note.setText(state.policy_note)
        self._tool_allow.setPlainText(state.tool_allow_text)
        self._tool_block.setPlainText(state.tool_block_text)
        self._endpoint_allow.setPlainText(state.endpoint_allow_text)
        self._endpoint_block.setPlainText(state.endpoint_block_text)
        self._governance_status.setText(state.status_text)

    def _apply_connector_editor_state(self, state) -> None:
        self._apply_selector(
            self._connector_id,
            build_selector_state(state.connector_ids, state.selected_connector_id),
        )
        self._connector_enabled.setChecked(state.enabled)
        self._connector_provider.blockSignals(True)
        self._connector_provider.clear()
        for option in state.provider_options:
            self._connector_provider.addItem(option.label, option.value)
        provider_idx = self._connector_provider.findData(state.selected_provider)
        self._connector_provider.setCurrentIndex(0 if provider_idx < 0 else provider_idx)
        self._connector_provider.blockSignals(False)
        self._connector_account.blockSignals(True)
        self._connector_account.clear()
        for option in state.account_options:
            self._connector_account.addItem(option.label, option.value)
        account_idx = self._connector_account.findData(state.selected_account)
        self._connector_account.setCurrentIndex(0 if account_idx < 0 else account_idx)
        self._connector_account.blockSignals(False)
        self._connector_action_allow.setPlainText(state.action_allow_text)
        self._connector_action_block.setPlainText(state.action_block_text)
        self._connector_endpoint_allow.setPlainText(state.endpoint_allow_text)
        self._connector_endpoint_block.setPlainText(state.endpoint_block_text)
        self._connector_note.setText(state.note)
        self._connector_status.setText(state.status_text)
        self._connector_validation.setText(state.validation_text)
        self._connector_history.setText(state.history_text)

    def _load_governance_editor(self, workspace_name: str) -> None:
        state = build_governance_editor_state(workspace_name, self._governance_by_name)
        self._apply_governance_editor_state(state)

    def _emit_governance_save(self) -> None:
        target = self._governance_workspace.currentText().strip()
        request, error = build_governance_save_request(
            target=target,
            policy=self._governance_by_name.get(target, {}),
            auth_mode=self._governance_auth_mode.currentText(),
            tool_allow_text=self._tool_allow.toPlainText(),
            tool_block_text=self._tool_block.toPlainText(),
            endpoint_allow_text=self._endpoint_allow.toPlainText(),
            endpoint_block_text=self._endpoint_block.toPlainText(),
            policy_note=self._governance_note.text(),
        )
        if request is None:
            self.set_governance_status(error, ok=False)
            return
        self.governance_save_requested.emit(request.as_payload())

    def _load_connector_binding_editor(self, _value: str) -> None:
        workspace_name = self._connector_workspace.currentText().strip()
        state = build_connector_binding_editor_state(
            workspace_name,
            self._connector_id.currentText().strip().lower(),
            self._connectors_by_name,
        )
        self._apply_connector_editor_state(state)

    def _refresh_connector_binding_feedback(self, *_args) -> None:
        workspace_name = self._connector_workspace.currentText().strip()
        connector_id = self._connector_id.currentText().strip().lower()
        connector_payload = self._connectors_by_name.get(workspace_name, {}).get(connector_id, {})
        validation_text, history_text = build_connector_binding_feedback(
            connector_payload,
            enabled=self._connector_enabled.isChecked(),
            selected_provider=str(self._connector_provider.currentData() or "").strip().lower(),
            selected_account=str(self._connector_account.currentData() or "").strip().lower(),
        )
        self._connector_validation.setText(validation_text)
        self._connector_history.setText(history_text)

    def _emit_connector_binding_save(self) -> None:
        request, error = build_connector_binding_save_request(
            workspace_name=self._connector_workspace.currentText(),
            connector_id=self._connector_id.currentText(),
            enabled=self._connector_enabled.isChecked(),
            account_id=str(self._connector_account.currentData() or ""),
            provider=str(self._connector_provider.currentData() or ""),
            action_allow_text=self._connector_action_allow.toPlainText(),
            action_block_text=self._connector_action_block.toPlainText(),
            endpoint_allow_text=self._connector_endpoint_allow.toPlainText(),
            endpoint_block_text=self._connector_endpoint_block.toPlainText(),
            note=self._connector_note.text(),
        )
        if request is None:
            self.set_connector_binding_status(error, ok=False)
            return
        self.connector_binding_save_requested.emit(request.as_payload())

    def set_persona_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._persona.currentData() or self._persona.currentText()).strip().lower()
        normalized = [(str(label).strip() or str(value).strip(), str(value).strip()) for label, value in options if str(value).strip()]
        if not normalized:
            normalized = [("Guppy", "guppy")]
        self._persona.blockSignals(True)
        self._persona.clear()
        for label, value in normalized:
            self._persona.addItem(label, value)
        index = 0
        for idx in range(self._persona.count()):
            if str(self._persona.itemData(idx) or "").strip().lower() == target:
                index = idx
                break
        self._persona.setCurrentIndex(index)
        self._persona.blockSignals(False)

    def set_voice_options(self, options: list[tuple[str, str]], selected: str | None = None) -> None:
        target = str(selected or self._voice.currentData() or self._voice.currentText()).strip().lower()
        normalized = [(str(label).strip() or str(value).strip(), str(value).strip()) for label, value in options if str(value).strip()]
        if not normalized:
            normalized = [("Default", "default")]
        self._voice.blockSignals(True)
        self._voice.clear()
        for label, value in normalized:
            self._voice.addItem(label, value)
        index = 0
        for idx in range(self._voice.count()):
            if str(self._voice.itemData(idx) or "").strip().lower() == target:
                index = idx
                break
        self._voice.setCurrentIndex(index)
        self._voice.blockSignals(False)

    def _sync_save_affordance(self) -> None:
        state = build_save_affordance_state(
            candidate_name=self._name.text(),
            known_names=self._known_names,
            configured=self._configured,
            max_configured=self._max_configured,
        )
        self._save_btn.setEnabled(state.enabled)
        if state.warning_text:
            self._status_lbl.setText(state.warning_text)
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )

    def set_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_governance_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._governance_status.setText(text)
        self._governance_status.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_connector_binding_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._connector_status.setText(text)
        self._connector_status.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def set_instances(self, payload: dict[str, object]) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        state = build_instance_manager_state(
            payload,
            previous_governance_workspace=self._governance_workspace.currentText().strip(),
            previous_connector_workspace=self._connector_workspace.currentText().strip(),
            previous_connector_id=self._connector_id.currentText().strip().lower(),
        )
        editors_state = build_workspace_editors_state(state)
        self._known_names = set(state.ordered_names)
        self._governance_by_name = state.governance_map
        self._connectors_by_name = state.connector_map
        self._apply_selector(self._governance_workspace, editors_state.governance_workspace)
        self._apply_governance_editor_state(editors_state.governance_editor)

        self._apply_selector(self._connector_workspace, editors_state.connector_workspace)
        self._apply_connector_editor_state(editors_state.connector_editor)

        self._configured = state.configured
        self._max_configured = state.max_configured
        self._active_runtime = state.active_runtime
        self._max_active_runtime = state.max_active_runtime
        self._summary_lbl.setText(state.summary_text)
        self._limits_lbl.setText(state.limits_text)
        self._role_mix_lbl.setText(state.role_mix_text)
        self._collab_lbl.setText(state.collaboration_text)
        self._recurring_lbl.setText(state.recurring_text)
        self._empty_state_lbl.setVisible(state.show_empty_state)
        if state.show_empty_state:
            empty_card = QLabel(
                state.empty_state_text
            )
            empty_card.setWordWrap(True)
            empty_card.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            empty_card.setStyleSheet(
                f"color: {T.DIM}; background-color: {T.BG1}; border: 1px dashed {T.BORDER};"
                f" padding: 14px; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
            )
            self._cards_layout.addWidget(empty_card)

        for item in state.items:
            card = _InstanceCard(item, str(item.get("name", "")).strip() == state.active_instance)
            card.activate_requested.connect(self.activate_requested.emit)
            card.delete_requested.connect(self.delete_requested.emit)
            card.logs_requested.connect(self.logs_requested.emit)
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()
        self._sync_save_affordance()

    def set_logs(self, instance_name: str, entries: list[dict[str, object]]) -> None:
        self._logs.setPlainText(build_workspace_activity_log_text(instance_name, entries))
