from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.guppy.local_llm.manifest import (
    get_baseline_model_entries,
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


if __name__ == "__main__":
    unittest.main()
