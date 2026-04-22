from tools import check_new_module_line_cap


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
