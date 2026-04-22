from __future__ import annotations

from src.guppy.launcher_application.launcher_api_runtime_control import startup_readiness_label


def test_startup_readiness_label_maps_reachable_ready_to_live() -> None:
    assert startup_readiness_label("reachable", {"overall": "READY"}) == "LIVE"


def test_startup_readiness_label_maps_reachable_partial_to_partial() -> None:
    assert startup_readiness_label("reachable", {"overall": "PARTIAL"}) == "PARTIAL"


def test_startup_readiness_label_maps_unknown_reachable_state_to_starting() -> None:
    assert startup_readiness_label("reachable", {"overall": "UNKNOWN"}) == "STARTING"


def test_startup_readiness_label_maps_auth_failure() -> None:
    assert startup_readiness_label("auth_failed", {"overall": "READY"}) == "AUTH"


def test_startup_readiness_label_maps_unreachable_to_down() -> None:
    assert startup_readiness_label("unreachable", {"overall": "READY"}) == "DOWN"
