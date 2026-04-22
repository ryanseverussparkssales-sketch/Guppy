from tools import check_new_module_line_cap


def test_classify_module_size_uses_hardening_tiers(monkeypatch) -> None:
    monkeypatch.setattr(check_new_module_line_cap, "IDEAL_MODULE_LINES", 250)
    monkeypatch.setattr(check_new_module_line_cap, "HEALTHY_MODULE_LINES", 400)
    monkeypatch.setattr(check_new_module_line_cap, "REVIEW_MODULE_LINES", 600)
    monkeypatch.setattr(check_new_module_line_cap, "LINE_CAP", 700)

    assert check_new_module_line_cap.classify_module_size(200) == "ideal"
    assert check_new_module_line_cap.classify_module_size(320) == "healthy"
    assert check_new_module_line_cap.classify_module_size(520) == "review"
    assert check_new_module_line_cap.classify_module_size(650) == "urgent"
    assert check_new_module_line_cap.classify_module_size(701) == "oversized"


def test_live_launcher_shell_is_tracked_in_enforced_prefixes() -> None:
    assert "compat_shims/launcher_ui/ui/launcher/" in check_new_module_line_cap.ENFORCED_PREFIXES
    assert (
        "compat_shims/launcher_ui/ui/launcher/launcher_window.py"
        not in check_new_module_line_cap.WAIVED_PATHS
    )


def test_waiver_drift_note_reports_stale_metadata(monkeypatch) -> None:
    monkeypatch.setattr(check_new_module_line_cap, "WAIVER_DRIFT_WARN_LINES", 25)
    waiver = check_new_module_line_cap.Waiver(
        max_lines=200,
        rationale="transitional hotspot",
    )

    note = check_new_module_line_cap._waiver_drift_note(  # pylint: disable=protected-access
        "ui/launcher/views/example.py",
        line_count=100,
        waiver=waiver,
    )

    assert "metadata drift: 100 lines of stale waiver headroom" in note
    assert "transitional hotspot" in note


def test_waiver_drift_note_reports_low_headroom(monkeypatch) -> None:
    monkeypatch.setattr(check_new_module_line_cap, "WAIVER_DRIFT_WARN_LINES", 25)
    waiver = check_new_module_line_cap.Waiver(
        max_lines=200,
        rationale="transitional hotspot",
    )

    note = check_new_module_line_cap._waiver_drift_note(  # pylint: disable=protected-access
        "ui/launcher/views/example.py",
        line_count=190,
        waiver=waiver,
    )

    assert "headroom 10" in note


def test_module_size_summary_reports_relative_path_and_tier(monkeypatch) -> None:
    monkeypatch.setattr(check_new_module_line_cap, "IDEAL_MODULE_LINES", 250)
    monkeypatch.setattr(check_new_module_line_cap, "HEALTHY_MODULE_LINES", 400)
    monkeypatch.setattr(check_new_module_line_cap, "REVIEW_MODULE_LINES", 600)
    monkeypatch.setattr(check_new_module_line_cap, "LINE_CAP", 700)

    summary = check_new_module_line_cap._module_size_summary(  # pylint: disable=protected-access
        check_new_module_line_cap.Path("src/guppy/example.py"),
        620,
    )

    assert summary == "src/guppy/example.py: 620 lines [urgent]"
