import tempfile
import unittest
import os
from pathlib import Path

from fastapi.testclient import TestClient

import guppy_api
from utils.session_logger import log_session_event, tail_session_events


class RuntimeSmokeTests(unittest.TestCase):
    def test_session_logger_roundtrip(self):
        event_name = "runtime_smoke_logger_roundtrip"
        log_session_event("test", event_name, level="info", note="ok")
        tail = tail_session_events(limit=20)
        self.assertTrue(any(item.get("event") == event_name for item in tail if isinstance(item, dict)))

    def test_api_core_routes(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"
        client = TestClient(app)
        status_resp = client.get("/status")
        metrics_resp = client.get("/metrics")
        logs_resp = client.get("/logs/recent?limit=5")
        startup_resp = client.get("/startup/check")
        telemetry_query_resp = client.get("/telemetry/query?limit=10")
        telemetry_report_resp = client.get("/telemetry/report?limit=200")
        repair_warmup_dry_resp = client.post("/repair", json={"action": "warmup", "dry_run": True})
        repair_restart_dry_resp = client.post("/repair", json={"action": "restart_daemon", "dry_run": True})
        repair_audit_dry_resp = client.post("/repair", json={"action": "audit_runtime", "dry_run": True})

        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertEqual(logs_resp.status_code, 200)
        self.assertEqual(startup_resp.status_code, 200)
        self.assertEqual(telemetry_query_resp.status_code, 200)
        self.assertEqual(telemetry_report_resp.status_code, 200)
        self.assertEqual(repair_warmup_dry_resp.status_code, 200)
        self.assertEqual(repair_restart_dry_resp.status_code, 200)
        self.assertEqual(repair_audit_dry_resp.status_code, 200)

        status_data = status_resp.json()
        metrics_data = metrics_resp.json()
        logs_data = logs_resp.json()
        startup_data = startup_resp.json()
        telemetry_query_data = telemetry_query_resp.json()
        telemetry_report_data = telemetry_report_resp.json()
        repair_warmup_data = repair_warmup_dry_resp.json()
        repair_restart_data = repair_restart_dry_resp.json()
        repair_audit_data = repair_audit_dry_resp.json()

        self.assertIn("status", status_data)
        self.assertIn("voice_status", status_data)
        self.assertIn("resource_envelope", status_data)
        self.assertIn("requests_total", metrics_data)
        self.assertIn("session_events", logs_data)
        self.assertIn("agent_performance", logs_data)
        self.assertIn("overall", startup_data)
        self.assertIn("checks", startup_data)
        self.assertIn("source", telemetry_query_data)
        self.assertIn("events", telemetry_query_data)
        self.assertIn("count", telemetry_query_data)
        self.assertIn("report", telemetry_report_data)
        self.assertIn("streams", telemetry_report_data["report"])
        self.assertTrue(repair_warmup_data.get("ok"))
        self.assertTrue(repair_restart_data.get("ok") or "unavailable" in str(repair_restart_data.get("summary", "")).lower())
        self.assertTrue(repair_audit_data.get("ok"))


if __name__ == "__main__":
    unittest.main()
