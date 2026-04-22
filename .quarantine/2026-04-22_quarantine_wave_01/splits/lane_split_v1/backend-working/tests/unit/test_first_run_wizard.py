"""Unit tests for first_run_wizard.py (PL-C5).

Tests cover:
- WizardState persistence and round-trip
- Checkpoint status transitions (pending → passed, pending → failed)
- run_all short-circuit on first failure
- skip_checkpoint operator override
- should_skip / is_complete logic
- request_verifier integration in checkpoint 3
- reset()
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.guppy.launcher_application.first_run_wizard import (
    CheckpointResult,
    CheckpointStatus,
    FirstRunWizard,
    WizardState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_state_path() -> Path:
    """Return a path inside a temporary directory (does not create the file)."""
    d = tempfile.mkdtemp()
    return Path(d) / "first_run_state.json"


def _passing_install() -> dict:
    return {"passed": ["check_a", "check_b"], "failed": [], "summary": "All OK"}


def _failing_install() -> dict:
    return {"passed": [], "failed": ["launcher_entrypoint"], "summary": "Failed: launcher_entrypoint"}


def _passing_model() -> dict:
    return {
        "passed": ["ollama_cli", "ollama_daemon", "ollama_model_pulled"],
        "failed": [],
        "optional_absent": [],
        "ready_runtimes": ["ollama"],
        "summary": "All OK",
    }


def _failing_model() -> dict:
    return {"passed": [], "failed": ["ollama_cli", "ollama_daemon", "ollama_model_pulled"], "optional_absent": [], "summary": "Failed"}


# ---------------------------------------------------------------------------
# WizardState
# ---------------------------------------------------------------------------


class TestWizardState:
    def test_default_state_is_all_pending(self) -> None:
        state = WizardState()
        for n in (1, 2, 3):
            assert state.get_status(n) == CheckpointStatus.PENDING

    def test_set_status_and_get_status(self) -> None:
        state = WizardState()
        state.set_status(1, CheckpointStatus.PASSED)
        assert state.get_status(1) == CheckpointStatus.PASSED
        assert state.get_status(2) == CheckpointStatus.PENDING

    def test_all_passed_when_all_three_passed(self) -> None:
        state = WizardState()
        for n in (1, 2, 3):
            state.set_status(n, CheckpointStatus.PASSED)
        assert state.all_passed is True

    def test_all_passed_false_if_one_pending(self) -> None:
        state = WizardState()
        state.set_status(1, CheckpointStatus.PASSED)
        state.set_status(2, CheckpointStatus.PASSED)
        # 3 is still pending
        assert state.all_passed is False

    def test_round_trip_via_dict(self) -> None:
        state = WizardState(workspace_id="my-workspace")
        state.set_status(1, CheckpointStatus.PASSED)
        state.set_status(2, CheckpointStatus.FAILED)
        restored = WizardState.from_dict(state.as_dict())
        assert restored.workspace_id == "my-workspace"
        assert restored.get_status(1) == CheckpointStatus.PASSED
        assert restored.get_status(2) == CheckpointStatus.FAILED
        assert restored.get_status(3) == CheckpointStatus.PENDING

    def test_from_dict_ignores_invalid_checkpoint_keys(self) -> None:
        state = WizardState.from_dict({"checkpoints": {"9": "passed", "1": "passed"}})
        assert state.get_status(1) == CheckpointStatus.PASSED
        assert state.get_status(2) == CheckpointStatus.PENDING

    def test_should_skip_only_when_all_passed(self) -> None:
        state = WizardState()
        assert state.should_skip() is False
        for n in (1, 2, 3):
            state.set_status(n, CheckpointStatus.PASSED)
        assert state.should_skip() is True


# ---------------------------------------------------------------------------
# FirstRunWizard — checkpoint 1
# ---------------------------------------------------------------------------


class TestCheckpoint1:
    def test_passes_when_install_readiness_has_no_failures(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_passing_install(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            result = wizard.run_checkpoint_1()
        assert result.status == CheckpointStatus.PASSED
        assert result.checkpoint == 1

    def test_fails_when_install_readiness_has_failures(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_failing_install(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            result = wizard.run_checkpoint_1()
        assert result.status == CheckpointStatus.FAILED
        assert "launcher_entrypoint" in result.summary
        assert result.remediation.strip()

    def test_already_passed_skips_re_run(self) -> None:
        path = _tmp_state_path()
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_passing_install(),
        ):
            wizard = FirstRunWizard(state_path=path)
            wizard.run_checkpoint_1()
        # Second wizard with same path — should not call run_install_readiness again
        mock = MagicMock(return_value=_passing_install())
        with patch("src.guppy.launcher_application.first_run_wizard.run_install_readiness", mock):
            wizard2 = FirstRunWizard(state_path=path)
            result = wizard2.run_checkpoint_1()
        mock.assert_not_called()
        assert result.status == CheckpointStatus.PASSED

    def test_result_has_detail_dict(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_failing_install(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            result = wizard.run_checkpoint_1()
        assert isinstance(result.detail, dict)
        assert "failed" in result.detail


# ---------------------------------------------------------------------------
# FirstRunWizard — checkpoint 2
# ---------------------------------------------------------------------------


class TestCheckpoint2:
    def test_passes_when_model_readiness_has_no_failures(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
            return_value=_passing_model(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            result = wizard.run_checkpoint_2()
        assert result.status == CheckpointStatus.PASSED
        assert result.checkpoint == 2
        assert "Ready via ollama." in result.summary

    def test_fails_when_model_readiness_has_required_failures(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
            return_value=_failing_model(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            result = wizard.run_checkpoint_2()
        assert result.status == CheckpointStatus.FAILED
        assert result.remediation.strip()


# ---------------------------------------------------------------------------
# FirstRunWizard — checkpoint 3
# ---------------------------------------------------------------------------


class TestCheckpoint3:
    def test_fails_closed_without_verifier(self) -> None:
        wizard = FirstRunWizard(state_path=_tmp_state_path())
        result = wizard.run_checkpoint_3()
        assert result.status == CheckpointStatus.FAILED
        assert "blocked" in result.summary.lower()

    def test_passes_when_verifier_returns_true(self) -> None:
        wizard = FirstRunWizard(state_path=_tmp_state_path(), request_verifier=lambda: True)
        result = wizard.run_checkpoint_3()
        assert result.status == CheckpointStatus.PASSED

    def test_fails_when_verifier_returns_false(self) -> None:
        wizard = FirstRunWizard(state_path=_tmp_state_path(), request_verifier=lambda: False)
        result = wizard.run_checkpoint_3()
        assert result.status == CheckpointStatus.FAILED
        assert result.remediation.strip()

    def test_fails_gracefully_when_verifier_raises(self) -> None:
        def bad_verifier() -> bool:
            raise RuntimeError("network error")

        wizard = FirstRunWizard(state_path=_tmp_state_path(), request_verifier=bad_verifier)
        result = wizard.run_checkpoint_3()
        assert result.status == CheckpointStatus.FAILED


# ---------------------------------------------------------------------------
# FirstRunWizard — run_all
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_returns_three_results(self) -> None:
        with (
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
                return_value=_passing_install(),
            ),
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
                return_value=_passing_model(),
            ),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path(), request_verifier=lambda: True)
            results = wizard.run_all()
        assert len(results) == 3

    def test_all_pass_sets_wizard_complete(self) -> None:
        with (
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
                return_value=_passing_install(),
            ),
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
                return_value=_passing_model(),
            ),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path(), request_verifier=lambda: True)
            results = wizard.run_all()
        assert all(r.status == CheckpointStatus.PASSED for r in results)
        assert wizard.should_skip() is True

    def test_short_circuits_after_checkpoint_1_failure(self) -> None:
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_failing_install(),
        ):
            wizard = FirstRunWizard(state_path=_tmp_state_path())
            results = wizard.run_all()
        assert results[0].status == CheckpointStatus.FAILED
        assert results[1].status == CheckpointStatus.SKIPPED
        assert results[2].status == CheckpointStatus.SKIPPED

    def test_run_all_when_already_complete_returns_all_passed(self) -> None:
        path = _tmp_state_path()
        with (
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
                return_value=_passing_install(),
            ),
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
                return_value=_passing_model(),
            ),
        ):
            FirstRunWizard(state_path=path, request_verifier=lambda: True).run_all()
        # Re-run: no patches needed, should skip
        results = FirstRunWizard(state_path=path).run_all()
        assert all(r.status == CheckpointStatus.PASSED for r in results)


# ---------------------------------------------------------------------------
# FirstRunWizard — skip and reset
# ---------------------------------------------------------------------------


class TestSkipAndReset:
    def test_skip_checkpoint_marks_skipped(self) -> None:
        wizard = FirstRunWizard(state_path=_tmp_state_path())
        wizard.skip_checkpoint(1)
        assert wizard.state.get_status(1) == CheckpointStatus.SKIPPED

    def test_skip_invalid_checkpoint_raises(self) -> None:
        wizard = FirstRunWizard(state_path=_tmp_state_path())
        with pytest.raises(ValueError):
            wizard.skip_checkpoint(99)

    def test_reset_clears_all_checkpoints(self) -> None:
        path = _tmp_state_path()
        with (
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
                return_value=_passing_install(),
            ),
            patch(
                "src.guppy.launcher_application.first_run_wizard.run_local_model_readiness",
                return_value=_passing_model(),
            ),
        ):
            wizard = FirstRunWizard(state_path=path, request_verifier=lambda: True)
            wizard.run_all()
        assert wizard.should_skip() is True
        wizard.reset()
        assert wizard.should_skip() is False
        assert wizard.state.get_status(1) == CheckpointStatus.PENDING


# ---------------------------------------------------------------------------
# FirstRunWizard — state file persistence
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_state_saved_after_checkpoint_1(self) -> None:
        path = _tmp_state_path()
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_passing_install(),
        ):
            wizard = FirstRunWizard(state_path=path)
            wizard.run_checkpoint_1()
        assert path.exists()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["checkpoints"]["1"] == "passed"

    def test_state_reloaded_on_next_wizard_instance(self) -> None:
        path = _tmp_state_path()
        with patch(
            "src.guppy.launcher_application.first_run_wizard.run_install_readiness",
            return_value=_passing_install(),
        ):
            FirstRunWizard(state_path=path).run_checkpoint_1()
        wizard2 = FirstRunWizard(state_path=path)
        assert wizard2.state.get_status(1) == CheckpointStatus.PASSED

    def test_corrupt_state_file_defaults_to_fresh_state(self) -> None:
        path = _tmp_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json {{{", encoding="utf-8")
        wizard = FirstRunWizard(state_path=path)
        assert wizard.state.get_status(1) == CheckpointStatus.PENDING
