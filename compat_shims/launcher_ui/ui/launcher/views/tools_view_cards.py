"""
ui/launcher/views/tools_view_cards.py
Helpers for the Tools catalog and per-tool policy rendering.
"""
from __future__ import annotations

from src.guppy.launcher_application.tool_action_registry import (
    get_action_for_tool,
    get_canonical_action_line,
)
from src.guppy.launcher_application.tool_readiness import (
    read_workspace_tool_readiness,
    tool_policy_fix_hint,
    tool_readiness_debug_fields,
    tool_readiness_summary,
    tool_settings_route,
)
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.guppy.workspace_governance import (
    auth_mode_label,
    check_instance_tool_permission,
    required_capability_for_tool,
)
from .. import tokens as T


INSTANCE_TOOL_CATALOG: list[dict[str, object]] = [
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


def mono_label(text: str, color: str = T.DIM, size: int = T.FS_SMALL, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; font-family: '{T.FF_MONO}'; font-size: {size}pt; letter-spacing: 1px;"
        + ("font-weight: bold;" if bold else "")
    )
    return label


def workspace_type_label(instance_type: str) -> str:
    value = str(instance_type or "user_instance").strip().lower()
    return {
        "user_instance": "daily workspace",
        "builder_instance": "builder collaborator",
        "read_only_instance": "read-only reference",
        "admin_instance": "operations workspace",
    }.get(value, value.replace("_", " ").strip() or "workspace")


def _tool_allowed(tool: dict[str, object], instance_type: str) -> bool:
    allowed = tool.get("allowed_types", set())
    if not isinstance(allowed, set):
        return False
    return instance_type in allowed


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


class ToolCard(QFrame):
    hint_requested = Signal(str)
    manage_requested = Signal(dict)

    def __init__(self, tool: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = dict(tool)
        self._state = "ready"
        self._reason = ""
        self._debug_evidence: dict[str, object] = {}
        self._manage_payload: dict[str, str] = {}
        self._details_visible = False
        self.setObjectName("agent_tool_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(240)
        self.setStyleSheet(
            f"QFrame#agent_tool_card {{ background-color: {T.BG1}; border: 1px solid {T.BORDER}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # Registry is authoritative for label, category, dry_run; catalog supplies
        # description, allowed_types, and reason which are card-specific.
        _reg_entry = get_action_for_tool(str(tool.get("key", "")))
        _display_name = _reg_entry.label if _reg_entry is not None else str(tool.get("name", "TOOL"))
        _display_category = _reg_entry.category if _reg_entry is not None else str(tool.get("category", "READ"))
        _display_dry_run = _reg_entry.dry_run if _reg_entry is not None else bool(tool.get("dry_run", False))

        header = QHBoxLayout()
        self._name_lbl = QLabel(_display_name)
        self._name_lbl.setStyleSheet(
            f"color: {T.TEXT}; font-family: '{T.FF_HEAD}'; font-size: {T.FS_LABEL}pt; font-weight: 800;"
        )
        header.addWidget(self._name_lbl)
        header.addStretch()
        self._status_lbl = mono_label("READY", T.GREEN, T.FS_TINY, True)
        header.addWidget(self._status_lbl)
        root.addLayout(header)

        self._desc_lbl = QLabel(str(tool.get("description", "")))
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color: {T.DIM}; font-family: '{T.FF_BODY}'; font-size: {T.FS_SMALL}pt;"
        )
        root.addWidget(self._desc_lbl)
        self._action_line_lbl = mono_label(get_canonical_action_line(str(tool.get("key", ""))), T.TERTIARY, T.FS_TINY, True)
        self._action_line_lbl.setToolTip("Canonical typed and spoken command line for this tool.")
        root.addWidget(self._action_line_lbl)

        meta = QHBoxLayout()
        meta.addWidget(
            mono_label(f"TYPE: {_display_category.upper()}", T.PRIMARY_DIM, T.FS_TINY, True)
        )
        if _display_dry_run:
            meta.addSpacing(10)
            meta.addWidget(mono_label("SET UP FIRST", T.DIM, T.FS_TINY, True))
        meta.addStretch()
        root.addLayout(meta)

        self._scope_lbl = mono_label("", T.DIM, T.FS_TINY)
        self._scope_lbl.setWordWrap(True)
        root.addWidget(self._scope_lbl)
        self._evidence_lbl = mono_label("", T.DIM, T.FS_TINY)
        self._evidence_lbl.setWordWrap(True)
        root.addWidget(self._evidence_lbl)
        self._policy_lbl = mono_label("", T.PRIMARY_DIM, T.FS_TINY)
        self._policy_lbl.setWordWrap(True)
        root.addWidget(self._policy_lbl)
        self._guard_lbl = mono_label("", T.DIM, T.FS_TINY)
        self._guard_lbl.setWordWrap(True)
        root.addWidget(self._guard_lbl)

        actions = QHBoxLayout()
        self._hint_btn = QPushButton("PRIME HOME")
        _hint_tooltip = (
            f'Say: "{_reg_entry.command_hint}" — sends a starter prompt to Home'
            if _reg_entry is not None
            else "Send a starter hint for this tool to Home"
        )
        self._hint_btn.setToolTip(_hint_tooltip)
        self._hint_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.DIM}; border: 1px solid {T.BORDER};"
            f" padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ border-color: {T.PRIMARY}; color: {T.PRIMARY}; }}"
            f"QPushButton:disabled {{ color: {T.BORDER}; border-color: {T.BORDER}; }}"
        )
        self._hint_btn.clicked.connect(lambda: self.hint_requested.emit(str(self._tool.get("key", ""))))
        actions.addWidget(self._hint_btn)
        self._manage_btn = QPushButton("OPEN DEVICE & ACCOUNTS")
        self._manage_btn.setToolTip(
            "Open Settings > Device & Accounts for connector setup, verify, reconnect, remove, or disable actions"
        )
        self._manage_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG0}; color: {T.SECONDARY}; border: 1px solid {T.SECONDARY};"
            f" padding: 4px 8px; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; }}"
            f"QPushButton:hover {{ background: {T.SECONDARY}; color: {T.BG}; }}"
            f"QPushButton:disabled {{ color: {T.BORDER}; border-color: {T.BORDER}; }}"
        )
        self._manage_btn.clicked.connect(self._emit_manage_requested)
        self._manage_btn.setVisible(False)
        actions.addWidget(self._manage_btn)
        actions.addStretch()
        root.addLayout(actions)
        self.set_details_visible(False)

    def set_details_visible(self, visible: bool) -> None:
        self._details_visible = bool(visible)
        self._scope_lbl.setVisible(self._details_visible)
        self._evidence_lbl.setVisible(self._details_visible)
        self._policy_lbl.setVisible(self._details_visible)
        self._guard_lbl.setVisible(self._details_visible)

    def apply_context(self, instance_name: str, instance_type: str) -> None:
        allowed_by_type = _tool_allowed(self._tool, instance_type)
        policy_allowed, policy_reason, permissions = check_instance_tool_permission(
            self.tool_key,
            instance_name=instance_name,
            instance_type=instance_type,
        )
        connector_context = read_workspace_tool_readiness(self.tool_key, instance_name)
        readiness = (
            connector_context.get("readiness", {})
            if isinstance(connector_context.get("readiness"), dict)
            else {}
        )
        binding_validation = (
            connector_context.get("binding_validation", {})
            if isinstance(connector_context.get("binding_validation"), dict)
            else {}
        )
        history = connector_context.get("history", {}) if isinstance(connector_context.get("history"), dict) else {}
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
        connector_binding_action_allow = [
            str(item) for item in permissions.get("_connector_binding_action_allow", []) if str(item).strip()
        ]
        connector_binding_action_block = [
            str(item) for item in permissions.get("_connector_binding_action_block", []) if str(item).strip()
        ]
        connector_binding_endpoint_allow = [
            str(item) for item in permissions.get("_connector_binding_endpoint_allow", []) if str(item).strip()
        ]
        connector_binding_endpoint_block = [
            str(item) for item in permissions.get("_connector_binding_endpoint_block", []) if str(item).strip()
        ]
        connector_binding_note = str(permissions.get("_connector_binding_note", "") or "").strip()
        policy_reason_code = str(permissions.get("_policy_reason_code", "") or "").strip().lower()
        settings_route = tool_settings_route(self.tool_key, policy_reason_code, readiness)
        readiness_state = str(readiness.get("state", "") or "").strip().lower()
        readiness_summary = tool_readiness_summary(readiness)
        binding_validation_message = str(binding_validation.get("message", "") or "").strip()
        workspace_gate = "Workspace/role check allows" if allowed_by_type else "Workspace/role check blocks"
        runtime_gate = "governance policy allows" if policy_allowed else "governance policy blocks"
        policy_text = f"Needs {capability} access. {workspace_gate}; {runtime_gate}. Sign-in mode: {auth_mode}."
        if resolved_endpoint:
            policy_text += f" Endpoint scope: {resolved_endpoint}."
        if bool(self._tool.get("dry_run", False)):
            policy_text += " Home prompting only appears when the real action is allowed."
        self._guard_lbl.setText(policy_text)
        self._evidence_lbl.setText(readiness_summary)
        self._guard_lbl.setToolTip(policy_text)
        self._evidence_lbl.setToolTip(readiness_summary)
        governance_text = " | ".join(
            [
                f"SIGN-IN: {auth_mode}",
                f"CONNECTION: {connector}",
                f"CONNECTION STATUS: {connector_auth_state}",
                f"SOURCE: {connector_auth_source}",
                f"READINESS: {(readiness_state or 'not_applicable').replace('_', ' ').upper()}",
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
                + _render_endpoint_scope(
                    connector_binding_endpoint_allow,
                    connector_binding_endpoint_block,
                ).replace("Endpoint filters: ", "")
            )
        if connector_auth_detail:
            governance_text += f" | Sign-in detail: {connector_auth_detail}"
        if binding_validation_message:
            governance_text += f" | Binding check: {binding_validation_message}"
        if connector_binding_note:
            governance_text += f" | Binding note: {connector_binding_note}"
        if policy_note:
            governance_text += f" | Note: {policy_note}"
        self._policy_lbl.setText(governance_text)
        self._policy_lbl.setToolTip(governance_text)
        self._debug_evidence = {
            "tool": self.tool_key,
            "allowed": allowed,
            "state": self._state,
            "required_capability": capability,
            "policy_reason": policy_reason or self._reason,
            "policy_reason_code": policy_reason_code,
            "policy_note": policy_note,
            "auth_mode": auth_mode,
            "connector": connector,
            "connector_auth_state": connector_auth_state,
            "connector_auth_detail": connector_auth_detail,
            "connector_auth_source": connector_auth_source,
            "connector_action": connector_action or "DEFAULT",
            "connector_binding_enabled": connector_binding_enabled,
            "connector_binding_inherited": connector_binding_inherited,
            "connector_binding_account": connector_binding_account,
            "connector_binding_provider": connector_binding_provider,
            "resolved_endpoint": resolved_endpoint,
            "tool_allow": tool_allow,
            "tool_block": tool_block,
            "endpoint_allow": endpoint_allow,
            "endpoint_block": endpoint_block,
            "connector_binding_action_allow": connector_binding_action_allow,
            "connector_binding_action_block": connector_binding_action_block,
            "connector_binding_endpoint_allow": connector_binding_endpoint_allow,
            "connector_binding_endpoint_block": connector_binding_endpoint_block,
            "binding_validation_state": str(binding_validation.get("state", "") or "").strip(),
            "binding_validation_message": binding_validation_message,
            "connector_history": history,
            "governance_text": governance_text,
            "evidence_text": readiness_summary,
            "guard_text": policy_text,
            "settings_route": dict(settings_route),
            **tool_readiness_debug_fields(readiness),
        }
        if allowed:
            self._status_lbl.setText("READY")
            self._status_lbl.setStyleSheet(
                f"color: {T.GREEN}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
            )
            availability_text = f"Available in {instance_name} ({workspace_type_label(instance_type)}). {self._reason}"
            if readiness_state in {"pending_verify", "verification_failed", "host_setup_incomplete"}:
                availability_text += " " + str(readiness.get("label", "") or "").strip()
            self._scope_lbl.setText(availability_text)
            self._scope_lbl.setToolTip(availability_text)
            self._hint_btn.setEnabled(True)
            self._manage_payload = {}
            self._manage_btn.setVisible(False)
            return

        self._status_lbl.setText("RESTRICTED")
        self._status_lbl.setStyleSheet(
            f"color: {T.ERROR}; font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; letter-spacing: 1px; font-weight: bold;"
        )
        restriction = policy_reason or self._reason
        fix_hint = tool_policy_fix_hint(policy_reason_code, readiness)
        self._scope_lbl.setText(
            f"{self._name_lbl.text().title()} is not available in {instance_name} ({workspace_type_label(instance_type)}) right now. {restriction}"
            + (f" {fix_hint}" if fix_hint else "")
        )
        self._scope_lbl.setToolTip(self._scope_lbl.text())
        self._hint_btn.setEnabled(False)
        self._manage_payload = {
            **settings_route,
            "instance": instance_name,
            "tool_label": self._name_lbl.text(),
        }
        self._manage_btn.setVisible(bool(settings_route))
        self._manage_btn.setEnabled(bool(settings_route))
        if settings_route:
            button_label = str(settings_route.get("button_label", "") or "").strip() or "OPEN DEVICE & ACCOUNTS"
            destination_label = str(settings_route.get("destination_label", "") or "").strip()
            note = str(settings_route.get("note", "") or "").strip()
            self._manage_btn.setText(button_label)
            tooltip = (
                f"Open {destination_label} for connector setup, verify, reconnect, remove, or disable actions"
                if destination_label
                else "Open the Settings-owned connector setup and account flow"
            )
            if note:
                tooltip += f" | {note}"
            self._manage_btn.setToolTip(tooltip)

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

    @property
    def debug_evidence(self) -> dict[str, object]:
        return dict(self._debug_evidence)

    def _emit_manage_requested(self) -> None:
        if self._manage_payload:
            self.manage_requested.emit(dict(self._manage_payload))


__all__ = [
    "INSTANCE_TOOL_CATALOG",
    "ToolCard",
    "mono_label",
    "workspace_type_label",
]
