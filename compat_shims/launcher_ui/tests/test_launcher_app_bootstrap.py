from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.guppy.apps import launcher_app


class LauncherAppBootstrapTests(unittest.TestCase):
    def test_api_reachable_uses_public_root_probe(self):
        captured: list[str] = []

        def _fake_request(url: str):
            captured.append(url)
            return object()

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch.object(launcher_app.urllib.request, "Request", side_effect=_fake_request), patch.object(
            launcher_app.urllib.request, "urlopen", return_value=_Response()
        ):
            self.assertTrue(launcher_app._api_reachable())

        self.assertEqual(captured, ["http://127.0.0.1:8081/"])

    def test_hub_running_cleans_stale_pid_when_process_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp) / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            pid_path = runtime_dir / "hub.pid"
            pid_path.write_text("12345", encoding="utf-8")

            fake_psutil = type(
                "FakePsutil",
                (),
                {
                    "pid_exists": staticmethod(lambda pid: False),
                },
            )

            with patch.object(launcher_app, "_ROOT", Path(tmp)), patch.dict("sys.modules", {"psutil": fake_psutil}):
                self.assertFalse(launcher_app._hub_running())

            self.assertFalse(pid_path.exists())

    def test_hub_running_rejects_non_hub_process_and_cleans_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp) / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            pid_path = runtime_dir / "hub.pid"
            pid_path.write_text("4567", encoding="utf-8")

            class _Process:
                def cmdline(self) -> list[str]:
                    return ["python.exe", "other_service.py"]

            fake_psutil = type(
                "FakePsutil",
                (),
                {
                    "NoSuchProcess": RuntimeError,
                    "AccessDenied": RuntimeError,
                    "ZombieProcess": RuntimeError,
                    "pid_exists": staticmethod(lambda pid: True),
                    "Process": staticmethod(lambda pid: _Process()),
                },
            )

            with patch.object(launcher_app, "_ROOT", Path(tmp)), patch.dict("sys.modules", {"psutil": fake_psutil}):
                self.assertFalse(launcher_app._hub_running())

            self.assertFalse(pid_path.exists())

    def test_hub_running_accepts_live_hub_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp) / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            pid_path = runtime_dir / "hub.pid"
            pid_path.write_text("8901", encoding="utf-8")

            class _Process:
                def cmdline(self) -> list[str]:
                    return ["pythonw.exe", str(Path(tmp) / "guppy_hub.py")]

            fake_psutil = type(
                "FakePsutil",
                (),
                {
                    "NoSuchProcess": RuntimeError,
                    "AccessDenied": RuntimeError,
                    "ZombieProcess": RuntimeError,
                    "pid_exists": staticmethod(lambda pid: True),
                    "Process": staticmethod(lambda pid: _Process()),
                },
            )

            with patch.object(launcher_app, "_ROOT", Path(tmp)), patch.dict("sys.modules", {"psutil": fake_psutil}):
                self.assertTrue(launcher_app._hub_running())

            self.assertTrue(pid_path.exists())

    def test_main_exits_when_launcher_instance_is_already_running(self):
        with patch.object(launcher_app, "acquire_process_guard", return_value=None), patch.object(
            launcher_app, "QApplication"
        ) as app_cls:
            self.assertEqual(launcher_app.main(), 0)

        app_cls.assert_not_called()

    def test_start_api_skips_duplicate_spawn_when_recent_attempt_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime").mkdir(parents=True, exist_ok=True)
            (root / "guppy_api.py").write_text("print('api')", encoding="utf-8")

            with patch.object(launcher_app, "_ROOT", root), patch.object(
                launcher_app, "_api_reachable", return_value=False
            ), patch.object(launcher_app, "_spawn_background_process") as spawn:
                launcher_app._mark_startup_attempt("api")
                launcher_app._start_api()

            spawn.assert_not_called()

    def test_start_api_clears_startup_stamp_once_api_is_reachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime").mkdir(parents=True, exist_ok=True)
            stamp = root / "runtime" / "api.starting"
            stamp.write_text("1", encoding="utf-8")

            with patch.object(launcher_app, "_ROOT", root), patch.object(
                launcher_app, "_api_reachable", return_value=True
            ):
                launcher_app._start_api()

            self.assertFalse(stamp.exists())

    def test_start_hub_skips_duplicate_spawn_when_recent_attempt_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime").mkdir(parents=True, exist_ok=True)
            (root / "guppy_hub.py").write_text("print('hub')", encoding="utf-8")

            with patch.object(launcher_app, "_ROOT", root), patch.object(
                launcher_app, "_hub_running", return_value=False
            ), patch.object(launcher_app, "_spawn_background_process") as spawn:
                launcher_app._mark_startup_attempt("hub")
                launcher_app._start_hub()

            spawn.assert_not_called()
