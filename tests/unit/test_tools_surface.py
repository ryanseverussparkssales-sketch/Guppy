from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]
VIEWS_DIR = ROOT / "ui" / "launcher" / "views"

views_package = sys.modules.get("ui.launcher.views")
if views_package is None:
    views_package = types.ModuleType("ui.launcher.views")
    views_package.__path__ = [str(VIEWS_DIR)]
    sys.modules["ui.launcher.views"] = views_package

tools_view_module = importlib.import_module("ui.launcher.views.tools_view_cards")
tools_page_module = importlib.import_module("ui.launcher.views.tools_view")
settings_operations_panel_module = importlib.import_module("ui.launcher.views.settings_operations_panel")
SettingsOperationsPanel = settings_operations_panel_module.SettingsOperationsPanel
from src.guppy.launcher_application.tools_trace_adapter import LauncherToolsTraceAdapter


@pytest.fixture(scope="module", autouse=True)
def _qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_tool_card_debug_console_respects_workspace_role_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools_view_module,
        "check_instance_tool_permission",
        lambda *args, **kwargs: (True, "", {"_auth_mode": "runtime_default"}),
    )

    tool = next(item for item in tools_view_module.INSTANCE_TOOL_CATALOG if item["key"] == "debug_console")
    debug_card = tools_view_module.ToolCard(tool)

    debug_card.apply_context("reference-desk", "read_only_instance")

    assert debug_card.state == "restricted"
    assert "debug console is not available in reference-desk" in debug_card._scope_lbl.text().lower()
    assert "trusted interactive workspaces only" in debug_card._scope_lbl.text().lower()
    assert not debug_card._hint_btn.isEnabled()

    debug_card.apply_context("builder-collab", "builder_instance")
    debug_card.set_details_visible(True)

    assert debug_card.state == "ready"
    assert "available in builder-collab" in debug_card._scope_lbl.text().lower()
    assert "needs read access" in debug_card._guard_lbl.text().lower()
    assert not debug_card._guard_lbl.isHidden()
    assert debug_card._hint_btn.isEnabled()


def test_tool_card_surfaces_host_auth_fix_hint_for_restricted_connector_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools_view_module,
        "check_instance_tool_permission",
        lambda *args, **kwargs: (
            False,
            "Machine Gmail auth is not ready for this workspace binding.",
            {
                "_auth_mode": "local_only",
                "_tool_allow": ["send_email"],
                "_endpoint_allow": ["instance://*", "http://localhost*"],
                "_connector": "gmail",
                "_connector_auth_state": "missing",
                "_connector_auth_detail": "credential file missing",
                "_connector_auth_source": "machine",
                "_connector_action": "send",
                "_connector_binding_enabled": True,
                "_connector_binding_account": "main",
                "_policy_reason_code": "connector_host_auth_missing",
                "_policy_note": "Builder stays inside workspace boundaries.",
            },
        ),
    )
    monkeypatch.setattr(tools_view_module, "required_capability_for_tool", lambda key: "network")
    monkeypatch.setattr(tools_view_module, "auth_mode_label", lambda value: "local only")

    tool = next(item for item in tools_view_module.INSTANCE_TOOL_CATALOG if item["key"] == "send_email")
    card = tools_view_module.ToolCard(tool)
    card.apply_context("builder-collab", "builder_instance")

    assert card.state == "restricted"
    assert "machine gmail auth is not ready" in card._scope_lbl.text().lower()
    assert "fix in app mgmt: connect or verify the machine-level connector auth." in card._scope_lbl.text().lower()
    assert "sign-in mode: local only." in card._guard_lbl.text().lower()
    assert "CONNECTION STATUS: MISSING" in card._policy_lbl.text()
    assert "Sign-in detail: credential file missing" in card._policy_lbl.text()
    assert "Note: Builder stays inside workspace boundaries." in card._policy_lbl.text()
    assert not card._hint_btn.isEnabled()


def test_settings_operations_panel_renders_recent_evidence_and_operator_notes() -> None:
    view = SettingsOperationsPanel()

    view.set_automation_snapshot(
        {
            "workspace": "Workspace step: active=builder-collab | preferred=builder-collab",
            "queue_counts": "Queue counts: pending=0 | running=1 | awaiting approval=0 | done=3",
            "report_path": "runtime/offhours_builder_report.json",
            "evidence_pack_path": "runtime/user_test_evidence.md",
            "stress_report_path": "runtime/stress_report_20260419_101500.json",
            "recent_events": "Recent operator notes: Evidence pack refreshed | builder review queued",
            "validation_command": ".venv\\Scripts\\python.exe -m pytest tests/unit/test_tools_surface.py -q",
            "status": "Automation test lane ready",
        }
    )

    assert view._automation_evidence_lbl.text() == "Evidence pack: runtime/user_test_evidence.md"
    assert view._automation_stress_lbl.text() == "Latest stress run: runtime/stress_report_20260419_101500.json"
    assert view._automation_recent_lbl.text() == (
        "Recent operator notes: Evidence pack refreshed | builder review queued"
    )
    assert view._automation_validation_lbl.text() == (
        "Validation command: .venv\\Scripts\\python.exe -m pytest tests/unit/test_tools_surface.py -q"
    )
    assert view._automation_status_lbl.text() == "Automation test lane ready"


