from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import pilot_exit_check


class PilotExitReportResilienceTests(unittest.TestCase):
    def test_main_writes_report_when_gate_execution_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "pilot_exit_report.json"

            def _fake_run_cmd(args: list[str], timeout_s: int = 300) -> pilot_exit_check.CmdResult:
                del timeout_s
                joined = " ".join(args)
                if "tests/smoke/test_runtime_smoke.py" in joined:
                    raise subprocess.TimeoutExpired(cmd=args, timeout=30)
                return pilot_exit_check.CmdResult(0, "ok", "")

            with patch("tools.pilot_exit_check.run_cmd", side_effect=_fake_run_cmd), patch(
                "sys.argv",
                [
                    "pilot_exit_check.py",
                    "--allow-limited-go",
                    "--report",
                    str(report_path),
                ],
            ):
                code = pilot_exit_check.main()

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertEqual(payload["verdict"], "NO_GO")
            failed = next(gate for gate in payload["gates"] if gate["id"] == "gate_1_core_runtime_stability")
            self.assertFalse(failed["passed"])
            self.assertIn("Gate execution failed", failed["summary"])
            self.assertIn("TimeoutExpired", failed["stderr_tail"])


if __name__ == "__main__":
    unittest.main()
