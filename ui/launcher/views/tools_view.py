"""
ui/launcher/views/tools_view.py
AGENT TOOLS tab — instance-scoped capability catalog with clear boundaries.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QComboBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T

_INSTANCE_TOOL_CATALOG: list[dict[str, object]] = [
    {
        "key": "read_file",
        "name": "READ FILE",
        "category": "READ",
        "description": "Read source, docs, tests, and configuration files in the active instance context.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance", "read_only_instance"},
        "reason": "Safe read access for inspection and retrieval.",
        "dry_run": False,
    },
    {
        "key": "screenshot",
        "name": "SCREENSHOT",
        "category": "READ",
        "description": "Capture or inspect the current screen when the active instance needs visual context.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance", "read_only_instance"},
        "reason": "Observation-only capability.",
        "dry_run": False,
    },
    {
        "key": "query_instance",
        "name": "QUERY INSTANCE",
        "category": "QUERY",
        "description": "Send a bounded synchronous request to another configured instance and return the answer to Home.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance", "read_only_instance"},
        "reason": "Cross-instance coordination within the M2 bounded bridge.",
        "dry_run": False,
    },
    {
        "key": "debug_console",
        "name": "DEBUG CONSOLE",
        "category": "DEBUG",
        "description": "Inspect runtime state and developer diagnostics that are safe to expose to the current instance.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Available to trusted interactive instances only.",
        "dry_run": False,
    },
    {
        "key": "run_python",
        "name": "RUN PYTHON",
        "category": "CODE",
        "description": "Execute bounded Python snippets and return output back into the active transcript.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Requires code-execution permission.",
        "dry_run": True,
    },
    {
        "key": "write_file",
        "name": "WRITE FILE",
        "category": "WRITE",
        "description": "Write changes within approved workspace areas. Builder instances stay scoped to docs, tests, and config paths.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Write capability is blocked for read-only instances.",
        "dry_run": True,
    },
    {
        "key": "execute_command",
        "name": "EXECUTE COMMAND",
        "category": "WRITE",
        "description": "Run shell commands when the active instance is permitted to mutate or inspect the local environment.",
        "allowed_types": {"user_instance", "admin_instance"},
        "reason": "Reserved for higher-trust instances.",
        "dry_run": True,
    },
]


def _mono(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label


def _tool_allowed(tool: dict[str, object], instance_type: str) -> bool:
    allowed = tool.get("allowed_types", set())
    if not isinstance(allowed, set):
        return False
    return instance_type in allowed


class _ToolCard(QFrame):
    hint_requested = Signal(str)

    def __init__(self, tool: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = dict(tool)
        self._state = "ready"
        self._reason = ""
        self.setObjectName("agent_tool_card")
        self.setStyleSheet(
            f"QFrame#agent_tool_card {{ background-color: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self._name_lbl = QLabel(str(tool.get("name", "TOOL")))
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: 800;"
        )
        header.addWidget(self._name_lbl)
        header.addStretch()
        self._status_lbl = _mono("READY", T.GREEN, T.FS_TINY, True)
        header.addWidget(self._status_lbl)
        root.addLayout(header)

        self._desc_lbl = QLabel(str(tool.get("description", "")))
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        root.addWidget(self._desc_lbl)

        meta = QHBoxLayout()
        meta.addWidget(_mono(f"CATEGORY: {str(tool.get('category', 'READ')).upper()}", T.PRIMARY_DIM, T.FS_TINY, True))
        if bool(tool.get("dry_run", False)):
            meta.addSpacing(10)
            meta.addWidget(_mono("DRY-RUN READY", T.DIM, T.FS_TINY, True))
        meta.addStretch()
        root.addLayout(meta)

        self._scope_lbl = _mono("", T.DIM, T.FS_TINY)
        self._scope_lbl.setWordWrap(True)
        root.addWidget(self._scope_lbl)

        actions = QHBoxLayout()
        self._hint_btn = QPushButton("OPEN IN HOME")
        self._hint_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            f"QPushButton:disabled {{ color: {T.BORDER}; border-color: {T.BORDER}; }}"
        )
        self._hint_btn.clicked.connect(lambda: self.hint_requested.emit(str(self._tool.get("key", ""))))
        actions.addWidget(self._hint_btn)
        actions.addStretch()
        root.addLayout(actions)

    def apply_context(self, instance_name: str, instance_type: str) -> None:
        allowed = _tool_allowed(self._tool, instance_type)
        self._state = "ready" if allowed else "restricted"
        self._reason = str(self._tool.get("reason", "")).strip()
        if allowed:
            self._status_lbl.setText("READY")
            self._status_lbl.setStyleSheet(
                f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            self._scope_lbl.setText(
                f"Available to {instance_name} ({instance_type.replace('_', ' ')}). {self._reason}"
            )
            self._hint_btn.setEnabled(True)
        else:
            self._status_lbl.setText("RESTRICTED")
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            self._scope_lbl.setText(
                f"Blocked for {instance_name} ({instance_type.replace('_', ' ')}). {self._reason}"
            )
            self._hint_btn.setEnabled(False)

    @property
    def tool_key(self) -> str:
        return str(self._tool.get("key", ""))

    @property
    def category(self) -> str:
        return str(self._tool.get("category", "ALL")).upper()

    @property
    def search_blob(self) -> str:
        return " ".join(
            [
                str(self._tool.get("key", "")),
                str(self._tool.get("name", "")),
                str(self._tool.get("description", "")),
                str(self._tool.get("reason", "")),
            ]
        ).lower()

    @property
    def state(self) -> str:
        return self._state


class ToolsView(QWidget):
    tool_state_changed = Signal(str, bool)  # (tool_key, enabled)
    tool_hint_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_cards: dict[str, _ToolCard] = {}
        self._tool_states: dict[str, bool] = {}
        self._instance_name = "guppy-primary"
        self._instance_type = "user_instance"
        self._limits: dict[str, int] = {
            "configured": 1,
            "max_configured": 5,
            "active_runtime": 1,
            "max_active_runtime": 2,
        }

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(18)

        title = QLabel("Agent Tools")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;"
        )
        layout.addWidget(title)
        layout.addWidget(_mono("Tools this active instance can use. App recovery and diagnostics stay in APP MGMT.", T.DIM, T.FS_SMALL))

        self._context_lbl = _mono("ACTIVE INSTANCE: GUPPY-PRIMARY · USER INSTANCE", T.PRIMARY, T.FS_TINY, True)
        self._limits_lbl = _mono("Configured slots: 1 / 5 · Runtime-active slots: 1 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._context_lbl)
        layout.addWidget(self._limits_lbl)

        filters = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Find a tool...")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
            f"QLineEdit:focus {{ border-color: {T.PRIMARY}; }}"
        )
        self._search.textChanged.connect(self._apply_filters)
        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["ALL", "READ", "WRITE", "CODE", "QUERY", "DEBUG", "RESTRICTED"])
        self._filter_cb.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        self._filter_cb.currentTextChanged.connect(self._apply_filters)
        filters.addWidget(self._search, stretch=1)
        filters.addWidget(self._filter_cb)
        layout.addLayout(filters)

        banner = QFrame()
        banner.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(4)
        banner_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        banner_layout.addWidget(_mono("Agent Tools are instance-scoped. Restart, warmup, audit, and app diagnostics belong to APP MGMT.", T.DIM, T.FS_SMALL))
        layout.addWidget(banner)

        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(12)
        for tool in _INSTANCE_TOOL_CATALOG:
            card = _ToolCard(tool)
            card.hint_requested.connect(self.tool_hint_requested.emit)
            self._tool_cards[card.tool_key] = card
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()
        layout.addWidget(self._cards_host)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.set_instance_context({}, {})

    def set_instance_context(self, instance: dict[str, object], snapshot: dict[str, object] | None = None) -> None:
        name = str(instance.get("name", self._instance_name) or self._instance_name).strip() or "guppy-primary"
        instance_type = str(instance.get("type", self._instance_type) or self._instance_type).strip() or "user_instance"
        self._instance_name = name
        self._instance_type = instance_type
        limits = snapshot.get("limits", {}) if isinstance(snapshot, dict) else {}
        if isinstance(limits, dict):
            self._limits = {
                "configured": int(limits.get("configured", self._limits["configured"]) or self._limits["configured"]),
                "max_configured": int(limits.get("max_configured", self._limits["max_configured"]) or self._limits["max_configured"]),
                "active_runtime": int(limits.get("active_runtime", self._limits["active_runtime"]) or self._limits["active_runtime"]),
                "max_active_runtime": int(limits.get("max_active_runtime", self._limits["max_active_runtime"]) or self._limits["max_active_runtime"]),
            }
        self._context_lbl.setText(
            f"ACTIVE INSTANCE: {name.upper()} · {instance_type.replace('_', ' ').upper()}"
        )
        limits_text = (
            f"Configured slots: {self._limits['configured']} / {self._limits['max_configured']} · "
            f"Runtime-active slots: {self._limits['active_runtime']} / {self._limits['max_active_runtime']}"
        )
        if self._limits["configured"] >= self._limits["max_configured"]:
            limits_text += " · CONFIG CAP REACHED"
        if self._limits["active_runtime"] >= self._limits["max_active_runtime"]:
            limits_text += " · COLLABORATOR CAP REACHED"
        self._limits_lbl.setText(limits_text)
        for card in self._tool_cards.values():
            card.apply_context(name, instance_type)
        self._apply_filters()

    def _apply_filters(self) -> None:
        category = self._filter_cb.currentText().strip().upper()
        query = self._search.text().strip().lower()
        for card in self._tool_cards.values():
            matches_query = not query or query in card.search_blob
            matches_category = (
                category == "ALL"
                or (category == "RESTRICTED" and card.state == "restricted")
                or card.category == category
            )
            card.setVisible(matches_query and matches_category)

    def get_states(self) -> dict[str, bool]:
        return dict(self._tool_states)

    def set_states(self, states: dict[str, bool]) -> None:
        self._tool_states = {str(k): bool(v) for k, v in states.items()}

    def current_tool_states(self) -> dict[str, str]:
        return {key: card.state for key, card in self._tool_cards.items()}
