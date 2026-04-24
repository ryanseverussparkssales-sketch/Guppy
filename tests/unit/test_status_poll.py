from __future__ import annotations

from src.guppy.launcher_application.status_poll import build_launcher_status_poll_snapshot


def test_build_launcher_status_poll_snapshot_defaults_status_to_unknown_without_api_payload() -> None:
    snapshot = build_launcher_status_poll_snapshot(
        launcher_status={"guppy_online": True, "active_model": "guppy"},
        api_status={},
        environment={},
        active_instance_name="builder-collab",
        last_instance_snapshot={"instances": [{"name": "builder-collab", "type": "builder_instance"}]},
    )

    assert snapshot.data["status"] == "unknown"


def test_build_launcher_status_poll_snapshot_background_summary_uses_online_not_ready() -> None:
    snapshot = build_launcher_status_poll_snapshot(
        launcher_status={"guppy_online": True},
        api_status={"status": "healthy"},
        environment={},
        active_instance_name="builder-collab",
        last_instance_snapshot={"instances": [{"name": "builder-collab", "type": "builder_instance"}]},
    )

    assert snapshot.background_summary.endswith("LIVE")


def test_build_launcher_status_poll_snapshot_embedded_runtime_promotes_live_status_fields() -> None:
    snapshot = build_launcher_status_poll_snapshot(
        launcher_status={"guppy_online": False, "daemon_running": False},
        api_status={"status": "healthy"},
        environment={},
        active_instance_name="builder-collab",
        last_instance_snapshot={"instances": [{"name": "builder-collab", "type": "builder_instance"}]},
        embedded_online=("guppy",),
    )

    assert snapshot.data["guppy_online"] is True
    assert snapshot.data["daemon"] is True
    assert snapshot.guppy_online is True
    assert snapshot.background_summary.endswith("LIVE")
