from __future__ import annotations

import unittest
from pathlib import Path

from src.guppy.local_llm.runtime_challengers import HostRuntimeFacts, probe_runtime_challengers


class RuntimeChallengerProbeTests(unittest.TestCase):
    def test_probe_prefers_llamacpp_for_benchmark_and_lemonade_for_integration(self) -> None:
        manifest = {
            "runtime": {
                "runtime_challengers": [
                    {"id": "llama.cpp", "status": "planned", "priority": "high"},
                    {"id": "lemonade", "status": "planned", "priority": "high"},
                    {"id": "vllm-rocm", "status": "research", "priority": "medium"},
                ]
            }
        }
        host = HostRuntimeFacts(
            platform_system="Windows",
            gpu_names=("AMD Radeon RX 7900 XTX",),
            total_memory_bytes=100_000_000_000,
        )

        def fake_which(name: str) -> str | None:
            return {
                "llama-server": None,
                "llama-cli": None,
                "lemonade": r"C:\Tools\lemonade.exe",
                "lemond": None,
                "vllm": None,
            }.get(name)

        payload = probe_runtime_challengers(
            manifest,
            host=host,
            which_fn=fake_which,
            repo_root=Path(r"C:\Repo"),
        )
        self.assertEqual(payload["recommended_next"]["benchmark_first"], "llama.cpp")
        self.assertEqual(payload["recommended_next"]["integration_first"], "lemonade")
        self.assertEqual(payload["recommended_next"]["research_track"], "vllm-rocm")

        rows = {row["id"]: row for row in payload["challengers"]}
        self.assertEqual(rows["lemonade"]["host_fit"], "strong")
        self.assertTrue(rows["lemonade"]["installed"])
        self.assertEqual(rows["vllm-rocm"]["host_fit"], "research")
        self.assertFalse(rows["llama.cpp"]["installed"])

    def test_probe_marks_lemonade_vendor_repo_when_present(self) -> None:
        manifest = {"runtime": {"runtime_challengers": [{"id": "lemonade"}]}}
        host = HostRuntimeFacts(platform_system="Windows", gpu_names=("AMD Radeon(TM) Graphics",))

        payload = probe_runtime_challengers(
            manifest,
            host=host,
            which_fn=lambda _: None,
            repo_root=Path(r"c:\Users\Ryan\Guppy"),
        )
        row = payload["challengers"][0]
        self.assertTrue(row["vendor_repo_present"])
        self.assertTrue(row["vendor_repo_path"].endswith("vendor\\lemonade"))


if __name__ == "__main__":
    unittest.main()
