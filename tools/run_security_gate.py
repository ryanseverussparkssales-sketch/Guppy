"""tools/run_security_gate.py

Standalone runner for the Guppy launch-grade security gate.
Called by `python tools/dev_workflow.py release-check` as the security-gate step.

Exit code:
  0 — gate passed (launch_ready=True)
  1 — gate failed (one or more checks failed)

Writes runtime/security_gate_report.json with the full gate result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.guppy.launcher_application.security_gate import (  # noqa: E402
    format_gate_report,
    run_security_gate,
)

_REPORT_PATH = _ROOT / "runtime" / "security_gate_report.json"


def main() -> int:
    result = run_security_gate()

    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(format_gate_report(result))
    print(f"\nSecurity gate report written to: {_REPORT_PATH}")

    return 0 if result["launch_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
