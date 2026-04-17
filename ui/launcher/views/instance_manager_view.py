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
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.instance_manager_presenter import (
    build_connector_binding_editor_state,
    build_connector_binding_feedback,
    build_governance_editor_state,
    build_instance_manager_state,
    connector_history_line,
    parse_policy_lines,
    role_preset,
    selector_label,
    workspace_collaboration_hint,
    workspace_default_purpose,
    workspace_example_names,
    workspace_first_run_recipe,
    workspace_recent_context,
    workspace_reentry_hint,
    workspace_role_label,
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


def _workspace_role_label(workspace_type: str) -> str:
    return workspace_role_label(workspace_type)


def _workspace_default_purpose(workspace_type: str) -> str:
    return workspace_default_purpose(workspace_type)


def _workspace_collaboration_hint(workspace_type: str) -> str:
    return workspace_collaboration_hint(workspace_type)


def _workspace_reentry_hint(workspace_type: str) -> str:
    return workspace_reentry_hint(workspace_type)


def _workspace_first_run_recipe(workspace_type: str) -> str:
    return workspace_first_run_recipe(workspace_type)


def _workspace_example_names(workspace_type: str) -> str:
    return workspace_example_names(workspace_type)


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
        header.addSpacing(8)
        header.addWidget(_mono(_workspace_role_label(workspace_type).upper(), T.DIM, T.FS_TINY, True))
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
            f"Role: {_workspace_role_label(workspace_type)}",
        ]
        description = str(payload.get("description", "")).strip()
        details.append(f"Purpose: {description or _workspace_default_purpose(workspace_type)}")
        details.append(f"Fit: {_workspace_collaboration_hint(workspace_type)}")
        details.append(_workspace_first_run_recipe(workspace_type))
        details.append(_workspace_saved_context(payload))
        details.append(f"Return here for: {_workspace_reentry_hint(workspace_type)}")
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
        self._last_role_preset_type = "user_instance"
        self._governance_visible = False
        self._connector_bindings_visible = False

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
        layout.addWidget(
            _mono(
                "Choose the right workspace for the task. Workspaces keep purpose, persona, voice, and recent context together.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        guide = _mono(
            "Daily = everyday help | Builder = review and planning | Read-only = safe reference | Ops = recovery and diagnostics",
            T.DIM,
            T.FS_TINY,
        )
        guide.setWordWrap(True)
        layout.addWidget(guide)

        self._status_lbl = _mono("Ready to review and edit saved workspaces.", T.DIM, T.FS_TINY)
        layout.addWidget(self._status_lbl)

        form = QFrame()
        form.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(8)
        form_layout.addWidget(_mono("WORKSPACE DETAILS", T.PRIMARY, T.FS_TINY, True))
        self._preset_lbl = _mono("Preset: daily workspace defaults are ready.", T.DIM, T.FS_TINY)
        self._preset_lbl.setWordWrap(True)
        form_layout.addWidget(self._preset_lbl)
        self._recipe_lbl = _mono("First run: use MORNING BRIEF to get the workspace moving.", T.DIM, T.FS_TINY)
        self._recipe_lbl.setWordWrap(True)
        form_layout.addWidget(self._recipe_lbl)
        self._examples_lbl = _mono(_workspace_example_names("user_instance"), T.DIM, T.FS_TINY)
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
        layout.addLayout(collapse_row)

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
        self.create_requested.emit(
            {
                "name": self._name.text().strip(),
                "description": self._description.text().strip(),
                "mode": self._mode.currentText().strip(),
                "persona": str(self._persona.currentData() or self._persona.currentText()).strip(),
                "voice": str(self._voice.currentData() or self._voice.currentText()).strip(),
                "type": self._type.currentText().strip(),
                "enabled": self._enabled.isChecked(),
            }
        )

    def _toggle_governance_section(self) -> None:
        self._governance_visible = not self._governance_visible
        self._governance_frame.setVisible(self._governance_visible)
        self._governance_toggle_btn.setText("HIDE ACCESS RULES" if self._governance_visible else "SHOW ACCESS RULES")

    def _toggle_connector_bindings_section(self) -> None:
        self._connector_bindings_visible = not self._connector_bindings_visible
        self._connectors_frame.setVisible(self._connector_bindings_visible)
        self._connector_toggle_btn.setText(
            "HIDE CONNECTOR RULES" if self._connector_bindings_visible else "SHOW CONNECTOR RULES"
        )

    @staticmethod
    def _parse_policy_lines(text: str) -> list[str]:
        return parse_policy_lines(text)

    @staticmethod
    def _selector_label(item: dict[str, object], *, fallback: str) -> str:
        return selector_label(item, fallback=fallback)

    @staticmethod
    def _history_line(payload: dict[str, object]) -> str:
        return connector_history_line(payload)

    @staticmethod
    def _role_preset(workspace_type: str) -> dict[str, str]:
        preset = role_preset(workspace_type)
        return {
            "name_placeholder": preset.name_placeholder,
            "description_placeholder": preset.description_placeholder,
            "mode": preset.mode,
            "summary": preset.summary,
            "recipe": preset.recipe,
        }

    def _apply_role_preset(self, workspace_type: str) -> None:
        preset = self._role_preset(workspace_type)
        previous_preset = self._role_preset(self._last_role_preset_type)
        self._name.setPlaceholderText(preset["name_placeholder"])
        self._description.setPlaceholderText(preset["description_placeholder"])
        self._preset_lbl.setText(preset["summary"])
        self._recipe_lbl.setText(preset.get("recipe", _workspace_first_run_recipe(workspace_type)))
        self._examples_lbl.setText(_workspace_example_names(workspace_type))
        current_description = self._description.text().strip()
        if not current_description or current_description == previous_preset["description_placeholder"]:
            self._description.setText(preset["description_placeholder"])
        current_mode = self._mode.currentText().strip().lower()
        if not current_mode or current_mode == previous_preset["mode"]:
            idx = self._mode.findText(preset["mode"])
            if idx >= 0:
                self._mode.setCurrentIndex(idx)
        self._last_role_preset_type = (workspace_type or "user_instance").strip().lower() or "user_instance"

    def _load_governance_editor(self, workspace_name: str) -> None:
        state = build_governance_editor_state(workspace_name, self._governance_by_name)
        auth_index = max(0, self._governance_auth_mode.findText(state.auth_mode))
        self._governance_auth_mode.setCurrentIndex(auth_index)
        self._governance_note.setText(state.policy_note)
        self._tool_allow.setPlainText(state.tool_allow_text)
        self._tool_block.setPlainText(state.tool_block_text)
        self._endpoint_allow.setPlainText(state.endpoint_allow_text)
        self._endpoint_block.setPlainText(state.endpoint_block_text)
        self._governance_status.setText(state.status_text)

    def _emit_governance_save(self) -> None:
        target = self._governance_workspace.currentText().strip()
        if not target:
            self.set_governance_status("Choose a workspace before saving governance.", ok=False)
            return
        policy = self._governance_by_name.get(target, {})
        self.governance_save_requested.emit(
            {
                "name": target,
                "instance_type": str(policy.get("instance_type", "user_instance") or "user_instance"),
                "auth_mode": self._governance_auth_mode.currentText().strip(),
                "tool_allow": self._parse_policy_lines(self._tool_allow.toPlainText()),
                "tool_block": self._parse_policy_lines(self._tool_block.toPlainText()),
                "endpoint_allow": self._parse_policy_lines(self._endpoint_allow.toPlainText()),
                "endpoint_block": self._parse_policy_lines(self._endpoint_block.toPlainText()),
                "policy_note": self._governance_note.text().strip(),
            }
        )

    def _load_connector_binding_editor(self, _value: str) -> None:
        workspace_name = self._connector_workspace.currentText().strip()
        state = build_connector_binding_editor_state(
            workspace_name,
            self._connector_id.currentText().strip().lower(),
            self._connectors_by_name,
        )
        self._connector_id.blockSignals(True)
        self._connector_id.clear()
        for connector_id in state.connector_ids:
            self._connector_id.addItem(connector_id)
        idx = self._connector_id.findText(state.selected_connector_id)
        self._connector_id.setCurrentIndex(max(0, idx))
        self._connector_id.blockSignals(False)
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
        workspace_name = self._connector_workspace.currentText().strip()
        connector_id = self._connector_id.currentText().strip().lower()
        if not workspace_name or not connector_id:
            self.set_connector_binding_status("Choose a workspace and connector before saving.", ok=False)
            return
        self.connector_binding_save_requested.emit(
            {
                "name": workspace_name,
                "connector": connector_id,
                "enabled": self._connector_enabled.isChecked(),
                "account_id": str(self._connector_account.currentData() or "").strip().lower(),
                "provider": str(self._connector_provider.currentData() or "").strip().lower(),
                "action_allow": self._parse_policy_lines(self._connector_action_allow.toPlainText()),
                "action_block": self._parse_policy_lines(self._connector_action_block.toPlainText()),
                "endpoint_allow": self._parse_policy_lines(self._connector_endpoint_allow.toPlainText()),
                "endpoint_block": self._parse_policy_lines(self._connector_endpoint_block.toPlainText()),
                "note": self._connector_note.text().strip(),
            }
        )

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
        candidate = self._name.text().strip()
        is_new_name = bool(candidate) and candidate not in self._known_names
        at_limit = self._configured >= self._max_configured
        self._save_btn.setEnabled(not (at_limit and is_new_name))
        if at_limit and is_new_name:
            self._status_lbl.setText("Workspace limit reached (5 / 5). Update an existing workspace or delete one first.")
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
        self._known_names = set(state.ordered_names)
        self._governance_by_name = state.governance_map
        self._connectors_by_name = state.connector_map
        self._governance_workspace.blockSignals(True)
        self._governance_workspace.clear()
        for name in state.ordered_names:
            self._governance_workspace.addItem(name)
        if state.governance_target:
            idx = self._governance_workspace.findText(state.governance_target)
            self._governance_workspace.setCurrentIndex(max(0, idx))
        self._governance_workspace.blockSignals(False)
        self._load_governance_editor(self._governance_workspace.currentText())

        self._connector_workspace.blockSignals(True)
        self._connector_workspace.clear()
        for name in state.ordered_names:
            self._connector_workspace.addItem(name)
        if state.connector_target_workspace:
            idx = self._connector_workspace.findText(state.connector_target_workspace)
            self._connector_workspace.setCurrentIndex(max(0, idx))
        self._connector_workspace.blockSignals(False)
        self._connector_id.blockSignals(True)
        self._connector_id.clear()
        for connector_id in state.connector_ids:
            self._connector_id.addItem(connector_id)
        connector_idx = self._connector_id.findText(state.connector_target_id)
        self._connector_id.setCurrentIndex(max(0, connector_idx))
        self._connector_id.blockSignals(False)
        self._load_connector_binding_editor("")

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
        lines: list[str] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            timestamp = str(item.get("timestamp", "")).replace("T", " ").replace("+00:00", "Z")
            role = str(item.get("role", "event")).upper()
            message = str(item.get("message", item.get("response", ""))).strip()
            if message:
                lines.append(f"[{timestamp}] {role}: {message}")
        self._logs.setPlainText(
            "\n".join(lines) if lines else f"No recent conversation or ops activity yet for workspace {instance_name}"
        )
