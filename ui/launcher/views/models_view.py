from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from src.guppy.experience_config import (
    apply_runtime_settings_to_env as apply_settings_to_env,
    ensure_personalization_scaffold,
    load_provider_registry,
    load_runtime_settings as load_app_settings,
    personalization_backend_available,
    runtime_settings_backend_available,
    save_provider_registry,
    save_runtime_settings as save_app_settings,
    validate_provider_registry,
)
from src.guppy.inference.router import LAUNCHER_MODES_DISPLAY, resolve_ui_route
from .. import tokens as T
from .models_runtime_library import (
    assign_runtime_model as runtime_library_assign_runtime_model,
    refresh_runtime_library as runtime_library_refresh_runtime_library,
    set_selected_runtime_role as runtime_library_set_selected_runtime_role,
)

_RUNTIME_SETTINGS_BACKEND = runtime_settings_backend_available()
_PROVIDER_BACKEND = personalization_backend_available()

try:
    from src.guppy.local_llm.manifest import get_local_llm_policy_summary, load_local_llm_manifest
    _LOCAL_LLM_MANIFEST_BACKEND = True
except Exception:
    _LOCAL_LLM_MANIFEST_BACKEND = False

    def load_local_llm_manifest():
        return {}

    def get_local_llm_policy_summary(_manifest):
        return {}


CLOUD_MODELS = [
    {"name": "claude-haiku-4-5-20251001", "display": "Claude Haiku 4.5", "context": "200K tokens", "tier": "CLOUD", "note": "Fast / cost-efficient"},
    {"name": "claude-sonnet-4-6", "display": "Claude Sonnet 4.6", "context": "200K tokens", "tier": "CLOUD", "note": "Balanced / recommended"},
    {"name": "claude-opus-4", "display": "Claude Opus 4", "context": "200K tokens", "tier": "CLOUD", "note": "Maximum intelligence"},
]
_RUNTIME = Path(__file__).resolve().parent.parent.parent.parent / "runtime"
_HEARTBEAT_FRESH_SECONDS = float(os.environ.get("GUPPY_HEARTBEAT_FRESH_SECONDS", "20") or "20")
_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_LEMONADE_ROLE_FIELDS = [
    ("lemonade_fast_model", "FAST"),
    ("lemonade_complex_model", "COMPLEX"),
    ("lemonade_teach_model", "TEACH"),
    ("lemonade_code_model", "CODE"),
    ("lemonade_vault_model", "VAULT"),
]


def _fmt_size(num_bytes: int) -> str:
    if not num_bytes:
        return "-"
    gb = num_bytes / (1024 ** 3)
    return f"{gb:.1f} GB" if gb >= 1 else f"{num_bytes / (1024 ** 2):.0f} MB"


def _model_use_hint(name: str, display: str, tier: str, context: str = "", note: str = "") -> str:
    joined = " ".join(str(part or "").lower() for part in (name, display, context, note))
    if "haiku" in joined or "fast" in joined:
        return "Good for quick everyday help and lighter tasks."
    if "sonnet" in joined:
        return "Good default for balanced quality and speed."
    if "opus" in joined:
        return "Good for the hardest writing and reasoning work."
    if "vault" in joined:
        return "Good for document lookup and extraction work."
    if "code" in joined or "coder" in joined or "merlin" in joined:
        return "Good for coding, repo work, and technical tasks."
    if "teach" in joined:
        return "Good for guided explanations and teaching-style help."
    if "guppy-fast" in joined:
        return "Good for fast local replies when you want low wait time."
    if "guppy" in joined and tier == "LOCAL":
        return "Good for everyday chat on this PC."
    if "small" in joined or "1b" in joined or "3b" in joined:
        return "Good for lighter local tasks and quick experiments."
    if "30b" in joined or "32b" in joined or "24b" in joined:
        return "Good for heavier work when you can trade speed for depth."
    return "Use this when it best fits the work you are doing."


def _normalized_model_name(value: str) -> str:
    return str(value or "").strip().lower()


class _LocalRuntimeFetch(QThread):
    finished = Signal(dict)

    def __init__(self, backend: str, base_url: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backend = (backend or "ollama").strip().lower()
        self._base_url = (base_url or "").strip()

    def run(self) -> None:
        try:
            if self._backend == "lemonade":
                url = f"{(self._base_url or _DEFAULT_LEMONADE_BASE_URL).rstrip('/')}/models"
                req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read())
                models = [{"name": str(item.get("id", "")).strip(), "display": str(item.get("id", "")).strip().replace("-", " ").replace("_", " ").title(), "size": 0, "context": "GGUF / OpenAI API", "note": "Downloaded in Lemonade"} for item in data.get("data", []) if isinstance(item, dict) and str(item.get("id", "")).strip()]
            else:
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read())
                models = [{"name": str(item.get("name", "")).strip(), "display": str(item.get("name", "")).strip().split(":")[0].replace("-", " ").title(), "size": int(item.get("size", 0) or 0), "context": "Installed on this PC", "note": ""} for item in data.get("models", []) if isinstance(item, dict) and str(item.get("name", "")).strip()]
            self.finished.emit({"backend": self._backend, "models": models, "error": ""})
        except Exception as exc:
            self.finished.emit({"backend": self._backend, "models": [], "error": str(exc)})


