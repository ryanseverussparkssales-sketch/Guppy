"""
ui/launcher/views/models_view.py
MODELS tab — local (Ollama) and cloud (Anthropic) model library.
Fetches installed Ollama models in a background thread.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T

# ── Static model catalogue ─────────────────────────────────────────────────────
CLOUD_MODELS: list[dict[str, Any]] = [
    {
        "name": "claude-haiku-4-5-20251001",
        "display": "Claude Haiku 4.5",
        "context": "200K tokens",
        "tier": "CLOUD",
        "note": "Fast / cost-efficient",
    },
    {
        "name": "claude-sonnet-4-6",
        "display": "Claude Sonnet 4.6",
        "context": "200K tokens",
        "tier": "CLOUD",
        "note": "Balanced / recommended",
    },
    {
        "name": "claude-opus-4",
        "display": "Claude Opus 4",
        "context": "200K tokens",
        "tier": "CLOUD",
        "note": "Maximum intelligence",
    },
]


def _fmt_size(num_bytes: int) -> str:
    if not num_bytes:
        return "—"
    gb = num_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = num_bytes / (1024 ** 2)
    return f"{mb:.0f} MB"


class _OllamaFetch(QThread):
    finished = Signal(list)

    def run(self) -> None:
        try:
            url = "http://127.0.0.1:11434/api/tags"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read())
            self.finished.emit(data.get("models", []))
        except Exception:
            self.finished.emit([])


class _ModelCard(QFrame):
    set_active = Signal(str)

    def __init__(
        self,
        name: str,
        display: str,
        tier: str,
        context: str = "—",
        note: str = "",
        size_bytes: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model_name = name
        self.setObjectName("model_card")
        self.setStyleSheet(
            f"QFrame#model_card {{"
            f"  background-color: {T.BG1}; border: 1px solid {T.BORDER};"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        # ── Name + tier badge ────────────────────────────────────────────────
        top = QHBoxLayout()
        name_lbl = QLabel(display)
        name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_LABEL}pt; font-weight: bold;"
        )
        badge_color = T.PRIMARY if tier == "LOCAL" else T.SECONDARY
        badge = QLabel(tier)
        badge.setStyleSheet(
            f"color: {badge_color}; background: transparent;"
            f"font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"letter-spacing: 1px; padding: 1px 4px;"
            f"border: 1px solid {badge_color};"
        )
        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(badge)
        layout.addLayout(top)

        # ── Model id label ───────────────────────────────────────────────────
        id_lbl = QLabel(name)
        id_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt;"
        )
        layout.addWidget(id_lbl)

        # ── Meta row ─────────────────────────────────────────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        for label_text in ([context] + ([_fmt_size(size_bytes)] if size_bytes else []) + ([note] if note else [])):
            chip = QLabel(label_text)
            chip.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
            )
            meta_row.addWidget(chip)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        layout.addSpacing(10)

        # ── Action row ───────────────────────────────────────────────────────
        act = QHBoxLayout()

        self._status_lbl = QLabel("AVAILABLE")
        self._status_lbl.setStyleSheet(
            f"color: {T.GREEN}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        act.addWidget(self._status_lbl)
        act.addStretch()

        self._set_btn = QPushButton("SET ACTIVE")
        self._set_btn.setFixedHeight(26)
        self._set_btn.clicked.connect(lambda: self.set_active.emit(self._model_name))
        act.addWidget(self._set_btn)
        layout.addLayout(act)

    def mark_active(self, active: bool) -> None:
        self._status_lbl.setText("LOADED" if active else "AVAILABLE")
        self._status_lbl.setStyleSheet(
            f"color: {T.PRIMARY if active else T.GREEN}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        self._set_btn.setEnabled(not active)

    def set_offline(self) -> None:
        self._status_lbl.setText("OFFLINE")
        self._status_lbl.setStyleSheet(
            f"color: {T.ERROR}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )


class _ColumnHeader(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
            f"border-bottom: 1px solid {T.BORDER}; padding-bottom: 4px;"
        )


class ModelsView(QWidget):
    model_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_cards: list[_ModelCard] = []
        self._active_model = os.environ.get("GUPPY_LOCAL_MODEL", "guppy")
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = QFrame()
        topbar.setFixedHeight(52)
        topbar.setObjectName("models_topbar")
        topbar.setStyleSheet(
            f"QFrame#models_topbar {{"
            f"  background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};"
            f"}}"
        )
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(28, 0, 28, 0)

        title = QLabel("MODEL LIBRARY")
        title.setStyleSheet(
            f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}';"
            f"font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;"
        )
        tb.addWidget(title)
        tb.addStretch()

        self._active_lbl = QLabel(f"ACTIVE: {self._active_model.upper()}")
        self._active_lbl.setStyleSheet(
            f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_TINY}pt; letter-spacing: 2px;"
        )
        tb.addWidget(self._active_lbl)
        tb.addSpacing(16)

        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.clicked.connect(self._refresh)
        tb.addWidget(self._refresh_btn)
        root.addWidget(topbar)

        # ── Scrollable grid ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._content = QWidget()
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(28, 24, 28, 24)
        self._grid.setSpacing(16)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)

        loc_hdr = _ColumnHeader("LOCAL  —  OLLAMA")
        cld_hdr = _ColumnHeader("CLOUD  —  ANTHROPIC")
        self._grid.addWidget(loc_hdr, 0, 0)
        self._grid.addWidget(cld_hdr, 0, 1)

        # Cloud models are static
        for i, m in enumerate(CLOUD_MODELS):
            card = _ModelCard(
                name=m["name"],
                display=m["display"],
                tier=m["tier"],
                context=m["context"],
                note=m["note"],
            )
            card.set_active.connect(self._on_model_selected)
            self._grid.addWidget(card, i + 1, 1)

        # Placeholder for local models
        self._ollama_placeholder = QLabel("Fetching local models...")
        self._ollama_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ollama_placeholder.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
            f"font-size: {T.FS_SMALL}pt; letter-spacing: 1px; padding: 24px;"
        )
        self._grid.addWidget(self._ollama_placeholder, 1, 0)

        scroll.setWidget(self._content)
        root.addWidget(scroll)

    def _refresh(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("FETCHING...")
        self._fetch_thread = _OllamaFetch(self)
        self._fetch_thread.finished.connect(self._on_ollama_result)
        self._fetch_thread.start()

    def _on_ollama_result(self, models: list[dict]) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("REFRESH")

        # Remove old local cards
        for card in self._local_cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self._local_cards.clear()

        if self._ollama_placeholder:
            self._ollama_placeholder.setParent(None)
            self._ollama_placeholder = None

        if not models:
            placeholder = QLabel("No local models found.\nStart Ollama and click REFRESH.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                f"color: {T.DIM}; font-family: '{T.FF_MONO}';"
                f"font-size: {T.FS_SMALL}pt; padding: 24px;"
            )
            self._grid.addWidget(placeholder, 1, 0)
            self._ollama_placeholder = placeholder
            return

        for i, m in enumerate(models):
            name = m.get("name", "unknown")
            display = name.split(":")[0].replace("-", " ").title()
            size = m.get("size", 0)
            card = _ModelCard(
                name=name,
                display=display,
                tier="LOCAL",
                context="—",
                note="",
                size_bytes=size,
            )
            card.mark_active(name.startswith(self._active_model))
            card.set_active.connect(self._on_model_selected)
            self._grid.addWidget(card, i + 1, 0)
            self._local_cards.append(card)

    def _on_model_selected(self, name: str) -> None:
        self._active_model = name
        self._active_lbl.setText(f"ACTIVE: {name.upper()}")
        os.environ["GUPPY_LOCAL_MODEL"] = name
        for card in self._local_cards:
            card.mark_active(card._model_name == name)
        self.model_selected.emit(name)
