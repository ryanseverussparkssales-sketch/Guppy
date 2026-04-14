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
            f"Type: {str(payload.get('type', 'user_instance')).replace('_', ' ').upper()}",
        ]
        description = str(payload.get("description", "")).strip()
        if description:
            details.append(f"Notes: {description}")
        last_message = str(payload.get("last_message", "")).strip()
        if last_message:
            details.append(f"Last: {last_message[:120]}")
        for line in details:
            root.addWidget(_mono(line, T.DIM, T.FS_TINY))

        actions = QHBoxLayout()
        for label, signal in (("SWITCH", self.activate_requested), ("LOGS", self.logs_requested), ("DELETE", self.delete_requested)):
            button = QPushButton(label)
            button.setStyleSheet(
                f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
                f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            )
            button.clicked.connect(lambda _=False, n=self._name, s=signal: s.emit(n))
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_names: set[str] = set()
        self._configured = 0
        self._max_configured = 5
        self._active_runtime = 0
        self._max_active_runtime = 2
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

        title = QLabel("Instance Manager")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;"
        )
        layout.addWidget(title)
        layout.addWidget(_mono("Manage up to five configured instances with one active foreground slot and one collaborator.", T.DIM, T.FS_SMALL))

        self._status_lbl = _mono("Instance manager idle", T.DIM, T.FS_TINY)
        layout.addWidget(self._status_lbl)

        form = QFrame()
        form.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(8)
        form_layout.addWidget(_mono("CREATE OR UPDATE INSTANCE", T.PRIMARY, T.FS_TINY, True))

        row1 = QHBoxLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("instance-name")
        self._description = QLineEdit()
        self._description.setPlaceholderText("Description")
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
        self._persona.addItems(["guppy", "merlin", "council"])
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
        save_btn = QPushButton("SAVE INSTANCE")
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

        self._summary_lbl = _mono("No instance data loaded", T.DIM, T.FS_TINY)
        layout.addWidget(self._summary_lbl)
        self._limits_lbl = _mono("Configured slots: 0 / 5 · Runtime-active: 0 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._limits_lbl)

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
        logs_layout.addWidget(_mono("INSTANCE LOGS", T.PRIMARY, T.FS_TINY, True))
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
        self._save_btn = save_btn
        self._sync_save_affordance()

    def _emit_create(self) -> None:
        self.create_requested.emit(
            {
                "name": self._name.text().strip(),
                "description": self._description.text().strip(),
                "mode": self._mode.currentText().strip(),
                "persona": self._persona.currentText().strip(),
                "voice": self._voice.currentText().strip(),
                "type": self._type.currentText().strip(),
                "enabled": self._enabled.isChecked(),
            }
        )

    def _sync_save_affordance(self) -> None:
        candidate = self._name.text().strip()
        is_new_name = bool(candidate) and candidate not in self._known_names
        at_limit = self._configured >= self._max_configured
        self._save_btn.setEnabled(not (at_limit and is_new_name))
        if at_limit and is_new_name:
            self._status_lbl.setText("Configured-instance cap reached (5 / 5). Update an existing instance or delete one first.")
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )

    def set_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
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
        self._known_names = {
            str(item.get("name", "")).strip() for item in items if isinstance(item, dict) and str(item.get("name", "")).strip()
        }

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
                1 for item in items if isinstance(item, dict) and str(item.get("status", "idle")).strip().lower() in {"active", "running", "busy"}
            )
            self._max_active_runtime = 2

        self._summary_lbl.setText(
            f"Configured: {self._configured} / {self._max_configured} | Active: {active_instance or '—'}"
            + (f" | Warnings: {len(warnings)}" if isinstance(warnings, list) and warnings else "")
        )
        limits_text = f"Runtime-active: {self._active_runtime} / {self._max_active_runtime}"
        if self._configured >= self._max_configured:
            limits_text += " · config cap reached"
        if self._active_runtime >= self._max_active_runtime:
            limits_text += " · collaborator cap reached"
        self._limits_lbl.setText(limits_text)

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
        self._logs.setPlainText("\n".join(lines) if lines else f"No logs for {instance_name}")