class _ModelCard(QFrame):
    set_active = Signal(str)

    def __init__(self, name: str, display: str, tier: str, context: str = "-", note: str = "", size_bytes: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model_name = name
        self._tier = tier
        self._is_active = False
        self._is_recommended = False
        self._search_text = " ".join(
            part.strip().lower()
            for part in [name, display, tier, context, note]
            if isinstance(part, str) and part.strip()
        )
        self.setObjectName("model_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        top = QHBoxLayout()
        self._name_lbl = QLabel(display)
        self._name_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: bold;")
        self._badge_lbl = QLabel(tier)
        top.addWidget(self._name_lbl); top.addStretch(); top.addWidget(self._badge_lbl); layout.addLayout(top)
        self._id_lbl = QLabel(name)
        self._id_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
        layout.addWidget(self._id_lbl)
        self._use_lbl = QLabel(_model_use_hint(name, display, tier, context, note))
        self._use_lbl.setWordWrap(True)
        self._use_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;")
        layout.addWidget(self._use_lbl)
        meta = QHBoxLayout(); meta.setSpacing(12)
        for text in (([_fmt_size(size_bytes)] if size_bytes else []) + ([context] if context else [])):
            chip = QLabel(text); chip.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"); meta.addWidget(chip)
        meta.addStretch(); layout.addLayout(meta); layout.addSpacing(10)
        act = QHBoxLayout()
        self._status_lbl = QLabel("AVAILABLE")
        self._set_btn = QPushButton("USE THIS SESSION")
        self._set_btn.setFixedHeight(26)
        self._set_btn.clicked.connect(lambda: self.set_active.emit(self._model_name))
        act.addWidget(self._status_lbl); act.addStretch(); act.addWidget(self._set_btn); layout.addLayout(act)
        self._apply_card_style()

    def _apply_card_style(self) -> None:
        border = T.PRIMARY if self._is_recommended else T.BORDER
        background = T.BG0 if self._is_recommended else T.BG1
        self.setStyleSheet(f"QFrame#model_card {{ background-color: {background}; border: 1px solid {border}; }}")
        badge_text = f"{self._tier} PICK" if self._is_recommended else self._tier
        badge_color = T.PRIMARY if self._tier == "LOCAL" else T.SECONDARY
        badge_border = T.PRIMARY if self._is_recommended else badge_color
        badge_fill = T.BG0 if self._is_recommended else "transparent"
        self._badge_lbl.setText(badge_text)
        self._badge_lbl.setStyleSheet(
            f"color: {badge_border}; background: {badge_fill}; font-family: '{T.FF_MONO}'; "
            f"font-size: {T.FS_TINY}pt; letter-spacing: 1px; padding: 1px 4px; border: 1px solid {badge_border};"
        )
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; "
            f"font-weight: {'800' if self._is_recommended else 'bold'};"
        )
        self._use_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt; "
            f"font-weight: {'bold' if self._is_recommended else 'normal'};"
        )
        status_color = T.PRIMARY if self._is_active else T.GREEN
        self._status_lbl.setStyleSheet(
            f"color: {status_color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;"
        )
        button_border = T.PRIMARY if self._is_recommended else T.BORDER
        button_bg = T.BG0 if self._is_recommended else T.BG1
        button_color = T.PRIMARY if self._is_recommended else T.TEXT
        self._set_btn.setStyleSheet(
            f"QPushButton {{ background-color: {button_bg}; color: {button_color}; border: 1px solid {button_border}; "
            f"padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:disabled {{ color: {T.DIM}; border-color: {T.BORDER}; }}"
        )

    def set_recommended(self, recommended: bool) -> None:
        self._is_recommended = recommended
        self._apply_card_style()

    def mark_active(self, active: bool) -> None:
        self._is_active = active
        self._status_lbl.setText("IN USE" if active else "AVAILABLE")
        self._set_btn.setEnabled(not active)
        self._apply_card_style()

    def matches_query(self, query: str) -> bool:
        needle = (query or "").strip().lower()
        return not needle or needle in self._search_text


