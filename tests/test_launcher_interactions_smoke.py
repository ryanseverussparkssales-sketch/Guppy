import os
import tempfile
import unittest
from pathlib import Path
from queue import SimpleQueue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    from ui.launcher.components.agent_card import AgentCard
    from ui.launcher.components.status_panel import StatusPanel
    from ui.launcher.components.topbar import TopBar
    from ui.launcher.views.assistant_view import AssistantView
    from ui.launcher import launcher_window
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

import utils.runtime_profile as runtime_profile


class _DummyStatusPanel:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_syslog(self, line: str) -> None:
        self.lines.append(line)


class _DummyLauncher:
    def __init__(self) -> None:
        self._last_command = ""
        self._status_panel = _DummyStatusPanel()
        self._assistant_events = SimpleQueue()
        self._active_request_seq = 0
        self._chat_session_id = "test-session"
        self._assistant_view = self._AssistantViewStub()

    class _AssistantViewStub:
        def add_user_message(self, _text: str) -> None:
            return

        def add_system_message(self, _text: str) -> None:
            return

        def set_status(self, _text: str) -> None:
            return

        def selected_mode(self) -> str:
            return "auto"

    def _http_json(self, path: str, method: str = "GET", payload: dict | None = None, timeout: float = 8.0) -> dict:
        return {"response": "ok"}

    def _log_launcher_event(self, event: str, **fields) -> None:
        payload = {"event": event, **fields}
        path = launcher_window._RUNTIME / "launcher_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(__import__("json").dumps(payload) + "\n")


class LauncherInteractionsSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Launcher UI deps unavailable: {IMPORT_ERROR}")
        cls._app = QApplication.instance() or QApplication([])

    def test_disabled_placeholders_have_reason_tooltips(self):
        topbar = TopBar()
        assistant = AssistantView()

        topbar_buttons = [b for b in topbar.findChildren(QPushButton) if b.text() in {"🔔", "⌨"}]
        self.assertEqual(len(topbar_buttons), 2)
        for btn in topbar_buttons:
            self.assertFalse(btn.isEnabled())
            self.assertTrue(btn.toolTip().strip())

        mic_buttons = [b for b in assistant.findChildren(QPushButton) if b.text() == "●"]
        self.assertEqual(len(mic_buttons), 1)
        self.assertFalse(mic_buttons[0].isEnabled())
        self.assertTrue(mic_buttons[0].toolTip().strip())

        send_buttons = [b for b in assistant.findChildren(QPushButton) if b.text() == "▶"]
        self.assertEqual(len(send_buttons), 1)
        self.assertTrue(send_buttons[0].isEnabled())

    def test_assistant_mode_dropdown_excludes_internal_vault_mode(self):
        assistant = AssistantView()
        modes = [assistant._cb_mode.itemText(i) for i in range(assistant._cb_mode.count())]

        self.assertEqual(modes, ["AUTO", "CLAUDE", "OLLAMA", "LOCAL", "CODE", "TEACHING"])
        self.assertNotIn("VAULT", modes)

    def test_topbar_instance_switcher_emits_selection(self):
        topbar = TopBar()
        selected: list[str] = []
        topbar.instance_selected.connect(lambda name: selected.append(name))

        topbar.set_instances(["guppy-primary", "merlin-collab"], active_instance="guppy-primary")
        topbar.set_active_instance("merlin-collab")

        self.assertEqual(topbar._instance_cb.currentText(), "merlin-collab")
        self.assertEqual(selected, [])

        topbar._instance_cb.setCurrentText("guppy-primary")
        self.assertTrue(selected)
        self.assertEqual(selected[-1], "guppy-primary")

    def test_agent_card_offline_shows_wired_initialize_button(self):
        card = AgentCard("GUPPY")
        card.update_status(online=False, last_seen="now", load_pct=None)

        init_button = card._btn_init
        self.assertFalse(init_button.isHidden())
        self.assertTrue(init_button.isEnabled())  # wired — emits init_requested signal
        self.assertTrue(init_button.toolTip().strip())

    def test_assistant_command_logs_runtime_event(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            launcher_window._RUNTIME = runtime_dir
            try:
                dummy = _DummyLauncher()
                launcher_window.LauncherWindow._on_assistant_command(dummy, "status please")

                self.assertEqual(dummy._last_command, "status please")
                self.assertTrue(dummy._status_panel.lines)
                self.assertIn("command queued", dummy._status_panel.lines[-1])

                log_path = runtime_dir / "launcher_events.jsonl"
                self.assertTrue(log_path.exists())
                payload = log_path.read_text(encoding="utf-8").strip()
                self.assertIn('"event": "command_submitted"', payload)
                self.assertIn('"command": "status please"', payload)
            finally:
                launcher_window._RUNTIME = old_runtime

    def test_status_panel_recovery_outcome_label_updates(self):
        panel = StatusPanel()
        panel.set_recovery_outcome("warmup", True, "cache refreshed")
        labels = [lbl.text() for lbl in panel.findChildren(type(panel._syslog_lbl))]
        self.assertTrue(any("RECOVERY: WARMUP OK" in txt for txt in labels))

    def test_settings_mode_roundtrip_persists_selection(self):
        import ui.launcher.views.settings_view as settings_view_module

        old_settings_path = runtime_profile.SETTINGS_PATH
        old_runtime_dir = runtime_profile.RUNTIME_DIR
        old_profile_backend = settings_view_module._PROFILE_BACKEND
        old_personalization_backend = settings_view_module._PERSONALIZATION_BACKEND
        saved_env = {key: os.environ.get(key) for key in (
            "GUPPY_DEFAULT_MODE",
            "GUPPY_RUNTIME_PROFILE",
            "GUPPY_DEFAULT_SURFACE",
            "GUPPY_SHOW_ADVANCED_SURFACES",
            "GUPPY_ENABLE_DAEMON",
            "GUPPY_ENABLE_VOICE",
            "GUPPY_WAKE_WORD_DEFAULT",
        )}

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            runtime_profile.RUNTIME_DIR = runtime_dir
            runtime_profile.SETTINGS_PATH = runtime_dir / "app_settings.json"
            settings_view_module._PROFILE_BACKEND = True
            settings_view_module._PERSONALIZATION_BACKEND = False

            for key in saved_env:
                os.environ.pop(key, None)

            try:
                first = settings_view_module.SettingsView()
                first._cb_mode.setCurrentIndex(4)
                first._save()

                second = settings_view_module.SettingsView()
                self.assertEqual(second._cb_mode.currentText(), "CODE")
                self.assertEqual(runtime_profile.load_app_settings().get("default_mode"), "code")
            finally:
                runtime_profile.SETTINGS_PATH = old_settings_path
                runtime_profile.RUNTIME_DIR = old_runtime_dir
                settings_view_module._PROFILE_BACKEND = old_profile_backend
                settings_view_module._PERSONALIZATION_BACKEND = old_personalization_backend
                for key, value in saved_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_launcher_repair_token_reader_rejects_invalid_file_contents(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            launcher_window._RUNTIME = runtime_dir
            try:
                dummy = _DummyLauncher()
                invalid = runtime_dir / "repair_token.txt"
                invalid.write_text("not-a-valid-token\n", encoding="utf-8")
                token = launcher_window.LauncherWindow._read_repair_token(dummy)
                self.assertEqual(token, "")

                invalid.write_text("a" * 64, encoding="utf-8")
                token = launcher_window.LauncherWindow._read_repair_token(dummy)
                self.assertEqual(token, "a" * 64)
            finally:
                launcher_window._RUNTIME = old_runtime


if __name__ == "__main__":
    unittest.main()
