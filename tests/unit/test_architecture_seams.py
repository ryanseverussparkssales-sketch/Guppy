from __future__ import annotations

import unittest

from src.guppy.launcher_application.contracts import LauncherIntent, LauncherStateSnapshot
from src.guppy.launcher_application.state_builder import build_launcher_state_snapshot, build_windows_ops_plan
from src.guppy.launcher_application.workflows import get_workflow_spec, list_workflow_specs
from src.guppy.runtime_application.contracts import RuntimeHealthSnapshot, StartupReadinessSnapshot
from src.guppy.workspace_governance.connector_service import (
    build_connector_action_request,
    build_connector_action_result,
    build_connector_inventory,
    build_workspace_governance_snapshot,
    build_workspace_summary,
)


class ArchitectureSeamTests(unittest.TestCase):
    def test_workflow_catalog_includes_daily_loops_and_windows_ops(self):
        workflow_ids = {item.workflow_id for item in list_workflow_specs()}

        self.assertTrue(
            {
                "morning_boot",
                "acceptance_snapshot",
                "midday_stability",
                "evening_close",
                "overnight_low_compute",
                "windows_verify_runtime",
                "windows_update_runtime",
                "windows_package_desktop",
                "windows_release_dry_run",
            }.issubset(workflow_ids)
        )

    def test_midday_workflow_matches_current_launcher_command_shape(self):
        spec = get_workflow_spec("midday_stability")

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(
            spec.first_command,
            "python tools/verify_logging_health.py --emit-probe --require-fresh-core",
        )
        self.assertEqual(
            spec.command_strings()[-1],
            "python tools/verify_provider_runtime.py",
        )

    def test_windows_release_dry_run_preserves_review_order(self):
        spec = get_workflow_spec("windows_release_dry_run")

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(
            spec.review_order,
            (
                "runtime/beta_release_dry_run_report.json",
                "runtime/windows_release_receipt.json",
                "runtime/windows_release_summary.md",
            ),
        )

    def test_windows_ops_plan_uses_shared_workflow_catalog(self):
        verify = build_windows_ops_plan("verify_runtime")
        dry_run = build_windows_ops_plan("release_dry_run")
        restart = build_windows_ops_plan("restart_runtime")

        self.assertEqual(verify["label"], "WINDOWS VERIFY")
        self.assertTrue(any("verify_runtime_challengers.py" in item for item in verify["commands"]))
        self.assertEqual(dry_run["review_order"][0], "runtime/beta_release_dry_run_report.json")
        self.assertEqual(restart["label"], "WINDOWS RESTART")
        self.assertEqual(restart["docs_hint"], "docs/TROUBLESHOOTING.md")

    def test_workspace_governance_helpers_build_typed_snapshots(self):
        workspace = build_workspace_summary(
            {
                "name": "builder-collab",
                "label": "Builder Collab",
                "instance_type": "read_only_instance",
                "purpose": "Planning and review loops",
                "status": "ready",
                "auth_mode": "workspace",
                "active": True,
            }
        )
        connectors = build_connector_inventory(
            [
                {
                    "id": "gmail",
                    "label": "Gmail",
                    "auth_state": "ready",
                    "auth_detail": "connected",
                    "enabled": True,
                    "inherited": True,
                    "action_allow": ["send", "compose"],
                    "endpoint_allow": ["connector://gmail*"],
                    "supported_actions": ["verify", "connect", "disconnect"],
                },
                {
                    "id": "crm",
                    "label": "CRM",
                    "auth_state": "missing",
                    "auth_detail": "token missing",
                },
            ]
        )
        snapshot = build_workspace_governance_snapshot(
            workspace.metadata,
            connectors_payload=[item.raw for item in connectors],
            governance_payload={
                "auth_mode": "workspace",
                "tool_allow": ["send_email", "draft_email"],
                "endpoint_allow": ["connector://gmail*"],
                "next_step": "Bind the missing CRM provider before outbound contact sync.",
            },
        )

        self.assertEqual(workspace.name, "builder-collab")
        self.assertEqual(connectors[0].connector_id, "gmail")
        self.assertEqual(connectors[0].action_allow, ("send", "compose"))
        self.assertEqual(snapshot.readiness_state, "PARTIAL")
        self.assertIn("1/2 ready", snapshot.readiness_summary)
        self.assertEqual(snapshot.operator_hint, "Bind the missing CRM provider before outbound contact sync.")

    def test_connector_action_request_and_result_are_normalized(self):
        request = build_connector_action_request(
            "CRM",
            "VERIFY",
            provider="Salesforce",
            account_id="Primary",
            workspace_name="ops-workspace",
        )
        result = build_connector_action_result(
            {
                "connector": "crm",
                "action": "verify",
                "ok": True,
                "summary": "Salesforce verify passed.",
                "result_code": "ready",
                "next_step": "Keep Workspaces binding pointed at Salesforce.",
                "event_id": "evt-123",
                "status": {"auth_state": "ready"},
            }
        )

        self.assertEqual(request.connector_id, "crm")
        self.assertEqual(request.action, "verify")
        self.assertEqual(request.provider, "salesforce")
        self.assertEqual(request.account_id, "primary")
        self.assertTrue(result.ok)
        self.assertEqual(result.auth_state, "ready")
        self.assertEqual(result.event_id, "evt-123")

    def test_runtime_contracts_wrap_existing_payload_shapes(self):
        startup = StartupReadinessSnapshot.from_mapping(
            {
                "overall": "PARTIAL",
                "checks": {
                    "auth": {"state": "READY", "detail": "strict auth secrets configured"},
                    "ollama": {"state": "READY", "detail": "model reachable", "model": "guppy"},
                    "local_runtime": {
                        "state": "PARTIAL",
                        "detail": "local runtime reachable | chat lane warming",
                        "backend": "ollama",
                        "chat_ready": False,
                        "chat_state": "WARMING",
                        "chat_detail": "chat lane warming",
                        "chat_model": "guppy",
                        "available_roles": ["fast", "complex"],
                    },
                    "voice": {"state": "PARTIAL", "detail": "voice module available"},
                    "daemon": {"state": "READY", "detail": "daemon running"},
                    "memory": {"state": "READY", "detail": "memory module available"},
                },
            }
        )
        runtime = RuntimeHealthSnapshot.from_mapping(
            {
                "startup_readiness": startup.metadata,
                "local_runtime": {
                    "state": "PARTIAL",
                    "detail": "chat lane warming",
                    "backend": "ollama",
                    "chat_ready": False,
                    "chat_state": "WARMING",
                    "chat_detail": "warming",
                    "chat_model": "guppy",
                },
                "resource_envelope": {"state": "READY"},
                "voice_status": {"tts_backend": "azure"},
                "voice_tts_backend": "azure",
                "voice_stt_backend": "whisper",
                "daemon_available": True,
            }
        )

        self.assertEqual(startup.overall, "PARTIAL")
        self.assertEqual(startup.local_runtime.chat_state, "WARMING")
        self.assertEqual(startup.local_runtime.available_roles, ("fast", "complex"))
        self.assertEqual(runtime.overall, "PARTIAL")
        self.assertEqual(runtime.local_runtime.backend, "ollama")
        self.assertTrue(runtime.daemon_available)

    def test_runtime_health_uses_local_runtime_when_startup_overall_is_unknown(self):
        runtime = RuntimeHealthSnapshot.from_mapping(
            {
                "startup_readiness": {"overall": "UNKNOWN", "checks": {}},
                "local_runtime": {
                    "state": "READY",
                    "detail": "local runtime healthy",
                    "backend": "Ollama",
                    "available_roles": ["fast", "complex", ""],
                    "missing_roles": {"vision", "vision"},
                },
            }
        )

        self.assertEqual(runtime.overall, "READY")
        self.assertEqual(runtime.local_runtime.backend, "ollama")
        self.assertEqual(runtime.local_runtime.available_roles, ("fast", "complex"))
        self.assertEqual(runtime.local_runtime.missing_roles, ("vision",))

    def test_launcher_state_uses_runtime_and_workspace_contracts(self):
        workspace = build_workspace_summary({"name": "guppy-primary", "status": "ready"})
        runtime = RuntimeHealthSnapshot.from_mapping(
            {
                "startup_readiness": {"overall": "READY", "checks": {}},
                "local_runtime": {"state": "READY", "chat_ready": True},
            }
        )
        state = LauncherStateSnapshot(
            active_view="home",
            active_workspace=workspace,
            workspaces=(workspace,),
            runtime_health=runtime,
            status_message="ready",
        )

        self.assertEqual(state.workspace_name, "guppy-primary")
        self.assertEqual(state.overall_runtime_state, "READY")
        self.assertEqual(LauncherIntent.RUN_WINDOWS_VERIFY, "run_windows_verify")

    def test_launcher_state_builder_reuses_typed_connector_inventory(self):
        connectors = build_connector_inventory(
            [
                {"id": "gmail", "label": "Gmail", "auth_state": "ready"},
                {"id": "calendar", "label": "Calendar", "auth_state": "missing"},
            ]
        )
        state = build_launcher_state_snapshot(
            {
                "active_instance": "guppy-primary",
                "instances": [
                    {"name": "guppy-primary", "type": "user_instance", "enabled": True},
                    {"name": "builder-collab", "type": "builder_instance", "enabled": True},
                ],
            },
            connectors,
            {"service": "Recent service action: verify_runtime | OK | done"},
        )

        self.assertEqual(state.workspace_name, "guppy-primary")
        self.assertEqual(len(state.workspaces), 2)
        self.assertEqual(len(state.connector_inventory), 2)
        self.assertEqual(state.status_message, "Recent service action: verify_runtime | OK | done")

    def test_workspace_governance_snapshot_blocks_when_policy_reason_is_present(self):
        snapshot = build_workspace_governance_snapshot(
            {"name": "ops-workspace", "status": "ready"},
            connectors_payload=None,
            governance_payload={
                "reason": "Outbound CRM actions are disabled in this workspace.",
                "reason_code": "workspace_policy",
                "tool_allow": {"send_email", "draft_email", ""},
                "endpoint_block": ["connector://crm/private*", "  "],
            },
        )

        self.assertEqual(snapshot.policy_state, "blocked")
        self.assertEqual(snapshot.policy_reason_code, "workspace_policy")
        self.assertCountEqual(snapshot.tool_allow, ("send_email", "draft_email"))
        self.assertEqual(snapshot.endpoint_block, ("connector://crm/private*",))
        self.assertEqual(snapshot.readiness_state, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
