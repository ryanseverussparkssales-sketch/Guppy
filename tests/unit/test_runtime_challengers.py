from __future__ import annotations

import unittest

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
        )
        self.assertEqual(payload["recommended_next"]["benchmark_first"], "llama.cpp")
        self.assertEqual(payload["recommended_next"]["integration_first"], "lemonade")
        self.assertEqual(payload["recommended_next"]["research_track"], "vllm-rocm")

        rows = {row["id"]: row for row in payload["challengers"]}
        self.assertEqual(rows["lemonade"]["host_fit"], "strong")
        self.assertTrue(rows["lemonade"]["installed"])
        self.assertEqual(rows["vllm-rocm"]["host_fit"], "research")
        self.assertFalse(rows["llama.cpp"]["installed"])

    def test_probe_marks_lemonade_as_external_openai_compatible_runtime(self) -> None:
        manifest = {"runtime": {"runtime_challengers": [{"id": "lemonade"}]}}
        host = HostRuntimeFacts(platform_system="Windows", gpu_names=("AMD Radeon(TM) Graphics",))

        payload = probe_runtime_challengers(
            manifest,
            host=host,
            which_fn=lambda _: None,
        )
        row = payload["challengers"][0]
        self.assertEqual(row["integration_surface"], "external_openai_compatible_runtime")
        self.assertIn("/chat/completions", row["integration_contract"])


if __name__ == "__main__":
    unittest.main()
