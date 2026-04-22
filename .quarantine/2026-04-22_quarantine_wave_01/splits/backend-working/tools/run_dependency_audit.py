"""Run pip-audit and persist the machine-readable report for release evidence."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_REPORT_PATH = _ROOT / ".tmp" / "dev-workflow" / "reports" / "pip-audit-report.json"


def main() -> int:
    report_path = _REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pip_audit_exe = shutil.which("pip-audit")
    command: list[str]
    if pip_audit_exe:
        command = [pip_audit_exe, "-r", "requirements.txt", "--format", "json", "--output", str(report_path)]
    else:
        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            "requirements.txt",
            "--format",
            "json",
            "--output",
            str(report_path),
        ]
    completed = subprocess.run(command, cwd=_ROOT)
    if completed.returncode == 0:
        print(f"Dependency audit report written to: {report_path}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
