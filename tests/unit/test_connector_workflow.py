from __future__ import annotations

from queue import SimpleQueue

import pytest

from src.guppy.launcher_application import connector_workflow


class _StatusPanel:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_syslog(self, text: str) -> None:
        self.lines.append(text)


class _ManagerView:
    def __init__(self) -> None:
        self.governance_status: tuple[str, bool] | None = None
        self.binding_status: tuple[str, bool] | None = None

    def set_governance_status(self, text: str, ok: bool = True) -> None:
        self.governance_status = (text, ok)

    def set_connector_binding_status(self, text: str, ok: bool = True) -> None:
        self.binding_status = (text, ok)


class _AdvancedView:
    def __init__(self) -> None:
        self.logs: list[str] = []

    def append_log(self, text: str) -> None:
        self.logs.append(text)


class _MyPcView:
    def __init__(self) -> None:
        self.result: tuple[str, bool] | None = None

    def set_account_result(self, text: str, ok: bool = True) -> None:
        self.result = (text, ok)


class _Owner:
    def __init__(self) -> None:
        self._instance_manager_view = _ManagerView()
        self._status_panel = _StatusPanel()
        self._advanced_view = _AdvancedView()
        self._my_pc_view = _MyPcView()
        self._active_instance_name = "builder-collab"
        self._refresh_calls: list[tuple[bool, bool]] = []
        self._event_log: list[tuple[str, dict[str, object]]] = []
        self._daily_activity = ""
        self._connector_action_events: SimpleQueue = SimpleQueue()
        self._instances_config_path = lambda: None
        self._instance_state_path = lambda: None

    def _refresh_instance_views(self, *, load_logs: bool = False, force: bool = False) -> None:
        self._refresh_calls.append((load_logs, force))

    def _log_launcher_event(self, event: str, **fields: object) -> None:
        self._event_log.append((event, fields))

    def _set_daily_activity(self, text: str) -> None:
        self._daily_activity = text


def test_save_instance_governance_uses_local_backend_on_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner()
    owner._http_json = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("api warming"))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        connector_workflow,
        "resolve_instance_permissions",
        lambda name, instance_type: {"read": True, "write": False, "execute": False, "network": True},
    )
    monkeypatch.setattr(
        connector_workflow,
        "set_instance_tool_permission_policy",
        lambda name, policy: captured.update({"name": name, "policy": policy}),
    )

    connector_workflow.save_instance_governance(
        owner,
        {
            "name": "builder-collab",
            "instance_type": "builder_instance",
            "auth_mode": "workspace_bound",
            "tool_allow": ["read_file"],
            "policy_note": "builder policy",
        },
        backend_available=True,
    )

    assert captured["name"] == "builder-collab"
    assert captured["policy"]["auth_mode"] == "workspace_bound"
    assert captured["policy"]["read"] is True
    assert owner._instance_manager_view.governance_status == ("Governance saved for builder-collab", True)
    assert owner._event_log[-1][0] == "workspace_governance_saved"
    assert owner._refresh_calls[-1] == (True, True)


def test_save_instance_connector_binding_uses_local_backend_on_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner()
    owner._http_json = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("api warming"))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        connector_workflow,
        "save_workspace_connector_binding",
        lambda name, connector_id, payload: captured.update(
            {"name": name, "connector_id": connector_id, "payload": payload}
        ),
    )

    connector_workflow.save_instance_connector_binding(
        owner,
        {
            "name": "builder-collab",
            "connector": "gmail",
            "enabled": True,
            "provider": "google",
            "account_id": "primary",
            "action_allow": ["compose"],
        },
        backend_available=True,
    )

    assert captured["name"] == "builder-collab"
    assert captured["connector_id"] == "gmail"
    assert captured["payload"]["provider"] == "google"
    assert owner._instance_manager_view.binding_status == ("Connector binding saved for builder-collab / gmail", True)
    assert owner._event_log[-1][0] == "workspace_connector_binding_saved"
    assert owner._refresh_calls[-1] == (False, True)


def test_perform_connector_action_request_uses_service_backend_when_http_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _Owner()
    owner._http_json = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("http down"))

    def _fake_execute(request):
        return type(
            "Result",
            (),
            {
                "ok": True,
                "summary": "CRM verify passed.",
                "next_step": "Keep using CRM in workspaces.",
                "result_code": "ready",
                "fix_target": "Workspaces > Connector Bindings",
                "event_id": "evt-123",
                "history": {"last_action_record": {"integration_event": "crm.verify"}},
                "status": {"auth_state": "ready"},
            },
        )()

    monkeypatch.setattr(connector_workflow, "execute_connector_action", _fake_execute)

    record = connector_workflow.perform_connector_action_request(
        owner,
        {
            "connector": "crm",
            "action": "verify",
            "provider": "salesforce",
            "account_id": "primary",
        },
        backend_available=True,
    )

    assert record["connector"] == "crm"
    assert record["action"] == "verify"
    assert record["ok"] is True
    assert record["event_id"] == "evt-123"
    assert record["integration_event"] == "crm.verify"


def test_drain_connector_action_events_refreshes_only_last_batch_record() -> None:
    owner = _Owner()
    owner._connector_action_events.put(
        {
            "kind": "batch",
            "records": [
                {"connector": "gmail", "action": "connect", "ok": True, "summary": "step one"},
                {"connector": "gmail", "action": "verify", "ok": True, "summary": "step two"},
            ],
            "refresh_after": True,
        }
    )

    connector_workflow.drain_connector_action_events(owner)

    assert owner._advanced_view.logs == ["step one", "step two"]
    assert owner._refresh_calls == [(False, True)]
