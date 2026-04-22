from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import validate_live_lifecycle


class _FakeOperator:
    def __init__(self, *, failures: set[tuple[str, str]] | None = None) -> None:
        self._running = {
            "api": True,
            "cloudflared": False,
            "ollama": True,
        }
        self._failures = failures or set()

    def _check_service_running(self, svc: str) -> bool:
        return bool(self._running.get(svc, False))

    def restart_service(self, svc: str, dry_run: bool = False) -> dict:
        ok = (svc, "restart") not in self._failures
        return {"ok": ok, "status": f"{'dry_run:' if dry_run else ''}restart:{svc}"}

    def start_service(self, svc: str, dry_run: bool = False) -> dict:
        ok = (svc, "start") not in self._failures
        if ok and not dry_run:
            self._running[svc] = True
        return {"ok": ok, "status": f"{'dry_run:' if dry_run else ''}start:{svc}"}

    def stop_service(self, svc: str, dry_run: bool = False) -> dict:
        ok = (svc, "stop") not in self._failures
        if ok and not dry_run:
            self._running[svc] = False
        return {"ok": ok, "status": f"{'dry_run:' if dry_run else ''}stop:{svc}"}


class ValidateLiveLifecycleTests(unittest.TestCase):
    def test_main_returns_zero_when_all_actions_succeed(self) -> None:
        fake = _FakeOperator()
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "lifecycle.json"
            out = io.StringIO()
            with patch("tools.validate_live_lifecycle.get_operator", return_value=fake), patch(
                "tools.validate_live_lifecycle.time.sleep", return_value=None
            ), patch(
                "sys.argv",
                ["validate_live_lifecycle.py", "--mode", "live", "--report", str(report_path)],
            ), redirect_stdout(out):
                code = validate_live_lifecycle.main()

            report = json.loads(out.getvalue())
            persisted = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertTrue(report["ok"])
            self.assertEqual(len(report["actions"]), len(validate_live_lifecycle.SERVICES))
            self.assertEqual(persisted["ok"], report["ok"])

    def test_main_returns_nonzero_when_any_action_fails(self) -> None:
        fake = _FakeOperator(failures={("cloudflared", "start")})
        out = io.StringIO()
        with patch("tools.validate_live_lifecycle.get_operator", return_value=fake), patch(
            "tools.validate_live_lifecycle.time.sleep", return_value=None
        ), patch("sys.argv", ["validate_live_lifecycle.py", "--mode", "live"]), redirect_stdout(out):
            code = validate_live_lifecycle.main()

        report = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report["ok"])
        self.assertIn("initial", report)
        self.assertIn("actions", report)
        self.assertIn("final", report)


if __name__ == "__main__":
    unittest.main()
