from __future__ import annotations

from src.guppy.launcher_application import shell_status


class _TextStub:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _AssistantViewStub:
    def __init__(self) -> None:
        self._route_facts = _TextStub("route: waiting")
        self._runtime_facts = _TextStub("runtime: ready")
        self.last_route_preview: dict[str, str] = {}
        self.background_events: list[str] = []

    def set_route_preview(self, **kwargs) -> None:
        self.last_route_preview = {str(key): str(value) for key, value in kwargs.items()}
        reason = self.last_route_preview.get("reason", "").strip()
        if reason:
            self._route_facts.set_text(f"route: {reason}")
            return
        route = self.last_route_preview.get("route", "pending").strip() or "pending"
        evidence = self.last_route_preview.get("evidence", "").strip()
        detail = f"{route} | {evidence}" if evidence else route
        self._route_facts.set_text(f"route: {detail}")

    def set_background_event(self, text: str) -> None:
        self.background_events.append(str(text))

    def chat_context(self) -> tuple[str, str]:
        return ("auto", "guppy")


class _SettingsHubViewStub:
    def __init__(self) -> None:
        self.route_updates: list[str] = []
        self.activity_updates: list[str] = []
        self.workspace_updates: list[str] = []
        self.runtime_updates: list[str] = []

    def set_daily_context_route(self, text: str) -> None:
        self.route_updates.append(str(text))

    def set_daily_context_activity(self, text: str) -> None:
        self.activity_updates.append(str(text))

    def set_daily_context_workspace(self, text: str) -> None:
        self.workspace_updates.append(str(text))

    def set_daily_context_runtime(self, text: str) -> None:
        self.runtime_updates.append(str(text))


class _StatusPanelStub:
    def __init__(self) -> None:
        self.workspace_calls: list[tuple[str, str]] = []
        self.tool_state_calls: list[dict[str, object]] = []

    def set_workspace(self, name: str, workspace_type: str) -> None:
        self.workspace_calls.append((str(name), str(workspace_type)))

    def set_tool_states(self, tool_states: dict[str, object]) -> None:
        self.tool_state_calls.append(dict(tool_states))


class _ToolsViewStub:
    def current_tool_states(self) -> dict[str, object]:
        return {"read_file": {"state": "ready"}}


class _OwnerStub:
    def __init__(self) -> None:
        self._active_instance_name = "guppy-primary"
        self._last_command = ""
        self._assistant_view = _AssistantViewStub()
        self._settings_hub_view = _SettingsHubViewStub()
        self._status_panel = _StatusPanelStub()
        self._tools_view = _ToolsViewStub()
        self._runtime_dir = "runtime"


def test_update_route_preview_waiting_state_still_syncs_settings_route() -> None:
    owner = _OwnerStub()

    shell_status.update_route_preview(owner, "")

    assert owner._assistant_view.last_route_preview["reason"] == "waiting for command"
    assert owner._settings_hub_view.route_updates == ["route: waiting for command"]


def test_update_route_preview_success_includes_evidence_and_updates_settings(monkeypatch) -> None:
    owner = _OwnerStub()

    monkeypatch.setattr(
        shell_status,
        "resolve_ui_route",
        lambda **_kwargs: {
            "task_type": "simple",
            "route": "haiku",
            "model": "claude-haiku",
            "backup_model": "claude-sonnet",
            "route_reason": "classification",
        },
    )
    monkeypatch.setattr(shell_status, "route_evidence_summary", lambda *_args, **_kwargs: "Cloud evidence: ready")

    shell_status.update_route_preview(owner, "Summarize this note")

    assert owner._assistant_view.last_route_preview["route"] == "haiku"
    assert owner._assistant_view.last_route_preview["evidence"] == "Cloud evidence: ready"
    assert owner._settings_hub_view.route_updates[-1] == owner._assistant_view._route_facts.text()


def test_set_daily_activity_updates_home_and_settings_context() -> None:
    owner = _OwnerStub()

    shell_status.set_daily_activity(owner, "Reply saved to Library")

    assert owner._assistant_view.background_events == ["Reply saved to Library"]
    assert owner._settings_hub_view.activity_updates == ["Reply saved to Library"]


def test_sync_right_tray_updates_status_tools_and_settings_context() -> None:
    owner = _OwnerStub()

    shell_status.sync_right_tray(
        owner,
        {
            "name": "guppy-primary",
            "type": "user_instance",
            "description": "Daily workspace",
            "mode": "auto",
            "persona": "guppy",
            "voice": "default",
        },
    )

    assert owner._status_panel.workspace_calls == [("guppy-primary", "user_instance")]
    assert owner._status_panel.tool_state_calls == [{"read_file": {"state": "ready"}}]
    assert owner._settings_hub_view.workspace_updates
    assert "Workspace:" in owner._settings_hub_view.workspace_updates[-1]
    assert owner._settings_hub_view.runtime_updates == ["runtime: ready"]