def test_tools_trace_adapter_surfaces_recent_tool_events_and_state_drift(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "launcher_events.jsonl").write_text(
        "\n".join(
            [
                '{"ts":"2026-04-19T20:00:00","source":"launcher","event":"tool_hint_requested","tool":"read_file","summary":"primed into home"}',
                '{"ts":"2026-04-19T20:01:00","source":"launcher","event":"tool_hint_blocked","tool":"send_email","summary":"machine auth missing","error":"blocked"}',
                '{"ts":"2026-04-19T20:02:00","source":"launcher","event":"command_submitted","command":"status"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime_dir / "launcher_tools_state.json").write_text('{"read_file": true, "send_email": false}\n', encoding="utf-8")

    adapter = LauncherToolsTraceAdapter(
        runtime_dir,
        tool_state_path=runtime_dir / "launcher_tools_state.json",
        live_tool_states_getter=lambda: {"read_file": True, "send_email": True},
        live_tool_statuses_getter=lambda: {"read_file": "ready", "send_email": "restricted"},
    )

    snapshot = adapter.read_debug_snapshot(tool_key="send_email", limit=4)

    assert snapshot["persisted_tool_states"]["send_email"] is False
    assert snapshot["live_tool_states"]["send_email"] is True
    assert snapshot["live_tool_statuses"]["send_email"] == "restricted"
    assert snapshot["state_drift"] == [{"tool": "send_email", "persisted": False, "live": True}]
    assert snapshot["recent_tool_events"][0]["tool"] == "send_email"
    assert snapshot["recent_tool_events"][0]["level"] == "ERROR"


def test_tools_view_renders_trace_panel_from_debug_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools_view_module,
        "check_instance_tool_permission",
        lambda *args, **kwargs: (
            False,
            "Machine Gmail auth is not ready for this workspace binding.",
            {
                "_auth_mode": "local_only",
                "_connector": "gmail",
                "_connector_auth_state": "missing",
                "_connector_auth_source": "machine",
                "_policy_reason_code": "connector_host_auth_missing",
            },
        ),
    )
    monkeypatch.setattr(tools_view_module, "required_capability_for_tool", lambda key: "network")
    monkeypatch.setattr(tools_view_module, "auth_mode_label", lambda value: "local only")

    view = tools_page_module.ToolsView()
    view.read_debug_snapshot = lambda tool_key=None, limit=8: {
        "paths": {
            "launcher_events": "runtime/launcher_events.jsonl",
            "tool_states": "runtime/launcher_tools_state.json",
        },
        "recent_tool_events": [
            {
                "ts": "2026-04-19T20:01:00",
                "level": "ERROR",
                "event": "tool_hint_blocked",
                "tool": "send_email",
                "summary": "machine auth missing",
            }
        ],
        "recent_launcher_events": [],
        "persisted_tool_states": {"send_email": False},
        "live_tool_states": {"send_email": True},
        "live_tool_statuses": {"send_email": "restricted"},
        "state_drift": [{"tool": "send_email", "persisted": False, "live": True}],
    }
    view.set_instance_context({"name": "builder-collab", "type": "builder_instance"}, {"limits": {}})
    view._trace_panel._tool_picker.setCurrentIndex(view._trace_panel._tool_picker.findData("send_email"))
    view.refresh_debug_surface()

    assert "builder-collab trace focus: send email" in view._trace_panel._status_lbl.text().lower()
    assert "capability: network" in view._trace_panel._detail_lbl.text().lower()
    assert "policy evidence" in view._trace_panel._events_box.toPlainText().lower()
    assert "tool hint blocked" in view._trace_panel._events_box.toPlainText().lower()


def test_tools_view_reflows_cards_for_narrower_widths() -> None:
    view = tools_page_module.ToolsView()
    view._scroll = None
    view.resize(760, 900)
    view._apply_filters()

    first_row_columns = set()
    for index in range(min(3, view._cards_layout.count())):
        row, column, _row_span, _column_span = view._cards_layout.getItemPosition(index)
        if row == 0:
            first_row_columns.add(column)

    assert first_row_columns == {0}

    view.resize(1500, 900)
    view._apply_filters()

    wider_first_row_columns = set()
    for index in range(min(3, view._cards_layout.count())):
        row, column, _row_span, _column_span = view._cards_layout.getItemPosition(index)
        if row == 0:
            wider_first_row_columns.add(column)

    assert wider_first_row_columns == {0, 1, 2}
