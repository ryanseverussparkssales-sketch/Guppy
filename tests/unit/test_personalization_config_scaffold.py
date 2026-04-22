import tempfile
import unittest
from pathlib import Path

from utils import personalization_config as pc


class PersonalizationConfigScaffoldTests(unittest.TestCase):
    def test_default_configs_validate(self):
        self.assertEqual(pc.validate_persona_config(pc.DEFAULT_PERSONA_CONFIG), [])
        self.assertEqual(pc.validate_provider_registry(pc.DEFAULT_PROVIDER_REGISTRY), [])
        self.assertEqual(pc.validate_voice_bindings(pc.DEFAULT_VOICE_BINDINGS), [])

    def test_default_provider_registry_includes_opt_in_and_planned_local_adapter_lanes(self):
        providers = {
            provider["id"]: provider
            for provider in pc.DEFAULT_PROVIDER_REGISTRY["providers"]
            if isinstance(provider, dict) and isinstance(provider.get("id"), str)
        }

        self.assertIn("lemonade_local", providers)
        self.assertIn("anythingllm_local", providers)
        self.assertIn("huggingface_local", providers)

        self.assertFalse(providers["lemonade_local"]["enabled"])
        self.assertEqual(providers["lemonade_local"]["provider_tier"], "experimental")
        self.assertEqual(providers["lemonade_local"]["availability_status"], "opt_in")

        self.assertFalse(providers["anythingllm_local"]["enabled"])
        self.assertEqual(providers["anythingllm_local"]["availability_status"], "planned")
        self.assertEqual(providers["huggingface_local"]["availability_status"], "planned")

    def test_ensure_scaffold_writes_missing_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "runtime"
            runtime.mkdir(parents=True, exist_ok=True)

            old_runtime = pc.RUNTIME_DIR
            old_persona = pc.PERSONA_CONFIG_PATH
            old_provider = pc.PROVIDER_REGISTRY_PATH
            old_voice = pc.VOICE_BINDINGS_PATH
            try:
                pc.RUNTIME_DIR = runtime
                pc.PERSONA_CONFIG_PATH = runtime / "persona_config.json"
                pc.PROVIDER_REGISTRY_PATH = runtime / "provider_registry.json"
                pc.VOICE_BINDINGS_PATH = runtime / "voice_bindings.json"

                written = pc.ensure_personalization_scaffold()
                self.assertIn("persona", written)
                self.assertIn("providers", written)
                self.assertIn("voice", written)
                self.assertTrue((runtime / "persona_config.json").exists())
                self.assertTrue((runtime / "provider_registry.json").exists())
                self.assertTrue((runtime / "voice_bindings.json").exists())
            finally:
                pc.RUNTIME_DIR = old_runtime
                pc.PERSONA_CONFIG_PATH = old_persona
                pc.PROVIDER_REGISTRY_PATH = old_provider
                pc.VOICE_BINDINGS_PATH = old_voice

    def test_load_persona_config_with_diagnostics_normalizes_legacy_root_type(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Path(td)
            old_path = pc.PERSONA_CONFIG_PATH
            try:
                pc.PERSONA_CONFIG_PATH = runtime / "persona_config.json"
                pc.PERSONA_CONFIG_PATH.write_text("[]", encoding="utf-8")

                data, diagnostics = pc.load_persona_config_with_diagnostics()

                self.assertEqual(data["default_persona_id"], "main_guppy")
                self.assertTrue(diagnostics)
                self.assertIn("root must be an object", diagnostics[0])
            finally:
                pc.PERSONA_CONFIG_PATH = old_path

    def test_load_provider_registry_with_diagnostics_repairs_invalid_routes(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Path(td)
            old_path = pc.PROVIDER_REGISTRY_PATH
            try:
                pc.PROVIDER_REGISTRY_PATH = runtime / "provider_registry.json"
                pc.PROVIDER_REGISTRY_PATH.write_text(
                    '{"providers": [{"id": "anthropic", "models": [{"id": "claude-haiku-4-5-20251001"}]}], "routes": {"simple": "bad/route", "complex": 3, "teaching": null, "fallback_chain": ["bad/route"]}}',
                    encoding="utf-8",
                )

                data, diagnostics = pc.load_provider_registry_with_diagnostics()

                self.assertEqual(data["routes"]["simple"], "anthropic/claude-haiku-4-5-20251001")
                self.assertIn("local/guppy", data["routes"]["fallback_chain"])
                self.assertTrue(any("routes.simple" in item for item in diagnostics))
            finally:
                pc.PROVIDER_REGISTRY_PATH = old_path

    def test_load_voice_bindings_with_diagnostics_repairs_invalid_mappings(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = Path(td)
            old_path = pc.VOICE_BINDINGS_PATH
            try:
                pc.VOICE_BINDINGS_PATH = runtime / "voice_bindings.json"
                pc.VOICE_BINDINGS_PATH.write_text(
                    '{"defaults": [], "bindings": {"by_model": [], "by_persona": null}, "imports": {}}',
                    encoding="utf-8",
                )

                data, diagnostics = pc.load_voice_bindings_with_diagnostics()

                self.assertEqual(data["defaults"]["engine"], pc.DEFAULT_VOICE_BINDINGS["defaults"]["engine"])
                self.assertEqual(data["bindings"]["by_model"], {})
                self.assertTrue(any("bindings.by_model" in item for item in diagnostics))
            finally:
                pc.VOICE_BINDINGS_PATH = old_path


if __name__ == "__main__":
    unittest.main()
