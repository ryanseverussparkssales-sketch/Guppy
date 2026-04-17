"""Reusable workflow definitions for launcher and build tooling consumers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    """One shell command within a workflow."""

    command: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowSpec:
    """Versioned workflow definition shared by UI and tooling."""

    workflow_id: str
    title: str
    summary: str
    category: str
    commands: tuple[WorkflowCommand, ...]
    next_step: str = ""
    docs_hint: str = ""
    review_order: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def first_command(self) -> str:
        return self.commands[0].command if self.commands else ""

    def command_strings(self) -> tuple[str, ...]:
        return tuple(item.command for item in self.commands)


def _command(command: str, summary: str = "") -> WorkflowCommand:
    return WorkflowCommand(command=command, summary=summary)


_WORKFLOWS: tuple[WorkflowSpec, ...] = (
    WorkflowSpec(
        workflow_id="morning_boot",
        title="MORNING BOOT",
        summary="Start the day with the pilot gate and the fast canary checks.",
        category="workflow_loop",
        commands=(
            _command("python tools/pilot_exit_check.py --allow-limited-go"),
            _command("python -m pytest -q tests/test_pilot_exit_decision_canary.py"),
            _command("python tools/run_triage_fault_canary.py"),
        ),
        next_step="Review the pilot decision and canary output before opening broader work.",
        docs_hint="README.md",
        tags=("daily", "pilot", "readiness"),
    ),
    WorkflowSpec(
        workflow_id="acceptance_snapshot",
        title="ACCEPTANCE SNAPSHOT",
        summary="Run the signed evidence sequence after major functionality, auth, or security changes.",
        category="workflow_loop",
        commands=(
            _command(
                "python -m pytest tests/unit/test_security_hardening.py tests/smoke/test_launcher_interactions_smoke.py -W error::DeprecationWarning"
            ),
            _command("python -m pytest tests/smoke/test_runtime_smoke.py -v"),
            _command("python tools/check_architecture_boundaries.py"),
            _command("python tools/check_new_module_line_cap.py"),
            _command("python tools/check_wrapper_integrity.py"),
            _command("python tools/check_core_surface_integrity.py"),
            _command("python tools/check_doc_ownership.py"),
            _command("python tools/verify_logging_health.py --emit-probe --require-fresh-core"),
        ),
        next_step="Archive the acceptance evidence once smoke, boundaries, and ownership checks all pass.",
        docs_hint="docs/PROJECT_BRIEF.md",
        tags=("acceptance", "smoke", "guardrails"),
    ),
    WorkflowSpec(
        workflow_id="midday_stability",
        title="MIDDAY STABILITY",
        summary="Refresh telemetry and local-model health when behavior starts to drift.",
        category="workflow_loop",
        commands=(
            _command("python tools/verify_logging_health.py --emit-probe --require-fresh-core"),
            _command("python tools/verify_ollama_runtime.py --prompt ok"),
        ),
        next_step="If runtime health still drifts, follow with challenger verification and review recent operator logs.",
        docs_hint="docs/TROUBLESHOOTING.md",
        tags=("stability", "runtime", "telemetry"),
    ),
    WorkflowSpec(
        workflow_id="evening_close",
        title="EVENING CLOSE",
        summary="Re-check pilot readiness and write the day-end triage summary.",
        category="workflow_loop",
        commands=(
            _command("python tools/pilot_exit_check.py --allow-limited-go"),
            _command("python tools/generate_triage_summary.py"),
        ),
        next_step="Share the generated triage summary with the next-day handoff.",
        docs_hint="ROADMAP.md",
        tags=("daily", "handoff", "summary"),
    ),
    WorkflowSpec(
        workflow_id="overnight_low_compute",
        title="OVERNIGHT LOW-COMPUTE",
        summary="Queue the lower-cost unattended verification loop.",
        category="workflow_loop",
        commands=(
            _command("python tools/run_overnight_low_compute.py --cycles 3 --interval-minutes 180"),
        ),
        next_step="Review the unattended verification results before starting the next active session.",
        docs_hint="README.md",
        tags=("overnight", "low-compute", "automation"),
    ),
    WorkflowSpec(
        workflow_id="windows_verify_runtime",
        title="WINDOWS VERIFY",
        summary="Refresh local runtime readiness, challenger availability, and logging-health evidence.",
        category="windows_ops",
        commands=(
            _command(".venv\\Scripts\\python.exe tools/verify_ollama_runtime.py --prompt ok"),
            _command(".venv\\Scripts\\python.exe tools/verify_runtime_challengers.py"),
            _command(".venv\\Scripts\\python.exe tools/verify_logging_health.py --emit-probe --require-fresh-core"),
        ),
        next_step="If verification passes, either package a new desktop build or continue normal operator use.",
        docs_hint="docs/PACKAGING.md",
        tags=("windows", "verify", "runtime"),
    ),
    WorkflowSpec(
        workflow_id="windows_update_runtime",
        title="WINDOWS UPDATE",
        summary="Refresh Python packaging tools, runtime dependencies, and post-update validation.",
        category="windows_ops",
        commands=(
            _command(".venv\\Scripts\\python.exe -m pip install --upgrade pip setuptools wheel"),
            _command(".venv\\Scripts\\python.exe -m pip install -r requirements.txt"),
            _command(".venv\\Scripts\\python.exe -m pip install -r requirements-optional.txt"),
            _command(".venv\\Scripts\\python.exe tools/validate_build_checks.py"),
            _command(".venv\\Scripts\\python.exe tools/verify_ollama_runtime.py --prompt ok"),
            _command(".venv\\Scripts\\python.exe tools/verify_runtime_challengers.py"),
        ),
        next_step="Rerun verify after major runtime changes, then package if the build lane is needed.",
        docs_hint="docs/PACKAGING.md",
        tags=("windows", "update", "servicing"),
    ),
    WorkflowSpec(
        workflow_id="windows_package_desktop",
        title="WINDOWS PACKAGE",
        summary="Build the desktop package and verify the beta package policy.",
        category="windows_ops",
        commands=(
            _command("cmd /c bin\\build_executable.bat --no-clean --ci"),
            _command(".venv\\Scripts\\python.exe tools/verify_beta_package_policy.py"),
        ),
        next_step="Review the packaged output in dist and keep the policy report with the servicing evidence.",
        docs_hint="docs/PACKAGING.md",
        tags=("windows", "package", "release"),
    ),
    WorkflowSpec(
        workflow_id="windows_release_dry_run",
        title="WINDOWS RELEASE DRY RUN",
        summary="Run the release dry-run gate and emit the reviewer bundle.",
        category="windows_ops",
        commands=(
            _command(".venv\\Scripts\\python.exe tools/beta_release_dry_run.py"),
        ),
        next_step="Review the dry-run report, receipt, and summary in that order before packaging or handoff.",
        docs_hint="docs/PACKAGING.md",
        review_order=(
            "runtime/beta_release_dry_run_report.json",
            "runtime/windows_release_receipt.json",
            "runtime/windows_release_summary.md",
        ),
        tags=("windows", "release", "dry-run"),
    ),
)


def list_workflow_specs(*, category: str | None = None) -> tuple[WorkflowSpec, ...]:
    if category is None:
        return _WORKFLOWS
    normalized = category.strip().lower()
    return tuple(item for item in _WORKFLOWS if item.category == normalized)


def get_workflow_spec(workflow_id: str) -> WorkflowSpec | None:
    normalized = workflow_id.strip().lower()
    for item in _WORKFLOWS:
        if item.workflow_id == normalized:
            return item
    return None
