from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.guppy.local_llm.manifest import (
    get_baseline_model_entries,
    get_local_llm_policy_summary,
    get_manifest_artifact_path,
    get_memory_backend_baseline,
    load_local_llm_manifest,
)


class LocalLlmManifestTests(unittest.TestCase):
    def test_load_manifest_and_baseline_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "models.json"
            path.write_text(
                json.dumps(
                    {
                        "runtime": {"artifact_paths": {"benchmark_latest": "runtime/latest.json"}},
                        "memory": {"baseline_backend": "semantic-sqlite"},
                        "baseline_models": [{"id": "guppy-fast", "tag": "guppy-fast:latest"}],
                    }
                ),
                encoding="utf-8",
            )
            manifest = load_local_llm_manifest(path)
            entries = get_baseline_model_entries(manifest)
            self.assertEqual(entries[0]["tag"], "guppy-fast:latest")
            self.assertEqual(get_memory_backend_baseline(manifest), "semantic-sqlite")
            self.assertEqual(
                get_manifest_artifact_path(manifest, "benchmark_latest"),
                Path("runtime/latest.json"),
            )

    def test_policy_summary_extracts_finalized_lane_decisions(self) -> None:
        manifest = {
            "runtime": {
                "baseline_backend": "ollama",
                "runtime_challengers": [{"id": "llama.cpp"}, {"id": "lemonade"}],
            },
            "memory": {"baseline_backend": "semantic-sqlite"},
            "challenger_models": [
                {"tag": "qwen3:8b", "status": "promotion_candidate", "notes": "best fit"},
                {"tag": "mistral-small3.1:24b", "status": "heavy_lane_candidate", "notes": "heavy"},
                {"tag": "qwen3:30b", "status": "daily_lane_rejected"},
                {"tag": "qwen2.5:32b", "status": "daily_lane_rejected"},
            ],
        }

        summary = get_local_llm_policy_summary(manifest)

        self.assertEqual(summary["runtime_baseline"], "ollama")
        self.assertEqual(summary["memory_baseline"], "semantic-sqlite")
        self.assertEqual(summary["daily_model_promotion_candidate"], "qwen3:8b")
        self.assertEqual(summary["heavy_model_candidate"], "mistral-small3.1:24b")
        self.assertEqual(summary["daily_lane_rejected_models"], ["qwen3:30b", "qwen2.5:32b"])
        self.assertEqual(summary["runtime_challenger_ids"], ["llama.cpp", "lemonade"])


if __name__ == "__main__":
    unittest.main()
