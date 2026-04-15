from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tools import local_llm_harness
from tools.verify_ollama_runtime import CmdResult


class LocalLlmHarnessTests(unittest.TestCase):
    def test_fetch_lemonade_downloaded_models_reads_openai_model_list(self) -> None:
        payload = {
            "object": "list",
            "data": [
                {"id": "Qwen3-0.6B-GGUF", "downloaded": True},
                {"id": "Gemma-3-4b-it-GGUF", "downloaded": True},
            ],
        }

        with patch(
            "tools.local_llm_harness.http_json_request",
            return_value=(payload, 12.0),
        ):
            models = local_llm_harness.fetch_lemonade_downloaded_models(timeout_s=30)

        self.assertEqual(models, {"Qwen3-0.6B-GGUF", "Gemma-3-4b-it-GGUF"})

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
                "tools.local_llm_harness.run_prompt_once",
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
            self.assertEqual(payload["records"][0]["prompt_style"], "raw")
            self.assertEqual(len(history_lines), 1)

    def test_harness_supports_override_tag_and_guppy_local_style(self) -> None:
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
                            "baseline_backend": "ollama",
                            "artifact_paths": {
                                "benchmark_latest": str(latest),
                                "benchmark_history": str(history),
                            }
                        },
                        "memory": {"baseline_backend": "semantic-sqlite"},
                        "baseline_models": [{"id": "guppy-fast", "tag": "guppy-fast:latest", "role": "fast_assistant"}],
                    }
                ),
                encoding="utf-8",
            )
            prompts.write_text(json.dumps({"tracks": [{"id": "daily_chat", "prompts": ["hi"]}]}), encoding="utf-8")

            with patch(
                "tools.local_llm_harness.run_cmd",
                return_value=CmdResult(0, "NAME ID SIZE MODIFIED\nqwen3:8b a 1 GB now", ""),
            ), patch(
                "tools.local_llm_harness.run_prompt_once",
                return_value={
                    "success": True,
                    "failure_mode": "none",
                    "response_preview": "ok",
                    "duration_ms": 10.0,
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
                    "--all-tracks-model-tag",
                    "qwen3:8b",
                    "--prompt-style",
                    "guppy_local",
                ],
            ):
                code = local_llm_harness.main()

            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["prompt_style"], "guppy_local")
            self.assertEqual(payload["records"][0]["requested_tag"], "qwen3:8b")

    def test_harness_supports_lemonade_runtime_override(self) -> None:
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
                            "baseline_backend": "ollama",
                            "artifact_paths": {
                                "benchmark_latest": str(latest),
                                "benchmark_history": str(history),
                            }
                        },
                        "memory": {"baseline_backend": "semantic-sqlite"},
                        "baseline_models": [{"id": "guppy-fast", "tag": "guppy-fast:latest", "role": "fast_assistant"}],
                    }
                ),
                encoding="utf-8",
            )
            prompts.write_text(json.dumps({"tracks": [{"id": "daily_chat", "prompts": ["hi"]}]}), encoding="utf-8")

            with patch(
                "tools.local_llm_harness.fetch_lemonade_downloaded_models",
                return_value={"Qwen3-0.6B-GGUF"},
            ), patch(
                "tools.local_llm_harness.run_prompt_once",
                return_value={
                    "success": True,
                    "failure_mode": "none",
                    "response_preview": "ok",
                    "duration_ms": 8.0,
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
                    "--all-tracks-model-tag",
                    "Qwen3-0.6B-GGUF",
                    "--prompt-style",
                    "guppy_local",
                    "--runtime-backend-override",
                    "lemonade",
                ],
            ):
                code = local_llm_harness.main()

            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["runtime_backend"], "lemonade")
            self.assertEqual(payload["runtime_base_url"], local_llm_harness.DEFAULT_LEMONADE_BASE_URL)
            self.assertEqual(payload["records"][0]["requested_tag"], "Qwen3-0.6B-GGUF")
            self.assertEqual(payload["records"][0]["resolved_tag"], "Qwen3-0.6B-GGUF")

    def test_harness_supports_memory_backend_compare_mode(self) -> None:
        @contextmanager
        def _fake_backend_session(memory_backend: str, run_root=None, seed_entries=None):
            yield memory_backend

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "models.json"
            prompts = root / "prompts.json"
            seeds = root / "memory_seeds.json"
            latest = root / "runtime" / "latest.json"
            history = root / "runtime" / "history.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "runtime": {
                            "baseline_backend": "ollama",
                            "artifact_paths": {
                                "benchmark_latest": str(latest),
                                "benchmark_history": str(history),
                            }
                        },
                        "memory": {"baseline_backend": "semantic-sqlite"},
                        "baseline_models": [{"id": "guppy-fast", "tag": "qwen3:8b", "role": "fast_assistant"}],
                    }
                ),
                encoding="utf-8",
            )
            prompts.write_text(json.dumps({"tracks": [{"id": "memory_recall", "prompts": ["Use yesterday's preference here."]}]}), encoding="utf-8")
            seeds.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "key": "preferences.concise_answers",
                                "category": "preferences",
                                "value": "Ryan prefers concise answers.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "tools.local_llm_harness.run_cmd",
                return_value=CmdResult(0, "NAME ID SIZE MODIFIED\nqwen3:8b a 1 GB now", ""),
            ), patch(
                "tools.local_llm_harness.run_prompt_once",
                return_value={
                    "success": True,
                    "failure_mode": "none",
                    "response_preview": "ok",
                    "duration_ms": 10.0,
                    "first_token_ms": None,
                },
            ), patch(
                "tools.local_llm_harness.activate_memory_backend",
                side_effect=lambda memory_backend, run_root=None, seed_entries=None: _fake_backend_session(memory_backend, run_root, seed_entries),
            ), patch(
                "sys.argv",
                [
                    "local_llm_harness.py",
                    "--manifest-file",
                    str(manifest),
                    "--prompt-file",
                    str(prompts),
                    "--prompt-style",
                    "guppy_local",
                    "--memory-seed-file",
                    str(seeds),
                    "--compare-memory-backends",
                    "semantic-sqlite",
                    "mempalace-adapter",
                ],
            ):
                code = local_llm_harness.main()

            payload = json.loads(latest.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertTrue(payload["comparison_mode"])
            self.assertEqual(payload["memory_seed_count"], 1)
            self.assertEqual(payload["memory_backends"], ["semantic-sqlite", "mempalace-adapter"])
            self.assertEqual(len(payload["records"]), 2)
            self.assertEqual(
                {record["memory_backend"] for record in payload["records"]},
                {"semantic-sqlite", "mempalace-adapter"},
            )


if __name__ == "__main__":
    unittest.main()
