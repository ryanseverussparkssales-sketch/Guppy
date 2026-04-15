from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils import connector_bindings, connector_manager


class ConnectorManagerTests(unittest.TestCase):
    def test_workspace_binding_round_trip_persists_fields(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "account_id": "sales",
                    "provider": "",
                    "action_allow": ["send", "compose"],
                    "action_block": ["cleanup"],
                    "endpoint_allow": ["connector://gmail*"],
                    "endpoint_block": [],
                    "note": "Builder can draft but not clean up mail.",
                },
                config_path=config_path,
            )
            binding = connector_bindings.resolve_workspace_connector_binding(
                "builder-collab",
                "gmail",
                config_path=config_path,
            )
            self.assertTrue(binding["enabled"])
            self.assertEqual(binding["account_id"], "sales")
            self.assertIn("send", binding["action_allow"])
            self.assertIn("cleanup", binding["action_block"])

    def test_non_primary_workspace_is_unbound_without_explicit_binding(self):
        allowed, reason, context = connector_manager.evaluate_workspace_connector_policy(
            "send_email",
            "builder-collab",
        )
        self.assertFalse(allowed)
        self.assertEqual(context["reason_code"], "connector_unbound")
        self.assertIn("not bound", reason)

    def test_primary_workspace_inherits_enabled_binding(self):
        allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
            "youtube_search",
            "guppy-primary",
        )
        self.assertTrue(allowed)
        self.assertTrue(context["binding_inherited"])

    def test_connector_action_block_is_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "action_block": ["send"],
                },
                config_path=config_path,
            )
            allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                "send_email",
                "builder-collab",
                config_path=config_path,
            )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "connector_action_blocked")

    def test_invalid_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "ops-workspace",
                "crm",
                {
                    "enabled": True,
                    "provider": "not-a-provider",
                },
                config_path=config_path,
            )
            allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                "crm_upsert_contact",
                "ops-workspace",
                config_path=config_path,
            )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "connector_provider_unconfigured")

    def test_missing_host_auth_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "ops-workspace",
                "crm",
                {
                    "enabled": True,
                    "provider": "hubspot",
                },
                config_path=config_path,
            )
            allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                "crm_upsert_contact",
                "ops-workspace",
                config_path=config_path,
            )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "connector_host_auth_missing")
