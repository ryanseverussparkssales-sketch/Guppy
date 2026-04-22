from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from utils import runtime_profile

_TEST_TEMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "test-scratch" / "runtime-profile-cleanup"


@contextmanager
def workspace_tempdir():
    _TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


tempfile.TemporaryDirectory = workspace_tempdir  # type: ignore[assignment]


class RuntimeProfileCleanupTests(unittest.TestCase):
    def test_load_app_settings_drops_legacy_surface_fields(self):
        old_runtime_dir = runtime_profile.RUNTIME_DIR
        old_settings_path = runtime_profile.SETTINGS_PATH
        saved_env = {
            "GUPPY_DEFAULT_SURFACE": os.environ.get("GUPPY_DEFAULT_SURFACE"),
            "GUPPY_SHOW_ADVANCED_SURFACES": os.environ.get("GUPPY_SHOW_ADVANCED_SURFACES"),
            "GUPPY_RUNTIME_PROFILE": os.environ.get("GUPPY_RUNTIME_PROFILE"),
            "GUPPY_DEFAULT_MODE": os.environ.get("GUPPY_DEFAULT_MODE"),
        }

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            runtime_profile.RUNTIME_DIR = runtime_dir
            runtime_profile.SETTINGS_PATH = runtime_dir / "app_settings.json"
            runtime_profile.SETTINGS_PATH.write_text(
                json.dumps(
                    {
                        "runtime_profile": "power",
                        "default_mode": "code",
                        "default_surface": "merlin",
                        "show_advanced_surfaces": True,
                    }
                ),
                encoding="utf-8",
            )
            os.environ["GUPPY_DEFAULT_SURFACE"] = "council"
            os.environ["GUPPY_SHOW_ADVANCED_SURFACES"] = "1"
            os.environ.pop("GUPPY_RUNTIME_PROFILE", None)
            os.environ.pop("GUPPY_DEFAULT_MODE", None)

            try:
                settings = runtime_profile.load_app_settings()
            finally:
                runtime_profile.RUNTIME_DIR = old_runtime_dir
                runtime_profile.SETTINGS_PATH = old_settings_path
                for key, value in saved_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(settings["runtime_profile"], "power")
        self.assertEqual(settings["default_mode"], "code")
        self.assertNotIn("default_surface", settings)
        self.assertNotIn("show_advanced_surfaces", settings)

    def test_apply_settings_to_env_clears_legacy_surface_env_vars(self):
        saved_env = {
            "GUPPY_DEFAULT_SURFACE": os.environ.get("GUPPY_DEFAULT_SURFACE"),
            "GUPPY_SHOW_ADVANCED_SURFACES": os.environ.get("GUPPY_SHOW_ADVANCED_SURFACES"),
            "GUPPY_RUNTIME_PROFILE": os.environ.get("GUPPY_RUNTIME_PROFILE"),
            "GUPPY_DEFAULT_MODE": os.environ.get("GUPPY_DEFAULT_MODE"),
        }
        os.environ["GUPPY_DEFAULT_SURFACE"] = "merlin"
        os.environ["GUPPY_SHOW_ADVANCED_SURFACES"] = "1"

        try:
            merged = runtime_profile.apply_settings_to_env(
                {
                    "runtime_profile": "standard",
                    "default_mode": "auto",
                }
            )
        finally:
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(merged["runtime_profile"], "standard")
        self.assertEqual(merged["default_mode"], "auto")
        self.assertNotIn("GUPPY_DEFAULT_SURFACE", os.environ)
        self.assertNotIn("GUPPY_SHOW_ADVANCED_SURFACES", os.environ)

    def test_apply_settings_to_env_maps_three_model_loadout(self):
        saved_env = {
            "GUPPY_MAIN_MODEL": os.environ.get("GUPPY_MAIN_MODEL"),
            "GUPPY_SUB_MODEL_A": os.environ.get("GUPPY_SUB_MODEL_A"),
            "GUPPY_SUB_MODEL_B": os.environ.get("GUPPY_SUB_MODEL_B"),
            "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL"),
            "OLLAMA_FAST_MODEL": os.environ.get("OLLAMA_FAST_MODEL"),
            "OLLAMA_CODE_MODEL": os.environ.get("OLLAMA_CODE_MODEL"),
            "GUPPY_LOCAL_COMPLEX_MODEL": os.environ.get("GUPPY_LOCAL_COMPLEX_MODEL"),
            "GUPPY_LOCAL_FAST_MODEL": os.environ.get("GUPPY_LOCAL_FAST_MODEL"),
            "GUPPY_LOCAL_CODE_MODEL": os.environ.get("GUPPY_LOCAL_CODE_MODEL"),
        }

        try:
            runtime_profile.apply_settings_to_env(
                {
                    "local_main_model": "guppy",
                    "local_sub_model_a": "guppy-fast",
                    "local_sub_model_b": "guppy-code",
                }
            )
            self.assertEqual(os.environ.get("GUPPY_MAIN_MODEL"), "guppy")
            self.assertEqual(os.environ.get("GUPPY_SUB_MODEL_A"), "guppy-fast")
            self.assertEqual(os.environ.get("GUPPY_SUB_MODEL_B"), "guppy-code")
            self.assertEqual(os.environ.get("OLLAMA_MODEL"), "guppy")
            self.assertEqual(os.environ.get("OLLAMA_FAST_MODEL"), "guppy-fast")
            self.assertEqual(os.environ.get("OLLAMA_CODE_MODEL"), "guppy-code")
            self.assertEqual(os.environ.get("GUPPY_LOCAL_COMPLEX_MODEL"), "guppy")
            self.assertEqual(os.environ.get("GUPPY_LOCAL_FAST_MODEL"), "guppy-fast")
            self.assertEqual(os.environ.get("GUPPY_LOCAL_CODE_MODEL"), "guppy-code")
        finally:
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
