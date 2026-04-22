from __future__ import annotations

import pytest

from src.guppy.launcher_application import services
from src.guppy.workspace_governance import ConnectorActionRequest


def test_connector_service_fallbacks_when_backend_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "_CONNECTOR_BACKEND_AVAILABLE", False)

    assert services.connector_backend_available() is False
    assert services.fetch_connector_inventory() == ()
    assert services.fetch_workspace_connector_inventory("builder-collab") == []

    result = services.execute_connector_action(
        ConnectorActionRequest(connector_id="crm", action="verify")
    )

    assert result.ok is False
    assert result.connector_id == "crm"
    assert result.action == "verify"
    assert result.summary == "connector manager unavailable"

    with pytest.raises(RuntimeError, match="connector manager unavailable"):
        services.save_workspace_connector_binding("builder-collab", "crm", {"provider": "salesforce"})


def test_connector_service_filters_and_normalizes_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "_CONNECTOR_BACKEND_AVAILABLE", True)
    monkeypatch.setattr(
        services,
        "_connector_inventory",
        lambda: [
            {"id": "gmail", "auth_state": "ready", "supported_actions": ["verify", "connect"]},
            "ignore-me",
            {"connector": "CRM", "binding_inherited": True},
        ],
    )

    inventory = services.fetch_connector_inventory()

    assert tuple(item.connector_id for item in inventory) == ("gmail", "crm")
    assert inventory[0].supported_actions == ("verify", "connect")
    assert inventory[1].label == "Crm"
    assert inventory[1].inherited is True


def test_workspace_connector_inventory_filters_non_dict_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "_CONNECTOR_BACKEND_AVAILABLE", True)
    recorded: list[tuple[str, object]] = []

    def fake_workspace_inventory(workspace_name: str, *, config_path=None):
        recorded.append((workspace_name, config_path))
        return [{"id": "gmail"}, None, {"id": "crm"}]

    monkeypatch.setattr(services, "_workspace_connector_inventory", fake_workspace_inventory)

    rows = services.fetch_workspace_connector_inventory("ops-workspace", config_path="runtime/workspaces.json")

    assert rows == [{"id": "gmail"}, {"id": "crm"}]
    assert recorded == [("ops-workspace", "runtime/workspaces.json")]


def test_execute_connector_action_uses_request_id_when_backend_payload_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(services, "_CONNECTOR_BACKEND_AVAILABLE", True)
    captured: dict[str, str] = {}

    def fake_run_connector_action(
        connector_id: str,
        action: str,
        *,
        provider: str = "",
        account_id: str = "",
        secret_key: str = "",
        secret_value: str = "",
    ):
        captured.update(
            {
                "connector_id": connector_id,
                "action": action,
                "provider": provider,
                "account_id": account_id,
                "secret_key": secret_key,
                "secret_value": secret_value,
            }
        )
        return {
            "action": action,
            "ok": True,
            "summary": "Connector verify passed.",
            "result_code": "ready",
            "status": {"auth_state": "ready"},
            "next_step": "Keep the workspace binding in place.",
        }

    monkeypatch.setattr(services, "_run_connector_action", fake_run_connector_action)

    request = ConnectorActionRequest(
        connector_id="crm",
        action="verify",
        provider="salesforce",
        account_id="primary",
        secret_key="api_key",
        secret_value="top-secret",
    )
    result = services.execute_connector_action(request)

    assert captured == {
        "connector_id": "crm",
        "action": "verify",
        "provider": "salesforce",
        "account_id": "primary",
        "secret_key": "api_key",
        "secret_value": "top-secret",
    }
    assert result.connector_id == "crm"
    assert result.action == "verify"
    assert result.ok is True
    assert result.auth_state == "ready"
    assert result.next_step == "Keep the workspace binding in place."

