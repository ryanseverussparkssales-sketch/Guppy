from __future__ import annotations

from types import SimpleNamespace

from src.guppy.api import services_briefing


def _fake_owner(tmp_path, **overrides):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    owner = SimpleNamespace(
        _path_config=SimpleNamespace(runtime_dir=runtime_dir),
        GUPPY_MEMORY_AVAILABLE=True,
        memory=SimpleNamespace(get_tasks=lambda status: "1. Ship packaging audit\n2. Review traces"),
        _read_resource_envelope_status=lambda: {"state": "ready", "message": "cpu steady"},
        _startup_readiness_cached_or_unknown=lambda: {"overall": "READY"},
    )
    for key, value in overrides.items():
        setattr(owner, key, value)
    return owner


def test_request_is_morning_brief_accepts_follow_up_affirmation_with_history() -> None:
    request = SimpleNamespace(
        message="Yes please",
        history=[
            {"role": "assistant", "content": "I can prepare a morning brief if you want."},
        ],
    )

    assert services_briefing.request_is_morning_brief(request) is True


def test_request_is_morning_brief_rejects_plain_affirmation_without_offer() -> None:
    request = SimpleNamespace(message="Yes please", history=[])

    assert services_briefing.request_is_morning_brief(request) is False


def test_build_morning_brief_response_reads_saved_report_and_runtime_state(tmp_path) -> None:
    owner = _fake_owner(tmp_path)
    report_dir = owner._path_config.runtime_dir / "daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "2026-04-19.md"
    report_path.write_text(
        "\n".join(
            [
                "## Key Actions",
                "- Finish launcher audit",
                "- Verify packaging paths",
                "## Carry-Forward Items",
                "- Recheck connector backlog",
                "## World News",
                "- Runtime monitoring quiet",
            ]
        ),
        encoding="utf-8",
    )

    text = services_briefing.build_morning_brief_response(owner)

    assert "Top priorities:" in text
    assert "- Finish launcher audit" in text
    assert "Pending tasks:" in text
    assert "System status: resource envelope ready; startup readiness ready." in text
    assert "runtime/daily_reports/2026-04-19.md" in text


def test_build_morning_brief_response_falls_back_to_live_context_without_report(tmp_path) -> None:
    owner = _fake_owner(
        tmp_path,
        GUPPY_MEMORY_AVAILABLE=False,
        _read_resource_envelope_status=lambda: {"state": "warning", "message": ""},
        _startup_readiness_cached_or_unknown=lambda: {"overall": "PARTIAL"},
    )

    text = services_briefing.build_morning_brief_response(owner)

    assert "System status: resource envelope warning; startup readiness partial." in text
    assert "No saved daily report is available yet" in text


def test_build_morning_brief_response_supports_snapshot_style_runtime_dir_owner(tmp_path) -> None:
    runtime_dir = tmp_path / "runtime"
    report_dir = runtime_dir / "daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "2026-04-19.md").write_text(
        "## Key Actions\n- Reuse shared briefing helper",
        encoding="utf-8",
    )
    owner = SimpleNamespace(
        _runtime_dir=runtime_dir,
        GUPPY_MEMORY_AVAILABLE=False,
        memory=SimpleNamespace(get_tasks=lambda status: ""),
        _read_resource_envelope_status=lambda: {"state": "ready", "message": "snapshot stable"},
        _startup_readiness_cached_or_unknown=lambda: {"overall": "READY"},
    )

    text = services_briefing.build_morning_brief_response(owner)

    assert "Top priorities:" in text
    assert "- Reuse shared briefing helper" in text
    assert "runtime/daily_reports/2026-04-19.md" in text
