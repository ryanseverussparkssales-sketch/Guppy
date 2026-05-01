"""
ui/launcher/views/tools_trace_panel.py
Recent execution trace and per-tool debug evidence for the Tools hub.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import tokens as T
from .tools_view_cards import mono_label


def _bool_label(value: object) -> str:
    if value is True:
        return "ON"
    if value is False:
        return "OFF"
    return "UNSET"


def _event_line(item: dict[str, object]) -> str:
    ts = str(item.get("ts", "") or "").strip() or "time unknown"
    level = str(item.get("level", "INFO") or "INFO").strip().upper()
    event = str(item.get("event", "event") or "event").replace("_", " ").strip()
    tool = str(item.get("tool", "") or "").strip()
    summary = str(item.get("summary", "") or "").strip()
    parts = [f"{ts} [{level}] {event}"]
    if tool:
        parts.append(f"tool={tool}")
    if summary:
        parts.append(summary)
    return " | ".join(parts)


class ToolsTracePanel(QFrame):
    tool_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {T.BG1}; border: 1px solid {T.BORDER}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        root.addWidget(mono_label("TRACE + DEBUG", T.PRIMARY, T.FS_TINY, True))
        root.addWidget(
            mono_label(
                "Recent operational evidence stays here so you can inspect last-run outcomes, policy posture, and trace drift without leaving Tools.",
                T.DIM,
                T.FS_SMALL,
            )
        )

        picker_row = QHBoxLayout()
        picker_row.addWidget(mono_label("FOCUS", T.PRIMARY_DIM, T.FS_TINY, True))
        self._tool_picker = QComboBox()
        self._tool_picker.setStyleSheet(
            f"QComboBox {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_SMALL}pt; padding: 4px 8px; }}"
        )
        self._tool_picker.currentIndexChanged.connect(self._emit_tool_selected)
        picker_row.addWidget(self._tool_picker, stretch=1)
        root.addLayout(picker_row)

        self._status_lbl = mono_label("Recent tool evidence will appear here after launcher events are available.", T.DIM, T.FS_SMALL)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        self._detail_lbl = mono_label("Choose a tool to inspect its last-run and permission evidence.", T.DIM, T.FS_TINY)
        self._detail_lbl.setWordWrap(True)
        root.addWidget(self._detail_lbl)

        self._paths_lbl = mono_label("", T.DIM, T.FS_TINY)
        self._paths_lbl.setWordWrap(True)
        root.addWidget(self._paths_lbl)

        self._events_box = QPlainTextEdit()
        self._events_box.setReadOnly(True)
        self._events_box.setMinimumHeight(150)
        self._events_box.setStyleSheet(
            f"QPlainTextEdit {{ background: {T.BG0}; border: 1px solid {T.BORDER}; color: {T.TEXT};"
            f" font-family: '{T.FF_MONO}'; font-size: {T.FS_TINY}pt; padding: 8px; }}"
        )
        root.addWidget(self._events_box)

        self.set_tool_options([])

    def selected_tool(self) -> str:
        value = str(self._tool_picker.currentData() or "").strip()
        return value

    def set_tool_options(self, tool_keys: list[str]) -> None:
        current = self.selected_tool()
        self._tool_picker.blockSignals(True)
        self._tool_picker.clear()
        self._tool_picker.addItem("ALL TOOLS", "")
        for key in tool_keys:
            text = key.replace("_", " ").upper()
            self._tool_picker.addItem(text, key)
        index = self._tool_picker.findData(current)
        self._tool_picker.setCurrentIndex(0 if index < 0 else index)
        self._tool_picker.blockSignals(False)

    def set_snapshot(
        self,
        snapshot: dict[str, object],
        *,
        instance_name: str,
        tool_debug: dict[str, object] | None = None,
    ) -> None:
        selected_tool = self.selected_tool()
        paths = snapshot.get("paths", {}) if isinstance(snapshot.get("paths"), dict) else {}
        recent_tool_events = (
            [item for item in snapshot.get("recent_tool_events", []) if isinstance(item, dict)]
            if isinstance(snapshot.get("recent_tool_events"), list)
            else []
        )
        recent_launcher_events = (
            [item for item in snapshot.get("recent_launcher_events", []) if isinstance(item, dict)]
            if isinstance(snapshot.get("recent_launcher_events"), list)
            else []
        )
        live_statuses = snapshot.get("live_tool_statuses", {}) if isinstance(snapshot.get("live_tool_statuses"), dict) else {}
        live_states = snapshot.get("live_tool_states", {}) if isinstance(snapshot.get("live_tool_states"), dict) else {}
        persisted_states = snapshot.get("persisted_tool_states", {}) if isinstance(snapshot.get("persisted_tool_states"), dict) else {}
        state_drift = (
            [item for item in snapshot.get("state_drift", []) if isinstance(item, dict)]
            if isinstance(snapshot.get("state_drift"), list)
            else []
        )
        target_label = selected_tool.replace("_", " ") if selected_tool else "all tools"
        if selected_tool:
            latest = recent_tool_events[0] if recent_tool_events else None
            latest_text = _event_line(latest) if latest else "No recent tool event recorded for this tool yet."
            self._status_lbl.setText(
                f"{instance_name} trace focus: {target_label}. Last run: {latest_text}"
            )
            if isinstance(tool_debug, dict) and tool_debug:
                self._detail_lbl.setText(
                    " | ".join(
                        [
                            f"STATE: {str(tool_debug.get('state', 'unknown') or 'unknown').upper()}",
                            f"CAPABILITY: {str(tool_debug.get('required_capability', 'unknown') or 'unknown').upper()}",
                            f"SIGN-IN: {str(tool_debug.get('auth_mode', 'unknown') or 'unknown')}",
                            f"CONNECTOR: {str(tool_debug.get('connector', 'workspace tool') or 'workspace tool')}",
                            f"AUTH: {str(tool_debug.get('connector_auth_state', 'unknown') or 'unknown')}",
                            f"LIVE TOGGLE: {_bool_label(live_states.get(selected_tool))}",
                            f"PERSISTED: {_bool_label(persisted_states.get(selected_tool))}",
                        ]
                    )
                )
            else:
                self._detail_lbl.setText(
                    f"LIVE TOGGLE: {_bool_label(live_states.get(selected_tool))} | "
                    f"PERSISTED: {_bool_label(persisted_states.get(selected_tool))} | "
                    f"STATUS: {str(live_statuses.get(selected_tool, 'unknown') or 'unknown').upper()}"
                )
        else:
            self._status_lbl.setText(
                f"{instance_name} trace focus: all tools. Recent tool events: {len(recent_tool_events)} | "
                f"recent launcher events: {len(recent_launcher_events)} | state drift: {len(state_drift)}"
            )
            if state_drift:
                drift_preview = ", ".join(str(item.get("tool", "")).strip() for item in state_drift[:3] if str(item.get("tool", "")).strip())
                self._detail_lbl.setText(f"State drift detected for: {drift_preview}" if drift_preview else "State drift detected.")
            else:
                self._detail_lbl.setText("No persisted/live tool-state drift detected.")

        launcher_events_path = str(paths.get("launcher_events", "") or "").replace("\\", "/")
        tool_states_path = str(paths.get("tool_states", "") or "").replace("\\", "/")
        self._paths_lbl.setText(f"Evidence: {launcher_events_path or 'runtime/launcher_events.jsonl'} | {tool_states_path or 'runtime/launcher_tools_state.json'}")

        lines: list[str] = []
        if isinstance(tool_debug, dict) and tool_debug:
            lines.extend(
                [
                    "Policy evidence",
                    f"- Required capability: {tool_debug.get('required_capability', 'unknown')}",
                    f"- Policy reason: {tool_debug.get('policy_reason', 'n/a')}",
                    f"- Policy code: {tool_debug.get('policy_reason_code', 'n/a')}",
                    f"- Connector auth source: {tool_debug.get('connector_auth_source', 'n/a')}",
                    f"- Resolved endpoint: {tool_debug.get('resolved_endpoint', 'inherited') or 'inherited'}",
                ]
            )
            governance_text = str(tool_debug.get("governance_text", "") or "").strip()
            if governance_text:
                lines.append(f"- Governance: {governance_text}")
        if recent_tool_events:
            lines.append("")
            lines.append("Recent tool events")
            lines.extend(f"- {_event_line(item)}" for item in recent_tool_events[:8])
        elif selected_tool:
            lines.append("")
            lines.append("Recent tool events")
            lines.append("- No tool-specific events recorded yet for this tool.")
        if not selected_tool and recent_launcher_events:
            lines.append("")
            lines.append("Recent launcher events")
            lines.extend(f"- {_event_line(item)}" for item in recent_launcher_events[:6])
        self._events_box.setPlainText("\n".join(lines).strip() or "No recent trace evidence recorded yet.")

    def _emit_tool_selected(self, _index: int) -> None:
        self.tool_selected.emit(self.selected_tool())
