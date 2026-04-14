import shutil
import tempfile
import unittest
import os
import sqlite3
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.guppy.api import server as guppy_api
import guppy_core
from utils import operational_telemetry
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
        app.dependency_overrides[guppy_api._require_repair_token] = lambda: None
        client = TestClient(app)
        status_resp = client.get("/status")
        metrics_resp = client.get("/metrics")
        logs_resp = client.get("/logs/recent?limit=5")
        startup_resp = client.get("/startup/check")
        instances_resp = client.get("/instances")
        telemetry_query_resp = client.get("/telemetry/query?limit=10")
        telemetry_report_resp = client.get("/telemetry/report?limit=200")
        repair_warmup_dry_resp = client.post("/repair", json={"action": "warmup", "dry_run": True})
        repair_restart_dry_resp = client.post("/repair", json={"action": "restart_daemon", "dry_run": True})
        repair_audit_dry_resp = client.post("/repair", json={"action": "audit_runtime", "dry_run": True})

        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertEqual(logs_resp.status_code, 200)
        self.assertEqual(startup_resp.status_code, 200)
        self.assertEqual(instances_resp.status_code, 200)
        self.assertEqual(telemetry_query_resp.status_code, 200)
        self.assertEqual(telemetry_report_resp.status_code, 200)
        self.assertEqual(repair_warmup_dry_resp.status_code, 200)
        self.assertEqual(repair_restart_dry_resp.status_code, 200)
        self.assertEqual(repair_audit_dry_resp.status_code, 200)

        status_data = status_resp.json()
        metrics_data = metrics_resp.json()
        logs_data = logs_resp.json()
        startup_data = startup_resp.json()
        instances_data = instances_resp.json()
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
        self.assertIn("instances", instances_data)
        self.assertIn("limits", instances_data)
        self.assertIn("warnings", instances_data)
        self.assertIn("source", telemetry_query_data)
        self.assertIn("events", telemetry_query_data)
        self.assertIn("count", telemetry_query_data)
        self.assertIn("report", telemetry_report_data)
        self.assertIn("streams", telemetry_report_data["report"])
        self.assertTrue(repair_warmup_data.get("ok"))
        self.assertTrue(repair_restart_data.get("ok") or "unavailable" in str(repair_restart_data.get("summary", "")).lower())
        self.assertTrue(repair_audit_data.get("ok"))

    def test_instances_endpoint_tolerates_malformed_config_and_state(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"

        old_config_dir = guppy_api._config_dir
        old_runtime_dir = guppy_api._runtime_dir
        old_instances_path = guppy_api._instances_path
        old_instance_state_path = guppy_api._instance_state_path

        tmp_root = Path(tempfile.mkdtemp())
        try:
            cfg = tmp_root / "config"
            rt = tmp_root / "runtime"
            cfg.mkdir(parents=True, exist_ok=True)
            rt.mkdir(parents=True, exist_ok=True)

            malformed_config = {
                "version": "x",
                "active_instance": "missing-name",
                "instances": [
                    {"description": "no-name"},
                    "not-an-object",
                    {"name": "zeta", "enabled": True},
                    {"name": "alpha", "enabled": False},
                    {"name": "zeta", "enabled": True},
                ],
            }
            malformed_state = {
                "instances": {
                    "ghost": {"status": "idle", "message_count": 999},
                    "alpha": {"status": "NOT_A_STATUS", "message_count": "7"},
                    "zeta": "invalid-state",
                }
            }

            instances_path = cfg / "instances.json"
            state_path = rt / "instance_state.json"
            instances_path.write_text(json.dumps(malformed_config), encoding="utf-8")
            state_path.write_text(json.dumps(malformed_state), encoding="utf-8")

            guppy_api._config_dir = cfg
            guppy_api._runtime_dir = rt
            guppy_api._instances_path = instances_path
            guppy_api._instance_state_path = state_path

            client = TestClient(app)
            resp = client.get("/instances")
            self.assertEqual(resp.status_code, 200)

            payload = resp.json()
            names = [item.get("name") for item in payload.get("instances", [])]
            self.assertEqual(names, ["zeta", "alpha"])
            self.assertEqual(payload.get("active_instance"), "zeta")
            self.assertTrue(payload.get("warnings"))
            self.assertTrue(any("ignored" in str(w).lower() for w in payload.get("warnings", [])))
        finally:
            guppy_api._config_dir = old_config_dir
            guppy_api._runtime_dir = old_runtime_dir
            guppy_api._instances_path = old_instances_path
            guppy_api._instance_state_path = old_instance_state_path
            app.dependency_overrides.pop(guppy_api.require_rate_limit, None)
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_instance_lifecycle_endpoints_roundtrip(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"

        old_config_dir = guppy_api._config_dir
        old_runtime_dir = guppy_api._runtime_dir
        old_instances_path = guppy_api._instances_path
        old_instance_state_path = guppy_api._instance_state_path

        tmp_root = Path(tempfile.mkdtemp())
        try:
            cfg = tmp_root / "config"
            rt = tmp_root / "runtime"
            cfg.mkdir(parents=True, exist_ok=True)
            rt.mkdir(parents=True, exist_ok=True)

            instances_path = cfg / "instances.json"
            state_path = rt / "instance_state.json"
            instances_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "active_instance": "guppy-primary",
                        "instances": [
                            {
                                "name": "guppy-primary",
                                "description": "Primary",
                                "mode": "auto",
                                "persona": "guppy",
                                "voice": "default",
                                "enabled": True,
                                "type": "user_instance",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "active_instance": "guppy-primary",
                        "instances": {
                            "guppy-primary": {
                                "status": "active",
                                "last_message": "",
                                "last_updated": None,
                                "message_count": 0,
                                "model_currently_using": "auto",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            guppy_api._config_dir = cfg
            guppy_api._runtime_dir = rt
            guppy_api._instances_path = instances_path
            guppy_api._instance_state_path = state_path

            client = TestClient(app)
            create_resp = client.post(
                "/instances",
                json={
                    "name": "merlin-collab",
                    "description": "Collaborator",
                    "mode": "teaching",
                    "persona": "merlin",
                    "voice": "default",
                    "enabled": True,
                    "type": "builder_instance",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            self.assertEqual(create_resp.json().get("action"), "created")

            list_resp = client.get("/instances")
            self.assertEqual(list_resp.status_code, 200)
            payload = list_resp.json()
            names = [item.get("name") for item in payload.get("instances", [])]
            self.assertIn("merlin-collab", names)
            self.assertIn("limits", payload)
            target = next(item for item in payload.get("instances", []) if item.get("name") == "merlin-collab")
            self.assertEqual(target.get("type"), "builder_instance")
            self.assertIn("created_at", target)
            self.assertIn("model_currently_using", target)
            self.assertEqual(payload["limits"]["configured"], 2)
            self.assertEqual(payload["limits"]["max_configured"], 5)

            activate_resp = client.post("/instances/merlin-collab/activate")
            self.assertEqual(activate_resp.status_code, 200)
            self.assertEqual(activate_resp.json().get("active_instance"), "merlin-collab")

            logs_resp = client.get("/instances/merlin-collab/logs?limit=10")
            self.assertEqual(logs_resp.status_code, 200)
            self.assertIn("entries", logs_resp.json())
            self.assertIn("summary", logs_resp.json())

            delete_resp = client.delete("/instances/merlin-collab")
            self.assertEqual(delete_resp.status_code, 200)
            self.assertEqual(delete_resp.json().get("deleted"), "merlin-collab")
        finally:
            guppy_api._config_dir = old_config_dir
            guppy_api._runtime_dir = old_runtime_dir
            guppy_api._instances_path = old_instances_path
            guppy_api._instance_state_path = old_instance_state_path
            app.dependency_overrides.pop(guppy_api.require_rate_limit, None)
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_chat_and_instance_query_forward_instance_context(self):
        app = guppy_api.app
        app.dependency_overrides[guppy_api.require_rate_limit] = lambda: "smoke-user"

        old_config_dir = guppy_api._config_dir
        old_runtime_dir = guppy_api._runtime_dir
        old_instances_path = guppy_api._instances_path
        old_instance_state_path = guppy_api._instance_state_path

        tmp_root = Path(tempfile.mkdtemp())
        calls: list[tuple[str | None, str | None, str]] = []
        try:
            cfg = tmp_root / "config"
            rt = tmp_root / "runtime"
            cfg.mkdir(parents=True, exist_ok=True)
            rt.mkdir(parents=True, exist_ok=True)

            instances_path = cfg / "instances.json"
            state_path = rt / "instance_state.json"
            instances_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "active_instance": "merlin-collab",
                        "instances": [
                            {
                                "name": "guppy-primary",
                                "description": "Primary",
                                "mode": "auto",
                                "persona": "guppy",
                                "voice": "default",
                                "enabled": True,
                                "type": "user_instance",
                            },
                            {
                                "name": "merlin-collab",
                                "description": "Collaborator",
                                "mode": "teaching",
                                "persona": "merlin",
                                "voice": "default",
                                "enabled": True,
                                "type": "builder_instance",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "active_instance": "merlin-collab",
                        "instances": {
                            "guppy-primary": {
                                "status": "idle",
                                "last_message": "",
                                "last_updated": None,
                                "message_count": 0,
                                "model_currently_using": "auto",
                            },
                            "merlin-collab": {
                                "status": "active",
                                "last_message": "",
                                "last_updated": None,
                                "message_count": 0,
                                "model_currently_using": "teaching",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            guppy_api._config_dir = cfg
            guppy_api._runtime_dir = rt
            guppy_api._instances_path = instances_path
            guppy_api._instance_state_path = state_path

            def _fake_inference(message, system_prompt, mode=None, history=None, instance_name=None, instance_type=None):
                del system_prompt, mode, history
                calls.append((instance_name, instance_type, message))
                return f"ok:{instance_name}:{instance_type}"

            client = TestClient(app)
            from unittest.mock import patch

            with patch.object(guppy_api, "_call_unified_inference", side_effect=_fake_inference):
                chat_resp = client.post("/chat", json={"message": "hello"})
                self.assertEqual(chat_resp.status_code, 200)
                query_resp = client.post(
                    "/instances/merlin-collab/query",
                    json={"message": "builder question", "source_instance": "guppy-primary"},
                )
                self.assertEqual(query_resp.status_code, 200)

            self.assertGreaterEqual(len(calls), 2)
            self.assertEqual(calls[0][0], "merlin-collab")
            self.assertEqual(calls[0][1], "builder_instance")
            self.assertEqual(calls[1][0], "merlin-collab")
            self.assertEqual(calls[1][1], "builder_instance")
        finally:
            guppy_api._config_dir = old_config_dir
            guppy_api._runtime_dir = old_runtime_dir
            guppy_api._instances_path = old_instances_path
            guppy_api._instance_state_path = old_instance_state_path
            app.dependency_overrides.pop(guppy_api.require_rate_limit, None)
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_guppy_core_tool_health_snapshot_is_available(self):
        snapshot = guppy_core.get_tool_health_snapshot()

        self.assertIsInstance(snapshot, dict)
        self.assertIn("calls", snapshot)
        self.assertIn("per_tool", snapshot)

    def test_operational_telemetry_sqlite_roundtrip(self):
        old_db_path = operational_telemetry._DB_PATH
        old_runtime = operational_telemetry._RUNTIME
        old_backend = os.environ.get("GUPPY_TELEMETRY_BACKEND")
        runtime_dir = Path(tempfile.mkdtemp())

        operational_telemetry._RUNTIME = runtime_dir
        operational_telemetry._DB_PATH = runtime_dir / "ops_telemetry.sqlite3"
        os.environ["GUPPY_TELEMETRY_BACKEND"] = "sqlite+jsonl"
        try:
            operational_telemetry.log_operational_event(
                "runtime_smoke",
                "sqlite_roundtrip",
                {"ok": True, "component": "test"},
            )

            self.assertTrue(operational_telemetry._DB_PATH.exists())
            with sqlite3.connect(operational_telemetry._DB_PATH) as conn:
                row = conn.execute(
                    "SELECT stream, event, payload_json FROM operational_events ORDER BY id DESC LIMIT 1"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "runtime_smoke")
            self.assertEqual(row[1], "sqlite_roundtrip")
            self.assertIn('"ok": true', row[2].lower())
        finally:
            operational_telemetry._DB_PATH = old_db_path
            operational_telemetry._RUNTIME = old_runtime
            if old_backend is None:
                os.environ.pop("GUPPY_TELEMETRY_BACKEND", None)
            else:
                os.environ["GUPPY_TELEMETRY_BACKEND"] = old_backend
            shutil.rmtree(runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
