from unittest.mock import patch

from tools.pilot_exit_check import CmdResult, decide, gate_lifecycle_dry_run, gate_runtime_smoke


def test_decide_go_when_all_pass() -> None:
    gates = [
        {"id": "g1", "mandatory": True, "passed": True},
        {"id": "g2", "mandatory": True, "passed": True},
        {"id": "g3", "mandatory": False, "passed": True},
    ]
    verdict, _ = decide(gates, allow_limited_go=True)
    assert verdict == "GO"


def test_decide_limited_go_when_optional_fails() -> None:
    gates = [
        {"id": "g1", "mandatory": True, "passed": True},
        {"id": "g2", "mandatory": True, "passed": True},
        {"id": "g_opt", "mandatory": False, "passed": False},
    ]
    verdict, reason = decide(gates, allow_limited_go=True)
    assert verdict == "LIMITED_GO"
    assert "g_opt" in reason


def test_decide_no_go_when_mandatory_fails() -> None:
    gates = [
        {"id": "g1", "mandatory": True, "passed": False},
        {"id": "g2", "mandatory": True, "passed": True},
        {"id": "g_opt", "mandatory": False, "passed": True},
    ]
    verdict, _ = decide(gates, allow_limited_go=True)
    assert verdict == "NO_GO"


def test_decide_no_go_when_optional_fails_and_limited_not_allowed() -> None:
    gates = [
        {"id": "g1", "mandatory": True, "passed": True},
        {"id": "g2", "mandatory": True, "passed": True},
        {"id": "g_opt", "mandatory": False, "passed": False},
    ]
    verdict, _ = decide(gates, allow_limited_go=False)
    assert verdict == "NO_GO"


def test_gate_runtime_smoke_covers_builder_regressions() -> None:
    with patch("tools.pilot_exit_check.run_cmd", return_value=CmdResult(0, "", "")):
        gate = gate_runtime_smoke("python", timeout_s=1)
    command = str(gate["command"])

    assert "tests/unit/test_personalization_resolution.py" in command
    assert "tests/unit/test_models_routes.py" in command
    assert "tests/unit/test_voices_view_validation.py" in command


def test_gate_lifecycle_dry_run_writes_expected_artifact_command() -> None:
    with patch("tools.pilot_exit_check.run_cmd", return_value=CmdResult(0, "", "")):
        gate = gate_lifecycle_dry_run("python", timeout_s=1)
    command = str(gate["command"])

    assert "tools/validate_live_lifecycle.py" in command
    assert "--mode dry" in command
    assert gate["snapshot"] == "runtime/lifecycle_validation_report.json"
