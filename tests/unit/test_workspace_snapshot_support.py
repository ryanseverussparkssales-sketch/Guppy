from __future__ import annotations

import json
import time
from pathlib import Path

from src.guppy.launcher_application import workspace_snapshot_support as support


def test_build_local_instance_snapshot_preserves_governance_and_connectors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "instances.json"
    state_path = tmp_path / "instance_state.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 3,
                "active_instance": "builder-collab",
                "instances": [
                    {
                        "name": "builder-collab",
                        "description": "Builder workspace",
                        "type": "builder_instance",
                        "mode": "auto",
                        "persona": "custom",
                        "voice": "guide",
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps(
            {
                "instances": {
                    "builder-collab": {
                        "status": "busy",
                        "message_count": 7,
                        "last_message": "queued task",
                        "model_currently_using": "gpt-4.1-mini",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        support,
        "resolve_instance_permissions",
        lambda name, instance_type: {
            "_auth_mode": "workspace_token_required",
            "_tool_allow": ["query_instance"],
            "_tool_block": [],
            "_endpoint_allow": ["/instances"],
            "_endpoint_block": [],
            "_policy_note": f"{name}:{instance_type}",
            "read": True,
            "write": True,
            "execute": False,
            "network": True,
        },
    )
    monkeypatch.setattr(
        support,
        "fetch_workspace_connector_inventory",
        lambda name: [{"id": "youtube", "workspace": name}],
    )

    snapshot = support.build_local_instance_snapshot(
        config_path=config_path,
        state_path=state_path,
        include_workspace_details=True,
    )

    assert snapshot["version"] == 3
    assert snapshot["active_instance"] == "builder-collab"
    assert snapshot["limits"]["configured"] == 1
    item = snapshot["instances"][0]
    assert item["name"] == "builder-collab"
    assert item["status"] == "busy"
    assert item["message_count"] == 7
    assert item["model_currently_using"] == "gpt-4.1-mini"
    assert item["governance"]["auth_mode"] == "workspace_token_required"
    assert item["governance"]["capabilities"]["execute"] is False
    assert item["connectors"] == [{"id": "youtube", "workspace": "builder-collab"}]


def test_fetch_instance_snapshot_uses_cache_and_local_fallback() -> None:
    class _Owner:
        def __init__(self) -> None:
            self._last_instance_snapshot = {"cached": True}
            self._instance_snapshot_expires_at = time.monotonic() + 60.0
            self._instance_snapshot_ttl_s = 6.0
            self.http_calls = 0

        def _http_json(self, *args, **kwargs):
            self.http_calls += 1
            raise RuntimeError("api unavailable")

        @staticmethod
        def _local_instance_snapshot():
            return {"active_instance": "guppy-primary", "instances": [{"name": "guppy-primary"}]}

    owner = _Owner()

    cached = support.fetch_instance_snapshot(owner, force=False)
    assert cached == {"cached": True}
    assert owner.http_calls == 0

    owner._instance_snapshot_expires_at = 0.0
    fallback = support.fetch_instance_snapshot(owner, force=True)
    assert fallback["active_instance"] == "guppy-primary"
    assert owner.http_calls == 1
    assert owner._last_instance_snapshot["active_instance"] == "guppy-primary"


def test_load_instance_catalog_prefers_enabled_names_and_valid_active() -> None:
    class _Owner:
        @staticmethod
        def _local_instance_snapshot(*, include_workspace_details: bool = True):
            assert include_workspace_details is False
            return {
                "active_instance": "missing",
                "instances": [
                    {"name": "guppy-primary", "enabled": True},
                    {"name": "builder-collab", "enabled": False},
                    {"name": "ops-watch", "enabled": True},
                ],
            }

        @staticmethod
        def _fetch_instance_snapshot(force: bool = False):
            raise AssertionError("fetch should not be used when local snapshot is populated")

    names, active = support.load_instance_catalog(_Owner(), snapshot=None)

    assert names == ["guppy-primary", "ops-watch"]
    assert active == "guppy-primary"


def test_load_instance_history_from_logs_filters_to_user_and_assistant() -> None:
    history = support.load_instance_history_from_logs(
        "builder-collab",
        instance_logger_available=True,
        log_reader=lambda _name, limit=80: [
            {"role": "system", "message": "ignore"},
            {"role": "user", "message": "hello"},
            {"role": "assistant", "response": "hi"},
            {"role": "assistant", "message": ""},
        ],
    )

    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
