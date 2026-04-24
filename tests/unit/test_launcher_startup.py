"""
tests/unit/test_launcher_startup.py

TR54-D1: Startup sequence reliability.

Verifies that complete_startup_phase does not raise for each known phase name
and that startup phase transitions are deterministic and properly recorded.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.guppy.launcher_application.launcher_poll_orchestration import complete_startup_phase

# All phase names that LauncherWindow and launcher_app.py emit.
KNOWN_STARTUP_PHASES = [
    "build_ui",
    "status_poll_start",
    "first_status_poll",
    "window_init",
    "bootstrap_services",
    "bootstrap_services_begin",
    "bootstrap_services_complete",
    "api_autostart_debounced",
    "hub_autostart_debounced",
    "hub_autostart_skipped",
    "personalization_scaffold_thread_start",
]


def _make_owner(budget_ms: int = 3000) -> SimpleNamespace:
    """Return a minimal owner stub accepted by complete_startup_phase."""
    status_panel = MagicMock()
    status_panel.append_syslog = MagicMock()
    owner = SimpleNamespace(
        _startup_budget_ms=budget_ms,
        _startup_phase_started={phase: time.monotonic() for phase in KNOWN_STARTUP_PHASES},
        _startup_phase_durations_ms={},
        _startup_over_budget=[],
        _status_panel=status_panel,
    )
    owner._log_launcher_event = MagicMock()
    return owner


class TestCompleteStartupPhaseKnownPhases:
    """Each known phase name must not raise."""

    @pytest.mark.parametrize("phase", KNOWN_STARTUP_PHASES)
    def test_known_phase_does_not_raise(self, phase: str) -> None:
        owner = _make_owner()
        complete_startup_phase(owner, phase)  # must not raise

    @pytest.mark.parametrize("phase", KNOWN_STARTUP_PHASES)
    def test_known_phase_records_duration(self, phase: str) -> None:
        owner = _make_owner()
        complete_startup_phase(owner, phase)
        assert phase in owner._startup_phase_durations_ms
        assert owner._startup_phase_durations_ms[phase] >= 0


class TestCompleteStartupPhaseTransitions:
    """Determinism: duration is always recorded, budget logic is explicit."""

    def test_duration_is_non_negative(self) -> None:
        owner = _make_owner()
        complete_startup_phase(owner, "build_ui")
        assert owner._startup_phase_durations_ms["build_ui"] >= 0

    def test_within_budget_produces_no_over_budget_entry(self) -> None:
        owner = _make_owner(budget_ms=99_999)
        owner._startup_phase_started["build_ui"] = time.monotonic()
        complete_startup_phase(owner, "build_ui")
        assert not owner._startup_over_budget

    def test_over_budget_appends_phase_entry(self) -> None:
        # budget_ms=-1 ensures dur_ms (always >=0) is always > budget
        owner = _make_owner(budget_ms=-1)
        complete_startup_phase(owner, "build_ui")
        assert any("build_ui" in item for item in owner._startup_over_budget)

    def test_over_budget_calls_syslog(self) -> None:
        owner = _make_owner(budget_ms=-1)
        complete_startup_phase(owner, "build_ui")
        owner._status_panel.append_syslog.assert_called()

    def test_custom_start_at_is_respected(self) -> None:
        owner = _make_owner()
        start = time.monotonic() - 0.05  # ~50 ms ago; allow ±10 ms jitter
        complete_startup_phase(owner, "first_status_poll", start_at=start)
        assert owner._startup_phase_durations_ms["first_status_poll"] >= 40

    def test_log_event_called_for_duration(self) -> None:
        owner = _make_owner()
        complete_startup_phase(owner, "build_ui")
        call_names = [c[0][0] for c in owner._log_launcher_event.call_args_list]
        assert "startup_phase_duration" in call_names

    def test_unknown_phase_does_not_raise(self) -> None:
        """Phases not listed in KNOWN_STARTUP_PHASES must also be safe."""
        owner = _make_owner()
        complete_startup_phase(owner, "unknown_phase_xyz_tr54d1")
        assert "unknown_phase_xyz_tr54d1" in owner._startup_phase_durations_ms

    def test_no_status_panel_does_not_raise(self) -> None:
        """complete_startup_phase is safe even if _status_panel is absent."""
        owner = _make_owner(budget_ms=0)
        del owner._status_panel
        complete_startup_phase(owner, "build_ui")  # must not raise

    def test_multiple_phases_each_recorded_independently(self) -> None:
        owner = _make_owner()
        for phase in ("build_ui", "status_poll_start", "first_status_poll"):
            complete_startup_phase(owner, phase)
        for phase in ("build_ui", "status_poll_start", "first_status_poll"):
            assert phase in owner._startup_phase_durations_ms
