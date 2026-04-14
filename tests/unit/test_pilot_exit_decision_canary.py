from tools.pilot_exit_check import decide


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
