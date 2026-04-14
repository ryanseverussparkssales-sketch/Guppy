from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guppy_core import tool_runner
from utils import instance_capabilities, instance_logger


class InstanceCapabilityTests(unittest.TestCase):
    def test_builder_instance_blocks_execute_and_allows_write(self):
        allowed, reason, permissions = instance_capabilities.check_instance_tool_permission(
            "execute_command",
            instance_name="merlin-collab",
            instance_type="builder_instance",
        )
        self.assertFalse(allowed)
        self.assertIn("execute", reason)
        self.assertTrue(permissions["write"])

        allowed_write, _, write_permissions = instance_capabilities.check_instance_tool_permission(
            "write_file",
            instance_name="merlin-collab",
            instance_type="builder_instance",
        )
        self.assertTrue(allowed_write)
        self.assertTrue(write_permissions["write"])

    def test_run_tool_returns_capability_error_before_exec(self):
        result = tool_runner.run_tool(
            "execute_command",
            {"command": "echo blocked"},
            instance_name="merlin-collab",
            instance_type="builder_instance",
        )
        self.assertIn("requires execute capability", result)


class InstanceLogRetentionTests(unittest.TestCase):
    def test_old_raw_entries_are_pruned_and_summary_is_retained(self):
        old_log_dir = instance_logger._LOG_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                instance_logger._LOG_DIR = Path(td)
                path = instance_logger.instance_log_path("merlin-collab")
                path.parent.mkdir(parents=True, exist_ok=True)

                now = datetime.now(timezone.utc)
                old_entry = {
                    "timestamp": (now - timedelta(days=20)).isoformat(),
                    "role": "user",
                    "message": "old secret sk-1234567890123456",
                    "status": "ok",
                }
                fresh_entry = {
                    "timestamp": (now - timedelta(days=2)).isoformat(),
                    "role": "assistant",
                    "message": "fresh value",
                    "status": "ok",
                }
                path.write_text(
                    json.dumps(old_entry) + "\n" + json.dumps(fresh_entry) + "\n",
                    encoding="utf-8",
                )

                entries = instance_logger.read_instance_log_tail("merlin-collab", limit=10)
                summary = instance_logger.read_instance_log_summary("merlin-collab")

                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["role"], "assistant")
                self.assertEqual(summary["entry_count"], 2)
                self.assertEqual(summary["window_days"], 30)
        finally:
            instance_logger._LOG_DIR = old_log_dir

    def test_append_instance_log_redacts_sensitive_tokens(self):
        old_log_dir = instance_logger._LOG_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                instance_logger._LOG_DIR = Path(td)
                instance_logger.append_instance_log(
                    "guppy-primary",
                    {"role": "user", "message": "token sk-secret-secret-secret", "status": "ok"},
                )
                entries = instance_logger.read_instance_log_tail("guppy-primary", limit=5)
                self.assertEqual(len(entries), 1)
                self.assertIn("[redacted]", entries[0]["message"])
        finally:
            instance_logger._LOG_DIR = old_log_dir
