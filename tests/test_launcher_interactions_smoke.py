import os
import tempfile
import unittest
from pathlib import Path

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


class _DummyStatusPanel:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_syslog(self, line: str) -> None:
        self.lines.append(line)


class _DummyLauncher:
    def __init__(self) -> None:
        self._last_command = ""
        self._status_panel = _DummyStatusPanel()

    def _log_launcher_event(self, event: str, **fields) -> None:
        payload = {"event": event, **fields}
        path = launcher_window._RUNTIME / "launcher_events.jsonl"
        path.write_text(__import__("json").dumps(payload), encoding="utf-8")


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

    def test_agent_card_offline_shows_disabled_initialize_reason(self):
        card = AgentCard("GUPPY")
        card.update_status(online=False, last_seen="now", load_pct=None)

        init_button = card._btn_init
        self.assertFalse(init_button.isHidden())
        self.assertFalse(init_button.isEnabled())
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


if __name__ == "__main__":
    unittest.main()
