"""First-run wizard state machine (PL-C5).

Stateful three-checkpoint wizard for new Guppy installs. Designed to run
once per workspace; subsequent runs are skipped if all checkpoints passed.

Checkpoints
-----------
1. Install readiness — basic desktop install OK (Track 1)
2. Model runtime detected — one declared local runtime path reachable (Track 2)
3. First successful request — a minimal API round-trip completed

State is persisted in ``runtime/first_run_state.json``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from src.guppy.launcher_application.install_readiness import run_install_readiness
from src.guppy.launcher_application.local_model_readiness import run_local_model_readiness

_LOG = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_PATH = _REPO_ROOT / "runtime" / "first_run_state.json"

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class CheckpointStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckpointResult:
    checkpoint: int
    status: CheckpointStatus
    summary: str
    detail: dict[str, object] = field(default_factory=dict)
    remediation: str = ""

    def as_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class WizardState:
    """Persisted state for the first-run wizard."""

    version: int = 1
    workspace_id: str = "default"
    checkpoints: dict[str, str] = field(default_factory=dict)
    """Keys are "1", "2", "3"; values are CheckpointStatus values."""
    all_passed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WizardState":
        obj = cls()
        obj.version = int(data.get("version", 1))
        obj.workspace_id = str(data.get("workspace_id", "default") or "default")
        raw_checkpoints = data.get("checkpoints")
        if isinstance(raw_checkpoints, dict):
            obj.checkpoints = {
                str(k): str(v)
                for k, v in raw_checkpoints.items()
                if str(k) in {"1", "2", "3"}
            }
        obj.all_passed = bool(data.get("all_passed", False))
        return obj

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def get_status(self, checkpoint: int) -> CheckpointStatus:
        value = self.checkpoints.get(str(checkpoint), CheckpointStatus.PENDING.value)
        try:
            return CheckpointStatus(value)
        except ValueError:
            return CheckpointStatus.PENDING

    def set_status(self, checkpoint: int, status: CheckpointStatus) -> None:
        self.checkpoints[str(checkpoint)] = status.value
        self.all_passed = all(
            self.get_status(n) == CheckpointStatus.PASSED for n in (1, 2, 3)
        )

    def is_complete(self) -> bool:
        return self.all_passed

    def should_skip(self) -> bool:
        """Return True if all checkpoints already passed — wizard should be skipped."""
        return self.all_passed


# ---------------------------------------------------------------------------
# FirstRunWizard
# ---------------------------------------------------------------------------


class FirstRunWizard:
    """Stateful three-checkpoint first-run wizard.

    Args:
        state_path: Path to the JSON state file. Defaults to runtime/first_run_state.json.
        workspace_id: Logical workspace identifier for multi-workspace setups.
        request_verifier: Optional callable returning bool for checkpoint 3.
            Receives no arguments. When None, checkpoint 3 fails closed until a
            real request verifier is provided.
    """

    def __init__(
        self,
        *,
        state_path: Path | None = None,
        workspace_id: str = "default",
        request_verifier: Callable[[], bool] | None = None,
    ) -> None:
        self._state_path = state_path or _STATE_PATH
        self._workspace_id = workspace_id
        self._request_verifier = request_verifier
        self._state = self._load_state()

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> WizardState:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                state = WizardState.from_dict(data)
                if state.workspace_id == self._workspace_id:
                    return state
        except Exception as exc:
            _LOG.warning("first_run_wizard: could not load state: %s", exc)
        return WizardState(workspace_id=self._workspace_id)

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(self._state.as_dict(), indent=2), encoding="utf-8"
            )
        except Exception as exc:
            _LOG.warning("first_run_wizard: could not save state: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> WizardState:
        return self._state

    def should_skip(self) -> bool:
        """Return True if wizard is already complete for this workspace."""
        return self._state.should_skip()

    def run_checkpoint_1(self) -> CheckpointResult:
        """Checkpoint 1 — desktop install readiness (Track 1).

        Passes when all required install readiness checks pass.
        """
        if self._state.get_status(1) == CheckpointStatus.PASSED:
            return CheckpointResult(
                checkpoint=1,
                status=CheckpointStatus.PASSED,
                summary="Install readiness already passed.",
            )

        result = run_install_readiness()
        failed = result.get("failed", [])
        if not failed:
            status = CheckpointStatus.PASSED
            summary = "Install readiness check passed."
            remediation = ""
        else:
            status = CheckpointStatus.FAILED
            summary = f"Install readiness check failed: {', '.join(str(f) for f in failed)}"
            remediation = (
                "Fix the failing checks above and run checkpoint 1 again. "
                "Common fixes: ensure guppy_launcher.py is present at the repo root "
                "and that runtime/ is writable."
            )

        self._state.set_status(1, status)
        self._save_state()
        _LOG.info("first_run_checkpoint_1_completed status=%s", status.value)

        return CheckpointResult(
            checkpoint=1,
            status=status,
            summary=summary,
            detail=dict(result),
            remediation=remediation,
        )

    def run_checkpoint_2(self) -> CheckpointResult:
        """Checkpoint 2 — local model runtime detected (Track 2).

        Passes when at least one declared local runtime path is ready.
        Ollama with a pulled model, LM Studio, or the local harness can
        satisfy this checkpoint; optional challenger checks are reported
        but do not block.
        """
        if self._state.get_status(2) == CheckpointStatus.PASSED:
            return CheckpointResult(
                checkpoint=2,
                status=CheckpointStatus.PASSED,
                summary="Model runtime detection already passed.",
            )

        result = run_local_model_readiness()
        failed = result.get("failed", [])
        ready_runtimes = [
            str(item).strip()
            for item in result.get("ready_runtimes", [])
            if str(item).strip()
        ]
        if not failed:
            status = CheckpointStatus.PASSED
            summary = "Model runtime detection passed."
            if ready_runtimes:
                summary += " Ready via " + ", ".join(ready_runtimes) + "."
            remediation = ""
        else:
            status = CheckpointStatus.FAILED
            summary = f"Model runtime detection failed: {', '.join(str(f) for f in failed)}"
            remediation = (
                "Bring up one supported local runtime path, then run checkpoint 2 again. "
                "Examples: start Ollama and pull at least one model (`ollama pull llama3.2`), "
                "enable the LM Studio local server on `http://127.0.0.1:1234`, or start the local harness on `http://127.0.0.1:8001`."
            )

        self._state.set_status(2, status)
        self._save_state()
        _LOG.info("first_run_checkpoint_2_completed status=%s", status.value)

        return CheckpointResult(
            checkpoint=2,
            status=status,
            summary=summary,
            detail=dict(result),
            remediation=remediation,
        )

    def run_checkpoint_3(self) -> CheckpointResult:
        """Checkpoint 3 — first successful request.

        If a ``request_verifier`` callable was provided at construction, it
        is called and its bool return value determines pass/fail.
        When no verifier is provided, this checkpoint fails closed so the
        readiness lane cannot claim a successful request without evidence.
        """
        if self._state.get_status(3) == CheckpointStatus.PASSED:
            return CheckpointResult(
                checkpoint=3,
                status=CheckpointStatus.PASSED,
                summary="First request verification already passed.",
            )

        if self._request_verifier is None:
            status = CheckpointStatus.FAILED
            summary = "First request verification is blocked until a real request verifier is configured."
            remediation = (
                "Wire a real request verifier into the first-run wizard, then complete one successful Home or API request "
                "before marking checkpoint 3 as passed."
            )
        else:
            try:
                ok = bool(self._request_verifier())
            except Exception as exc:
                ok = False
                _LOG.warning("first_run_wizard checkpoint 3 verifier raised: %s", exc)

            if ok:
                status = CheckpointStatus.PASSED
                summary = "First successful request completed."
                remediation = ""
            else:
                status = CheckpointStatus.FAILED
                summary = "First request verification failed."
                remediation = (
                    "Ensure the Guppy API is running (`python guppy_api.py`), "
                    "then try a test message in the Home hub. Run checkpoint 3 again once the API responds."
                )

        self._state.set_status(3, status)
        self._save_state()
        _LOG.info("first_run_checkpoint_3_completed status=%s", status.value)

        return CheckpointResult(
            checkpoint=3,
            status=status,
            summary=summary,
            remediation=remediation,
        )

    def run_all(self) -> list[CheckpointResult]:
        """Run all three checkpoints in sequence.

        Short-circuits after the first FAILED checkpoint: later checkpoints
        are returned with status SKIPPED and a note explaining they depend
        on the prior checkpoint.
        """
        if self.should_skip():
            return [
                CheckpointResult(
                    checkpoint=n,
                    status=CheckpointStatus.PASSED,
                    summary="Already passed — wizard complete.",
                )
                for n in (1, 2, 3)
            ]

        results: list[CheckpointResult] = []
        blocked = False
        runners = [self.run_checkpoint_1, self.run_checkpoint_2, self.run_checkpoint_3]
        for n, runner in enumerate(runners, start=1):
            if blocked:
                results.append(
                    CheckpointResult(
                        checkpoint=n,
                        status=CheckpointStatus.SKIPPED,
                        summary=f"Checkpoint {n} skipped — checkpoint {n - 1} must pass first.",
                        remediation=f"Fix checkpoint {n - 1}, then re-run the wizard.",
                    )
                )
            else:
                result = runner()
                results.append(result)
                if result.status == CheckpointStatus.FAILED:
                    blocked = True
        return results

    def skip_checkpoint(self, checkpoint: int) -> None:
        """Mark a checkpoint as skipped (operator override)."""
        if checkpoint not in (1, 2, 3):
            raise ValueError(f"checkpoint must be 1, 2, or 3; got {checkpoint!r}")
        self._state.set_status(checkpoint, CheckpointStatus.SKIPPED)
        self._save_state()
        _LOG.info("first_run_checkpoint_%d_skipped", checkpoint)

    def reset(self) -> None:
        """Reset all checkpoint state for this workspace."""
        self._state = WizardState(workspace_id=self._workspace_id)
        self._save_state()
        _LOG.info("first_run_wizard_reset workspace=%s", self._workspace_id)
