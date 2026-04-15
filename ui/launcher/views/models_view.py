"""
ui/launcher/views/models_view.py
MODELS tab — local (Ollama) and cloud (Anthropic) model library.
Fetches installed Ollama models in a background thread.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from inference_router import LAUNCHER_MODES_DISPLAY, resolve_ui_route
from .. import tokens as T

try:
    from utils.personalization_config import (
        ensure_personalization_scaffold,
        load_provider_registry,
        save_provider_registry,
        validate_provider_registry,
    )
    _PROVIDER_BACKEND = True
except Exception:
    _PROVIDER_BACKEND = False

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

_RUNTIME = Path(__file__).resolve().parent.parent.parent.parent / "runtime"
_HEARTBEAT_FRESH_SECONDS = float(os.environ.get("GUPPY_HEARTBEAT_FRESH_SECONDS", "20") or "20")


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
        self._provider_registry: dict[str, Any] = {}
        self._route_options: list[str] = []
        self._build_ui()
        self._load_route_config()
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

        # ── Route strategy panel (W1-04) ────────────────────────────────────
        route_bar = QFrame()
        route_bar.setObjectName("models_route_bar")
        route_bar.setStyleSheet(
            f"QFrame#models_route_bar {{"
            f"  background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};"
            f"}}"
        )
        rbl = QVBoxLayout(route_bar)
        rbl.setContentsMargins(28, 10, 28, 10)
        rbl.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        def _task_combo(label: str) -> QComboBox:
            row1.addWidget(QLabel(label))
            cb = QComboBox()
            cb.setFixedWidth(300)
            cb.currentTextChanged.connect(lambda _=None: self._refresh_route_summary())
            row1.addWidget(cb)
            return cb

        self._simple_route_cb = _task_combo("TASK: SIMPLE")
        self._complex_route_cb = _task_combo("TASK: COMPLEX")
        self._teaching_route_cb = _task_combo("TASK: TEACHING")
        row1.addStretch()
        rbl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        fb_lbl = QLabel("FALLBACK CHAIN")
        fb_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        row2.addWidget(fb_lbl)
        self._fallback_chain_input = QLineEdit("")
        self._fallback_chain_input.textChanged.connect(lambda _=None: self._refresh_route_summary())
        self._fallback_chain_input.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
        )
        self._fallback_chain_input.setMinimumWidth(620)
        row2.addWidget(self._fallback_chain_input)

        self._apply_routes_btn = QPushButton("APPLY ROUTES")
        self._apply_routes_btn.setFixedHeight(28)
        self._apply_routes_btn.clicked.connect(self._apply_routes)
        row2.addWidget(self._apply_routes_btn)
        row2.addStretch()
        rbl.addLayout(row2)

        self._route_status_lbl = QLabel("Route strategy ready")
        self._route_status_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        rbl.addWidget(self._route_status_lbl)

        self._route_summary_lbl = QLabel("")
        self._route_summary_lbl.setWordWrap(True)
        self._route_summary_lbl.setStyleSheet(
            f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
        )
        rbl.addWidget(self._route_summary_lbl)

        self._route_evidence_lbl = QLabel("")
        self._route_evidence_lbl.setWordWrap(True)
        self._route_evidence_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
        )
        rbl.addWidget(self._route_evidence_lbl)

        row3 = QHBoxLayout()
        row3.setSpacing(10)
        preview_lbl = QLabel("WHY GUPPY CHOSE THIS")
        preview_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        row3.addWidget(preview_lbl)
        self._route_mode_cb = QComboBox()
        self._route_mode_cb.addItems(list(LAUNCHER_MODES_DISPLAY))
        self._route_mode_cb.setFixedWidth(150)
        self._route_mode_cb.currentTextChanged.connect(lambda _=None: self._refresh_route_preview())
        row3.addWidget(self._route_mode_cb)
        self._route_input = QLineEdit()
        self._route_input.setPlaceholderText("Type a sample request to preview task classification and route choice")
        self._route_input.textChanged.connect(lambda _=None: self._refresh_route_preview())
        self._route_input.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;"
        )
        row3.addWidget(self._route_input, stretch=1)
        rbl.addLayout(row3)

        self._route_preview_lbl = QLabel("Route preview appears here once you type a sample request.")
        self._route_preview_lbl.setWordWrap(True)
        self._route_preview_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;"
            f"background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;"
        )
        rbl.addWidget(self._route_preview_lbl)
        root.addWidget(route_bar)

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

    def _set_route_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._route_status_lbl.setText(text)
        self._route_status_lbl.setStyleSheet(
            f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )

    def _load_route_config(self) -> None:
        if not _PROVIDER_BACKEND:
            self._apply_routes_btn.setEnabled(False)
            self._set_route_status("Provider backend unavailable", ok=False)
            return
        try:
            ensure_personalization_scaffold()
            registry = load_provider_registry()
            self._provider_registry = registry if isinstance(registry, dict) else {}
            self._route_options = self._route_targets_from_registry(self._provider_registry)

            for cb in [self._simple_route_cb, self._complex_route_cb, self._teaching_route_cb]:
                cb.clear()
                cb.addItems(self._route_options)

            routes = self._provider_registry.get("routes", {}) if isinstance(self._provider_registry, dict) else {}
            if isinstance(routes, dict):
                self._set_combo_to_text(self._simple_route_cb, str(routes.get("simple", "")))
                self._set_combo_to_text(self._complex_route_cb, str(routes.get("complex", "")))
                self._set_combo_to_text(self._teaching_route_cb, str(routes.get("teaching", "")))
                fallback = routes.get("fallback_chain", [])
                if isinstance(fallback, list):
                    self._fallback_chain_input.setText(", ".join(str(item).strip() for item in fallback if str(item).strip()))
            self._refresh_route_summary()
            self._refresh_route_preview()
            self._set_route_status("Route strategy loaded", ok=True)
        except Exception as exc:
            self._set_route_status(f"Route load failed: {exc}", ok=False)

    @staticmethod
    def _route_targets_from_registry(registry: dict[str, Any]) -> list[str]:
        options: list[str] = []
        providers = registry.get("providers", []) if isinstance(registry, dict) else []
        if isinstance(providers, list):
            for provider in providers:
                if not isinstance(provider, dict):
                    continue
                pid = provider.get("id")
                models = provider.get("models", [])
                if not isinstance(pid, str) or not isinstance(models, list):
                    continue
                for model in models:
                    if not isinstance(model, dict):
                        continue
                    mid = model.get("id")
                    if isinstance(mid, str) and mid:
                        options.append(f"{pid}/{mid}")
        return sorted(set(options))

    @staticmethod
    def _parse_fallback_chain(raw: str) -> list[str]:
        return [part.strip() for part in (raw or "").split(",") if part.strip()]

    def _set_combo_to_text(self, combo: QComboBox, target: str) -> None:
        idx = combo.findText(target)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _refresh_route_summary(self) -> None:
        fallback = self._parse_fallback_chain(self._fallback_chain_input.text())
        health = self._route_health_summary()
        summary = (
            "Current route plan:\n"
            f"Simple requests start with {self._friendly_route_target(self._simple_route_cb.currentText())}.\n"
            f"Complex requests start with {self._friendly_route_target(self._complex_route_cb.currentText())}.\n"
            f"Teaching requests start with {self._friendly_route_target(self._teaching_route_cb.currentText())}.\n"
            f"If the first choice is unavailable, Guppy falls back to "
            f"{', '.join(self._friendly_route_target(item) for item in fallback) if fallback else 'the built-in defaults'}."
        )
        self._route_summary_lbl.setText(summary)
        self._route_evidence_lbl.setText(f"Live evidence: {health}")

    @staticmethod
    def _describe_route_decision(decision: dict[str, Any]) -> str:
        if not isinstance(decision, dict):
            return "Route preview unavailable."
        task_type = str(decision.get("task_type", "unknown") or "unknown").strip()
        route = str(decision.get("route", "pending") or "pending").strip()
        executor = str(decision.get("executor", "") or "").strip()
        model = str(decision.get("model", "") or "").strip()
        backup = str(decision.get("backup_model", "") or "").strip()
        reason = str(decision.get("route_reason", "") or "no explanation available").strip()
        route_label = ModelsView._friendly_route_name(route)
        route_target = ModelsView._friendly_route_target(model or route_label)
        summary = f"{task_type.capitalize()} work will start with {route_target}."
        if executor:
            summary += f" Guppy will execute it through {executor.upper()}."
        details: list[str] = []
        if backup:
            details.append(f"Backup: {ModelsView._friendly_route_target(backup)}")
        details.append(f"Why: {reason}")
        return summary + ("\n" + " ".join(details) if details else "")

    def _route_health_summary(self) -> str:
        api_key = bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip())
        local_count = max(0, len(self._local_cards))
        latency = self._latest_runtime_latency()
        heartbeat_path = _RUNTIME / "guppy.heartbeat"
        heartbeat = False
        if heartbeat_path.exists():
            try:
                heartbeat = (time.time() - heartbeat_path.stat().st_mtime) < _HEARTBEAT_FRESH_SECONDS
            except OSError:
                heartbeat = False
        parts = [
            f"Cloud path {'configured' if api_key else 'needs API key'}",
            f"Local runtime {'heartbeat seen' if heartbeat else 'heartbeat missing'}",
        ]
        if local_count:
            parts.append(f"{local_count} local model{'s' if local_count != 1 else ''} visible")
        else:
            parts.append("local library not loaded yet")
        if latency:
            parts.append(f"launcher-wide last reply {latency}")
        return " | ".join(parts)

    def _route_evidence_for_decision(self, decision: dict[str, Any]) -> str:
        route = str(decision.get("route", "pending") or "pending").strip().lower()
        health = self._route_health_summary()
        if route in {"haiku", "sonnet", "opus"}:
            return f"Cloud evidence: {health}"
        if route == "local":
            return f"Local evidence: {health}"
        return f"Launcher evidence: {health}"

    @staticmethod
    def _latest_runtime_latency() -> str:
        try:
            payload = json.loads((_RUNTIME / "guppy.status").read_text(encoding="utf-8"))
        except Exception:
            return ""
        latency = str(payload.get("last_latency_ms", "") or "").strip()
        if not latency or latency in {"—", "-"}:
            return ""
        return f"{latency} ms"

    @staticmethod
    def _friendly_route_name(route: str) -> str:
        value = str(route or "").strip().lower()
        return {
            "haiku": "Claude Haiku",
            "sonnet": "Claude Sonnet",
            "opus": "Claude Opus",
            "local": "the local model",
            "code": "the code specialist",
            "teaching": "the teaching route",
            "auto": "the automatic route",
            "pending": "the pending route",
        }.get(value, value.replace("-", " ").replace("_", " ").strip().title() or "the selected route")

    @classmethod
    def _friendly_route_target(cls, target: str) -> str:
        raw = str(target or "").strip()
        if not raw:
            return "an unset route"
        provider, sep, model = raw.partition("/")
        if sep and provider and model:
            provider_label = "local" if provider.lower() == "local" else provider.upper()
            return f"{provider_label} / {model}"
        return cls._friendly_route_name(raw)

    def _refresh_route_preview(self) -> None:
        sample = self._route_input.text().strip()
        if not sample:
            self._route_preview_lbl.setText(
                "Route preview appears here once you type a sample request. Try the kind of question you would ask on Home."
            )
            return
        try:
            decision = resolve_ui_route(
                user_text=sample,
                mode=self._route_mode_cb.currentText().strip().lower(),
                api_key_available=bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()),
            )
            self._route_preview_lbl.setText(
                self._describe_route_decision(decision) + "\n" + self._route_evidence_for_decision(decision)
            )
        except Exception as exc:
            self._route_preview_lbl.setText(f"Route preview failed: {exc}")

    def _apply_routes(self) -> None:
        if not _PROVIDER_BACKEND:
            self._set_route_status("Provider backend unavailable", ok=False)
            return
        try:
            registry = load_provider_registry()
            if not isinstance(registry, dict):
                self._set_route_status("Provider registry is invalid", ok=False)
                return
            valid_targets = set(self._route_targets_from_registry(registry))
            simple = self._simple_route_cb.currentText().strip()
            complex_route = self._complex_route_cb.currentText().strip()
            teaching = self._teaching_route_cb.currentText().strip()

            for label, value in [("simple", simple), ("complex", complex_route), ("teaching", teaching)]:
                if value not in valid_targets:
                    self._set_route_status(f"Invalid {label} target: {value}", ok=False)
                    return

            fallback = self._parse_fallback_chain(self._fallback_chain_input.text())
            allowed_fallback = valid_targets | {"local/guppy"}
            invalid_fallback = [item for item in fallback if item not in allowed_fallback]
            if invalid_fallback:
                self._set_route_status(f"Invalid fallback target: {invalid_fallback[0]}", ok=False)
                return

            routes = registry.setdefault("routes", {})
            if not isinstance(routes, dict):
                routes = {}
                registry["routes"] = routes
            routes["simple"] = simple
            routes["complex"] = complex_route
            routes["teaching"] = teaching
            routes["fallback_chain"] = fallback

            errors = validate_provider_registry(registry)
            if errors:
                self._set_route_status(f"Provider registry invalid: {errors[0]}", ok=False)
                return

            save_provider_registry(registry)
            self._provider_registry = registry
            self._refresh_route_summary()
            self._refresh_route_preview()
            self._set_route_status("Route strategy saved", ok=True)
        except Exception as exc:
            self._set_route_status(f"Apply routes failed: {exc}", ok=False)
