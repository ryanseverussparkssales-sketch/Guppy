from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_provider_runtime


class VerifyProviderRuntimeTests(unittest.TestCase):
    def test_build_validation_scope_marks_real_device_follow_up(self) -> None:
        scope = verify_provider_runtime._build_validation_scope(smoke_enabled=False)

        self.assertFalse(scope["real_device_coverage_included"])
        self.assertIn("VOICE_VALIDATION_MATRIX", " ".join(scope["follow_up"]))

    def test_main_writes_validation_scope_and_stays_ready_without_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / "provider_runtime_snapshot.json"

            with patch("tools.verify_provider_runtime._pkg_version", return_value="1.0.0"), patch.dict(
                "os.environ",
                {},
                clear=True,
            ), patch(
                "sys.argv",
                [
                    "verify_provider_runtime.py",
                    "--snapshot-file",
                    str(snapshot),
                ],
            ):
                code = verify_provider_runtime.main()

            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertIn("validation_scope", payload)
            self.assertFalse(payload["validation_scope"]["real_device_coverage_included"])
            self.assertEqual(payload["smoke_results"], {})

    def test_main_fails_when_smoke_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / "provider_runtime_snapshot.json"
            env = {
                "ANTHROPIC_API_KEY": "key",
            }

            with patch("tools.verify_provider_runtime._pkg_version", return_value="1.0.0"), patch(
                "tools.verify_provider_runtime._check_anthropic",
                return_value=(False, "Anthropic check failed: boom"),
            ), patch.dict("os.environ", env, clear=True), patch(
                "sys.argv",
                [
                    "verify_provider_runtime.py",
                    "--snapshot-file",
                    str(snapshot),
                    "--smoke",
                ],
            ):
                code = verify_provider_runtime.main()

            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertIn("anthropic", payload["smoke_results"])
            self.assertFalse(payload["smoke_results"]["anthropic"]["ok"])


if __name__ == "__main__":
    unittest.main()
