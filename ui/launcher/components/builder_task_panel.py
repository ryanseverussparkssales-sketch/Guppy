from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from src.guppy.launcher_application.builder_workflow import load_builder_templates

from .. import tokens as T


def _mono(text: str, color: str = T.DIM, size: int = T.FS_TINY, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label


class BuilderTaskPanel(QFrame):
    queue_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._templates = load_builder_templates()
        self._instance_name = "guppy-primary"
        self._instance_type = "user_instance"
        self.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        root.addWidget(_mono("LOCAL BUILDER TASKS", T.PRIMARY, T.FS_TINY, True))
        root.addWidget(
            _mono(
                "Queue low-risk local-model work. First-time testers should start in App Mgmt > Automation Test. "
                "Writes stay in docs/, tests/, or generated config paths and start in dry-run approval mode.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        row = QHBoxLayout()
        row.setSpacing(8)
        self._template_cb = QComboBox()
        self._template_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        for item in self._templates:
            self._template_cb.addItem(str(item.get("title", item.get("id", "TASK"))), str(item.get("id", "")))
        self._template_cb.currentIndexChanged.connect(self._sync_hint)
        row.addWidget(self._template_cb, stretch=1)

        self._target = QLineEdit()
        self._target.setPlaceholderText("Target module, feature, or prompt topic")
        self._target.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        row.addWidget(self._target, stretch=1)

        self._queue_btn = QPushButton("QUEUE TASK")
        self._queue_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.PRIMARY}; border: 1px solid {T.PRIMARY};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ background: rgba(242,202,80,0.12); }}"
            f"QPushButton:disabled {{ color: {T.BORDER}; border-color: {T.BORDER}; }}"
        )
        self._queue_btn.clicked.connect(self._emit_queue)
        row.addWidget(self._queue_btn)
        root.addLayout(row)

        self._hint_lbl = _mono("", T.DIM, T.FS_TINY)
        self._hint_lbl.setWordWrap(True)
        root.addWidget(self._hint_lbl)
        self._status_lbl = _mono("Builder queue ready", T.DIM, T.FS_TINY)
        root.addWidget(self._status_lbl)
        self._sync_hint()

    def _template(self) -> dict[str, object]:
        template_id = str(self._template_cb.currentData() or "")
        return next((item for item in self._templates if item.get("id") == template_id), self._templates[0] if self._templates else {})

    def _sync_hint(self) -> None:
        template = self._template()
        hint = str(template.get("target_hint", "Target"))
        description = str(template.get("description", ""))
        self._hint_lbl.setText(f"{description} Hint: {hint}")

    def set_instance_context(self, instance_name: str, instance_type: str) -> None:
        self._instance_name = instance_name or "guppy-primary"
        self._instance_type = instance_type or "user_instance"
        enabled = self._instance_type != "read_only_instance"
        self._queue_btn.setEnabled(enabled)
        if enabled:
            self._status_lbl.setText(
                f"Power-user queue ready for {self._instance_name} ({self._instance_type.replace('_', ' ')}). "
                "First-time testers: App Mgmt > Automation Test."
            )
            self._status_lbl.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
        else:
            self._status_lbl.setText("Builder queue blocked for read-only instances")
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )

    def set_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def _emit_queue(self) -> None:
        template = self._template()
        template_id = str(template.get("id", "")).strip()
        if not template_id:
            self.set_status("No builder template selected", ok=False)
            return
        payload = {
            "template_id": template_id,
            "target_ref": self._target.text().strip(),
            "instance_name": self._instance_name,
            "instance_type": self._instance_type,
        }
        self.queue_requested.emit(payload)
