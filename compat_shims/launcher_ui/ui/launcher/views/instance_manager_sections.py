from __future__ import annotations

from dataclasses import dataclass

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
    build_workspace_create_copy,
    connector_history_line,
    workspace_recent_context,
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


def _button_style() -> str:
    return (
        f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px;"
        f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QPushButton:hover {{ border-color: {T.ACCENT_TEAL}; color: {T.ACCENT_TEAL}; }}"
    )


def _line_edit_style() -> str:
    return (
        f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
    )


def _combo_style() -> str:
    return (
        f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
    )


def _plain_text_style() -> str:
    return (
        f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER_SOFT}; border-radius: 4px; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
    )


class InstanceCard(QFrame):
    activate_requested = Signal(str)
    delete_requested = Signal(str)
    logs_requested = Signal(str)

    def __init__(self, payload: dict[str, object], active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = str(payload.get("name", "")).strip()
        self.setObjectName("instance_card")
        border = T.ACCENT_ORANGE if active else T.BORDER_SOFT
        self.setStyleSheet(f"QFrame#instance_card {{ background-color: {T.BG1}; border: 1px solid {border}; border-radius: 4px; }}")

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
        header.addWidget(_mono(status, T.STATUS_SUCCESS if status in {"ACTIVE", "RUNNING"} else T.DIM, T.FS_TINY, True))
        if active:
            header.addSpacing(8)
            header.addWidget(_mono("ACTIVE", T.ACCENT_ORANGE, T.FS_TINY, True))
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
        details.append(workspace_saved_context(payload))
        details.append(f"Return here for: {workspace_copy.reentry_hint}")
        details.append(workspace_recent_context(payload))
        for line in details:
            root.addWidget(_mono(line, T.DIM, T.FS_TINY))

        actions = QHBoxLayout()
        for label, signal in (("OPEN", self.activate_requested), ("LOGS", self.logs_requested), ("DELETE", self.delete_requested)):
            button = QPushButton(label)
            button.setStyleSheet(_button_style())
            button.clicked.connect(lambda _=False, name=self._name, emitter=signal: emitter.emit(name))
            if label == "DELETE" and active:
                button.setEnabled(False)
                button.setToolTip("Switch away before deleting the active instance.")
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)


@dataclass
class InstanceManagerShell:
    scroll: QScrollArea
    status_lbl: QLabel
    sections: QTabWidget
    overview_layout: QVBoxLayout
    create_layout: QVBoxLayout
    access_layout: QVBoxLayout
    connector_layout: QVBoxLayout
    activity_layout: QVBoxLayout
    preset_lbl: QLabel
    recipe_lbl: QLabel
    examples_lbl: QLabel
    name: QLineEdit
    description: QLineEdit
    mode: QComboBox
    persona: QComboBox
    voice: QComboBox
    type: QComboBox
    enabled: QCheckBox
    refresh_btn: QPushButton
    save_btn: QPushButton
    governance_toggle_btn: QPushButton
    connector_toggle_btn: QPushButton
    governance_frame: QFrame
    governance_workspace: QComboBox
    governance_auth_mode: QComboBox
    governance_note: QLineEdit
    tool_allow: QPlainTextEdit
    tool_block: QPlainTextEdit
    endpoint_allow: QPlainTextEdit
    endpoint_block: QPlainTextEdit
    governance_status: QLabel
    governance_save_btn: QPushButton
    connectors_frame: QFrame
    connector_workspace: QComboBox
    connector_id: QComboBox
    connector_enabled: QCheckBox
    connector_account: QComboBox
    connector_provider: QComboBox
    connector_action_allow: QPlainTextEdit
    connector_action_block: QPlainTextEdit
    connector_endpoint_allow: QPlainTextEdit
    connector_endpoint_block: QPlainTextEdit
    connector_note: QLineEdit
    connector_status: QLabel
    connector_validation: QLabel
    connector_history: QLabel
    connector_save_btn: QPushButton
    summary_lbl: QLabel
    role_mix_lbl: QLabel
    collab_lbl: QLabel
    recurring_lbl: QLabel
    empty_state_lbl: QLabel
    limits_lbl: QLabel
    cards_host: QWidget
    cards_layout: QVBoxLayout
    logs: QPlainTextEdit


