from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import local_llm_harness
from tools.verify_ollama_runtime import CmdResult


class LocalLlmHarnessTests(unittest.TestCase):
    def test_harness_writes_latest_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "models.json"
            prompts = root / "prompts.json"
            latest = root / "runtime" / "latest.json"
            history = root / "runtime" / "history.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "runtime": {
                            "artifact_paths": {
                                "benchmark_latest": str(latest),
                                "benchmark_history": str(history),
                            }
                        },
                        "memory": {"baseline_backend": "semantic-sqlite"},
                        "baseline_models": [
                            {"id": "guppy-fast", "tag": "guppy-fast:latest", "role": "fast_assistant"},
                            {"id": "guppy-code", "tag": "guppy-code:latest", "role": "code_assistant"},
                            {"id": "guppy", "tag": "guppy:latest", "role": "general_reasoning"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            prompts.write_text(
                json.dumps(
                    {
                        "tracks": [
                            {"id": "daily_chat", "prompts": ["hi"]},
                            {"id": "code_repo", "prompts": ["review this"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "tools.local_llm_harness.run_cmd",
                return_value=CmdResult(0, "NAME ID SIZE MODIFIED\nguppy-fast:latest a 1 GB now\nguppy-code:latest b 1 GB now\nguppy:latest c 1 GB now", ""),
            ), patch(
                "tools.local_llm_harness.generate_once",
                return_value={
                    "success": True,
                    "failure_mode": "none",
                    "response_preview": "ok",
                    "duration_ms": 12.5,
                    "first_token_ms": None,
                },
            ), patch(
                "sys.argv",
                [
                    "local_llm_harness.py",
                    "--manifest-file",
                    str(manifest),
                    "--prompt-file",
                    str(prompts),
                ],
            ):
                code = local_llm_harness.main()

            payload = json.loads(latest.read_text(encoding="utf-8"))
            history_lines = history.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(code, 0)
            self.assertEqual(payload["successful_cases"], 2)
            self.assertEqual(len(payload["records"]), 2)
            self.assertEqual(len(history_lines), 1)


if __name__ == "__main__":
    unittest.main()
