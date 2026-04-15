from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.local_llm_review_packet import apply_review_packet, build_review_packet


class LocalLlmReviewPacketTests(unittest.TestCase):
    def test_build_review_packet_includes_record_ids(self) -> None:
        artifact = {
            "records": [
                {
                    "track": "memory_recall",
                    "prompt_index": 1,
                    "requested_tag": "qwen3:8b",
                    "prompt_style": "guppy_local",
                    "memory_backend": "semantic-sqlite",
                    "prompt": "What did we decide about MemPalace?",
                    "response_preview": "We decided not to promote it yet.",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            packet = build_review_packet(artifact, Path(td) / "artifact.json")
        self.assertEqual(len(packet["records"]), 1)
        self.assertTrue(packet["records"][0]["record_id"])

    def test_apply_review_packet_updates_summary(self) -> None:
        artifact = {
            "records": [
                {
                    "track": "memory_recall",
                    "prompt_index": 1,
                    "requested_tag": "qwen3:8b",
                    "prompt_style": "guppy_local",
                    "memory_backend": "semantic-sqlite",
                    "prompt": "What did we decide about MemPalace?",
                    "response_preview": "We decided not to promote it yet.",
                }
            ]
        }
        packet = build_review_packet(artifact, "artifact.json")
        packet["records"][0]["review_score"] = 4
        packet["records"][0]["notes"] = "Grounded and concise."
        packet["records"][0]["reviewer"] = "Ryan"
        updated = apply_review_packet(artifact, packet)
        self.assertEqual(updated["records"][0]["review_score"], 4)
        self.assertEqual(updated["records"][0]["notes"], "Grounded and concise.")
        self.assertEqual(updated["human_review_summary"]["reviewed_records"], 1)


if __name__ == "__main__":
    unittest.main()
