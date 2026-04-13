import tempfile
import unittest
from pathlib import Path

from utils import personalization_config as pc


class PersonalizationConfigScaffoldTests(unittest.TestCase):
    def test_default_configs_validate(self):
        self.assertEqual(pc.validate_persona_config(pc.DEFAULT_PERSONA_CONFIG), [])
        self.assertEqual(pc.validate_provider_registry(pc.DEFAULT_PROVIDER_REGISTRY), [])
        self.assertEqual(pc.validate_voice_bindings(pc.DEFAULT_VOICE_BINDINGS), [])

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


if __name__ == "__main__":
    unittest.main()
