"""
instance_card.py
InstanceCard widget — extracted from instance_manager_sections.py.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.guppy.launcher_application.instance_manager_presenter import (
    build_workspace_create_copy,
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
        continuity = payload.get("continuity") if isinstance(payload.get("continuity"), dict) else {}
        continuity_hint = str(continuity.get("continuity_hint", "") or "").strip()
        if continuity_hint:
            details.append(continuity_hint)
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
