from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_local_model_runtime


class VerifyLocalModelRuntimeTests(unittest.TestCase):
    def test_load_manifest_models_reads_baseline_tags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "models.json"
            manifest.write_text(
                json.dumps(
                    {
                        "baseline_models": [
                            {"id": "guppy-fast", "tag": "guppy-fast:latest"},
                            {"id": "guppy", "tag": "guppy:latest"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload, models = verify_local_model_runtime.load_manifest_models(manifest)
            self.assertEqual(payload["baseline_models"][0]["tag"], "guppy-fast:latest")
            self.assertEqual(models, ["guppy-fast:latest", "guppy:latest"])

    def test_main_fails_when_ollama_ps_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / "snapshot.json"
            manifest = Path(td) / "models.json"
            manifest.write_text(
                json.dumps({"baseline_models": [{"id": "guppy", "tag": "guppy:latest"}]}),
                encoding="utf-8",
            )

            def _fake_run_cmd(args: list[str], timeout_s: int = 180) -> verify_local_model_runtime.CmdResult:
                del timeout_s
                if args == ["ollama", "--version"]:
                    return verify_local_model_runtime.CmdResult(0, "ollama version is ok", "")
                if args == ["ollama", "list"]:
                    return verify_local_model_runtime.CmdResult(0, "NAME ID SIZE MODIFIED\nguppy:latest abc 1 GB now", "")
                if args[:2] == ["ollama", "show"]:
                    return verify_local_model_runtime.CmdResult(0, "num_ctx 8192", "")
                if args == ["ollama", "ps"]:
                    return verify_local_model_runtime.CmdResult(1, "", "ps failed")
                raise AssertionError(f"unexpected command: {args}")

            with patch("tools.verify_ollama_runtime.run_cmd", side_effect=_fake_run_cmd), patch(
                "tools.verify_ollama_runtime._http_ping",
                return_value={"ok": True, "reason": "ok", "sample": "OK"},
            ), patch(
                "sys.argv",
                [
                    "verify_local_model_runtime.py",
                    "--manifest-file",
                    str(manifest),
                    "--snapshot-file",
                    str(snapshot),
                ],
            ):
                code = verify_local_model_runtime.main()

            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertFalse(payload["ps_ok"])
            self.assertEqual(payload["ps_returncode"], 1)
            self.assertEqual(payload["manifest_path"], str(manifest))


if __name__ == "__main__":
    unittest.main()
