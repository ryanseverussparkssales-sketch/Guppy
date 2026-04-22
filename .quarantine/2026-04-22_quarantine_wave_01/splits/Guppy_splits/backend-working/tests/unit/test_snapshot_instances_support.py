from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.guppy.api import snapshot_instances_support


def _fake_owner() -> SimpleNamespace:
    saved = {"config": None, "state": None, "binding": None, "deleted_log": None}

    config = {
        "version": 2,
        "active_instance": "alpha",
        "instances": [
            {
                "name": "alpha",
                "description": "Primary",
                "mode": "auto",
                "persona": "guppy",
                "voice": "default",
                "type": "user_instance",
                "enabled": True,
                "created_at": "2026-04-20T00:00:00+00:00",
            },
            {
                "name": "beta",
                "description": "Secondary",
                "mode": "teach",
                "persona": "guide",
                "voice": "warm",
                "type": "builder_instance",
                "enabled": False,
                "created_at": "2026-04-20T00:01:00+00:00",
            },
        ],
    }
    state = {
        "active_instance": "alpha",
        "instances": {
            "alpha": {
                "status": "active",
                "last_message": "hello",
                "last_updated": "2026-04-20T00:02:00+00:00",
                "message_count": 3,
                "model_currently_using": "auto",
            },
            "beta": {
                "status": "idle",
                "last_message": "",
                "last_updated": None,
                "message_count": 0,
                "model_currently_using": "teach",
            },
        },
    }

    def load_normalized_instance_bundle(*, persist_repairs: bool = False):
        assert persist_repairs is True
        return config, state, ["config normalized"], ["state normalized"]

    def normalize_instances_config(raw):
        return raw, []

    def instance_names(raw):
        return [item["name"] for item in raw["instances"]]

    def get_instance_entry(raw, name):
        return next((item for item in raw["instances"] if item["name"] == name), None)

    def normalize_instance_state(raw, *, valid_names, active_instance):
        del valid_names, active_instance
        return raw, []

    def activate_instance_state(raw_state, target):
        raw_state["active_instance"] = target
        return raw_state

    return SimpleNamespace(
        _path_config=SimpleNamespace(connector_bindings_path=Path("connector_bindings.json")),
        _INSTANCE_LOGGER_AVAILABLE=True,
        _load_normalized_instance_bundle=load_normalized_instance_bundle,
        _instance_limits_payload=lambda cfg, st: {
            "configured": len(cfg["instances"]),
            "max_configured": 5,
            "active_runtime": 1 if st["active_instance"] else 0,
            "max_active_runtime": 2,
        },
        resolve_instance_permissions=lambda name, instance_type: {
            "_auth_mode": "runtime_default" if name == "alpha" else "strict",
            "_tool_allow": ["read"],
            "_tool_block": [],
            "_endpoint_allow": ["/status"],
            "_endpoint_block": [],
            "_policy_note": f"{instance_type} note",
            "read": True,
            "write": name == "alpha",
            "execute": False,
            "network": name == "beta",
        },
        auth_mode_label=lambda mode: f"label:{mode}",
        workspace_connector_inventory=lambda name, config_path=None: [
            {"id": "gmail", "enabled": True, "instance": name, "config_path": str(config_path)}
        ],
        connector_inventory=lambda: [{"id": "gmail"}, {"id": "drive"}],
        run_connector_action=lambda connector_id, action, **kwargs: {
            "ok": True,
            "action": action,
            "connector_id": connector_id,
            "kwargs": kwargs,
        },
        save_workspace_connector_binding=lambda workspace_name, connector_id, payload, *, config_path=None: saved.__setitem__(
            "binding",
            (workspace_name, connector_id, payload, str(config_path)),
        ),
        _load_instances_config=lambda: config,
        _normalize_instances_config=normalize_instances_config,
        _upsert_instance_config=lambda raw, payload: (
            {
                **raw,
                "instances": list(raw["instances"])
                + [
                    {
                        "name": payload.name,
                        "description": payload.description,
                        "mode": payload.mode,
                        "persona": payload.persona,
                        "voice": payload.voice,
                        "type": payload.type,
                        "enabled": payload.enabled,
                        "created_at": "2026-04-20T00:03:00+00:00",
                    }
                ],
            },
            "created",
        ),
        _save_instances_config=lambda raw: saved.__setitem__("config", raw),
        _instance_names=instance_names,
        _load_instance_state=lambda raw=None: state,
        _normalize_instance_state=normalize_instance_state,
        _default_instance_state=lambda mode: {
            "status": "idle",
            "last_message": "",
            "last_updated": None,
            "message_count": 0,
            "model_currently_using": mode,
        },
        _activate_instance_state=activate_instance_state,
        _save_instance_state=lambda raw: saved.__setitem__("state", raw),
        _get_instance_entry=get_instance_entry,
        set_instance_tool_permission_policy=lambda name, payload: saved.__setitem__(
            "policy",
            (name, payload),
        ),
        delete_instance_log=lambda name: saved.__setitem__("deleted_log", name),
        read_instance_log_tail=lambda name, limit=50: [{"instance": name, "limit": limit}],
        read_instance_log_summary=lambda name: {"instance": name, "entry_count": 1},
        _saved=saved,
    )


def test_build_instance_list_response_includes_governance_and_connector_payloads() -> None:
    owner = _fake_owner()

    payload = snapshot_instances_support.build_instance_list_response(owner)

    assert payload["version"] == 2
    assert payload["active_instance"] == "alpha"
    assert payload["warnings"] == ["config normalized", "state normalized"]
    assert payload["instances"][0]["governance"]["auth_mode_label"] == "label:runtime_default"
    assert payload["instances"][1]["governance"]["capabilities"]["network"] is True
    assert payload["instances"][0]["connectors"][0]["instance"] == "alpha"


def test_run_connector_action_response_normalizes_connector_and_forwards_request_fields() -> None:
    owner = _fake_owner()
    request = SimpleNamespace(
        provider="google",
        account_id="acct-1",
        secret_key="api_key",
        secret_value="secret",
    )

    payload = snapshot_instances_support.run_connector_action_response(owner, " Gmail ", "verify", request)

    assert payload["connector"] == "gmail"
    assert payload["action"] == "verify"
    assert payload["kwargs"]["provider"] == "google"
    assert payload["kwargs"]["account_id"] == "acct-1"


def test_delete_instance_response_removes_instance_and_cleans_up_logs() -> None:
    owner = _fake_owner()

    payload = snapshot_instances_support.delete_instance_response(owner, "beta")

    assert payload["ok"] is True
    assert payload["deleted"] == "beta"
    assert payload["active_instance"] == "alpha"
    assert owner._saved["deleted_log"] == "beta"
    assert len(owner._saved["config"]["instances"]) == 1
    assert "beta" not in owner._saved["state"]["instances"]


def test_build_instance_logs_response_rejects_unknown_instance() -> None:
    owner = _fake_owner()

    with pytest.raises(Exception) as exc_info:
        snapshot_instances_support.build_instance_logs_response(owner, "missing")

    assert "unknown instance: missing" in str(exc_info.value)
