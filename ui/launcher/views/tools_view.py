"""
ui/launcher/views/tools_view.py
AGENT TOOLS tab - instance-scoped capability catalog with clear boundaries.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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

from ..components import BuilderTaskPanel
from .. import tokens as T

try:
    from utils.instance_capabilities import auth_mode_label, check_instance_tool_permission, required_capability_for_tool
except ImportError:
    def auth_mode_label(mode: str) -> str:
        return str(mode or "runtime default").strip() or "runtime default"

    def required_capability_for_tool(tool_name: str) -> str:
        del tool_name
        return "execute"

    def check_instance_tool_permission(
        tool_name: str,
        *,
        instance_name: str | None = None,
        instance_type: str | None = None,
        config_path=None,
    ) -> tuple[bool, str, dict]:
        del tool_name, instance_name, instance_type, config_path
        return False, "policy unavailable", {}


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
        "reason": "Available to trusted interactive workspaces only.",
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
        "description": "Write changes within approved workspace areas. Builder workspaces stay scoped to docs, tests, and config paths.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Write capability is blocked for read-only workspaces.",
        "dry_run": True,
    },
    {
        "key": "execute_command",
        "name": "EXECUTE COMMAND",
        "category": "WRITE",
        "description": "Run shell commands when the active instance is permitted to mutate or inspect the local environment.",
        "allowed_types": {"user_instance", "admin_instance"},
        "reason": "Reserved for higher-trust workspaces.",
        "dry_run": True,
    },
    {
        "key": "send_email",
        "name": "GMAIL",
        "category": "CONNECTOR",
        "description": "Send or clean up Gmail from the workspace-bound account when machine auth and workspace binding both allow it.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Connector access now respects workspace bindings, account choice, and machine-level auth.",
        "dry_run": False,
    },
    {
        "key": "calendar_events",
        "name": "CALENDAR",
        "category": "CONNECTOR",
        "description": "Read upcoming calendar events from the workspace-bound calendar scope.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance", "read_only_instance"},
        "reason": "Calendar reads stay subject to workspace connector policy and host auth readiness.",
        "dry_run": False,
    },
    {
        "key": "spotify_current",
        "name": "SPOTIFY",
        "category": "CONNECTOR",
        "description": "Inspect or control Spotify when the workspace binding and machine auth are ready.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Media connectors now have the same workspace governance story as file and code tools.",
        "dry_run": False,
    },
    {
        "key": "youtube_search",
        "name": "YOUTUBE",
        "category": "CONNECTOR",
        "description": "Search or open YouTube through the workspace connector binding and machine auth posture.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance", "read_only_instance"},
        "reason": "YouTube connector access is now visible through the same workspace policy surface.",
        "dry_run": False,
    },
    {
        "key": "crm_upsert_contact",
        "name": "CRM",
        "category": "CONNECTOR",
        "description": "Prepare CRM writes against the workspace-bound provider when the provider configuration is ready.",
        "allowed_types": {"user_instance", "admin_instance", "builder_instance"},
        "reason": "Business connectors must now pass workspace binding, provider, and auth checks.",
        "dry_run": True,
    },
    {
        "key": "voip_place_call",
        "name": "VOIP",
        "category": "CONNECTOR",
        "description": "Prepare or place outbound calls through the workspace-bound VoIP provider.",
        "allowed_types": {"user_instance", "admin_instance"},
        "reason": "VoIP stays restricted to higher-trust workspaces and now shows connector policy reasons explicitly.",
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


def _workspace_type_label(instance_type: str) -> str:
    value = str(instance_type or "user_instance").strip().lower()
    return {
        "user_instance": "daily workspace",
        "builder_instance": "builder collaborator",
        "read_only_instance": "read-only reference",
        "admin_instance": "operations workspace",
    }.get(value, value.replace("_", " ").strip() or "workspace")


def _render_scope_list(items: list[str], label: str) -> str:
    if not items:
        return f"{label}: inherited"
    preview = ", ".join(item.replace("_", " ") for item in items[:3])
    if len(items) > 3:
        preview += f", +{len(items) - 3} more"
    return f"{label}: {preview}"


def _render_endpoint_scope(allow: list[str], block: list[str]) -> str:
    if not allow and not block:
        return "Endpoint filters: inherited"
    parts: list[str] = []
    if allow:
        parts.append(_render_scope_list(allow, "allow"))
    if block:
        parts.append(_render_scope_list(block, "block"))
    return "Endpoint filters: " + " | ".join(parts)


class _ToolCard(QFrame):
    hint_requested = Signal(str)

    def __init__(self, tool: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = dict(tool)
        self._state = "ready"
        self._reason = ""
        self._details_visible = False
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
        meta.addWidget(_mono(f"TYPE: {str(tool.get('category', 'READ')).upper()}", T.PRIMARY_DIM, T.FS_TINY, True))
        if bool(tool.get("dry_run", False)):
            meta.addSpacing(10)
            meta.addWidget(_mono("SET UP FIRST", T.DIM, T.FS_TINY, True))
        meta.addStretch()
        root.addLayout(meta)

        self._scope_lbl = _mono("", T.DIM, T.FS_TINY)
        self._scope_lbl.setWordWrap(True)
        root.addWidget(self._scope_lbl)
        self._policy_lbl = _mono("", T.PRIMARY_DIM, T.FS_TINY)
        self._policy_lbl.setWordWrap(True)
        root.addWidget(self._policy_lbl)
        self._guard_lbl = _mono("", T.DIM, T.FS_TINY)
        self._guard_lbl.setWordWrap(True)
        root.addWidget(self._guard_lbl)

        actions = QHBoxLayout()
        self._hint_btn = QPushButton("PRIME HOME")
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
        self.set_details_visible(False)

    def set_details_visible(self, visible: bool) -> None:
        self._details_visible = bool(visible)
        self._scope_lbl.setVisible(self._details_visible)
        self._policy_lbl.setVisible(self._details_visible)
        self._guard_lbl.setVisible(self._details_visible)

    def apply_context(self, instance_name: str, instance_type: str) -> None:
        allowed_by_type = _tool_allowed(self._tool, instance_type)
        policy_allowed, policy_reason, permissions = check_instance_tool_permission(
            self.tool_key,
            instance_name=instance_name,
            instance_type=instance_type,
        )
        allowed = allowed_by_type and policy_allowed
        self._state = "ready" if allowed else "restricted"
        self._reason = str(self._tool.get("reason", "")).strip()
        capability = required_capability_for_tool(self.tool_key)
        auth_mode = auth_mode_label(str(permissions.get("_auth_mode", "runtime_default") or "runtime_default")).upper()
        tool_allow = [str(item) for item in permissions.get("_tool_allow", []) if str(item).strip()]
        tool_block = [str(item) for item in permissions.get("_tool_block", []) if str(item).strip()]
        endpoint_allow = [str(item) for item in permissions.get("_endpoint_allow", []) if str(item).strip()]
        endpoint_block = [str(item) for item in permissions.get("_endpoint_block", []) if str(item).strip()]
        policy_note = str(permissions.get("_policy_note", "") or "").strip()
        resolved_endpoint = str(permissions.get("_resolved_endpoint", "") or "").strip()
        connector = str(permissions.get("_connector", "workspace_tool") or "workspace_tool").replace("_", " ").upper()
        connector_auth_state = str(permissions.get("_connector_auth_state", "unknown") or "unknown").upper()
        connector_auth_detail = str(permissions.get("_connector_auth_detail", "") or "").strip()
        connector_auth_source = str(permissions.get("_connector_auth_source", "none") or "none").upper()
        connector_action = str(permissions.get("_connector_action", "") or "").strip().replace("_", " ").upper()
        connector_binding_enabled = bool(permissions.get("_connector_binding_enabled", False))
        connector_binding_inherited = bool(permissions.get("_connector_binding_inherited", False))
        connector_binding_account = str(permissions.get("_connector_binding_account", "") or "").strip()
        connector_binding_provider = str(permissions.get("_connector_binding_provider", "") or "").strip()
        connector_binding_action_allow = [str(item) for item in permissions.get("_connector_binding_action_allow", []) if str(item).strip()]
        connector_binding_action_block = [str(item) for item in permissions.get("_connector_binding_action_block", []) if str(item).strip()]
        connector_binding_endpoint_allow = [str(item) for item in permissions.get("_connector_binding_endpoint_allow", []) if str(item).strip()]
        connector_binding_endpoint_block = [str(item) for item in permissions.get("_connector_binding_endpoint_block", []) if str(item).strip()]
        connector_binding_note = str(permissions.get("_connector_binding_note", "") or "").strip()
        policy_reason_code = str(permissions.get("_policy_reason_code", "") or "").strip().lower()
        workspace_gate = "Workspace/role check allows" if allowed_by_type else "Workspace/role check blocks"
        runtime_gate = "governance policy allows" if policy_allowed else "governance policy blocks"
        policy_text = f"Needs {capability} access. {workspace_gate}; {runtime_gate}. Sign-in mode: {auth_mode}."
        if resolved_endpoint:
            policy_text += f" Endpoint scope: {resolved_endpoint}."
        if bool(self._tool.get("dry_run", False)):
            policy_text += " Home prompting only appears when the real action is allowed."
        self._guard_lbl.setText(policy_text)
        governance_text = " | ".join(
            [
                f"SIGN-IN: {auth_mode}",
                f"CONNECTION: {connector}",
                f"CONNECTION STATUS: {connector_auth_state}",
                f"SOURCE: {connector_auth_source}",
                f"BINDING: {'enabled' if connector_binding_enabled else 'not bound'}"
                + (" (inherited)" if connector_binding_inherited else ""),
                f"ACTION MODE: {connector_action or 'DEFAULT'}",
                _render_scope_list(tool_allow, "Allowed"),
                _render_scope_list(tool_block, "Blocked"),
                _render_endpoint_scope(endpoint_allow, endpoint_block),
            ]
        )
        if connector_binding_account:
            governance_text += f" | Account: {connector_binding_account}"
        if connector_binding_provider:
            governance_text += f" | Provider: {connector_binding_provider}"
        if connector_binding_action_allow or connector_binding_action_block:
            governance_text += (
                f" | Connection actions: {_render_scope_list(connector_binding_action_allow, 'allow')}"
                f" | {_render_scope_list(connector_binding_action_block, 'block')}"
            )
        if connector_binding_endpoint_allow or connector_binding_endpoint_block:
            governance_text += (
                " | Connector endpoint filters: "
                + _render_endpoint_scope(connector_binding_endpoint_allow, connector_binding_endpoint_block).replace("Endpoint filters: ", "")
            )
        if connector_auth_detail:
            governance_text += f" | Sign-in detail: {connector_auth_detail}"
        if connector_binding_note:
            governance_text += f" | Binding note: {connector_binding_note}"
        if policy_note:
            governance_text += f" | Note: {policy_note}"
        self._policy_lbl.setText(governance_text)
        if allowed:
            self._status_lbl.setText("READY")
            self._status_lbl.setStyleSheet(
                f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            self._scope_lbl.setText(
                f"Available in {instance_name} ({_workspace_type_label(instance_type)}). {self._reason}"
            )
            self._hint_btn.setEnabled(True)
        else:
            self._status_lbl.setText("RESTRICTED")
            self._status_lbl.setStyleSheet(
                f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            restriction = policy_reason or self._reason
            fix_hint = {
                "connector_unbound": "Fix in Workspaces: bind this connector to the active workspace.",
                "connector_action_blocked": "Fix in Workspaces: adjust connector action allow/block policy.",
                "connector_account_unavailable": "Fix in Workspaces: choose a valid connector account for this machine.",
                "connector_provider_unconfigured": "Fix in Workspaces or App Mgmt: choose a valid provider and verify host config.",
                "connector_host_auth_missing": "Fix in App Mgmt: connect or verify the machine-level connector auth.",
                "endpoint_block": "Fix in Workspaces: loosen the connector endpoint block filter if this is intentional.",
                "endpoint_allow": "Fix in Workspaces: expand the connector endpoint allow filter if this is intentional.",
            }.get(policy_reason_code, "")
            self._scope_lbl.setText(
                f"{self._name_lbl.text().title()} is not available in {instance_name} ({_workspace_type_label(instance_type)}) right now. {restriction}"
                + (f" {fix_hint}" if fix_hint else "")
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
    tool_state_changed = Signal(str, bool)
    tool_hint_requested = Signal(str)
    builder_task_requested = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_cards: dict[str, _ToolCard] = {}
        self._tool_states: dict[str, bool] = {}
        self._instance_name = "guppy-primary"
        self._instance_type = "user_instance"
        self._details_visible = False
        self._tool_card_order: list[str] = []
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

        title = QLabel("Workspace Tools")
        title.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: 26pt; font-weight: 900;"
        )
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        self._details_btn = QPushButton("SHOW DETAILS")
        self._details_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 10px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
        )
        self._details_btn.clicked.connect(self._toggle_details)
        title_row.addWidget(self._details_btn)
        layout.addLayout(title_row)
        layout.addWidget(
            _mono(
                "Use the tray for the fastest path. Open a tool card when you need a little more context.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        self._context_lbl = _mono("WORKSPACE: GUPPY-PRIMARY | DAILY", T.PRIMARY, T.FS_TINY, True)
        self._limits_lbl = _mono("Slots in use: 1 / 5 | Live now: 1 / 2", T.DIM, T.FS_TINY)
        layout.addWidget(self._context_lbl)
        layout.addWidget(self._limits_lbl)
        self._boundary_lbl = _mono(
            "Open App Management for setup, recovery, and logs.",
            T.DIM,
            T.FS_SMALL,
        )
        self._boundary_lbl.setWordWrap(True)
        layout.addWidget(self._boundary_lbl)
        self._execution_lbl = _mono(
            "Show details only when you want permission and sign-in checks.",
            T.DIM,
            T.FS_SMALL,
        )
        self._execution_lbl.setWordWrap(True)
        layout.addWidget(self._execution_lbl)

        filters = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Find a workspace tool...")
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

        self._banner = QFrame()
        self._banner.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")
        banner_layout = QVBoxLayout(self._banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(4)
        banner_layout.addWidget(_mono("BOUNDARY", T.PRIMARY, T.FS_TINY, True))
        banner_layout.addWidget(
            _mono(
                "The tray is the fast path. This page stays useful when you want builder context or deeper access notes.",
                T.DIM,
                T.FS_SMALL,
            )
        )
        self._tray_notice_lbl = _mono(
            "Use tray icons for common actions. Show details when you want the longer access explanation.",
            T.DIM,
            T.FS_SMALL,
        )
        self._tray_notice_lbl.setWordWrap(True)
        banner_layout.addWidget(self._tray_notice_lbl)
        layout.addWidget(self._banner)

        self._builder_panel = BuilderTaskPanel()
        self._builder_panel.queue_requested.connect(self.builder_task_requested.emit)
        layout.addWidget(self._builder_panel)

        self._cards_host = QWidget()
        self._cards_layout = QGridLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setHorizontalSpacing(12)
        self._cards_layout.setVerticalSpacing(12)
        for tool in _INSTANCE_TOOL_CATALOG:
            card = _ToolCard(tool)
            card.hint_requested.connect(self.tool_hint_requested.emit)
            self._tool_cards[card.tool_key] = card
            self._tool_card_order.append(card.tool_key)
        self._cards_host.setVisible(True)
        layout.addWidget(self._cards_host)

        self._empty_state_lbl = _mono(
            "No tools match this filter yet. Clear the search or choose another category to keep working.",
            T.DIM,
            T.FS_SMALL,
        )
        self._empty_state_lbl.setWordWrap(True)
        self._empty_state_lbl.setVisible(False)
        layout.addWidget(self._empty_state_lbl)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.set_instance_context({}, {})
        self._sync_detail_visibility()

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
        self._context_lbl.setText(f"WORKSPACE: {name.upper()} | {_workspace_type_label(instance_type).upper()}")
        limits_text = (
            f"Slots in use: {self._limits['configured']} / {self._limits['max_configured']} | "
            f"Live now: {self._limits['active_runtime']} / {self._limits['max_active_runtime']}"
        )
        if self._limits["configured"] >= self._limits["max_configured"]:
            limits_text += " | CONFIG CAP REACHED"
        if self._limits["active_runtime"] >= self._limits["max_active_runtime"]:
            limits_text += " | COLLABORATOR CAP REACHED"
        self._limits_lbl.setText(limits_text)
        self._boundary_lbl.setText(
            f"Use the tray for quick tools in {name}. Open App Management for setup, recovery, diagnostics, and logs."
        )
        self._tray_notice_lbl.setText(
            f"{name} can launch quick tools from the tray. This page keeps builder context and optional access detail."
        )
        self._execution_lbl.setText(
            f"{name} can only use tools that match its workspace role and sign-in state. Show details for the exact rules."
        )
        self._builder_panel.set_instance_context(name, instance_type)
        for card in self._tool_cards.values():
            card.apply_context(name, instance_type)
            card.set_details_visible(self._details_visible)
        self._apply_filters()

    def set_builder_status(self, text: str, ok: bool = True) -> None:
        self._builder_panel.set_status(text, ok=ok)

    def _apply_filters(self) -> None:
        category = self._filter_cb.currentText().strip().upper()
        query = self._search.text().strip().lower()
        visible_keys: list[str] = []
        for key in self._tool_card_order:
            card = self._tool_cards[key]
            matches_query = not query or query in card.search_blob
            matches_category = (
                category == "ALL"
                or (category == "RESTRICTED" and card.state == "restricted")
                or card.category == category
            )
            visible = matches_query and matches_category
            card.setVisible(visible)
            if visible:
                visible_keys.append(key)

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self._cards_host)

        for index, key in enumerate(visible_keys):
            self._cards_layout.addWidget(self._tool_cards[key], index // 2, index % 2)

        visible_cards = len(visible_keys)
        self._empty_state_lbl.setVisible(visible_cards == 0)
        self._cards_host.setVisible(visible_cards > 0)

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._sync_detail_visibility()

    def _sync_detail_visibility(self) -> None:
        self._banner.setVisible(self._details_visible)
        self._execution_lbl.setVisible(self._details_visible)
        self._details_btn.setText("HIDE DETAILS" if self._details_visible else "SHOW DETAILS")
        for card in self._tool_cards.values():
            card.set_details_visible(self._details_visible)

    def get_states(self) -> dict[str, bool]:
        return dict(self._tool_states)

    def set_states(self, states: dict[str, bool]) -> None:
        self._tool_states = {str(k): bool(v) for k, v in states.items()}

    def current_tool_states(self) -> dict[str, str]:
        return {key: card.state for key, card in self._tool_cards.items()}
