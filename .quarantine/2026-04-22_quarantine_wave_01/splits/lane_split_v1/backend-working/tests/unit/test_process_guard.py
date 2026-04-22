from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.guppy.apps import process_guard


class ProcessGuardTests(unittest.TestCase):
    def test_acquire_process_guard_reclaims_stale_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "runtime" / "launcher.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("999999\n", encoding="utf-8")

            fake_psutil = type(
                "FakePsutil",
                (),
                {
                    "NoSuchProcess": RuntimeError,
                    "AccessDenied": RuntimeError,
                    "ZombieProcess": RuntimeError,
                    "pid_exists": staticmethod(lambda pid: False),
                },
            )

            with patch.object(process_guard, "psutil", fake_psutil):
                guard = process_guard.acquire_process_guard(lock_path, process_markers=("guppy_launcher.py",))

            self.assertIsNotNone(guard)
            assert guard is not None
            self.assertEqual(lock_path.read_text(encoding="utf-8").strip(), str(process_guard.os.getpid()))
            guard.release()
            self.assertFalse(lock_path.exists())

    def test_acquire_process_guard_rejects_live_matching_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "runtime" / "hub.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("4242\n", encoding="utf-8")

            class _Process:
                def cmdline(self) -> list[str]:
                    return ["pythonw.exe", "guppy_hub.py"]

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

            with patch.object(process_guard, "psutil", fake_psutil):
                guard = process_guard.acquire_process_guard(lock_path, process_markers=("guppy_hub.py",))

            self.assertIsNone(guard)
            self.assertTrue(lock_path.exists())
