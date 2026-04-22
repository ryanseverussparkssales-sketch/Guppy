from __future__ import annotations

import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from utils import connector_bindings, connector_manager


_TEST_TEMP_ROOT = Path(".tmp/dev-workflow/unittest-temp")


@contextmanager
def _workspace_tempdir():
    _TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TEMP_ROOT / f"case-{uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ConnectorManagerTests(unittest.TestCase):
    def test_crm_status_exposes_provider_readiness_metadata(self):
        status = connector_manager.connector_status("crm")

        self.assertIn("scope_telemetry", status)
        self.assertTrue(status["providers"])
        first = status["providers"][0]
        self.assertIn("required_fields", first)
        self.assertIn("endpoint_prefixes", first)
        self.assertIn("auth_detail", first)
        self.assertIn("setup_summary", first)
        self.assertIn("next_field", first)
        self.assertIn("field_details", first)

    def test_workspace_binding_round_trip_persists_fields(self):
        with _workspace_tempdir() as td:
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
        with _workspace_tempdir() as td:
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

    def test_endpoint_block_wildcard_pattern_is_enforced(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "endpoint_block": ["connector://gmail/*/admin*"],
                },
                config_path=config_path,
            )
            with patch(
                "utils.connector_manager.connector_status",
                return_value={
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "ready",
                    "accounts": [],
                    "providers": [],
                },
            ):
                allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    endpoint="connector://gmail/inbox/admin/settings",
                    config_path=config_path,
                )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "endpoint_block")

    def test_endpoint_allow_wildcard_pattern_is_enforced(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "endpoint_allow": ["connector://gmail/inbox/*"],
                },
                config_path=config_path,
            )
            with patch(
                "utils.connector_manager.connector_status",
                return_value={
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "ready",
                    "accounts": [],
                    "providers": [],
                },
            ):
                allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    endpoint="connector://gmail/drafts/1",
                    config_path=config_path,
                )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "endpoint_allow")

    def test_endpoint_block_precedence_when_allow_and_block_overlap(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "endpoint_allow": ["connector://gmail/*"],
                    "endpoint_block": ["connector://gmail/*/admin*"],
                },
                config_path=config_path,
            )
            with patch(
                "utils.connector_manager.connector_status",
                return_value={
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "ready",
                    "accounts": [],
                    "providers": [],
                },
            ):
                blocked, _reason, blocked_context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    endpoint="connector://gmail/inbox/admin/settings",
                    config_path=config_path,
                )
                allowed, _reason, allowed_context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    endpoint="connector://gmail/inbox/messages/123",
                    config_path=config_path,
                )
            self.assertFalse(blocked)
            self.assertEqual(blocked_context["reason_code"], "endpoint_block")
            self.assertTrue(allowed)
            self.assertEqual(allowed_context["reason_code"], "")

    def test_endpoint_pattern_matching_is_case_insensitive_with_wildcards(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "endpoint_allow": ["CONNECTOR://GMAIL/INBOX/*"],
                    "endpoint_block": ["CONNECTOR://GMAIL/INBOX/*/ADMIN*"],
                },
                config_path=config_path,
            )
            with patch(
                "utils.connector_manager.connector_status",
                return_value={
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "ready",
                    "accounts": [],
                    "providers": [],
                },
            ):
                blocked, _reason, blocked_context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    endpoint="CoNnEcToR://GMAIL/INBOX/TEAM/ADMIN",
                    config_path=config_path,
                )
            self.assertFalse(blocked)
            self.assertEqual(blocked_context["reason_code"], "endpoint_block")

    def test_action_block_precedence_when_allow_and_block_overlap(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "action_allow": ["send", "compose"],
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
        with _workspace_tempdir() as td:
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
        with _workspace_tempdir() as td:
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

    def test_gmail_account_binding_must_exist_on_host_inventory(self):
        with _workspace_tempdir() as td:
            config_path = Path(td) / "connector_bindings.json"
            connector_manager.save_workspace_connector_binding(
                "builder-collab",
                "gmail",
                {
                    "enabled": True,
                    "account_id": "sales",
                },
                config_path=config_path,
            )
            with patch(
                "utils.connector_manager.connector_status",
                return_value={
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "Gmail credentials and token are present.",
                    "accounts": [{"id": "main", "label": "Main"}],
                    "providers": [],
                },
            ):
                allowed, _reason, context = connector_manager.evaluate_workspace_connector_policy(
                    "send_email",
                    "builder-collab",
                    config_path=config_path,
                )
            self.assertFalse(allowed)
            self.assertEqual(context["reason_code"], "connector_account_unavailable")

    def test_verify_action_records_history(self):
        old_runtime_dir = connector_manager._RUNTIME_DIR
        old_state_path = connector_manager._CONNECTOR_STATE_PATH
        old_events_path = connector_manager._INTEGRATION_EVENTS_PATH
        with _workspace_tempdir() as td:
            runtime_dir = Path(td)
            connector_manager._RUNTIME_DIR = runtime_dir
            connector_manager._CONNECTOR_STATE_PATH = runtime_dir / "connector_state.json"
            connector_manager._INTEGRATION_EVENTS_PATH = runtime_dir / "integration_events.jsonl"
            try:
                result = connector_manager.run_connector_action("youtube", "verify")
                history = result.get("history", {})
                self.assertIn("last_verified_at", history)
                self.assertIn("last_result", history)
                self.assertTrue(history.get("last_event_id", ""))
                self.assertTrue(history.get("last_action_record", {}).get("event_id", ""))
                self.assertTrue(history.get("recent_events"))
            finally:
                connector_manager._RUNTIME_DIR = old_runtime_dir
                connector_manager._CONNECTOR_STATE_PATH = old_state_path
                connector_manager._INTEGRATION_EVENTS_PATH = old_events_path

    def test_salesforce_provider_status_exposes_verify_checks(self):
        secrets = {
            "SALESFORCE_ACCESS_TOKEN": "00Dxx0000000001!token",
            "SALESFORCE_INSTANCE_URL": "https://example.my.salesforce.com",
        }

        def fake_secret(key: str, *, fallback: str | None = None) -> str:
            return secrets.get(key, fallback or "")

        with patch("src.guppy.integrations.crm_voip.read_machine_secret", side_effect=fake_secret):
            status = connector_manager.connector_status("crm", provider="salesforce")

        salesforce = next(
            row for row in status["providers"] if row["id"] == "salesforce"
        )
        self.assertEqual(salesforce["auth_state"], "ready")
        self.assertTrue(salesforce["verify_summary"])
        self.assertTrue(salesforce["verify_checks"])
        self.assertTrue(all(item["passed"] for item in salesforce["verify_checks"]))
        self.assertTrue(salesforce["verify_check_summary"])
        self.assertIn("Workspaces", salesforce["next_step"])

    def test_twilio_verify_uses_provider_specific_summary(self):
        old_runtime_dir = connector_manager._RUNTIME_DIR
        old_state_path = connector_manager._CONNECTOR_STATE_PATH
        old_events_path = connector_manager._INTEGRATION_EVENTS_PATH
        secrets = {
            "TWILIO_ACCOUNT_SID": "AC123456789012345678901234567890",
            "TWILIO_AUTH_TOKEN": "twilio-auth-token",
        }

        def fake_secret(key: str, *, fallback: str | None = None) -> str:
            return secrets.get(key, fallback or "")

        with _workspace_tempdir() as td:
            runtime_dir = Path(td)
            connector_manager._RUNTIME_DIR = runtime_dir
            connector_manager._CONNECTOR_STATE_PATH = runtime_dir / "connector_state.json"
            connector_manager._INTEGRATION_EVENTS_PATH = runtime_dir / "integration_events.jsonl"
            try:
                with patch("src.guppy.integrations.crm_voip.read_machine_secret", side_effect=fake_secret):
                    result = connector_manager.run_connector_action("voip", "verify", provider="twilio")
                self.assertTrue(result["ok"])
                self.assertIn("Twilio verify passed", result["summary"])
                self.assertIn("outbound calling", result["summary"])
                self.assertTrue(result["event_id"])
                self.assertEqual(result["result_code"], "ready")
                self.assertIn("Workspaces", result["next_step"])
                self.assertTrue(result["history"].get("timeline"))
            finally:
                connector_manager._RUNTIME_DIR = old_runtime_dir
                connector_manager._CONNECTOR_STATE_PATH = old_state_path
                connector_manager._INTEGRATION_EVENTS_PATH = old_events_path

    def test_gmail_connect_reports_failure_when_auth_helper_errors(self):
        old_runtime_dir = connector_manager._RUNTIME_DIR
        old_state_path = connector_manager._CONNECTOR_STATE_PATH
        old_events_path = connector_manager._INTEGRATION_EVENTS_PATH
        with _workspace_tempdir() as td:
            runtime_dir = Path(td)
            connector_manager._RUNTIME_DIR = runtime_dir
            connector_manager._CONNECTOR_STATE_PATH = runtime_dir / "connector_state.json"
            connector_manager._INTEGRATION_EVENTS_PATH = runtime_dir / "integration_events.jsonl"
            try:
                with patch("src.guppy.tools.media.gmail_unread_count", return_value=(-1, "[Errno 2] No such file or directory: ''")):
                    result = connector_manager.run_connector_action("gmail", "connect")
                self.assertFalse(result["ok"])
                self.assertIn("No such file or directory", result["summary"])
            finally:
                connector_manager._RUNTIME_DIR = old_runtime_dir
                connector_manager._CONNECTOR_STATE_PATH = old_state_path
                connector_manager._INTEGRATION_EVENTS_PATH = old_events_path

    def test_duplicate_policy_denials_are_deduped_briefly(self):
        old_recent = dict(connector_manager._RECENT_POLICY_DENIALS)
        connector_manager._RECENT_POLICY_DENIALS.clear()
        try:
            with patch("utils.connector_manager._log_integration_event") as log_event:
                connector_manager.log_connector_policy_denial(
                    "calendar",
                    "guppy-primary",
                    "connector_host_auth_missing",
                    "Calendar credentials file is missing for this host.",
                )
                connector_manager.log_connector_policy_denial(
                    "calendar",
                    "guppy-primary",
                    "connector_host_auth_missing",
                    "Calendar credentials file is missing for this host.",
                )
                self.assertEqual(log_event.call_count, 1)
        finally:
            connector_manager._RECENT_POLICY_DENIALS.clear()
            connector_manager._RECENT_POLICY_DENIALS.update(old_recent)