class _ColumnHeader(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px; border-bottom: 1px solid {T.BORDER}; padding-bottom: 4px;")


class ModelsView(QWidget):
    model_selected = Signal(str)
    runtime_settings_saved = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_cards: list[_ModelCard] = []
        self._cloud_cards: list[_ModelCard] = []
        self._active_model = os.environ.get("GUPPY_LOCAL_MODEL", "guppy")
        self._provider_registry: dict[str, Any] = {}
        self._route_options: list[str] = []
        self._local_runtime_backend = "ollama"
        self._saved_runtime_backend = "ollama"
        self._status_snapshot: dict[str, Any] = {}
        self._policy_snapshot: dict[str, Any] = self._load_local_llm_policy()
        self._lemonade_role_inputs: dict[str, QComboBox] = {}
        self._selected_runtime_role_field = "lemonade_fast_model"
        self._runtime_library_buttons: list[QPushButton] = []
        self._build_ui()
        self._load_runtime_settings()
        self._load_route_config()
        if QApplication.instance() is not None:
            self._refresh()
        self._set_page_mode("library")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("models_topbar")
        topbar.setFixedHeight(52)
        topbar.setStyleSheet(f"QFrame#models_topbar {{ background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER}; }}")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(28, 0, 28, 0)
        self._title_lbl = QLabel("MODELS")
        self._title_lbl.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_TITLE}pt; font-weight: bold; letter-spacing: 2px;")
        self._active_lbl = QLabel(f"CURRENT MODEL: {self._active_model.upper()}")
        self._active_lbl.setStyleSheet(f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
        self._active_runtime_lbl = QLabel("LOCAL ENGINE: OLLAMA")
        self._active_runtime_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.clicked.connect(self._refresh)
        tb.addWidget(self._title_lbl); tb.addStretch(); tb.addWidget(self._active_lbl); tb.addSpacing(16); tb.addWidget(self._active_runtime_lbl); tb.addSpacing(16); tb.addWidget(self._refresh_btn)
        root.addWidget(topbar)

        self._library_summary_frame = QFrame()
        self._library_summary_frame.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
        library_shell = QVBoxLayout(self._library_summary_frame)
        library_shell.setContentsMargins(28, 14, 28, 14)
        library_shell.setSpacing(8)
        self._library_summary_lbl = QLabel("")
        self._library_summary_lbl.setWordWrap(True)
        self._library_summary_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 10px;")
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self._library_search = QLineEdit()
        self._library_search.setPlaceholderText("Search local and cloud models")
        self._library_search.setMinimumWidth(320)
        self._library_search.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
        self._library_search.textChanged.connect(lambda _=None: self._apply_library_filter())
        self._library_hint_lbl = QLabel("Pick the model Guppy should use for this session. Open Runtime only if you want to change the local engine or advanced routing.")
        self._library_hint_lbl.setWordWrap(True)
        self._library_hint_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
        search_row.addWidget(self._library_search)
        search_row.addWidget(self._library_hint_lbl, stretch=1)
        library_shell.addWidget(self._library_summary_lbl)
        library_shell.addLayout(search_row)
        root.addWidget(self._library_summary_frame)

        self._runtime_bar = QFrame()
        self._runtime_bar.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
        rtl = QVBoxLayout(self._runtime_bar)
        rtl.setContentsMargins(28, 12, 28, 12)
        rtl.setSpacing(8)
        row = QHBoxLayout(); row.setSpacing(10)
        row.addWidget(QLabel("LOCAL RUNTIME"))
        self._runtime_backend_cb = QComboBox()
        self._runtime_backend_cb.addItems(["OLLAMA", "LEMONADE"])
        self._runtime_backend_cb.setFixedWidth(160)
        self._runtime_backend_cb.currentTextChanged.connect(self._on_runtime_backend_changed)
        row.addWidget(self._runtime_backend_cb)
        row.addWidget(QLabel("LEMONADE ENDPOINT"))
        self._lemonade_base_url_input = QLineEdit()
        self._lemonade_base_url_input.setPlaceholderText(_DEFAULT_LEMONADE_BASE_URL)
        self._lemonade_base_url_input.setMinimumWidth(280)
        self._lemonade_base_url_input.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
        self._save_runtime_btn = QPushButton("SAVE RUNTIME")
        self._save_runtime_btn.setFixedHeight(28)
        self._save_runtime_btn.clicked.connect(self._save_runtime_settings)
        row.addWidget(self._lemonade_base_url_input); row.addWidget(self._save_runtime_btn); row.addStretch()
        rtl.addLayout(row)

        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(8)
        for index, (field_name, label_text) in enumerate(_LEMONADE_ROLE_FIELDS):
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.setMinimumWidth(220)
            combo.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 4px 6px;")
            combo.currentTextChanged.connect(lambda _=None, target_field=field_name: self._set_selected_runtime_role(target_field))
            grid.addWidget(label, index // 3, (index % 3) * 2)
            grid.addWidget(combo, index // 3, (index % 3) * 2 + 1)
            self._lemonade_role_inputs[field_name] = combo
        rtl.addLayout(grid)

        self._runtime_library_frame = QFrame()
        self._runtime_library_frame.setStyleSheet(f"background-color: {T.BG1}; border: 1px solid {T.BORDER};")
        library_layout = QVBoxLayout(self._runtime_library_frame)
        library_layout.setContentsMargins(10, 10, 10, 10)
        library_layout.setSpacing(8)
        library_hdr = QHBoxLayout()
        self._runtime_library_title = QLabel("LEMONADE MODEL PICKER")
        self._runtime_library_title.setStyleSheet(f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 2px;")
        self._runtime_library_target_lbl = QLabel("Assigning to FAST")
        self._runtime_library_target_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
        library_hdr.addWidget(self._runtime_library_title)
        library_hdr.addStretch()
        library_hdr.addWidget(self._runtime_library_target_lbl)
        library_layout.addLayout(library_hdr)
        self._runtime_library_search = QLineEdit()
        self._runtime_library_search.setPlaceholderText("Search downloaded models...")
        self._runtime_library_search.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG0}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
        self._runtime_library_search.textChanged.connect(lambda _=None: self._refresh_runtime_library())
        library_layout.addWidget(self._runtime_library_search)
        self._runtime_library_summary_lbl = QLabel("")
        self._runtime_library_summary_lbl.setWordWrap(True)
        self._runtime_library_summary_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt;")
        library_layout.addWidget(self._runtime_library_summary_lbl)
        self._runtime_library_host = QWidget()
        self._runtime_library_grid = QGridLayout(self._runtime_library_host)
        self._runtime_library_grid.setContentsMargins(0, 0, 0, 0)
        self._runtime_library_grid.setHorizontalSpacing(8)
        self._runtime_library_grid.setVerticalSpacing(8)
        library_layout.addWidget(self._runtime_library_host)
        rtl.addWidget(self._runtime_library_frame)

        self._runtime_summary_lbl = QLabel("")
        self._runtime_summary_lbl.setWordWrap(True)
        self._runtime_summary_lbl.setStyleSheet(f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        self._runtime_policy_lbl = QLabel("")
        self._runtime_policy_lbl.setWordWrap(True)
        self._runtime_policy_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        self._runtime_live_lbl = QLabel("Live lane evidence will appear here after the next /status poll.")
        self._runtime_live_lbl.setWordWrap(True)
        self._runtime_live_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        self._runtime_status_lbl = QLabel("Local runtime controls ready")
        self._runtime_status_lbl.setWordWrap(True)
        self._runtime_status_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
        rtl.addWidget(self._runtime_summary_lbl); rtl.addWidget(self._runtime_policy_lbl); rtl.addWidget(self._runtime_live_lbl); rtl.addWidget(self._runtime_status_lbl)
        root.addWidget(self._runtime_bar)

        self._route_bar = QFrame()
        self._route_bar.setStyleSheet(f"background-color: {T.BG0}; border-bottom: 1px solid {T.BORDER};")
        rbl = QVBoxLayout(self._route_bar)
        rbl.setContentsMargins(28, 10, 28, 10)
        rbl.setSpacing(8)
        row1 = QHBoxLayout(); row1.setSpacing(10)

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

        row2 = QHBoxLayout(); row2.setSpacing(10)
        row2.addWidget(QLabel("FALLBACK CHAIN"))
        self._fallback_chain_input = QLineEdit("")
        self._fallback_chain_input.textChanged.connect(lambda _=None: self._refresh_route_summary())
        self._fallback_chain_input.setMinimumWidth(620)
        self._fallback_chain_input.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
        self._apply_routes_btn = QPushButton("APPLY ROUTES")
        self._apply_routes_btn.setFixedHeight(28)
        self._apply_routes_btn.clicked.connect(self._apply_routes)
        row2.addWidget(self._fallback_chain_input); row2.addWidget(self._apply_routes_btn); row2.addStretch()
        rbl.addLayout(row2)

        self._route_status_lbl = QLabel("Route strategy ready")
        self._route_status_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")
        self._route_summary_lbl = QLabel("")
        self._route_summary_lbl.setWordWrap(True)
        self._route_summary_lbl.setStyleSheet(f"color: {T.PRIMARY_DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        self._route_evidence_lbl = QLabel("")
        self._route_evidence_lbl.setWordWrap(True)
        self._route_evidence_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        rbl.addWidget(self._route_status_lbl); rbl.addWidget(self._route_summary_lbl); rbl.addWidget(self._route_evidence_lbl)

        row3 = QHBoxLayout(); row3.setSpacing(10)
        row3.addWidget(QLabel("WHY GUPPY CHOSE THIS"))
        self._route_mode_cb = QComboBox()
        self._route_mode_cb.addItems(list(LAUNCHER_MODES_DISPLAY))
        self._route_mode_cb.setFixedWidth(150)
        self._route_mode_cb.currentTextChanged.connect(lambda _=None: self._refresh_route_preview())
        self._route_input = QLineEdit()
        self._route_input.setPlaceholderText("Type a sample request to preview task classification and route choice")
        self._route_input.textChanged.connect(lambda _=None: self._refresh_route_preview())
        self._route_input.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 6px 8px;")
        row3.addWidget(self._route_mode_cb); row3.addWidget(self._route_input, stretch=1)
        rbl.addLayout(row3)

        self._route_preview_lbl = QLabel("Route preview appears here once you type a sample request.")
        self._route_preview_lbl.setWordWrap(True)
        self._route_preview_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
        rbl.addWidget(self._route_preview_lbl)
        root.addWidget(self._route_bar)

        self._library_scroll = QScrollArea()
        self._library_scroll.setWidgetResizable(True)
        self._library_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._library_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._content = QWidget()
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(28, 24, 28, 24)
        self._grid.setSpacing(16)
        self._grid.setColumnStretch(0, 1); self._grid.setColumnStretch(1, 1)
        self._local_header = _ColumnHeader("ON THIS PC")
        self._grid.addWidget(self._local_header, 0, 0)
        self._cloud_header = _ColumnHeader("CLOUD OPTIONS")
        self._grid.addWidget(self._cloud_header, 0, 1)
        self._local_host = QWidget()
        self._local_layout = QVBoxLayout(self._local_host)
        self._local_layout.setContentsMargins(0, 0, 0, 0)
        self._local_layout.setSpacing(16)
        self._local_sections: dict[str, QWidget] = {}
        self._local_section_layouts: dict[str, QVBoxLayout] = {}
        self._local_section_cards: dict[str, list[_ModelCard]] = {
            "recommended": [],
            "installed": [],
            "advanced": [],
        }
        for key, title, subtitle in [
            ("recommended", "RECOMMENDED", "Start here for the best everyday fit on this PC."),
            ("installed", "INSTALLED ON THIS PC", "Other local models you can still use this session."),
            ("advanced", "ADVANCED / EXPERIMENTAL", "More specialized or heavier picks when you want to explore."),
        ]:
            section = QFrame()
            if key == "recommended":
                section.setStyleSheet(
                    f"background-color: {T.BG1}; border: 1px solid {T.PRIMARY};"
                )
            else:
                section.setStyleSheet(
                    f"background-color: {T.BG1}; border: 1px solid {T.BORDER};"
                )
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(14, 12, 14, 14)
            section_layout.setSpacing(10)
            header = _ColumnHeader(title)
            if key == "recommended":
                header.setStyleSheet(
                    f"color: {T.PRIMARY}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; "
                    f"font-weight: bold; letter-spacing: 2px; border-bottom: 1px solid {T.PRIMARY}; padding-bottom: 4px;"
                )
            section_layout.addWidget(header)
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setWordWrap(True)
            subtitle_lbl.setStyleSheet(
                f"color: {T.TEXT if key == 'recommended' else T.DIM}; font-family: '{T.FF_BODY}'; "
                f"font-size: {T.FS_SMALL}pt;"
            )
            section_layout.addWidget(subtitle_lbl)
            cards_host = QWidget()
            cards_layout = QVBoxLayout(cards_host)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(16)
            section_layout.addWidget(cards_host)
            self._local_sections[key] = section
            self._local_section_layouts[key] = cards_layout
            self._local_layout.addWidget(section)
            section.setVisible(False)
        for i, model in enumerate(CLOUD_MODELS):
            card = _ModelCard(model["name"], model["display"], model["tier"], model["context"], model["note"])
            card.set_active.connect(self._on_model_selected)
            self._cloud_cards.append(card)
        self._cloud_host = QWidget()
        self._cloud_layout = QVBoxLayout(self._cloud_host)
        self._cloud_layout.setContentsMargins(0, 0, 0, 0)
        self._cloud_layout.setSpacing(16)
        for card in self._cloud_cards:
            self._cloud_layout.addWidget(card)
        self._cloud_layout.addStretch(1)
        self._local_placeholder = QLabel("Fetching local models...")
        self._local_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._local_placeholder.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; letter-spacing: 1px; padding: 24px;")
        self._local_layout.addWidget(self._local_placeholder)
        self._local_layout.addStretch(1)
        self._grid.addWidget(self._local_host, 1, 0)
        self._grid.addWidget(self._cloud_host, 1, 1)
        self._library_scroll.setWidget(self._content)
        root.addWidget(self._library_scroll)

    @staticmethod
    def _normalize_runtime_backend(value: str) -> str:
        return "lemonade" if str(value or "").strip().lower() == "lemonade" else "ollama"

    def _set_runtime_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._runtime_status_lbl.setText(text)
        self._runtime_status_lbl.setStyleSheet(f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")

    def _runtime_settings_payload(self) -> dict[str, Any]:
        return {
            "local_runtime_backend": self._local_runtime_backend,
            "lemonade_base_url": self._lemonade_base_url_input.text().strip() or _DEFAULT_LEMONADE_BASE_URL,
            **{k: combo.currentText().strip() for k, combo in self._lemonade_role_inputs.items()},
        }

    def _load_runtime_settings(self) -> None:
        settings = load_app_settings() if _RUNTIME_SETTINGS_BACKEND else {}
        self._local_runtime_backend = self._normalize_runtime_backend(str(settings.get("local_runtime_backend", os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama"))))
        self._saved_runtime_backend = self._local_runtime_backend
        self._runtime_backend_cb.blockSignals(True); self._runtime_backend_cb.setCurrentText(self._local_runtime_backend.upper()); self._runtime_backend_cb.blockSignals(False)
        self._lemonade_base_url_input.setText(str(settings.get("lemonade_base_url", os.environ.get("GUPPY_LEMONADE_BASE_URL", _DEFAULT_LEMONADE_BASE_URL)) or _DEFAULT_LEMONADE_BASE_URL).strip())
        for field_name, _label in _LEMONADE_ROLE_FIELDS:
            combo = self._lemonade_role_inputs[field_name]
            value = str(settings.get(field_name, os.environ.get(f"GUPPY_{field_name.upper()}", "")) or "").strip()
            combo.clear()
            if value:
                combo.addItem(value)
                combo.setCurrentText(value)
        self._update_runtime_controls()

    def _update_runtime_controls(self) -> None:
        is_lemonade = self._local_runtime_backend == "lemonade"
        self._active_runtime_lbl.setText(f"LOCAL ENGINE: {self._local_runtime_backend.upper()}")
        self._lemonade_base_url_input.setEnabled(is_lemonade)
        for combo in self._lemonade_role_inputs.values():
            combo.setEnabled(is_lemonade)
        self._runtime_library_frame.setVisible(is_lemonade)
        self._refresh_runtime_summary()
        self._refresh_runtime_library()

    def _set_page_mode(self, mode: str) -> None:
        runtime_mode = str(mode or "").strip().lower() == "runtime"
        self._runtime_bar.setVisible(runtime_mode)
        self._route_bar.setVisible(runtime_mode)
        self._library_summary_frame.setVisible(not runtime_mode)
        self._library_scroll.setVisible(not runtime_mode)
        self._refresh_library_summary()

    def _available_local_model_names(self) -> list[str]:
        return [card._model_name for card in self._local_cards]

    @staticmethod
    def _normalize_policy_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
        return payload if isinstance(payload, dict) else {}

    def _load_local_llm_policy(self) -> dict[str, Any]:
        if not _LOCAL_LLM_MANIFEST_BACKEND:
            return {}
        try:
            return self._normalize_policy_snapshot(get_local_llm_policy_summary(load_local_llm_manifest()))
        except Exception:
            return {}

    def _render_runtime_policy(self) -> None:
        policy = self._normalize_policy_snapshot(self._policy_snapshot)
        if not policy:
            self._runtime_policy_lbl.setText("Policy view unavailable. Launcher will fall back to live runtime evidence only.")
            self._runtime_policy_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
            return
        runtime_baseline = str(policy.get("runtime_baseline", "ollama") or "ollama").strip().upper()
        memory_baseline = str(policy.get("memory_baseline", "semantic-sqlite") or "semantic-sqlite").strip()
        daily = str(policy.get("daily_model_promotion_candidate", "") or "").strip()
        heavy = str(policy.get("heavy_model_candidate", "") or "").strip()
        rejected = [str(item).strip() for item in policy.get("daily_lane_rejected_models", []) if str(item).strip()]
        challengers = [str(item).strip().upper() for item in policy.get("runtime_challenger_ids", []) if str(item).strip()]
        lines = [
            f"FINALIZED POLICY: runtime baseline {runtime_baseline} | daily lane candidate {daily or 'unset'} | heavy fallback {heavy or 'unset'}",
            f"Memory baseline: {memory_baseline}",
        ]
        if rejected:
            lines.append("Daily-lane rejects on this machine: " + ", ".join(rejected))
        if challengers:
            lines.append("Runtime challengers only: " + ", ".join(challengers))
        if self._local_runtime_backend != "ollama":
            lines.append("Current editor selection is a challenger runtime. Save it only if you are intentionally testing the opt-in lane.")
        self._runtime_policy_lbl.setText("\n".join(lines))
        self._runtime_policy_lbl.setStyleSheet(f"color: {T.TEXT}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")

    def _refresh_runtime_summary(self) -> None:
        names = self._available_local_model_names()
        pending_save = self._local_runtime_backend != self._saved_runtime_backend
        if self._local_runtime_backend == "lemonade":
            mapped = [f"{label.lower()} -> {self._lemonade_role_inputs[field_name].currentText().strip()}" for field_name, label in _LEMONADE_ROLE_FIELDS if self._lemonade_role_inputs[field_name].currentText().strip()]
            text = "Lemonade is opt-in for the local lane. Map Guppy's role aliases to downloaded Lemonade model ids here."
            text += "\nCurrent Lemonade mapping: " + (" | ".join(mapped) if mapped else "none saved yet")
            if names:
                text += f"\nDownloaded Lemonade models visible now: {', '.join(names[:6])}"
        else:
            text = "Ollama remains the default local runtime. Local cards reflect direct Ollama tags, and the Lemonade mapping controls wake up when you switch runtimes."
            if names:
                text += f"\nVisible Ollama tags: {', '.join(names[:6])}"
        text += f"\nSaved local lane: {self._saved_runtime_backend.upper()}"
        if pending_save:
            text += f" | editor selection pending save: {self._local_runtime_backend.upper()}"
        self._runtime_summary_lbl.setText(text)
        self._render_runtime_policy()
        self._render_runtime_evidence()
        self._refresh_library_summary()

    def _refresh_library_summary(self) -> None:
        if not hasattr(self, "_library_summary_lbl"):
            return
        policy = self._normalize_policy_snapshot(self._policy_snapshot)
        daily = str(policy.get("daily_model_promotion_candidate", "") or "").strip() or self._active_model
        heavy = str(policy.get("heavy_model_candidate", "") or "").strip() or "none set"
        local_count = len(self._local_cards)
        advanced_count = len(self._local_section_cards.get("advanced", []))
        runtime_name = self._saved_runtime_backend.upper()
        selected_name = self._active_model or "unset"
        self._library_summary_lbl.setText(
            f"Recommended default: {daily} for everyday use. Heavier local option: {heavy} when you want a deeper local pass. "
            f"This session is using {selected_name} on {runtime_name}. "
            f"{local_count} local models are installed on this PC"
            + (f", with {advanced_count} advanced picks kept in their own section." if advanced_count else ".")
        )

    def _apply_library_filter(self) -> None:
        if not hasattr(self, "_library_search"):
            return
        query = self._library_search.text().strip().lower()
        local_matches = 0
        cloud_matches = 0
        section_matches = {key: 0 for key in self._local_sections}
        for card in self._local_cards:
            match = card.matches_query(query)
            card.setVisible(match)
            local_matches += int(match)
            section_matches[getattr(card, "_library_section", "installed")] += int(match)
        for card in self._cloud_cards:
            match = card.matches_query(query)
            card.setVisible(match)
            cloud_matches += int(match)
        for key, section in self._local_sections.items():
            section.setVisible(section_matches.get(key, 0) > 0)
        if self._local_placeholder is not None:
            self._local_placeholder.setVisible(not self._local_cards)
        if query:
            self._library_hint_lbl.setText(
                f"Showing {local_matches} local and {cloud_matches} cloud matches. Open Runtime only if you want to change the local engine or advanced routing."
            )
        else:
            self._library_hint_lbl.setText(
                "Pick the model Guppy should use for this session. Open Runtime only if you want to change the local engine or advanced routing."
            )

    def _local_model_section(self, model_name: str) -> str:
        normalized = _normalized_model_name(model_name)
        policy = self._normalize_policy_snapshot(self._policy_snapshot)
        daily = _normalized_model_name(policy.get("daily_model_promotion_candidate", ""))
        heavy = _normalized_model_name(policy.get("heavy_model_candidate", ""))
        rejected = {
            _normalized_model_name(item)
            for item in policy.get("daily_lane_rejected_models", [])
            if _normalized_model_name(item)
        }
        advanced_tokens = ("experimental", "preview", "alpha", "beta", "test", "canary")
        if normalized in rejected or any(token in normalized for token in advanced_tokens):
            return "advanced"
        if normalized in {daily, heavy}:
            return "recommended"
        if normalized == _normalized_model_name(self._active_model) and normalized not in rejected:
            return "recommended"
        return "installed"

    def _rebuild_local_sections(self) -> None:
        for key, cards in self._local_section_cards.items():
            layout = self._local_section_layouts.get(key)
            if layout is None:
                continue
            for card in cards:
                layout.removeWidget(card)
            self._local_section_cards[key] = []
        for card in self._local_cards:
            section = self._local_model_section(card._model_name)
            card._library_section = section
            card.set_recommended(section == "recommended")
            self._local_section_layouts[section].addWidget(card)
            self._local_section_cards[section].append(card)

    def _render_runtime_evidence(self) -> None:
        snapshot = self._status_snapshot if isinstance(self._status_snapshot, dict) else {}
        runtime = snapshot.get("local_runtime", {}) if isinstance(snapshot, dict) else {}
        pending_save = self._local_runtime_backend != self._saved_runtime_backend
        if not isinstance(runtime, dict) or not runtime:
            waiting = f"Live lane evidence: waiting for /status. Saved runtime: {self._saved_runtime_backend.upper()}."
            if pending_save:
                waiting += f" Editor selection: {self._local_runtime_backend.upper()} (unsaved)."
            self._runtime_live_lbl.setText(waiting)
            self._runtime_live_lbl.setStyleSheet(f"color: {T.DIM}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")
            return

        backend = self._normalize_runtime_backend(str(runtime.get("backend", self._saved_runtime_backend)))
        state = str(runtime.get("state", "unknown") or "unknown").upper()
        detail = str(runtime.get("detail", "") or "").strip()
        requested_model = str(runtime.get("requested_model", "") or "").strip()
        resolved_model = str(runtime.get("resolved_model", "") or "").strip()
        base_url = str(runtime.get("base_url", "") or "").strip()
        tool_loop = str(runtime.get("tool_loop", "") or "").strip()
        available_roles = [str(item).strip().upper() for item in runtime.get("available_roles", []) if str(item).strip()]
        missing_roles = [str(item).strip().upper() for item in runtime.get("missing_roles", []) if str(item).strip()]
        style_color = T.GREEN if state == "READY" else T.PRIMARY if state == "PARTIAL" else T.ERROR

        lines = [
            f"LIVE LANE: {state} | server runtime {backend.upper()} | saved runtime {self._saved_runtime_backend.upper()}",
        ]
        if pending_save:
            lines[0] += f" | editor selection {self._local_runtime_backend.upper()} (unsaved)"
        if backend != self._saved_runtime_backend:
            lines.append("Server runtime does not match the saved launcher choice yet.")
        if detail:
            lines.append(detail)
        resolved_bits = []
        if requested_model:
            resolved_bits.append(f"requested {requested_model}")
        if resolved_model:
            resolved_bits.append(f"resolved {resolved_model}")
        if tool_loop:
            resolved_bits.append(f"tool loop {tool_loop}")
        if base_url:
            resolved_bits.append(f"endpoint {base_url}")
        if resolved_bits:
            lines.append("Live runtime details: " + " | ".join(resolved_bits))
        if available_roles:
            lines.append("Available mapped roles: " + ", ".join(available_roles))
        if missing_roles:
            lines.append("Missing mapped roles: " + ", ".join(missing_roles))

        self._runtime_live_lbl.setText("\n".join(lines))
        self._runtime_live_lbl.setStyleSheet(f"color: {style_color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; background-color: {T.BG1}; border: 1px solid {T.BORDER}; padding: 8px;")

    @staticmethod
    def _set_combo_items_preserve_text(combo: QComboBox, options: list[str], current: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for option in options:
            combo.addItem(option)
        if current and combo.findText(current) < 0:
            combo.addItem(current)
        if current:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def _sync_runtime_mapping_options(self) -> None:
        names = self._available_local_model_names()
        for _field_name, combo in self._lemonade_role_inputs.items():
            self._set_combo_items_preserve_text(combo, names, combo.currentText().strip())
        self._refresh_runtime_summary()
        self._refresh_runtime_library()

    def _set_selected_runtime_role(self, field_name: str) -> None:
        runtime_library_set_selected_runtime_role(self, field_name, _LEMONADE_ROLE_FIELDS)

    def _assign_runtime_model(self, model_name: str) -> None:
        runtime_library_assign_runtime_model(self, model_name)

    def _refresh_runtime_library(self) -> None:
        runtime_library_refresh_runtime_library(self)

    def _on_runtime_backend_changed(self, text: str) -> None:
        self._local_runtime_backend = self._normalize_runtime_backend(text)
        self._update_runtime_controls()
        self._refresh()

    def _save_runtime_settings(self) -> None:
        if not _RUNTIME_SETTINGS_BACKEND:
            self._set_runtime_status("Runtime settings backend unavailable", ok=False)
            return
        payload = self._runtime_settings_payload()
        try:
            save_app_settings(payload)
            merged = apply_settings_to_env(payload)
            self._local_runtime_backend = self._normalize_runtime_backend(str(merged.get("local_runtime_backend", self._local_runtime_backend)))
            self._saved_runtime_backend = self._local_runtime_backend
            self._update_runtime_controls()
            self._set_runtime_status(f"Saved local runtime: {self._local_runtime_backend.upper()}", ok=True)
            self.runtime_settings_saved.emit(dict(merged))
        except Exception as exc:
            self._set_runtime_status(f"Runtime save failed: {exc}", ok=False)

    def _refresh(self) -> None:
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("FETCHING...")
        self._fetch_thread = _LocalRuntimeFetch(self._local_runtime_backend, self._lemonade_base_url_input.text().strip(), self)
        self._fetch_thread.finished.connect(self._on_local_result)
        self._fetch_thread.start()

    def _on_local_result(self, payload: dict[str, Any]) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("REFRESH")
        backend = self._normalize_runtime_backend(str(payload.get("backend", self._local_runtime_backend)))
        models = payload.get("models", [])
        error = str(payload.get("error", "") or "").strip()
        for card in self._local_cards:
            section = getattr(card, "_library_section", "installed")
            section_layout = self._local_section_layouts.get(section)
            if section_layout is not None:
                section_layout.removeWidget(card)
            card.deleteLater()
        self._local_cards.clear()
        for key in self._local_section_cards:
            self._local_section_cards[key] = []
        if self._local_placeholder:
            self._local_placeholder.setVisible(False)
        if not isinstance(models, list) or not models:
            text = "No local models found.\n" + ("Pull a Lemonade GGUF model and click REFRESH." if backend == "lemonade" else "Start Ollama and click REFRESH.")
            self._local_placeholder.setText(text)
            self._local_placeholder.setVisible(True)
            for section in self._local_sections.values():
                section.setVisible(False)
            self._set_runtime_status(f"{backend.upper()} library unavailable: {error}" if error else f"{backend.upper()} library is empty", ok=not bool(error))
            self._sync_runtime_mapping_options()
            self._apply_library_filter()
            return
        for i, item in enumerate(models):
            if not isinstance(item, dict):
                continue
            card = _ModelCard(str(item.get("name", "unknown")), str(item.get("display", item.get("name", "unknown"))), "LOCAL", str(item.get("context", "-") or "-"), str(item.get("note", "") or ""), int(item.get("size", 0) or 0))
            card.mark_active(card._model_name == self._active_model)
            card.set_active.connect(self._on_model_selected)
            self._local_cards.append(card)
        self._local_placeholder.setVisible(False)
        self._rebuild_local_sections()
        self._sync_runtime_mapping_options()
        self._set_runtime_status(f"{backend.upper()} library refreshed", ok=True)
        self._apply_library_filter()

    def _on_model_selected(self, name: str) -> None:
        self._active_model = name
        self._active_lbl.setText(f"CURRENT MODEL: {name.upper()}")
        os.environ["GUPPY_LOCAL_MODEL"] = name
        for card in self._local_cards:
            card.mark_active(card._model_name == name)
        self._rebuild_local_sections()
        self._apply_library_filter()
        self.model_selected.emit(name)
        self._refresh_library_summary()

    def set_status_snapshot(self, payload: dict[str, Any]) -> None:
        self._status_snapshot = payload if isinstance(payload, dict) else {}
        runtime = self._status_snapshot.get("local_runtime", {}) if isinstance(self._status_snapshot, dict) else {}
        live_policy = runtime.get("policy", {}) if isinstance(runtime, dict) else {}
        if isinstance(live_policy, dict) and live_policy:
            self._policy_snapshot = live_policy
        else:
            self._policy_snapshot = self._load_local_llm_policy()
        self._render_runtime_policy()
        self._render_runtime_evidence()
        self._refresh_library_summary()

    def _set_route_status(self, text: str, ok: bool = True) -> None:
        color = T.GREEN if ok else T.ERROR
        self._route_status_lbl.setText(text)
        self._route_status_lbl.setStyleSheet(f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px;")

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
                cb.clear(); cb.addItems(self._route_options)
            routes = self._provider_registry.get("routes", {}) if isinstance(self._provider_registry, dict) else {}
            if isinstance(routes, dict):
                self._set_combo_to_text(self._simple_route_cb, str(routes.get("simple", "")))
                self._set_combo_to_text(self._complex_route_cb, str(routes.get("complex", "")))
                self._set_combo_to_text(self._teaching_route_cb, str(routes.get("teaching", "")))
                fallback = routes.get("fallback_chain", [])
                if isinstance(fallback, list):
                    self._fallback_chain_input.setText(", ".join(str(item).strip() for item in fallback if str(item).strip()))
            self._refresh_route_summary(); self._refresh_route_preview(); self._set_route_status("Route strategy loaded", ok=True)
        except Exception as exc:
            self._set_route_status(f"Route load failed: {exc}", ok=False)

    @staticmethod
    def _route_targets_from_registry(registry: dict[str, Any]) -> list[str]:
        options = []
        providers = registry.get("providers", []) if isinstance(registry, dict) else []
        for provider in providers if isinstance(providers, list) else []:
            if not isinstance(provider, dict):
                continue
            pid, models = provider.get("id"), provider.get("models", [])
            if not isinstance(pid, str) or not isinstance(models, list):
                continue
            for model in models:
                mid = model.get("id") if isinstance(model, dict) else None
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
            f"If the first choice is unavailable, Guppy falls back to {', '.join(self._friendly_route_target(item) for item in fallback) if fallback else 'the built-in defaults'}."
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
        summary = f"{task_type.capitalize()} work will start with {ModelsView._friendly_route_target(model or ModelsView._friendly_route_name(route))}."
        if executor:
            summary += f" Guppy will execute it through {executor.upper()}."
        details = ([f"Backup: {ModelsView._friendly_route_target(backup)}"] if backup else []) + [f"Why: {reason}"]
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
            f"Local runtime {self._local_runtime_backend.upper()} {'heartbeat seen' if heartbeat else 'heartbeat missing'}",
            f"{local_count} local model{'s' if local_count != 1 else ''} visible" if local_count else "local library not loaded yet",
        ]
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
        return "" if not latency or latency in {"-", "—"} else f"{latency} ms"

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
            return f"{'local' if provider.lower() == 'local' else provider.upper()} / {model}"
        return cls._friendly_route_name(raw)

    def _refresh_route_preview(self) -> None:
        sample = self._route_input.text().strip()
        if not sample:
            self._route_preview_lbl.setText("Route preview appears here once you type a sample request. Try the kind of question you would ask on Home.")
            return
        try:
            decision = resolve_ui_route(user_text=sample, mode=self._route_mode_cb.currentText().strip().lower(), api_key_available=bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()))
            self._route_preview_lbl.setText(self._describe_route_decision(decision) + "\n" + self._route_evidence_for_decision(decision))
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
            simple, complex_route, teaching = self._simple_route_cb.currentText().strip(), self._complex_route_cb.currentText().strip(), self._teaching_route_cb.currentText().strip()
            for label, value in [("simple", simple), ("complex", complex_route), ("teaching", teaching)]:
                if value not in valid_targets:
                    self._set_route_status(f"Invalid {label} target: {value}", ok=False)
                    return
            fallback = self._parse_fallback_chain(self._fallback_chain_input.text())
            invalid_fallback = [item for item in fallback if item not in (valid_targets | {"local/guppy"})]
            if invalid_fallback:
                self._set_route_status(f"Invalid fallback target: {invalid_fallback[0]}", ok=False)
                return
            routes = registry.setdefault("routes", {})
            registry["routes"] = routes if isinstance(routes, dict) else {}
            registry["routes"]["simple"] = simple
            registry["routes"]["complex"] = complex_route
            registry["routes"]["teaching"] = teaching
            registry["routes"]["fallback_chain"] = fallback
            errors = validate_provider_registry(registry)
            if errors:
                self._set_route_status(f"Provider registry invalid: {errors[0]}", ok=False)
                return
            save_provider_registry(registry)
            self._provider_registry = registry
            self._refresh_route_summary(); self._refresh_route_preview(); self._set_route_status("Route strategy saved", ok=True)
        except Exception as exc:
            self._set_route_status(f"Apply routes failed: {exc}", ok=False)
