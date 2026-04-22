from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import tokens as T


class FirstRunBanner(QFrame):
    settings_requested = Signal()
    models_requested = Signal()
    focus_input_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("first_run_banner")
        self.setStyleSheet(
            "QFrame#first_run_banner { background-color: rgba(255,255,255,0.60); border: 1px solid rgba(214,197,174,0.44); border-radius: 18px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._title_lbl = QLabel("FIRST RUN")
        self._title_lbl.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
        self._summary_lbl = QLabel("Finish setup in order: install, model runtime, then one real test ask.")
        self._summary_lbl.setWordWrap(True)
        self._summary_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        self._detail_lbl = QLabel("")
        self._detail_lbl.setWordWrap(True)
        self._detail_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )

        self._status_row = QHBoxLayout()
        self._status_row.setSpacing(8)
        self._install_chip = QLabel("INSTALL · PENDING")
        self._model_chip = QLabel("MODEL · PENDING")
        self._request_chip = QLabel("FIRST ASK · PENDING")
        for chip in (self._install_chip, self._model_chip, self._request_chip):
            chip.setStyleSheet(
                f"color: {T.DIM}; background: rgba(255,255,255,0.92); border: 1px solid rgba(214,197,174,0.42);"
                f" border-radius: 12px; padding: 5px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            self._status_row.addWidget(chip)
        self._status_row.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._settings_btn = QPushButton("OPEN SETTINGS")
        self._settings_btn.setToolTip("Open Settings to review install checks, accounts, and setup notes")
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        self._models_btn = QPushButton("OPEN MODELS")
        self._models_btn.setToolTip("Open Models to verify local runtime options and model readiness")
        self._models_btn.clicked.connect(self.models_requested.emit)
        self._try_btn = QPushButton("TRY TEST ASK")
        self._try_btn.setToolTip("Jump to the composer and send one short test ask")
        self._try_btn.clicked.connect(self.focus_input_requested.emit)
        for button in (self._settings_btn, self._models_btn, self._try_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                f"QPushButton {{ background: rgba(255,255,255,0.92); color: {T.DIM}; border: 1px solid rgba(214,197,174,0.54);"
                f" border-radius: 12px; padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
                f"QPushButton:hover {{ border-color: rgba(70,98,199,0.46); color: {T.TERTIARY}; background: #ffffff; }}"
            )
            actions.addWidget(button)
        actions.addStretch()

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._summary_lbl)
        layout.addLayout(self._status_row)
        layout.addWidget(self._detail_lbl)
        layout.addLayout(actions)
        self.hide()

    def set_status(
        self,
        *,
        visible: bool,
        summary: str = "",
        detail: str = "",
        install_status: str = "pending",
        model_status: str = "pending",
        request_status: str = "pending",
    ) -> None:
        self.setVisible(bool(visible))
        if not visible:
            return
        self._summary_lbl.setText(
            (summary or "Finish setup in order: install, model runtime, then one real test ask.").strip()
        )
        self._detail_lbl.setText(
            (detail or "Open Settings or Models as needed, then send one short test ask from Home.").strip()
        )
        self._set_chip(self._install_chip, "INSTALL", install_status)
        self._set_chip(self._model_chip, "MODEL", model_status)
        self._set_chip(self._request_chip, "FIRST ASK", request_status)

    def apply_density_mode(self, width: int) -> None:
        ultra = max(int(width or 0), 0) < 780
        if ultra:
            self._settings_btn.setText("SETTINGS")
            self._models_btn.setText("MODELS")
            self._try_btn.setText("TRY ASK")
        else:
            self._settings_btn.setText("OPEN SETTINGS")
            self._models_btn.setText("OPEN MODELS")
            self._try_btn.setText("TRY TEST ASK")
        self._model_chip.setVisible(not ultra)
        self._request_chip.setVisible(not ultra)

    def _set_chip(self, chip: QLabel, label: str, status: str) -> None:
        normalized = (status or "pending").strip().lower() or "pending"
        if normalized == "passed":
            color = T.GREEN
            bg = "rgba(44,123,89,0.12)"
            text = "READY"
        elif normalized in {"failed", "skipped"}:
            color = T.ERROR if normalized == "failed" else T.PRIMARY
            bg = "rgba(183,73,66,0.12)" if normalized == "failed" else "rgba(201,106,43,0.12)"
            text = normalized.upper()
        else:
            color = T.TERTIARY
            bg = "rgba(70,98,199,0.10)"
            text = "PENDING"
        chip.setText(f"{label} · {text}")
        chip.setStyleSheet(
            f"color: {color}; background: {bg}; border: 1px solid rgba(214,197,174,0.42);"
            f" border-radius: 12px; padding: 5px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