def build_instance_manager_shell() -> InstanceManagerShell:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(28, 22, 28, 22)
    layout.setSpacing(16)

    title = QLabel("Workspaces")
    title.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;")
    layout.addWidget(title)
    status_lbl = _mono("Ready to review saved workspaces, defaults, and workspace memory.", T.DIM, T.FS_TINY)
    layout.addWidget(status_lbl)

    sections = QTabWidget()
    sections.setDocumentMode(True)
    sections.setStyleSheet(
        f"QTabWidget::pane {{ border: 1px solid {T.BORDER}; background: rgba(255,255,255,0.42); }}"
        f"QTabBar::tab {{ background: rgba(255,255,255,0.86); color: {T.DIM}; border: 1px solid {T.BORDER};"
        f" padding: 4px 8px; margin-right: 4px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
        f"QTabBar::tab:selected {{ color: {T.INK}; border-color: {T.PRIMARY}; background: rgba(242,202,80,0.14); }}"
    )
    overview_tab = QWidget()
    overview_layout = QVBoxLayout(overview_tab)
    overview_layout.setContentsMargins(10, 10, 10, 10)
    overview_layout.setSpacing(10)
    create_tab = QWidget()
    create_layout = QVBoxLayout(create_tab)
    create_layout.setContentsMargins(10, 10, 10, 10)
    create_layout.setSpacing(10)
    access_tab = QWidget()
    access_layout = QVBoxLayout(access_tab)
    access_layout.setContentsMargins(10, 10, 10, 10)
    access_layout.setSpacing(10)
    connector_tab = QWidget()
    connector_layout = QVBoxLayout(connector_tab)
    connector_layout.setContentsMargins(10, 10, 10, 10)
    connector_layout.setSpacing(10)
    activity_tab = QWidget()
    activity_layout = QVBoxLayout(activity_tab)
    activity_layout.setContentsMargins(10, 10, 10, 10)
    activity_layout.setSpacing(10)
    sections.addTab(overview_tab, "Overview")
    sections.addTab(create_tab, "Create")
    sections.addTab(access_tab, "Access")
    sections.addTab(connector_tab, "Connectors")
    sections.addTab(activity_tab, "Activity")
    layout.addWidget(sections)

    form = QFrame()
    form.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    form_layout = QVBoxLayout(form)
    form_layout.setContentsMargins(14, 12, 14, 12)
    form_layout.setSpacing(8)
    form_layout.addWidget(_mono("WORKSPACE SETUP", T.PRIMARY, T.FS_TINY, True))
    preset_lbl = _mono("Preset: daily workspace defaults are ready.", T.DIM, T.FS_TINY)
    preset_lbl.setWordWrap(True)
    form_layout.addWidget(preset_lbl)
    recipe_lbl = _mono("First run: use MORNING BRIEF to get the workspace moving.", T.DIM, T.FS_TINY)
    recipe_lbl.setWordWrap(True)
    form_layout.addWidget(recipe_lbl)
    examples_lbl = _mono(build_workspace_create_copy("user_instance").example_names, T.DIM, T.FS_TINY)
    examples_lbl.setWordWrap(True)
    form_layout.addWidget(examples_lbl)

    row1 = QHBoxLayout()
    name = QLineEdit()
    name.setPlaceholderText("research-desk")
    description = QLineEdit()
    description.setPlaceholderText("What this workspace helps with")
    for widget in (name, description):
        widget.setStyleSheet(_line_edit_style())
    row1.addWidget(name)
    row1.addWidget(description, stretch=1)
    form_layout.addLayout(row1)

    row2 = QHBoxLayout()
    mode = QComboBox()
    mode.addItems(["auto", "claude", "ollama", "local", "code", "teaching"])
    persona = QComboBox()
    persona.addItems(["guppy"])
    voice = QComboBox()
    voice.addItems(["default", "kokoro", "system"])
    workspace_type = QComboBox()
    workspace_type.addItems(["user_instance", "builder_instance", "read_only_instance", "admin_instance"])
    for combo in (mode, persona, voice, workspace_type):
        combo.setStyleSheet(_combo_style())
        row2.addWidget(combo)
    form_layout.addLayout(row2)

    row3 = QHBoxLayout()
    enabled = QCheckBox("Enabled")
    enabled.setChecked(True)
    enabled.setStyleSheet(f"QCheckBox {{ color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; }}")
    save_btn = QPushButton("SAVE WORKSPACE")
    refresh_btn = QPushButton("REFRESH")
    for button in (save_btn, refresh_btn):
        button.setStyleSheet(_button_style())
    row3.addWidget(enabled)
    row3.addStretch()
    row3.addWidget(refresh_btn)
    row3.addWidget(save_btn)
    form_layout.addLayout(row3)
    layout.addWidget(form)

    governance_toggle_btn = QPushButton("SHOW ACCESS RULES")
    connector_toggle_btn = QPushButton("SHOW CONNECTOR RULES")
    for button in (governance_toggle_btn, connector_toggle_btn):
        button.setStyleSheet(_button_style())

    governance_frame = QFrame()
    governance_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    governance_layout = QVBoxLayout(governance_frame)
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
    governance_workspace = QComboBox()
    governance_auth_mode = QComboBox()
    governance_auth_mode.addItems(["runtime_default", "workspace_token_required", "local_only", "disabled"])
    for combo in (governance_workspace, governance_auth_mode):
        combo.setStyleSheet(_combo_style())
    gov_row1.addWidget(governance_workspace, stretch=1)
    gov_row1.addWidget(governance_auth_mode, stretch=1)
    governance_layout.addLayout(gov_row1)

    governance_note = QLineEdit()
    governance_note.setPlaceholderText("Short note shown when something is blocked in this workspace")
    governance_note.setStyleSheet(_line_edit_style())
    governance_layout.addWidget(governance_note)

    gov_row2 = QHBoxLayout()
    gov_row3 = QHBoxLayout()
    tool_allow = QPlainTextEdit()
    tool_block = QPlainTextEdit()
    endpoint_allow = QPlainTextEdit()
    endpoint_block = QPlainTextEdit()
    for editor, placeholder in (
        (tool_allow, "tool allow list\none tool per line"),
        (tool_block, "tool block list\none tool per line"),
        (endpoint_allow, "endpoint allow filters\none pattern per line"),
        (endpoint_block, "endpoint block filters\none pattern per line"),
    ):
        editor.setPlaceholderText(placeholder)
        editor.setMinimumHeight(88)
        editor.setStyleSheet(_plain_text_style())
    gov_row2.addWidget(tool_allow)
    gov_row2.addWidget(tool_block)
    gov_row3.addWidget(endpoint_allow)
    gov_row3.addWidget(endpoint_block)
    governance_layout.addLayout(gov_row2)
    governance_layout.addLayout(gov_row3)

    governance_status = _mono("Access settings ready.", T.DIM, T.FS_TINY)
    governance_status.setWordWrap(True)
    governance_layout.addWidget(governance_status)
    gov_actions = QHBoxLayout()
    gov_actions.addStretch()
    governance_save_btn = QPushButton("SAVE ACCESS")
    governance_save_btn.setStyleSheet(_button_style())
    gov_actions.addWidget(governance_save_btn)
    governance_layout.addLayout(gov_actions)
    governance_frame.setVisible(False)
    layout.addWidget(governance_frame)

    connectors_frame = QFrame()
    connectors_frame.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
    connectors_layout = QVBoxLayout(connectors_frame)
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
    connector_workspace = QComboBox()
    connector_id = QComboBox()
    for combo in (connector_workspace, connector_id):
        combo.setStyleSheet(_combo_style())
    connector_row1.addWidget(connector_workspace, stretch=1)
    connector_row1.addWidget(connector_id, stretch=1)
    connectors_layout.addLayout(connector_row1)

    connector_row2 = QHBoxLayout()
    connector_enabled = QCheckBox("Bound to this workspace")
    connector_enabled.setStyleSheet(
        f"QCheckBox {{ color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; }}"
    )
    connector_account = QComboBox()
    connector_provider = QComboBox()
    for widget in (connector_account, connector_provider):
        widget.setStyleSheet(_combo_style())
    connector_row2.addWidget(connector_enabled)
    connector_row2.addWidget(connector_account, stretch=1)
    connector_row2.addWidget(connector_provider, stretch=1)
    connectors_layout.addLayout(connector_row2)

    connector_row3 = QHBoxLayout()
    connector_action_allow = QPlainTextEdit()
    connector_action_block = QPlainTextEdit()
    connector_endpoint_allow = QPlainTextEdit()
    connector_endpoint_block = QPlainTextEdit()
    for editor, placeholder in (
        (connector_action_allow, "action allow list\none action per line"),
        (connector_action_block, "action block list\none action per line"),
        (connector_endpoint_allow, "connector endpoint allow filters\none pattern per line"),
        (connector_endpoint_block, "connector endpoint block filters\none pattern per line"),
    ):
        editor.setPlaceholderText(placeholder)
        editor.setMinimumHeight(88)
        editor.setStyleSheet(_plain_text_style())
    connector_row3.addWidget(connector_action_allow)
    connector_row3.addWidget(connector_action_block)
    connectors_layout.addLayout(connector_row3)

    connector_row4 = QHBoxLayout()
    connector_row4.addWidget(connector_endpoint_allow)
    connector_row4.addWidget(connector_endpoint_block)
    connectors_layout.addLayout(connector_row4)

    connector_note = QLineEdit()
    connector_note.setPlaceholderText("Operator-visible connector note for this workspace")
    connector_note.setStyleSheet(_line_edit_style())
    connectors_layout.addWidget(connector_note)

    connector_status = _mono("Connector binding editor ready", T.DIM, T.FS_TINY)
    connector_status.setWordWrap(True)
    connectors_layout.addWidget(connector_status)
    connector_validation = _mono("Binding validation will appear here after connector data loads.", T.DIM, T.FS_TINY)
    connector_validation.setWordWrap(True)
    connectors_layout.addWidget(connector_validation)
    connector_history = _mono("Connector history will appear here after verify/connect activity runs.", T.DIM, T.FS_TINY)
    connector_history.setWordWrap(True)
    connectors_layout.addWidget(connector_history)

    connector_actions = QHBoxLayout()
    connector_actions.addStretch()
    connector_save_btn = QPushButton("SAVE CONNECTOR BINDING")
    connector_save_btn.setStyleSheet(_button_style())
    connector_actions.addWidget(connector_save_btn)
    connectors_layout.addLayout(connector_actions)
    connectors_frame.setVisible(False)
    layout.addWidget(connectors_frame)

    summary_lbl = _mono("No workspace data loaded", T.DIM, T.FS_TINY)
    role_mix_lbl = _mono("Role mix: Daily 0 | Builder 0 | Reference 0 | Ops 0", T.DIM, T.FS_TINY)
    collab_lbl = _mono("Collaboration cues appear here once workspaces load.", T.DIM, T.FS_TINY)
    collab_lbl.setWordWrap(True)
    recurring_lbl = _mono("Recurring context cues appear here once workspaces load.", T.DIM, T.FS_TINY)
    recurring_lbl.setWordWrap(True)
    empty_state_lbl = _mono(
        "Create a workspace to get started: Daily for recurring help, Builder for review loops, Reference for safe source checks, or Ops for recovery work.",
        T.DIM,
        T.FS_TINY,
    )
    empty_state_lbl.setWordWrap(True)
    limits_lbl = _mono("Configured workspaces: 0 / 5 | Live workspaces: 0 / 2", T.DIM, T.FS_TINY)

    cards_host = QWidget()
    cards_layout = QVBoxLayout(cards_host)
    cards_layout.setContentsMargins(0, 0, 0, 0)
    cards_layout.setSpacing(12)

    logs_frame = QFrame()
    logs_frame.setStyleSheet(f"QFrame {{ background: {T.BG0}; border: 1px solid {T.BORDER}; }}")
    logs_layout = QVBoxLayout(logs_frame)
    logs_layout.setContentsMargins(12, 10, 12, 10)
    logs_layout.setSpacing(6)
    logs_layout.addWidget(_mono("WORKSPACE ACTIVITY", T.PRIMARY, T.FS_TINY, True))
    logs = QPlainTextEdit()
    logs.setReadOnly(True)
    logs.setMinimumHeight(180)
    logs.setStyleSheet(
        f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
        f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
    )
    logs_layout.addWidget(logs)

    for widget in (limits_lbl, summary_lbl, role_mix_lbl, collab_lbl, recurring_lbl, empty_state_lbl, cards_host):
        overview_layout.addWidget(widget)
    overview_layout.addStretch()

    create_layout.addWidget(form)
    create_layout.addStretch()

    access_btn_row = QHBoxLayout()
    access_btn_row.addWidget(governance_toggle_btn)
    access_btn_row.addStretch()
    access_layout.addLayout(access_btn_row)
    access_layout.addWidget(governance_frame)
    access_layout.addStretch()

    conn_btn_row = QHBoxLayout()
    conn_btn_row.addWidget(connector_toggle_btn)
    conn_btn_row.addStretch()
    connector_layout.addLayout(conn_btn_row)
    connector_layout.addWidget(connectors_frame)
    connector_layout.addStretch()

    activity_layout.addWidget(logs_frame)
    activity_layout.addStretch()

    layout.addStretch()
    scroll.setWidget(content)

    return InstanceManagerShell(
        scroll=scroll,
        status_lbl=status_lbl,
        sections=sections,
        overview_layout=overview_layout,
        create_layout=create_layout,
        access_layout=access_layout,
        connector_layout=connector_layout,
        activity_layout=activity_layout,
        preset_lbl=preset_lbl,
        recipe_lbl=recipe_lbl,
        examples_lbl=examples_lbl,
        name=name,
        description=description,
        mode=mode,
        persona=persona,
        voice=voice,
        type=workspace_type,
        enabled=enabled,
        refresh_btn=refresh_btn,
        save_btn=save_btn,
        governance_toggle_btn=governance_toggle_btn,
        connector_toggle_btn=connector_toggle_btn,
        governance_frame=governance_frame,
        governance_workspace=governance_workspace,
        governance_auth_mode=governance_auth_mode,
        governance_note=governance_note,
        tool_allow=tool_allow,
        tool_block=tool_block,
        endpoint_allow=endpoint_allow,
        endpoint_block=endpoint_block,
        governance_status=governance_status,
        governance_save_btn=governance_save_btn,
        connectors_frame=connectors_frame,
        connector_workspace=connector_workspace,
        connector_id=connector_id,
        connector_enabled=connector_enabled,
        connector_account=connector_account,
        connector_provider=connector_provider,
        connector_action_allow=connector_action_allow,
        connector_action_block=connector_action_block,
        connector_endpoint_allow=connector_endpoint_allow,
        connector_endpoint_block=connector_endpoint_block,
        connector_note=connector_note,
        connector_status=connector_status,
        connector_validation=connector_validation,
        connector_history=connector_history,
        connector_save_btn=connector_save_btn,
        summary_lbl=summary_lbl,
        role_mix_lbl=role_mix_lbl,
        collab_lbl=collab_lbl,
        recurring_lbl=recurring_lbl,
        empty_state_lbl=empty_state_lbl,
        limits_lbl=limits_lbl,
        cards_host=cards_host,
        cards_layout=cards_layout,
        logs=logs,
    )
