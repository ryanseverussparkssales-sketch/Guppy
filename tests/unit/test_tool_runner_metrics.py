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
