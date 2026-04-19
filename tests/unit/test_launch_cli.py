from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call
from unittest.mock import patch

from src.guppy.cli import launch as launch_cli


class LaunchCliTests(unittest.TestCase):
    def test_repo_batch_launcher_uses_cli_entrypoint(self):
        batch = (launch_cli.ROOT / "bin" / "Guppy.bat").read_text(encoding="utf-8")

        self.assertIn(r"src\guppy\cli\launch.py launcher", batch)
        self.assertNotIn("guppy_launcher.py", batch)

    def test_resolve_python_executable_prefers_windowed_binary_for_gui_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / ".venv" / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            python = scripts / "python.exe"
            pythonw = scripts / "pythonw.exe"
            python.write_text("", encoding="utf-8")
            pythonw.write_text("", encoding="utf-8")

            resolved = launch_cli._resolve_python_executable(root, prefer_windowed=True)

            self.assertEqual(resolved, str(pythonw))

    def test_launcher_start_sets_destination_env(self):
        prior = os.environ.get("GUPPY_START_DESTINATION")
        try:
            os.environ.pop("GUPPY_START_DESTINATION", None)
            with patch.object(launch_cli, "setup_env") as setup_env, patch.object(
                launch_cli, "start_hub_background"
            ) as start_hub, patch.object(
                launch_cli, "_launch_gui_surface", return_value=0
            ) as launch_gui:
                rc = launch_cli.main(["launcher", "--start", "automation-test", "--no-hub"])

            self.assertEqual(rc, 0)
            self.assertEqual(os.environ.get("GUPPY_START_DESTINATION"), "automation-test")
            setup_env.assert_called_once()
            start_hub.assert_not_called()
            launch_gui.assert_called_once()
        finally:
            if prior is None:
                os.environ.pop("GUPPY_START_DESTINATION", None)
            else:
                os.environ["GUPPY_START_DESTINATION"] = prior

    def test_launcher_surface_uses_windowed_python_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / ".venv" / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            python = scripts / "python.exe"
            pythonw = scripts / "pythonw.exe"
            python.write_text("", encoding="utf-8")
            pythonw.write_text("", encoding="utf-8")

            with patch.object(launch_cli, "ROOT", root), patch.object(
                launch_cli, "setup_env"
            ) as setup_env, patch.object(
                launch_cli, "_launch_gui_surface", return_value=0
            ) as launch_gui:
                rc = launch_cli.main(["launcher", "--no-hub"])

            self.assertEqual(rc, 0)
            setup_env.assert_called_once_with(root, profile="standard")
            launch_gui.assert_called_once_with(str(pythonw), "guppy_launcher.py")

    def test_launcher_surface_does_not_prestart_hub_from_cli(self):
        with patch.object(launch_cli, "setup_env") as setup_env, patch.object(
            launch_cli, "start_hub_background"
        ) as start_hub, patch.object(
            launch_cli, "_launch_gui_surface", return_value=0
        ) as launch_gui, patch("builtins.print") as print_mock:
            rc = launch_cli.main(["launcher"])

        self.assertEqual(rc, 0)
        setup_env.assert_called_once()
        start_hub.assert_not_called()
        launch_gui.assert_called_once()
        self.assertIn(
            call("[launch] Launcher surface manages hub bootstrap internally; skipping pre-launch hub spawn"),
            print_mock.mock_calls,
        )

    def test_hub_surface_uses_detached_gui_launch_path(self):
        with patch.object(launch_cli, "setup_env") as setup_env, patch.object(
            launch_cli, "_launch_gui_surface", return_value=0
        ) as launch_gui:
            rc = launch_cli.main(["hub", "--no-hub"])

        self.assertEqual(rc, 0)
        setup_env.assert_called_once()
        launch_gui.assert_called_once()

    def test_launcher_without_start_clears_destination_env(self):
        prior = os.environ.get("GUPPY_START_DESTINATION")
        try:
            os.environ["GUPPY_START_DESTINATION"] = "automation-test"
            with patch.object(launch_cli, "setup_env") as setup_env, patch.object(
                launch_cli, "_launch_gui_surface", return_value=0
            ) as launch_gui:
                rc = launch_cli.main(["launcher", "--no-hub"])

            self.assertEqual(rc, 0)
            self.assertNotIn("GUPPY_START_DESTINATION", os.environ)
            setup_env.assert_called_once()
            launch_gui.assert_called_once()
        finally:
            if prior is None:
                os.environ.pop("GUPPY_START_DESTINATION", None)
            else:
                os.environ["GUPPY_START_DESTINATION"] = prior

    def test_non_launcher_surface_warns_when_start_destination_is_ignored(self):
        prior = os.environ.get("GUPPY_START_DESTINATION")
        try:
            os.environ.pop("GUPPY_START_DESTINATION", None)
            with patch.object(launch_cli, "setup_env") as setup_env, patch.object(
                launch_cli, "_launch_gui_surface", return_value=0
            ) as launch_gui, patch("builtins.print") as print_mock:
                rc = launch_cli.main(["hub", "--start", "automation-test", "--no-hub"])

            self.assertEqual(rc, 0)
            self.assertNotIn("GUPPY_START_DESTINATION", os.environ)
            setup_env.assert_called_once()
            launch_gui.assert_called_once()
            self.assertIn(
                call("[launch] WARNING: --start only applies to launcher surfaces; ignoring 'automation-test' for hub"),
                print_mock.mock_calls,
            )
        finally:
            if prior is None:
                os.environ.pop("GUPPY_START_DESTINATION", None)
            else:
                os.environ["GUPPY_START_DESTINATION"] = prior
