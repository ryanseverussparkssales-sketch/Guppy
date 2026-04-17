"""Canonical developer and CI command entrypoint for Guppy build workflows."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp" / "dev-workflow"


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    duration_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _preferred_python() -> Path:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


PYTHON = _preferred_python()


def _workflow_paths() -> dict[str, Path]:
    paths = {
        "root": TMP_ROOT,
        "tmp": TMP_ROOT / "tmp",
        "cache": TMP_ROOT / "cache",
        "pycache": TMP_ROOT / "pycache",
        "pytest_cache": TMP_ROOT / "pytest-cache",
        "reports": TMP_ROOT / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _workflow_env() -> dict[str, str]:
    paths = _workflow_paths()
    env = os.environ.copy()
    env["TMP"] = str(paths["tmp"])
    env["TEMP"] = str(paths["tmp"])
    env["TMPDIR"] = str(paths["tmp"])
    env["XDG_CACHE_HOME"] = str(paths["cache"])
    env["PIP_CACHE_DIR"] = str(paths["cache"] / "pip")
    env["PYTHONPYCACHEPREFIX"] = str(paths["pycache"])
    env["GUPPY_DEV_WORKFLOW_ROOT"] = str(paths["root"])
    return env


def _python_command(*args: str) -> list[str]:
    return [str(PYTHON), *args]


def _pytest_command(*targets: str, label: str) -> list[str]:
    paths = _workflow_paths()
    base_temp = paths["root"] / "pytest-basetemp" / label
    base_temp.mkdir(parents=True, exist_ok=True)
    return _python_command(
        "-m",
        "pytest",
        "--basetemp",
        str(base_temp),
        "-o",
        f"cache_dir={paths['pytest_cache']}",
        *targets,
    )


def _dev_check_steps(scope: str) -> list[tuple[str, list[str]]]:
    report_path = _workflow_paths()["reports"] / f"tool-schema-audit-{scope}.json"
    return [
        ("module line-cap guard", _python_command("tools/check_new_module_line_cap.py")),
        ("architecture boundary guard", _python_command("tools/check_architecture_boundaries.py")),
        ("runtime artifact hygiene guard", _python_command("tools/check_runtime_artifact_hygiene.py")),
        ("wrapper integrity guard", _python_command("tools/check_wrapper_integrity.py")),
        ("core surface integrity guard", _python_command("tools/check_core_surface_integrity.py")),
        ("doc ownership guard", _python_command("tools/check_doc_ownership.py")),
        ("tool schema audit", _python_command("tools/audit_tool_schemas.py", "--report", str(report_path))),
    ]


def _test_fast_steps() -> list[tuple[str, list[str]]]:
    return [("fast unit suite", _pytest_command("tests/unit", label="test-fast"))]


def _test_default_steps() -> list[tuple[str, list[str]]]:
    return [("default unit+integration suite", _pytest_command(label="test-default"))]


def _test_smoke_steps() -> list[tuple[str, list[str]]]:
    return [
        (
            "product smoke suite",
            _pytest_command(
                "tests/smoke/test_runtime_smoke.py",
                "tests/smoke/test_launcher_interactions_smoke.py",
                "tests/test_security_hardening.py",
                label="test-smoke",
            ),
        )
    ]


def _release_check_steps() -> list[tuple[str, list[str], dict[str, str]]]:
    paths = _workflow_paths()
    delta_env = {"GUPPY_GUARD_SCOPE": "delta"}
    baseline_env = {"GUPPY_GUARD_SCOPE": "baseline"}
    return [
        ("guardrails (delta)", _python_command("tools/dev_workflow.py", "dev-check", "--guard-scope", "delta"), delta_env),
        ("guardrails (baseline)", _python_command("tools/dev_workflow.py", "dev-check", "--guard-scope", "baseline"), baseline_env),
        ("default tests", _python_command("tools/dev_workflow.py", "test-default"), {}),
        ("product smoke", _python_command("tools/dev_workflow.py", "test-smoke"), {}),
        ("build validation", _python_command("tools/validate_build_checks.py"), {}),
    ]


def _run_step(name: str, command: list[str], extra_env: dict[str, str] | None = None) -> StepResult:
    env = _workflow_env()
    if extra_env:
        env.update(extra_env)

    print(f"\n==> {name}")
    print(" ".join(command))
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, env=env)
    duration = time.perf_counter() - started
    return StepResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        duration_seconds=round(duration, 2),
    )


def _write_release_outputs(
    subcommand: str,
    results: list[StepResult],
    receipt_path: Path,
    summary_path: Path,
) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    finished_at = datetime.now(timezone.utc).isoformat()
    overall_ok = all(result.ok for result in results)
    receipt = {
        "subcommand": subcommand,
        "python": str(PYTHON),
        "finished_at": finished_at,
        "ok": overall_ok,
        "steps": [asdict(result) | {"ok": result.ok} for result in results],
        "workspace_paths": {name: str(path) for name, path in _workflow_paths().items()},
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    lines = [
        f"release-check: {'PASS' if overall_ok else 'FAIL'}",
        f"finished_at: {finished_at}",
        f"python: {PYTHON}",
        "steps:",
    ]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"- {status} {result.name} ({result.duration_seconds:.2f}s)")
    lines.append(f"receipt: {receipt_path}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nRelease receipt: {receipt_path}")
    print(f"Release summary: {summary_path}")


def _run_simple_workflow(steps: list[tuple[str, list[str]]], scope: str | None = None) -> int:
    for name, command in steps:
        extra_env = {"GUPPY_GUARD_SCOPE": scope} if scope else None
        result = _run_step(name, command, extra_env=extra_env)
        if not result.ok:
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical Guppy developer workflow entrypoint")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    dev_check = subparsers.add_parser("dev-check", help="Run guardrails and audits")
    dev_check.add_argument(
        "--guard-scope",
        choices=("delta", "baseline"),
        default="delta",
        help="Select guardrail scope for architecture and line-cap checks",
    )

    subparsers.add_parser("test-fast", help="Run the fast unit-focused suite")
    subparsers.add_parser("test-default", help="Run the default unit+integration suite")
    subparsers.add_parser("test-smoke", help="Run launcher/runtime/security smoke tests")

    release_check = subparsers.add_parser("release-check", help="Run the release-oriented validation bundle")
    release_check.add_argument(
        "--receipt",
        default=str(_workflow_paths()["reports"] / "release-check-receipt.json"),
        help="Path for the machine-readable JSON receipt",
    )
    release_check.add_argument(
        "--summary",
        default=str(_workflow_paths()["reports"] / "release-check-summary.txt"),
        help="Path for the human-readable text summary",
    )

    args = parser.parse_args()

    if args.subcommand == "dev-check":
        return _run_simple_workflow(_dev_check_steps(args.guard_scope), scope=args.guard_scope)
    if args.subcommand == "test-fast":
        return _run_simple_workflow(_test_fast_steps())
    if args.subcommand == "test-default":
        return _run_simple_workflow(_test_default_steps())
    if args.subcommand == "test-smoke":
        return _run_simple_workflow(_test_smoke_steps())

    results: list[StepResult] = []
    for name, command, extra_env in _release_check_steps():
        result = _run_step(name, command, extra_env=extra_env)
        results.append(result)
        if not result.ok:
            break

    _write_release_outputs(
        subcommand="release-check",
        results=results,
        receipt_path=Path(args.receipt),
        summary_path=Path(args.summary),
    )
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
