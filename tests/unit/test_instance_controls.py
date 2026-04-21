from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from guppy_core import tool_runner
from utils import connector_manager, instance_capabilities, instance_logger


class InstanceCapabilityTests(unittest.TestCase):
    def test_builder_instance_blocks_execute_and_allows_write(self):
        allowed, reason, permissions = instance_capabilities.check_instance_tool_permission(
            "execute_command",
            instance_name="builder-collab",
            instance_type="builder_instance",
        )
        self.assertFalse(allowed)
        self.assertIn("execute", reason)
        self.assertTrue(permissions["write"])

        allowed_write, _, write_permissions = instance_capabilities.check_instance_tool_permission(
            "write_file",
            instance_name="builder-collab",
            instance_type="builder_instance",
        )
        self.assertTrue(allowed_write)
        self.assertTrue(write_permissions["write"])

    def test_run_tool_returns_capability_error_before_exec(self):
        result = tool_runner.run_tool(
            "execute_command",
            {"command": "echo blocked"},
            instance_name="builder-collab",
            instance_type="builder_instance",
        )
        self.assertIn("workspace allow list", result)

    def test_explicit_tool_capability_mappings_cover_runtime_seams(self):
        self.assertEqual(instance_capabilities.required_capability_for_tool("query_instance"), "network")
        self.assertEqual(instance_capabilities.required_capability_for_tool("debug_console"), "read")
        self.assertEqual(instance_capabilities.required_capability_for_tool("run_python"), "execute")

    def test_tool_block_list_overrides_capability_allow(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "tool_permissions.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "defaults": {"read": True, "write": True, "execute": True, "network": True},
                        "instances": {
                            "governed-workspace": {
                                "read": True,
                                "write": True,
                                "execute": True,
                                "network": True,
                                "tool_block": ["execute_command"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            allowed, reason, permissions = instance_capabilities.check_instance_tool_permission(
                "execute_command",
                instance_name="governed-workspace",
                instance_type="user_instance",
                config_path=config_path,
            )
            self.assertFalse(allowed)
            self.assertIn("block-listed", reason)
            self.assertIn("execute_command", permissions["_tool_block"])

    def test_local_only_auth_mode_blocks_external_network_endpoints(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "tool_permissions.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "defaults": {"read": True, "write": False, "execute": False, "network": True},
                        "instances": {
                            "builder-collab": {
                                "read": True,
                                "write": True,
                                "execute": False,
                                "network": True,
                                "auth_mode": "local_only",
                                "endpoint_allow": ["instance://*", "http://127.0.0.1*", "http://localhost*"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            allowed, reason, _permissions = instance_capabilities.check_instance_tool_permission(
                "fetch_url",
                instance_name="builder-collab",
                instance_type="builder_instance",
                config_path=config_path,
                endpoint="https://example.com/api",
            )
            self.assertFalse(allowed)
            self.assertIn("local-only", reason)
            self.assertIn("example.com", reason)

    def test_endpoint_filters_are_exposed_in_permission_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "tool_permissions.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "defaults": {"read": True, "write": False, "execute": False, "network": True},
                        "instances": {
                            "builder-collab": {
                                "read": True,
                                "write": True,
                                "execute": False,
                                "network": True,
                                "auth_mode": "local_only",
                                "endpoint_allow": ["instance://*"],
                                "policy_note": "Builder stays inside workspace boundaries.",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            allowed, reason, permissions = instance_capabilities.check_instance_tool_permission(
                "query_instance",
                instance_name="builder-collab",
                instance_type="builder_instance",
                config_path=config_path,
                metadata={"target_instance": "guppy-primary"},
            )
            self.assertTrue(allowed, msg=reason)
            self.assertEqual(permissions["_auth_mode"], "local_only")
            self.assertEqual(permissions["_resolved_endpoint"], "instance://guppy-primary")
            self.assertEqual(permissions["_endpoint_allow"], ["instance://*"])
            self.assertIn("workspace boundaries", permissions["_policy_note"])

    def test_missing_connector_auth_returns_auth_specific_reason_code(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "tool_permissions.json"
            bindings_path = Path(td) / "connector_bindings.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "defaults": {"read": True, "write": False, "execute": False, "network": True},
                        "instances": {
                            "ops-workspace": {
                                "read": True,
                                "write": True,
                                "execute": True,
                                "network": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            connector_manager.save_workspace_connector_binding(
                "ops-workspace",
                "gmail",
                {
                    "enabled": True,
                    "account_id": "main",
                },
                config_path=bindings_path,
            )
            old_env = os.environ.get("GMAIL_CREDENTIALS_PATH")
            try:
                os.environ["GMAIL_CREDENTIALS_PATH"] = str(Path(td) / "missing-gmail-creds.json")
                with patch.object(instance_capabilities.Path, "home", return_value=Path(td)):
                    allowed, reason, permissions = instance_capabilities.check_instance_tool_permission(
                        "gmail_purge",
                        instance_name="ops-workspace",
                        instance_type="admin_instance",
                        config_path=config_path,
                    )
            finally:
                if old_env is None:
                    os.environ.pop("GMAIL_CREDENTIALS_PATH", None)
                else:
                    os.environ["GMAIL_CREDENTIALS_PATH"] = old_env
            self.assertFalse(allowed)
            self.assertEqual(permissions["_policy_reason_code"], "connector_host_auth_missing")
            self.assertEqual(permissions["_connector"], "gmail")
            self.assertEqual(permissions["_connector_auth_state"], "missing")
            self.assertIn("auth is not ready", reason)


class InstanceLogRetentionTests(unittest.TestCase):
    def test_old_raw_entries_are_pruned_and_summary_is_retained(self):
        old_log_dir = instance_logger._LOG_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                instance_logger._LOG_DIR = Path(td)
                path = instance_logger.instance_log_path("builder-collab")
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

                entries = instance_logger.read_instance_log_tail("builder-collab", limit=10)
                summary = instance_logger.read_instance_log_summary("builder-collab")

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
