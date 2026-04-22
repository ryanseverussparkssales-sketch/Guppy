from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from guppy_core import tool_metrics
from guppy_core import tool_runner


class ToolMetricsRegressionTests(unittest.TestCase):
    def test_tool_metrics_fall_back_when_debug_flags_state_missing(self):
        original_debug_flags = tool_metrics._debug_flags
        try:
            tool_metrics._debug_flags = SimpleNamespace()
            tool_metrics._record_tool_call("demo", 12.5, "error", "boom")
            snapshot = tool_metrics.get_tool_health_snapshot()
            self.assertGreaterEqual(snapshot["calls"], 1)
            self.assertIn("demo", snapshot["per_tool"])
        finally:
            tool_metrics._debug_flags = original_debug_flags

    def test_run_tool_preserves_underlying_failure_when_metrics_path_breaks(self):
        with patch.object(tool_runner, "_validate_tool_input", return_value=None), \
             patch.object(tool_runner, "_is_tool_blocked", return_value=(False, "")), \
             patch.object(tool_runner, "_exec_tool", side_effect=ValueError("root cause failure")), \
             patch.object(tool_runner, "_mark_tool_failure", side_effect=RuntimeError("metrics broke")), \
             patch.object(tool_runner, "_record_tool_call", side_effect=RuntimeError("metrics broke")):
            result = tool_runner.run_tool("demo_tool", {})

        self.assertIn("root cause failure", result)
        self.assertNotIn("metrics broke", result)

    def test_run_tool_does_not_apply_connector_side_effects_when_permission_denied(self):
        with patch.object(tool_runner, "get_workspace_connector_context", return_value={
            "connector_id": "gmail",
            "provider": "google",
            "account_id": "acct-1",
        }), \
             patch.object(tool_runner, "check_instance_tool_permission", return_value=(False, "blocked", {})), \
             patch.object(tool_runner, "_apply_workspace_connector_runtime_side_effects") as side_effects, \
             patch.object(tool_runner, "_record_tool_call", return_value=None), \
             patch.object(tool_runner, "_validate_tool_input", return_value=None), \
             patch.object(tool_runner, "_is_tool_blocked", return_value=(False, "")), \
             patch.object(tool_runner, "_exec_tool", return_value="ok"):
            result = tool_runner.run_tool("gmail_read", {}, instance_name="guppy-primary")

        self.assertEqual(result, "Error: blocked")
        side_effects.assert_not_called()

    def test_run_tool_returns_permission_error_when_policy_reports_backend_unavailable(self):
        with patch.object(tool_runner, "get_workspace_connector_context", return_value={}), \
             patch.object(
                 tool_runner,
                 "check_instance_tool_permission",
                 return_value=(False, "instance capability policy backend unavailable", {"reason_code": "instance_policy_backend_unavailable"}),
             ), \
             patch.object(tool_runner, "_record_tool_call", return_value=None):
            result = tool_runner.run_tool("send_email", {"subject": "test"}, instance_name="guppy-primary")

        assert result == "Error: instance capability policy backend unavailable"
