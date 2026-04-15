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

from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label


def _workspace_role_label(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "Daily assistant",
        "builder_instance": "Builder collaborator",
        "read_only_instance": "Read-only reference",
        "admin_instance": "Operations workspace",
    }.get(key, key.replace("_", " ").strip().title() or "Workspace")


def _workspace_default_purpose(workspace_type: str) -> str:
    key = (workspace_type or "user_instance").strip().lower()
    return {
        "user_instance": "General help, recurring work, and quick tasks.",
        "builder_instance": "Planning, reviews, and low-risk builder collaboration.",
        "read_only_instance": "Safe research, source review, and reference work without writes.",
        "admin_instance": "Recovery, diagnostics, and guarded changes.",
    }.get(key, "Task-focused context for this workspace.")


def _workspace_role_summary(items: list[dict[str, object]]) -> str:
    counts = {
        "daily": 0,
        "builder": 0,
        "reference": 0,
        "ops": 0,
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("type", "user_instance") or "user_instance").strip().lower()
        if key == "builder_instance":
            counts["builder"] += 1
        elif key == "read_only_instance":
            counts["reference"] += 1
        elif key == "admin_instance":
            counts["ops"] += 1
        else:
            counts["daily"] += 1
    return (
        f"Daily {counts['daily']} | Builder {counts['builder']} | "
        f"Reference {counts['reference']} | Ops {counts['ops']}"
    )


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
        collaboration_hint = {
            "user_instance": "Best for recurring daily work and live conversation.",
            "builder_instance": "Best for reviews, plans, and low-risk builder collaboration.",
            "read_only_instance": "Best for source checking and safe reference work.",
            "admin_instance": "Best for recovery, diagnostics, and guarded operational steps.",
        }.get(workspace_type, "Best for focused work in its saved context.")
        details.append(f"Fit: {collaboration_hint}")
        last_message = str(payload.get("last_message", "")).strip()
        if last_message:
            details.append(f"Recent: {last_message[:120]}")
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

        self._status_lbl = _mono("Workspace manager ready", T.DIM, T.FS_TINY)
        layout.addWidget(self._status_lbl)

        form = QFrame()
        form.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(8)
        form_layout.addWidget(_mono("SAVE WORKSPACE DETAILS", T.PRIMARY, T.FS_TINY, True))

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

        governance = QFrame()
        governance.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        governance_layout = QVBoxLayout(governance)
        governance_layout.setContentsMargins(14, 12, 14, 12)
        governance_layout.setSpacing(8)
        governance_layout.addWidget(_mono("WORKSPACE GOVERNANCE", T.PRIMARY, T.FS_TINY, True))
        governance_hint = _mono(
            "Edit workspace auth mode, tool allow/block lists, endpoint filters, and the operator note without touching config files.",
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
        self._governance_note.setPlaceholderText("Operator-visible policy note for this workspace")
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

        self._governance_status = _mono("Governance editor ready", T.DIM, T.FS_TINY)
        self._governance_status.setWordWrap(True)
        governance_layout.addWidget(self._governance_status)

        gov_actions = QHBoxLayout()
        gov_actions.addStretch()
        self._governance_save_btn = QPushButton("SAVE GOVERNANCE")
        self._governance_save_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        gov_actions.addWidget(self._governance_save_btn)
        governance_layout.addLayout(gov_actions)
        layout.addWidget(governance)

        connectors = QFrame()
        connectors.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        connectors_layout = QVBoxLayout(connectors)
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
        self._connector_account = QLineEdit()
        self._connector_account.setPlaceholderText("account id (for example: main)")
        self._connector_provider = QLineEdit()
        self._connector_provider.setPlaceholderText("provider (for example: hubspot)")
        for widget in (self._connector_account, self._connector_provider):
            widget.setStyleSheet(
                f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
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
        layout.addWidget(connectors)

        self._summary_lbl = _mono("No workspace data loaded", T.DIM, T.FS_TINY)
        layout.addWidget(self._summary_lbl)
        self._role_mix_lbl = _mono("Role mix: Daily 0 | Builder 0 | Reference 0 | Ops 0", T.DIM, T.FS_TINY)
        self._collab_lbl = _mono("Collaboration cues appear here once workspaces load.", T.DIM, T.FS_TINY)
        self._collab_lbl.setWordWrap(True)
        self._limits_lbl = _mono("Configured workspaces: 0 / 5 | Live workspaces: 0 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._limits_lbl)
        layout.addWidget(self._role_mix_lbl)
        layout.addWidget(self._collab_lbl)

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
        self._governance_workspace.currentTextChanged.connect(self._load_governance_editor)
        self._connector_workspace.currentTextChanged.connect(self._load_connector_binding_editor)
        self._connector_id.currentTextChanged.connect(self._load_connector_binding_editor)
        self._governance_save_btn.clicked.connect(self._emit_governance_save)
        self._connector_save_btn.clicked.connect(self._emit_connector_binding_save)
        self._save_btn = save_btn
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

    @staticmethod
    def _parse_policy_lines(text: str) -> list[str]:
        seen: set[str] = set()
        lines: list[str] = []
        for raw in str(text or "").splitlines():
            value = raw.strip()
            if not value:
                continue
            lowered = value.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            lines.append(lowered)
        return lines

    def _load_governance_editor(self, workspace_name: str) -> None:
        target = str(workspace_name or "").strip()
        policy = self._governance_by_name.get(target, {})
        auth_mode = str(policy.get("auth_mode", "runtime_default") or "runtime_default")
        auth_index = max(0, self._governance_auth_mode.findText(auth_mode))
        self._governance_auth_mode.setCurrentIndex(auth_index)
        self._governance_note.setText(str(policy.get("policy_note", "") or ""))
        self._tool_allow.setPlainText("\n".join(str(item) for item in policy.get("tool_allow", []) if str(item).strip()))
        self._tool_block.setPlainText("\n".join(str(item) for item in policy.get("tool_block", []) if str(item).strip()))
        self._endpoint_allow.setPlainText("\n".join(str(item) for item in policy.get("endpoint_allow", []) if str(item).strip()))
        self._endpoint_block.setPlainText("\n".join(str(item) for item in policy.get("endpoint_block", []) if str(item).strip()))
        capabilities = policy.get("capabilities", {}) if isinstance(policy.get("capabilities"), dict) else {}
        self._governance_status.setText(
            f"Editing {target or 'workspace'} | auth mode={auth_mode} | "
            f"caps r/w/x/n={int(bool(capabilities.get('read', False)))}/{int(bool(capabilities.get('write', False)))}/"
            f"{int(bool(capabilities.get('execute', False)))}/{int(bool(capabilities.get('network', False)))}"
        )

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
        connector_map = self._connectors_by_name.get(workspace_name, {})
        current_connector = self._connector_id.currentText().strip().lower()
        connector_ids = list(connector_map.keys()) or ["gmail", "calendar", "spotify", "youtube", "crm", "voip"]
        self._connector_id.blockSignals(True)
        self._connector_id.clear()
        for connector_id in connector_ids:
            self._connector_id.addItem(connector_id)
        idx = self._connector_id.findText(current_connector)
        self._connector_id.setCurrentIndex(max(0, idx))
        self._connector_id.blockSignals(False)
        connector_id = self._connector_id.currentText().strip().lower()
        connector_payload = connector_map.get(connector_id, {})
        binding = connector_payload.get("binding", {}) if isinstance(connector_payload.get("binding"), dict) else {}
        self._connector_enabled.setChecked(bool(binding.get("enabled", False)))
        self._connector_account.setText(str(binding.get("account_id", "") or ""))
        self._connector_provider.setText(str(binding.get("provider", "") or ""))
        self._connector_action_allow.setPlainText(
            "\n".join(str(item) for item in binding.get("action_allow", []) if str(item).strip())
        )
        self._connector_action_block.setPlainText(
            "\n".join(str(item) for item in binding.get("action_block", []) if str(item).strip())
        )
        self._connector_endpoint_allow.setPlainText(
            "\n".join(str(item) for item in binding.get("endpoint_allow", []) if str(item).strip())
        )
        self._connector_endpoint_block.setPlainText(
            "\n".join(str(item) for item in binding.get("endpoint_block", []) if str(item).strip())
        )
        self._connector_note.setText(str(binding.get("note", "") or ""))
        auth_state = str(connector_payload.get("auth_state", "unknown") or "unknown")
        auth_mode = str(connector_payload.get("workspace_auth_mode", "runtime_default") or "runtime_default")
        source = str(connector_payload.get("source", "none") or "none")
        self._connector_status.setText(
            f"Editing {workspace_name or 'workspace'} / {connector_id or 'connector'} | auth={auth_state} | "
            f"source={source} | workspace auth mode={auth_mode}"
        )

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
                "account_id": self._connector_account.text().strip().lower(),
                "provider": self._connector_provider.text().strip().lower(),
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

        instances = payload.get("instances", []) if isinstance(payload, dict) else []
        active_instance = str(payload.get("active_instance", "")).strip() if isinstance(payload, dict) else ""
        warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
        items = instances if isinstance(instances, list) else []
        ordered_names = [
            str(item.get("name", "")).strip()
            for item in items
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]
        self._known_names = set(ordered_names)
        previous_target = self._governance_workspace.currentText().strip()
        previous_connector_workspace = self._connector_workspace.currentText().strip()
        previous_connector_id = self._connector_id.currentText().strip().lower()
        governance_map: dict[str, dict[str, object]] = {}
        connector_map: dict[str, dict[str, dict[str, object]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            governance = item.get("governance", {}) if isinstance(item.get("governance"), dict) else {}
            governance_map[name] = {
                **governance,
                "instance_type": str(item.get("type", "user_instance") or "user_instance"),
            }
            connector_rows = item.get("connectors", []) if isinstance(item.get("connectors"), list) else []
            workspace_auth_mode = str(governance.get("auth_mode", "runtime_default") or "runtime_default")
            connector_map[name] = {
                str(row.get("id", "")).strip().lower(): {
                    **row,
                    "workspace_auth_mode": workspace_auth_mode,
                }
                for row in connector_rows
                if isinstance(row, dict) and str(row.get("id", "")).strip()
            }
        self._governance_by_name = governance_map
        self._connectors_by_name = connector_map
        self._governance_workspace.blockSignals(True)
        self._governance_workspace.clear()
        for name in ordered_names:
            self._governance_workspace.addItem(name)
        target = previous_target or active_instance or (ordered_names[0] if ordered_names else "")
        if target:
            idx = self._governance_workspace.findText(target)
            self._governance_workspace.setCurrentIndex(max(0, idx))
        self._governance_workspace.blockSignals(False)
        self._load_governance_editor(self._governance_workspace.currentText())

        self._connector_workspace.blockSignals(True)
        self._connector_workspace.clear()
        for name in ordered_names:
            self._connector_workspace.addItem(name)
        connector_target_workspace = previous_connector_workspace or active_instance or (ordered_names[0] if ordered_names else "")
        if connector_target_workspace:
            idx = self._connector_workspace.findText(connector_target_workspace)
            self._connector_workspace.setCurrentIndex(max(0, idx))
        self._connector_workspace.blockSignals(False)
        connector_rows = self._connectors_by_name.get(self._connector_workspace.currentText().strip(), {})
        self._connector_id.blockSignals(True)
        self._connector_id.clear()
        for connector_id in connector_rows.keys():
            self._connector_id.addItem(connector_id)
        if self._connector_id.count() == 0:
            for connector_id in ("gmail", "calendar", "spotify", "youtube", "crm", "voip"):
                self._connector_id.addItem(connector_id)
        connector_idx = self._connector_id.findText(previous_connector_id)
        self._connector_id.setCurrentIndex(max(0, connector_idx))
        self._connector_id.blockSignals(False)
        self._load_connector_binding_editor("")

        limits = payload.get("limits", {}) if isinstance(payload, dict) else {}
        if isinstance(limits, dict):
            self._configured = int(limits.get("configured", len(items)) or len(items))
            self._max_configured = int(limits.get("max_configured", 5) or 5)
            self._active_runtime = int(limits.get("active_runtime", 0) or 0)
            self._max_active_runtime = int(limits.get("max_active_runtime", 2) or 2)
        else:
            self._configured = len(items)
            self._max_configured = 5
            self._active_runtime = sum(
                1
                for item in items
                if isinstance(item, dict) and str(item.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
            )
            self._max_active_runtime = 2

        self._summary_lbl.setText(
            f"Configured workspaces: {self._configured} / {self._max_configured} | Active workspace: {active_instance or '-'}"
            + (f" | Roles: {_workspace_role_summary(items)}" if items else "")
            + (f" | Warnings: {len(warnings)}" if isinstance(warnings, list) and warnings else "")
        )
        limits_text = f"Live workspaces: {self._active_runtime} / {self._max_active_runtime}"
        if self._configured >= self._max_configured:
            limits_text += " | workspace cap reached"
        if self._active_runtime >= self._max_active_runtime:
            limits_text += " | collaborator cap reached"
        self._limits_lbl.setText(limits_text)
        self._role_mix_lbl.setText("Role mix: " + _workspace_role_summary(items))
        active_payload = next(
            (
                item
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip() == active_instance
            ),
            {},
        )
        active_type = str(active_payload.get("type", "user_instance") or "user_instance")
        active_purpose = str(active_payload.get("description", "") or _workspace_default_purpose(active_type)).strip()
        self._collab_lbl.setText(
            f"Active workspace fit: {_workspace_role_label(active_type)}. {active_purpose}"
            if active_instance
            else "Pick a workspace to see its saved purpose and collaboration fit."
        )

        for item in items:
            if not isinstance(item, dict):
                continue
            card = _InstanceCard(item, str(item.get("name", "")).strip() == active_instance)
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
