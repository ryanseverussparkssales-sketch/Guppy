import os
import tempfile
import unittest
import json
from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget
    from ui.launcher.components.agent_card import AgentCard
    from ui.launcher.components.sidebar import Sidebar
    from ui.launcher.components.status_panel import StatusPanel
    from ui.launcher.components.topbar import TopBar
    from ui.launcher.views.assistant_view import AssistantView
    from ui.launcher.views.settings_operations_panel import SettingsOperationsPanel
    from ui.launcher.views.instance_manager_view import InstanceManagerView
    from ui.launcher.views.library_view import LibraryView
    from ui.launcher.views.local_llm_view import LocalLLMView
    from ui.launcher.views.models_hub_view import ModelsHubView
    from ui.launcher.views.settings_device_accounts_panel import SettingsDeviceAccountsPanel
    from ui.launcher.views.models_view import ModelsView
    from ui.launcher.views.runtime_routing_view import RuntimeRoutingView
    from ui.launcher.views import library_view as library_view_module
    from ui.launcher.views import models_view as models_view_module
    from ui.launcher.views import settings_view as settings_view_module
    from ui.launcher.views.tools_view import ToolsView
    from ui.launcher.views.voices_view import VoicesView
    from ui.launcher import launcher_window
except Exception as exc:  # pragma: no cover
    QApplication = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

from utils import personalization_config as personalization_config
import utils.runtime_profile as runtime_profile
from src.guppy.launcher_application.launch_attempt_guard import mark_launch_attempt


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
        self._request_in_flight = False
        self._assistant_view = self._AssistantViewStub()
        self._api_reachable_result = True
        self._api_recovery_result = (True, "api already reachable")

    class _AssistantViewStub:
        def add_user_message(self, _text: str) -> None:
            return

        def add_system_message(self, _text: str) -> None:
            return

        def set_status(self, _text: str) -> None:
            return

        def selected_mode(self) -> str:
            return "auto"

        def recent_history(self, limit: int = 12) -> list[dict[str, str]]:
            del limit
            return []

        def set_request_in_flight(self, _in_flight: bool) -> None:
            return

    def _api_reachable(self, timeout: float = 0.8) -> bool:
        del timeout
        return bool(self._api_reachable_result)

    def _ensure_api_reachable_for_command(self) -> tuple[bool, str]:
        return self._api_recovery_result
    def _validate_mode_ready(self, _mode: str) -> tuple[bool, str]:
        return True, ""

    def _chat_timeout_for_request(self, mode: str, command: str = "") -> float:
        return launcher_window.LauncherWindow._chat_timeout_for_request(mode, command)

    def _http_json(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
        timeout: float = 8.0,
        **kwargs,
    ) -> dict:
        del path, method, payload, timeout, kwargs
        return {"response": "ok"}

    def _is_unauthorized_error(self, _text: str) -> bool:
        return False

    def _log_launcher_event(self, event: str, **fields) -> None:
        payload = {"event": event, **fields}
        path = launcher_window._RUNTIME / "launcher_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(__import__("json").dumps(payload) + "\n")


class _ImmediateThread:
    def __init__(self, *, target=None, args=(), kwargs=None, daemon=None) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = daemon

    def start(self) -> None:
        if callable(self._target):
            self._target(*self._args, **self._kwargs)


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
            self.assertTrue(btn.isEnabled())
            self.assertTrue(btn.toolTip().strip())

        mic_buttons = [b for b in assistant.findChildren(QPushButton) if b.text() == "●"]
        self.assertEqual(len(mic_buttons), 1)
        self.assertTrue(mic_buttons[0].isEnabled())
        self.assertTrue(mic_buttons[0].toolTip().strip())

        send_buttons = [b for b in assistant.findChildren(QPushButton) if b.text() == "▶"]
        self.assertEqual(len(send_buttons), 1)
        self.assertTrue(send_buttons[0].isEnabled())

    def test_supervised_api_start_debounces_recent_launcher_command_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            logged: list[tuple[str, dict]] = []
            stub = SimpleNamespace(
                _log_launcher_event=lambda event, **fields: logged.append((event, fields)),
                _api_reachability_status=lambda timeout=0.8: ("offline", "still booting"),
            )
            mark_launch_attempt(runtime_dir, "launcher_command_supervised_api")

            original_runtime = launcher_window._RUNTIME
            try:
                launcher_window._RUNTIME = runtime_dir
                started, detail = launcher_window.LauncherWindow._start_supervised_api_subprocess(stub)
            finally:
                launcher_window._RUNTIME = original_runtime

        self.assertFalse(started)
        self.assertIn("already attempted recently", detail)
        self.assertEqual(logged, [("api_command_launch_debounced", {"mode": "supervised"})])

    def test_command_api_recovery_uses_hidden_direct_start_only(self):
        logged: list[tuple[str, dict]] = []
        direct_calls: list[str] = []
        supervised_calls: list[str] = []
        stub = SimpleNamespace(
            _api_reachability_status=lambda timeout=0.8: ("offline", "down"),
            _start_api_subprocess=lambda: (direct_calls.append("direct"), (True, "api started and published startup readiness"))[1],
            _start_supervised_api_subprocess=lambda: (supervised_calls.append("supervised"), (True, "should not be used"))[1],
            _log_launcher_event=lambda event, **fields: logged.append((event, fields)),
        )

        started, detail = launcher_window.LauncherWindow._ensure_api_reachable_for_command(stub)

        self.assertTrue(started)
        self.assertEqual(detail, "api started and published startup readiness")
        self.assertEqual(direct_calls, ["direct"])
        self.assertEqual(supervised_calls, [])
        self.assertEqual(logged, [])

    def test_tool_management_redirect_routes_to_settings_connectors(self):
        focused: list[dict[str, str]] = []
        syslog: list[str] = []
        events: list[tuple[str, dict]] = []
        messages: list[str] = []
        tabs: list[int] = []
        dummy = SimpleNamespace(
            _settings_hub_view=SimpleNamespace(
                focus_connectors=lambda connector_id="", provider="", account_id="", note="": focused.append(
                    {
                        "connector": connector_id,
                        "provider": provider,
                        "account_id": account_id,
                        "note": note,
                    }
                )
            ),
            _assistant_view=SimpleNamespace(add_system_message=messages.append),
            _status_panel=SimpleNamespace(append_syslog=syslog.append),
            _on_tab_change=lambda index: tabs.append(index),
            _set_daily_activity=lambda text: setattr(dummy, "_daily_activity", text),
            _log_launcher_event=lambda event, **fields: events.append((event, fields)),
        )

        launcher_window.LauncherWindow._on_tool_management_requested(
            dummy,
            {
                "tool": "send_email",
                "connector": "gmail",
                "destination": "settings_device_accounts",
                "note": "Open Gmail setup in Settings.",
            },
        )

        self.assertEqual(tabs[-1], launcher_window._SETTINGS_VIEW_INDEX)
        self.assertEqual(focused[-1]["connector"], "gmail")
        self.assertIn("Settings owns connector setup", messages[-1])
        self.assertEqual(events[-1][0], "tool_management_redirected")

    def test_assistant_mode_dropdown_excludes_internal_vault_mode(self):
        assistant = AssistantView()
        modes = [assistant._cb_mode.itemText(i) for i in range(assistant._cb_mode.count())]

        self.assertEqual(modes, ["AUTO", "CLAUDE", "OLLAMA", "LOCAL", "CODE", "TEACHING"])
        self.assertNotIn("VAULT", modes)

    def test_topbar_instance_switcher_emits_selection(self):
        topbar = TopBar()
        selected: list[str] = []
        topbar.instance_selected.connect(lambda name: selected.append(name))

        visible_nav = [btn.text() for btn in topbar._nav_btns if not btn.isHidden()]
        self.assertEqual(visible_nav, ["HOME", "MODELS", "TOOLS", "LIBRARY", "SETTINGS"])
        self.assertEqual(topbar._workspace_nav_btn.text(), "WORKSPACES")
        self.assertIn("ACTIVE MODEL:", topbar._summary_primary_lbl.full_text())

        topbar.set_instances(["guppy-primary", "builder-collab"], active_instance="guppy-primary")
        topbar.set_active_instance("builder-collab")

        self.assertEqual(topbar._instance_cb.currentText(), "builder-collab")
        self.assertEqual(selected, [])

        topbar._instance_cb.setCurrentText("guppy-primary")
        self.assertTrue(selected)
        self.assertEqual(selected[-1], "guppy-primary")

    def test_topbar_runtime_chip_updates_copy_and_tooltip(self):
        topbar = TopBar()

        topbar.set_runtime_status(
            "CHECK",
            detail="Startup checks are partial and need attention.",
            severity="warn",
        )

        self.assertEqual(topbar._runtime_chip.text(), "CHECK")
        self.assertIn("partial", topbar._runtime_chip.toolTip().lower())

    def test_home_drawer_toggle_actually_opens_and_closes_on_home(self):
        visible_states: list[bool] = []
        dummy = SimpleNamespace(
            _home_drawer_open=False,
            _stack=SimpleNamespace(currentIndex=lambda: launcher_window._HOME_VIEW_INDEX),
            _status_panel=SimpleNamespace(isVisible=lambda: False),
            _set_status_panel_visible=lambda visible: visible_states.append(bool(visible)),
        )

        launcher_window.LauncherWindow._toggle_status_panel(dummy)
        launcher_window.LauncherWindow._toggle_status_panel(dummy)

        self.assertEqual(visible_states, [True, False])
        self.assertFalse(dummy._home_drawer_open)

    def test_sidebar_exposes_five_hub_visible_nav_and_hides_legacy_aliases(self):
        sidebar = Sidebar()
        visible_labels = [item._label.text() for item in sidebar._visible_items]
        hidden_labels = [item._label.text() for item in sidebar._items if item not in sidebar._visible_items]
        self.assertEqual(visible_labels, ["HOME", "MODELS", "TOOLS", "LIBRARY", "SETTINGS"])
        self.assertIn("LOCAL LLM", hidden_labels)
        self.assertIn("MY PC", hidden_labels)
        self.assertIn("RUNTIME", hidden_labels)

    def test_models_view_is_library_only(self):
        view = ModelsView()

        self.assertTrue(view._runtime_bar.isHidden())
        self.assertTrue(view._route_bar.isHidden())
        self.assertFalse(view._library_scroll.isHidden())
        self.assertEqual(view._title_lbl.text(), "MODELS")
        self.assertTrue(view._active_lbl.text().startswith("CURRENT MODEL:"))
        self.assertTrue(view._active_runtime_lbl.text().startswith("LOCAL RUNTIME:"))
        self.assertEqual(view._local_header.text(), "ON THIS PC")
        self.assertEqual(view._cloud_header.text(), "CLOUD OPTIONS")
        labels = [child.text() for child in view.findChildren(type(view._local_header))]
        self.assertIn("RECOMMENDED", labels)
        self.assertIn("INSTALLED ON THIS PC", labels)
        self.assertIn("ADVANCED / EXPERIMENTAL", labels)
        self.assertIn("Pick the model for this assistant session", view._library_hint_lbl.text())
        self.assertIn("Recommended default:", view._library_summary_lbl.text())
        self.assertIn("Heavier local option:", view._library_summary_lbl.text())
        runtime_options = [view._runtime_backend_cb.itemText(i) for i in range(view._runtime_backend_cb.count())]
        self.assertEqual(runtime_options, ["OLLAMA", "LM STUDIO", "LOCAL HARNESS", "LEMONADE"])

    def test_settings_device_accounts_panel_surfaces_human_friendly_api_key_field(self):
        view = SettingsDeviceAccountsPanel()
        view.set_windows_snapshot(
            {
                "install": "Installed on this PC: Ollama CLI found",
                "runtime": "Local AI runtime: OLLAMA | Live backend: OLLAMA | Status: READY",
                "next": "Recommended next step: verify runtime",
                "diagnostics": "Diagnostics: ready",
            }
        )
        view.set_connector_inventory(
            [
                {
                    "id": "youtube",
                    "label": "YouTube",
                    "auth_kind": "api_key",
                    "auth_state": "optional",
                    "auth_detail": "API key improves quota stability.",
                    "next_step": "Paste an API key, save it, then verify.",
                    "actions_supported": ["verify", "connect", "disconnect"],
                    "secret_fields": ["YOUTUBE_API_KEY"],
                    "providers": [],
                    "accounts": [],
                }
            ]
        )

        self.assertIn("ready on this pc", view._summary_lbl.text().lower())
        self.assertIn("Ollama is healthy and ready", view._pc_runtime_lbl.text())
        self.assertIn("Next step: verify runtime", view._pc_next_lbl.text())
        self.assertIn("supervised launch", view._pc_diag_lbl.text())
        self.assertIn("Local AI health:", view._pc_runtime_lbl.text())
        self.assertIn("YouTube", view._account_status_lbl.text())
        self.assertIn("video tools", view._account_status_lbl.text().lower())
        self.assertEqual(len(view._connector_card_buttons), 1)
        self.assertIn("YouTube", view._connector_card_buttons[0][1].text())
        self.assertTrue(view._connector_card_buttons[0][1].text().startswith(">"))
        self.assertFalse(view._provider_cb.isVisible())
        self.assertFalse(view._account_cb.isVisible())
        self.assertEqual(view._save_btn.text(), "SAVE API KEY")
        self.assertIn("find a youtube video", view._next_step_hint_lbl.text().lower())
        self.assertIn("verify youtube", view._verify_btn.toolTip().lower())
        visible_fields = [row for row in view._field_rows if not row[0].isHidden()]
        self.assertTrue(visible_fields)
        self.assertEqual(visible_fields[0][1].text(), "API Key")
        self.assertIn("Paste the YouTube Data API key", visible_fields[0][3].text())

    def test_settings_device_accounts_panel_hides_calendar_sign_in_until_credentials_file_exists(self):
        view = SettingsDeviceAccountsPanel()
        view.set_connector_inventory(
            [
                {
                    "id": "calendar",
                    "label": "Calendar",
                    "auth_kind": "oauth_file_token",
                    "auth_state": "missing",
                    "auth_detail": "Calendar credentials file is missing for this host.",
                    "next_step": "Add the credentials JSON on this PC, then sign in.",
                    "actions_supported": ["verify", "connect", "disconnect"],
                    "secret_fields": [],
                    "providers": [],
                    "accounts": [{"id": "primary", "label": "Primary calendar"}],
                }
            ]
        )

        self.assertIn("browser sign-in", view._account_status_lbl.text().lower())
        self.assertIn("credentials file", view._account_detail_lbl.text().lower())
        self.assertIn("credentials json", view._account_step_lbl.text().lower())
        self.assertFalse(view._connect_btn.isVisible())
        self.assertFalse(view._verify_btn.isHidden())

    def test_local_llm_view_loads_repo_artifacts_without_touching_home(self):
        view = LocalLLMView()
        view.refresh()
        self.assertIn("Using qwen3:8b", view._summary_lbl.text())
        self.assertIn("Default chat model:", view._manifest_lbl.text())
        self.assertTrue(view._benchmark_lbl.parentWidget().isHidden())

    def test_models_hub_view_unifies_models_local_llm_and_voice_surfaces(self):
        hub = ModelsHubView(ModelsView(), LocalLLMView(), VoicesView())

        self.assertEqual(hub._models_view._title_lbl.text(), "MODELS")
        self.assertIn("Using qwen3:8b", hub._local_llm_panel._summary_lbl.text())
        self.assertIn("Ready now:", hub._voice_panel._voice_evidence_lbl.text())
        labels = [label.text() for label in hub.findChildren(QLabel)]
        buttons = [button.text() for button in hub.findChildren(QPushButton)]
        self.assertTrue(
            any("Keys and accounts stay in Settings" in text for text in labels),
            "Models hub should keep credential storage ownership in Settings",
        )
        self.assertTrue(
            {"LOCAL LLMS STATUS", "MODEL SWAPPING", "MODEL INSTALLATION", "MODEL UNINSTALLATION", "MODEL SOURCING"}.issubset(set(buttons)),
            "Models hub should expose the requested focused tabs",
        )

    def test_topbar_quick_actions_emit_for_live_buttons(self):
        topbar = TopBar()
        actions: list[str] = []
        topbar.quick_action.connect(actions.append)

        topbar._notif_btn.click()
        topbar._term_btn.click()

        self.assertEqual(actions, ["notifications", "terminal"])

    def test_models_tab_routes_to_models_stack_and_highlight_lane(self):
        class _StackRecorder:
            def __init__(self) -> None:
                self.indices: list[int] = []

            def setCurrentIndex(self, index: int) -> None:
                self.indices.append(index)

        class _TopbarRecorder:
            def __init__(self) -> None:
                self.active_tabs: list[int] = []
                self.summaries: list[str] = []

            def set_active_tab(self, index: int) -> None:
                self.active_tabs.append(index)

            def set_launcher_summary(self, text: str) -> None:
                self.summaries.append(str(text))

        class _SidebarRecorder:
            def __init__(self) -> None:
                self.active_tabs: list[int] = []

            def set_active(self, index: int) -> None:
                self.active_tabs.append(index)

            def is_collapsed(self) -> bool:
                return True

            def set_collapsed(self, collapsed: bool) -> None:
                del collapsed

        dummy = type("LauncherNavDummy", (), {})()
        dummy._stack = _StackRecorder()
        dummy._topbar = _TopbarRecorder()
        dummy._sidebar = _SidebarRecorder()
        dummy._home_drawer_open = False
        dummy._sync_automation_test_state = lambda: None
        dummy._set_status_panel_visible = lambda visible: setattr(dummy, "_status_visible", visible)
        dummy._resolve_stack_index = launcher_window.LauncherWindow._resolve_stack_index
        dummy._visible_nav_index = launcher_window.LauncherWindow._visible_nav_index
        dummy._shell_model_loadout_summary = launcher_window.LauncherWindow._shell_model_loadout_summary
        dummy._sync_topbar_model_context = lambda **kwargs: None
        dummy._sync_shell_model_summary = launcher_window.LauncherWindow._sync_shell_model_summary.__get__(dummy, type(dummy))

        original_read_json = launcher_window.read_json_dict
        launcher_window.read_json_dict = lambda _path: {
            "local_runtime_backend": "ollama",
            "local_main_model": "guppy-main",
            "local_sub_model_a": "guppy-fast",
            "local_sub_model_b": "guppy-code",
        }
        try:
            launcher_window.LauncherWindow._on_tab_change(dummy, launcher_window._MODELS_VIEW_INDEX)
        finally:
            launcher_window.read_json_dict = original_read_json

        self.assertEqual(dummy._stack.indices[-1], launcher_window._MODELS_VIEW_INDEX)
        self.assertEqual(dummy._topbar.active_tabs[-1], launcher_window._MODELS_LIBRARY_ALIAS_INDEX)
        self.assertEqual(dummy._sidebar.active_tabs[-1], launcher_window._MODELS_LIBRARY_ALIAS_INDEX)
    def test_shell_model_loadout_summary_prefers_saved_three_model_state(self):
        summary = launcher_window.LauncherWindow._shell_model_loadout_summary(
            active_model="fallback-model",
            runtime_backend="lemonade",
            settings_payload={
                "local_runtime_backend": "ollama",
                "local_main_model": "qwen-main",
                "local_sub_model_a": "qwen-fast",
                "local_sub_model_b": "qwen-code",
            },
            environment={
                "GUPPY_MAIN_MODEL": "env-main",
                "GUPPY_SUB_MODEL_A": "env-fast",
                "GUPPY_SUB_MODEL_B": "env-code",
            },
        )

        self.assertEqual(
            summary,
            "MODELS / OLLAMA / MAIN qwen-main / SUB A qwen-fast / SUB B qwen-code",
        )

    def test_sync_shell_model_summary_pushes_three_model_state_to_topbar(self):
        class _TopbarRecorder:
            def __init__(self) -> None:
                self.summaries: list[str] = []

            def set_launcher_summary(self, text: str) -> None:
                self.summaries.append(str(text))

        dummy = type("LauncherSummaryDummy", (), {})()
        dummy._topbar = _TopbarRecorder()
        dummy._shell_model_loadout_summary = launcher_window.LauncherWindow._shell_model_loadout_summary
        dummy._sync_topbar_model_context = lambda **kwargs: None

        original_read_json = launcher_window.read_json_dict
        launcher_window.read_json_dict = lambda _path: {
            "local_runtime_backend": "ollama",
            "local_main_model": "guppy-main",
            "local_sub_model_a": "guppy-fast",
            "local_sub_model_b": "guppy-code",
        }
        try:
            launcher_window.LauncherWindow._sync_shell_model_summary(
                dummy,
                active_model="fallback-model",
                runtime_backend="lemonade",
            )
        finally:
            launcher_window.read_json_dict = original_read_json

        self.assertEqual(
            dummy._topbar.summaries[-1],
            "MODELS / OLLAMA / MAIN guppy-main / SUB A guppy-fast / SUB B guppy-code",
        )

    def test_topbar_notification_badge_updates_count_and_severity(self):
        topbar = TopBar()

        topbar.set_notification_badge(3, severity="warn")
        self.assertEqual(topbar._notif_badge.text(), "3")
        self.assertFalse(topbar._notif_badge.isHidden())

        topbar.set_notification_badge(0, severity="info")
        self.assertTrue(topbar._notif_badge.isHidden())

    def test_sidebar_badge_uses_clean_painted_mark(self):
        sidebar = Sidebar()

        badge = sidebar._art_card.layout().itemAt(0).widget()

        self.assertEqual(badge.size().width(), 48)

    def test_agent_card_offline_shows_wired_initialize_button(self):
        card = AgentCard("GUPPY")
        card.update_status(online=False, last_seen="now", load_pct=None)

        init_button = card._btn_init
        self.assertFalse(init_button.isHidden())
        self.assertTrue(init_button.isEnabled())  # wired — emits init_requested signal
        self.assertTrue(init_button.toolTip().strip())

    def test_assistant_home_surface_shows_instance_and_background_context(self):
        assistant = AssistantView()

        assistant.set_active_instance(
            "builder-collab",
            workspace_type="builder_instance",
            description="Planning partner for review loops.",
            mode="code",
            persona="guppy",
            voice="default",
            last_message="Finish the launcher framing pass and verify the workspace cues.",
        )
        assistant.set_background_status("builder-collab · STANDARD · GUPPY LIVE", healthy=True)
        assistant.set_background_event("Recovery warmup completed")
        assistant.set_runtime_facts(
            profile="standard",
            model="guppy",
            voice="EDGE TTS from persona voice",
            latency="42",
            last_query="status",
        )
        assistant.set_route_preview(
            task_type="simple",
            route="haiku",
            model="claude-haiku-4-5-20251001",
            backup_model="claude-sonnet-4-6",
            reason="simple task classification",
            evidence="cloud route needs API key; launcher-wide last reply 42 ms",
        )
        assistant.set_recovery_summary("warmup complete", healthy=True)
        assistant.activate_agent("guppy")

        self.assertIn("BUILDER-COLLAB", assistant._instance_chip.text())
        self.assertIn("WORKSPACE", assistant._instance_chip.text())
        self.assertIn("GUPPY LIVE", assistant._background_chip.text())
        self.assertIn("Active agent switched to GUPPY", assistant._background_event.text())
        self.assertTrue(assistant._background_event.isHidden())
        self.assertIn("Starters are optional.", assistant._hero_subtitle.text())
        self.assertIn("Resume cue: Recent context: Finish the launcher framing pass", assistant._hero_subtitle.text())
        self.assertNotIn("Active agent switched to GUPPY", assistant._hero_subtitle.text())
        self.assertTrue(assistant._workspace_summary.isHidden())
        self.assertTrue(assistant._context_bar.isHidden())
        self.assertTrue(assistant._workspace_details_strip.isHidden())
        self.assertTrue(assistant._workspace_details_host.isHidden())
        self.assertTrue(assistant._launcher_panel.isHidden())
        self.assertTrue(assistant._identity_details_btn.isHidden())
        self.assertTrue(assistant._starter_summary.isHidden())
        self.assertIn("GUPPY model", assistant._runtime_facts.text())
        self.assertIn("EDGE TTS from persona voice", assistant._runtime_facts.text())
        self.assertTrue(assistant._runtime_facts.isHidden())
        self.assertIn("Why: simple task classification", assistant._route_facts.text())
        self.assertIn("Evidence: cloud route needs API key; launcher-wide last reply 42 ms", assistant._route_facts.text())
        self.assertTrue(assistant._route_facts.isHidden())
        self.assertIn("warmup complete", assistant._recovery_summary.text().lower())
        self.assertTrue(assistant._recovery_summary.isHidden())
        self.assertIn("Start here in builder-collab", assistant._entry_hint.text())
        self.assertIn("PLAN NEXT PASS", assistant._entry_hint.text())
        self.assertIn("next pass", assistant._input.placeholderText().lower())
        self.assertEqual(assistant._cb_persona.currentText(), "GUPPY")

    def test_assistant_home_surface_updates_copy_when_workspace_role_changes(self):
        assistant = AssistantView()

        assistant.set_active_instance(
            "guppy-primary",
            workspace_type="user_instance",
            description="Daily help and recurring requests.",
            mode="auto",
            persona="guppy",
            voice="default",
            last_message="Start with the morning brief and inbox review.",
        )
        daily_summary = assistant._workspace_summary.text()
        daily_entry = assistant._entry_hint.text()
        daily_placeholder = assistant._input.placeholderText()
        daily_starter = assistant._starter_buttons["morning_brief"].text()

        assistant.set_active_instance(
            "builder-collab",
            workspace_type="builder_instance",
            description="Planning partner for review loops.",
            mode="code",
            persona="guppy",
            voice="default",
            last_message="Finish the launcher framing pass and verify the workspace cues.",
        )

        self.assertIn("Daily help and recurring requests.", daily_summary)
        self.assertIn("Recent context: Start with the morning brief", daily_summary)
        self.assertIn("Start here in guppy-primary", daily_entry)
        self.assertIn("next thing you want to move forward", daily_placeholder.lower())
        self.assertEqual(daily_starter, "MORNING BRIEF")
        self.assertIn("Planning partner for review loops.", assistant._workspace_summary.text())
        self.assertIn("Recent context: Finish the launcher framing pass", assistant._workspace_summary.text())
        self.assertIn("Resume cue: Recent context: Finish the launcher framing pass", assistant._hero_subtitle.text())
        self.assertIn("Start here in builder-collab", assistant._entry_hint.text())
        self.assertIn("next pass", assistant._input.placeholderText().lower())
        self.assertEqual(assistant._starter_buttons["morning_brief"].text(), "PLAN NEXT PASS")

    def test_assistant_home_can_surface_first_run_banner_and_focus_input(self):
        assistant = AssistantView()

        assistant.set_first_run_status(
            visible=True,
            summary="Finish desktop install checks first.",
            detail="Open Settings, then come back and send one short ask.",
            install_status="failed",
            model_status="pending",
            request_status="pending",
        )
        assistant._focus_input_for_first_run()

        self.assertFalse(assistant._first_run_frame.isHidden())
        self.assertIn("desktop install checks", assistant._first_run_summary.text().lower())
        self.assertIn("FAILED", assistant._first_run_install_chip.text())
        self.assertIs(assistant.focusWidget(), assistant._input)

    def test_assistant_home_hides_first_run_banner_when_not_needed(self):
        assistant = AssistantView()
        assistant.set_first_run_status(visible=False)

        self.assertTrue(assistant._first_run_frame.isHidden())

    def test_assistant_starter_actions_load_prompt_and_mode(self):
        assistant = AssistantView()
        loaded: list[tuple[str, str]] = []
        assistant.starter_requested.connect(lambda starter_id, prompt: loaded.append((starter_id, prompt)))

        self.assertEqual(
            set(assistant._starter_buttons.keys()),
            {"morning_brief", "focused_research", "file_triage", "builder_review"},
        )

        assistant._starter_buttons["builder_review"].click()

        self.assertEqual(assistant.selected_mode(), "code")
        self.assertIn("missing tests first", assistant._input.text())
        self.assertIn("Starter loaded: BUILDER REVIEW", assistant._background_event.text())
        self.assertIn("Starters are optional.", assistant._hero_subtitle.text())
        self.assertNotIn("Starter loaded: BUILDER REVIEW", assistant._hero_subtitle.text())
        self.assertIn("BUILDER REVIEW is ready", assistant._starter_summary.text())

    def test_launcher_refresh_first_run_banner_maps_statuses_to_home_banner(self):
        class _WizardStateStub:
            def get_status(self, checkpoint: int):
                values = {1: "passed", 2: "failed", 3: "pending"}
                return SimpleNamespace(value=values[checkpoint])

        class _WizardStub:
            def __init__(self, workspace_id: str) -> None:
                self.workspace_id = workspace_id
                self.state = _WizardStateStub()

            def should_skip(self) -> bool:
                return False

        calls: list[dict[str, object]] = []
        dummy = SimpleNamespace(
            _active_instance_name="builder-collab",
            _assistant_view=SimpleNamespace(set_first_run_status=lambda **kwargs: calls.append(kwargs)),
        )

        original = launcher_window.FirstRunWizard
        try:
            launcher_window.FirstRunWizard = _WizardStub
            launcher_window.LauncherWindow._refresh_first_run_banner(dummy)
        finally:
            launcher_window.FirstRunWizard = original

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["visible"])
        self.assertEqual(calls[0]["install_status"], "passed")
        self.assertEqual(calls[0]["model_status"], "failed")
        self.assertEqual(calls[0]["request_status"], "pending")
        self.assertIn("local model runtime", calls[0]["summary"].lower())

    def test_assistant_builder_workspace_refreshes_starter_language(self):
        assistant = AssistantView()
        loaded: list[tuple[str, str]] = []
        assistant.starter_requested.connect(lambda starter_id, prompt: loaded.append((starter_id, prompt)))

        assistant.set_active_instance(
            "builder-collab",
            workspace_type="builder_instance",
            description="Planning partner for review loops.",
        )

        self.assertEqual(assistant._starter_buttons["morning_brief"].text(), "PLAN NEXT PASS")
        assistant._starter_buttons["morning_brief"].click()

        self.assertEqual(assistant.selected_mode(), "code")
        self.assertIn("Plan the next builder pass", assistant._input.text())
        assistant.ensure_welcome_message()
        self.assertTrue(assistant._conversation_history)
        self.assertIn("Builder workspace ready", assistant._conversation_history[-1]["content"])
        self.assertIn("next pass", assistant._conversation_history[-1]["content"].lower())
        self.assertIn("Optional starter: PLAN NEXT PASS.", assistant._conversation_history[-1]["content"])
        self.assertEqual(loaded[-1][0], "morning_brief")

    def test_assistant_daily_workspace_welcome_keeps_one_clear_primary_action(self):
        assistant = AssistantView()
        assistant.ensure_welcome_message()

        self.assertTrue(assistant._conversation_history)
        welcome = assistant._conversation_history[-1]["content"]
        self.assertIn("Start here.", welcome)
        self.assertIn("Next step:", welcome)
        self.assertIn("Optional starter: MORNING BRIEF.", welcome)
        self.assertNotIn("head start", welcome.lower())

    def test_assistant_mic_button_emits_and_updates_state(self):
        assistant = AssistantView()
        triggered: list[str] = []
        assistant.mic_requested.connect(lambda: triggered.append("mic"))

        assistant._mic_btn.click()
        self.assertEqual(triggered, ["mic"])

        assistant.set_mic_capture_state(True)
        self.assertEqual(assistant._mic_btn.text(), "◉")
        self.assertTrue(assistant._mic_btn.isEnabled())

        assistant.set_mic_capture_state(False)
        self.assertEqual(assistant._mic_btn.text(), "●")

    def test_assistant_saved_reply_context_refreshes_from_latest_reply_and_can_swap(self):
        assistant = AssistantView()
        refresh_calls: list[tuple[str, bool]] = []
        focused_titles: list[str] = []
        assistant.active_context_refresh_requested.connect(
            lambda text, as_artifact: refresh_calls.append((text, as_artifact))
        )
        assistant.active_context_focus_requested.connect(focused_titles.append)

        assistant.add_assistant_message("Latest answer from this turn.")
        assistant.set_active_context_items(
            [
                {
                    "title": "Release review",
                    "kind": "note",
                    "detail": "Saved from the latest assistant reply in builder-collab",
                    "origin": "assistant_reply",
                    "source_label": "Saved reply note",
                },
                {"title": "review-notes.md", "kind": "study", "detail": "C:/repo/docs/review-notes.md"},
            ]
        )

        self.assertFalse(assistant._active_context_refresh_btn.isHidden())
        self.assertFalse(assistant._active_context_swap_btn.isHidden())

        assistant._active_context_refresh_btn.click()
        assistant._active_context_swap_btn.click()

        self.assertEqual(refresh_calls, [("Latest answer from this turn.", False)])
        self.assertEqual(focused_titles, ["review-notes.md"])

    def test_assistant_saved_output_context_refreshes_from_latest_reply_as_artifact(self):
        assistant = AssistantView()
        refresh_calls: list[tuple[str, bool]] = []
        assistant.active_context_refresh_requested.connect(
            lambda text, as_artifact: refresh_calls.append((text, as_artifact))
        )

        assistant.add_assistant_message("Latest artifact content.")
        assistant.set_active_context_items(
            [
                {
                    "title": "Release review artifact",
                    "kind": "artifact",
                    "detail": "Checklist and validation notes ready for the next pass.",
                    "origin": "assistant_reply_artifact",
                    "source_label": "Saved reply artifact",
                },
                {"title": "release-bundle.zip", "kind": "artifact", "detail": "C:/tmp/release-bundle.zip"},
            ]
        )

        self.assertFalse(assistant._active_context_refresh_btn.isHidden())
        assistant._active_context_refresh_btn.click()
        self.assertEqual(refresh_calls, [("Latest artifact content.", True)])

    def test_active_context_refresh_routing_uses_reply_or_artifact_save_paths(self):
        class _WorkflowStub:
            def __init__(self) -> None:
                self.reply_saved_calls: list[tuple[str, bool]] = []
                self.artifact_saved_calls: list[tuple[str, bool]] = []

            def handle_reply_saved(self, content: str, *, attach_next: bool = False) -> None:
                self.reply_saved_calls.append((content, attach_next))

            def handle_reply_artifact_saved(self, content: str, *, attach_now: bool = False) -> None:
                self.artifact_saved_calls.append((content, attach_now))

        workflow = _WorkflowStub()
        dummy = type("ActiveContextRefreshDummy", (), {})()
        dummy._ensure_library_workflow = lambda: workflow

        launcher_window.LauncherWindow._on_active_context_refresh_requested(
            dummy,
            "Latest answer from this turn.",
            False,
        )
        launcher_window.LauncherWindow._on_active_context_refresh_requested(
            dummy,
            "Latest artifact content.",
            True,
        )

        self.assertEqual(workflow.reply_saved_calls, [("Latest answer from this turn.", True)])
        self.assertEqual(workflow.artifact_saved_calls, [("Latest artifact content.", True)])

    def test_library_view_picker_actions_fill_root_and_artifact_paths(self):
        view = LibraryView()
        view._root_label.clear()
        view._root_path.clear()
        view._artifact_title.clear()
        view._artifact_path.clear()

        old_root_picker = library_view_module.QFileDialog.getExistingDirectory
        old_file_picker = library_view_module.QFileDialog.getOpenFileName
        try:
            library_view_module.QFileDialog.getExistingDirectory = (
                lambda *_args, **_kwargs: "C:/Users/Ryan/Documents/Study"
            )
            library_view_module.QFileDialog.getOpenFileName = (
                lambda *_args, **_kwargs: ("C:/Users/Ryan/Documents/Study/checklist.md", "")
            )
            view._root_browse_btn.click()
            view._artifact_browse_btn.click()
        finally:
            library_view_module.QFileDialog.getExistingDirectory = old_root_picker
            library_view_module.QFileDialog.getOpenFileName = old_file_picker

        self.assertEqual(view._root_path.text(), "C:/Users/Ryan/Documents/Study")
        self.assertEqual(view._root_label.text(), "Study")
        self.assertEqual(view._artifact_title.text(), "checklist")
        self.assertEqual(view._artifact_path.text(), "C:/Users/Ryan/Documents/Study/checklist.md")

    def test_library_view_edit_cancel_buttons_restore_note_and_artifact_inputs(self):
        view = LibraryView()

        view._begin_note_edit(17, "Review packet", "Validation notes\nWith another line.")
        self.assertEqual(view._note_save_btn.text(), "UPDATE NOTE")
        self.assertFalse(view._note_cancel_btn.isHidden())
        view._note_cancel_btn.click()
        self.assertEqual(view._note_save_btn.text(), "PIN NOTE")
        self.assertTrue(view._note_cancel_btn.isHidden())
        self.assertEqual(view._note_title.text(), "")
        self.assertEqual(view._note_body.toPlainText(), "")

        view._begin_artifact_edit(21, "Release bundle", "C:/tmp/release.zip")
        self.assertEqual(view._artifact_save_btn.text(), "UPDATE ARTIFACT")
        self.assertFalse(view._artifact_cancel_btn.isHidden())
        view._artifact_cancel_btn.click()
        self.assertEqual(view._artifact_save_btn.text(), "SAVE ARTIFACT")
        self.assertTrue(view._artifact_cancel_btn.isHidden())
        self.assertEqual(view._artifact_title.text(), "")
        self.assertEqual(view._artifact_path.text(), "")

    def test_library_view_surfaces_selected_root_and_chat_reuse_guidance(self):
        view = LibraryView()
        view.set_instance_context(
            {
                "name": "builder-collab",
                "type": "builder_instance",
                "description": "Planning partner for review loops.",
            },
            {},
        )

        self.assertIn("Nothing outside approved roots is scanned", view._roots_hint.text())
        self.assertIn("READY TO USE IN CHAT", view._recent_header.text())
        self.assertIn("USE IN CHAT attaches one as source context", view._recent_hint.text())
        self.assertIn("CURRENT ROOT", view._selected_root_status.text())
        self.assertIn("USE IN CHAT", view._browse_hint.text())
        self.assertFalse(view._root_picker.isHidden())

    def test_library_view_root_picker_switches_selected_root_and_note_editor_hint_tracks_edit_state(self):
        view = LibraryView()
        view.set_instance_context(
            {
                "name": "builder-collab",
                "type": "builder_instance",
                "description": "Planning partner for review loops.",
            },
            {},
        )

        self.assertGreaterEqual(view._root_picker.count(), 1)
        self.assertIn("Multiline notes stay in Library", view._note_editor_hint.text())

        target_index = 0
        if view._root_picker.count() > 1:
            target_index = 1
        view._root_picker.setCurrentIndex(target_index)

        self.assertEqual(view._selected_root_path, str(view._root_picker.currentData() or ""))

        view._begin_note_edit(17, "Review packet", "Validation notes\nWith another line.")
        self.assertIn("Editing pinned note: Review packet.", view._note_editor_hint.text())
        self.assertIn("Body ready:", view._note_editor_hint.text())

    def test_library_view_search_status_and_artifact_hint_track_reuse_state(self):
        view = LibraryView()
        view.set_instance_context(
            {
                "name": "builder-collab",
                "type": "builder_instance",
                "description": "Planning partner for review loops.",
            },
            {},
        )

        self.assertIn("Current root:", view._search_status_lbl.text())
        self.assertIn("Pinned keeps durable notes and artifacts.", view._search_status_lbl.text())
        self.assertIn("Artifacts keep reusable local file references", view._artifact_editor_hint.text())

        view._artifact_title.setText("Checklist bundle")
        view._artifact_path.setText("C:/Users/Ryan/Documents/Study/checklist.md")
        view._refresh_artifact_editor_state()
        self.assertIn("Artifact draft ready: Checklist bundle.", view._artifact_editor_hint.text())

        view._search.setText("guide")
        self.assertIn('Matches for "guide"', view._search_status_lbl.text())

    def test_library_view_media_panel_loads_controls_and_unloads_media(self):
        from PySide6.QtMultimedia import QMediaPlayer

        class _Signal:
            def __init__(self) -> None:
                self._callbacks = []

            def connect(self, callback) -> None:
                self._callbacks.append(callback)

            def emit(self, *args) -> None:
                for callback in list(self._callbacks):
                    callback(*args)

        class _FakeAudioOutput:
            def __init__(self, _owner=None) -> None:
                return

        class _FakePlayer:
            def __init__(self, _owner=None) -> None:
                self.playbackStateChanged = _Signal()
                self.mediaStatusChanged = _Signal()
                self.positionChanged = _Signal()
                self.durationChanged = _Signal()
                self.errorOccurred = _Signal()
                self._state = QMediaPlayer.PlaybackState.StoppedState
                self._source = None

            def setAudioOutput(self, _audio) -> None:
                return

            def setVideoOutput(self, _video) -> None:
                return

            def setSource(self, source) -> None:
                self._source = source

            def play(self) -> None:
                self._state = QMediaPlayer.PlaybackState.PlayingState
                self.playbackStateChanged.emit(self._state)
                self.durationChanged.emit(90000)
                self.positionChanged.emit(15000)

            def pause(self) -> None:
                self._state = QMediaPlayer.PlaybackState.PausedState
                self.playbackStateChanged.emit(self._state)

            def stop(self) -> None:
                self._state = QMediaPlayer.PlaybackState.StoppedState
                self.playbackStateChanged.emit(self._state)

            def playbackState(self):
                return self._state

            def setPosition(self, position: int) -> None:
                self.positionChanged.emit(position)

            def errorString(self) -> str:
                return ""

        view = LibraryView()
        view._media_panel._player_factory = _FakePlayer
        view._media_panel._audio_output_factory = _FakeAudioOutput

        with tempfile.TemporaryDirectory() as td:
            media_path = Path(td) / "walkthrough.mp4"
            media_path.write_bytes(b"fake-media")

            loaded = view._media_panel.load_media("Walkthrough clip", str(media_path))

        self.assertTrue(loaded)
        self.assertEqual(view._media_panel.current_media_title(), "Walkthrough clip")
        self.assertEqual(view._media_panel._play_btn.text(), "PAUSE")
        self.assertIn("Loaded local video", view._media_panel.status_text())
        view._media_panel._toggle_playback()
        self.assertEqual(view._media_panel._play_btn.text(), "PLAY")
        view._media_panel.stop_media()
        self.assertIn("Stopped media", view._media_panel.status_text())
        view._media_panel.unload_media()
        self.assertEqual(view._media_panel.current_media_path(), "")
        self.assertFalse(view._media_panel._play_btn.isEnabled())

    def test_assistant_active_context_surfaces_current_sources_and_primary_source_copy(self):
        assistant = AssistantView()
        assistant.set_active_context_items(
            [
                {
                    "title": "Release review",
                    "kind": "note",
                    "detail": "Saved from the latest assistant reply in builder-collab",
                    "origin": "assistant_reply",
                    "source_label": "Saved reply note",
                },
                {
                    "title": "review-notes.md",
                    "kind": "study",
                    "detail": "C:/repo/docs/review-notes.md",
                },
            ]
        )

        self.assertIn("Current sources:", assistant._active_context_summary.text())
        self.assertIn("Primary source:", assistant._active_context_summary.text())
        self.assertIn("saved reply note", assistant._active_context_summary.text().lower())
        self.assertIn("Current source:", assistant._starter_summary.text())
        self.assertIn("saved reply note", assistant._starter_summary.text().lower())
        self.assertIn("CURRENT SOURCE", assistant._grounding_chip.text())

    def test_assistant_transcript_reply_actions_emit_library_and_artifact_requests(self):
        assistant = AssistantView()
        library_calls: list[tuple[str, bool]] = []
        artifact_calls: list[str] = []
        assistant.assistant_reply_library_requested.connect(
            lambda text, attach_next: library_calls.append((text, attach_next))
        )
        assistant.assistant_reply_artifact_requested.connect(lambda text: artifact_calls.append(text))

        assistant.add_assistant_message("Ship the next tranche.")

        buttons = [
            button
            for button in assistant.findChildren(QPushButton)
            if button.toolTip() in {
                "Save this reply to Library",
                "Attach this reply as source for the next turn",
                "Save this reply as an artifact",
            }
        ]
        self.assertEqual(len(buttons), 3)
        for button in buttons:
            button.click()

        self.assertEqual(
            library_calls,
            [
                ("Ship the next tranche.", False),
                ("Ship the next tranche.", True),
            ],
        )
        self.assertEqual(artifact_calls, ["Ship the next tranche."])

    def test_instance_manager_view_renders_snapshot_and_logs(self):
        view = InstanceManagerView()
        payload = {
            "active_instance": "guppy-primary",
            "limits": {
                "configured": 2,
                "max_configured": 5,
                "active_runtime": 1,
                "max_active_runtime": 2,
            },
            "instances": [
                {
                    "name": "guppy-primary",
                    "description": "Primary",
                    "mode": "auto",
                    "persona": "guppy",
                    "voice": "default",
                    "type": "user_instance",
                    "status": "active",
                    "enabled": True,
                    "last_message": "ready",
                    "governance": {
                        "auth_mode": "runtime_default",
                        "tool_allow": [],
                        "tool_block": [],
                        "endpoint_allow": [],
                        "endpoint_block": [],
                        "policy_note": "Primary workspace inherits the shared runtime policy.",
                        "capabilities": {"read": True, "write": True, "execute": True, "network": True},
                    },
                    "connectors": [
                        {
                            "id": "gmail",
                            "auth_state": "ready",
                            "source": "token_cache",
                            "history": {
                                "last_action": "verify",
                                "last_action_at": "2026-04-15T10:00:00+00:00",
                                "last_result": "Gmail verify passed.",
                            },
                            "binding_validation": {
                                "state": "ready",
                                "message": "Workspace binding matches the current machine inventory.",
                            },
                            "binding": {
                                "enabled": True,
                                "account_id": "main",
                                "provider": "",
                                "action_allow": [],
                                "action_block": [],
                                "endpoint_allow": [],
                                "endpoint_block": [],
                                "note": "",
                            },
                        },
                        {
                            "id": "calendar",
                            "auth_state": "ready",
                            "source": "token_cache",
                            "accounts": [
                                {
                                    "id": "primary",
                                    "label": "Primary calendar",
                                    "auth_state": "ready",
                                }
                            ],
                            "binding": {
                                "enabled": True,
                                "account_id": "main",
                                "provider": "",
                                "action_allow": [],
                                "action_block": [],
                                "endpoint_allow": [],
                                "endpoint_block": [],
                                "note": "",
                            },
                        },
                    ],
                },
                {
                    "name": "builder-collab",
                    "description": "Collaborator",
                    "mode": "teaching",
                    "persona": "guppy",
                    "voice": "default",
                    "type": "builder_instance",
                    "status": "idle",
                    "enabled": False,
                    "last_message": "",
                    "governance": {
                        "auth_mode": "local_only",
                        "tool_allow": ["query_instance", "write_file"],
                        "tool_block": ["execute_command"],
                        "endpoint_allow": ["instance://*"],
                        "endpoint_block": ["https://external*"],
                        "policy_note": "Builder stays local-first.",
                        "capabilities": {"read": True, "write": True, "execute": False, "network": True},
                    },
                    "connectors": [
                        {
                            "id": "gmail",
                            "auth_state": "ready",
                            "source": "token_cache",
                            "accounts": [
                                {
                                    "id": "sales",
                                    "label": "sales@company.com",
                                    "auth_state": "ready",
                                    "auth_detail": "Cached browser token is present for Gmail account sales.",
                                }
                            ],
                            "history": {
                                "last_action": "verify",
                                "last_action_at": "2026-04-15T11:30:00+00:00",
                                "last_result": "Gmail account sales verified.",
                            },
                            "binding_validation": {
                                "state": "ready",
                                "message": "Workspace binding matches the current machine inventory.",
                            },
                            "binding": {
                                "enabled": True,
                                "account_id": "sales",
                                "provider": "",
                                "action_allow": ["compose", "send"],
                                "action_block": ["cleanup"],
                                "endpoint_allow": ["connector://gmail*"],
                                "endpoint_block": [],
                                "note": "Builder can draft from sales.",
                            },
                        },
                        {
                            "id": "crm",
                            "auth_state": "missing",
                            "source": "keyring",
                            "providers": [
                                {
                                    "id": "hubspot",
                                    "label": "HubSpot",
                                    "auth_state": "missing",
                                    "auth_detail": "HubSpot still needs HUBSPOT_API_KEY.",
                                }
                            ],
                            "history": {
                                "last_action": "verify",
                                "last_action_at": "2026-04-15T11:45:00+00:00",
                                "last_result": "CRM verify: missing credentials.",
                            },
                            "binding_validation": {
                                "state": "unbound",
                                "message": "Workspace is not bound to this connector yet.",
                            },
                            "binding": {
                                "enabled": False,
                                "account_id": "",
                                "provider": "hubspot",
                                "action_allow": [],
                                "action_block": ["delete"],
                                "endpoint_allow": ["connector://crm/hubspot*"],
                                "endpoint_block": [],
                                "note": "CRM stays disabled until hubspot auth is verified.",
                            },
                        },
                    ],
                },
            ],
            "warnings": ["disabled instance retained"],
        }

        view.set_instances(payload)
        view.set_logs(
            "guppy-primary",
            [{"timestamp": "2026-04-14T00:00:00+00:00", "role": "assistant", "message": "hello"}],
        )

        self.assertTrue(view._governance_frame.isHidden())
        self.assertTrue(view._connectors_frame.isHidden())
        view._governance_toggle_btn.click()
        self.assertFalse(view._governance_frame.isHidden())
        view._connector_toggle_btn.click()
        self.assertFalse(view._connectors_frame.isHidden())

        self.assertIn("Configured workspaces: 2 / 5", view._summary_lbl.text())
        self.assertIn("Roles:", view._summary_lbl.text())
        self.assertIn("Live workspaces: 1 / 2", view._limits_lbl.text())
        self.assertIn("Role mix:", view._role_mix_lbl.text())
        self.assertIn("Builder 1", view._role_mix_lbl.text())
        self.assertIn("Active workspace fit:", view._collab_lbl.text())
        self.assertIn("Saved context:", view._recurring_lbl.text())
        self.assertIn("AUTO mode", view._recurring_lbl.text())
        self.assertIn("Warnings: 1", view._summary_lbl.text())
        self.assertEqual(view._governance_workspace.currentText(), "guppy-primary")
        self.assertIn("runtime_default", view._governance_status.text())
        self.assertIn("hello", view._logs.toPlainText())
        self.assertEqual(view._description.text(), "Daily tasks, follow-ups, and recurring requests")

        view._governance_workspace.setCurrentText("builder-collab")
        self.assertEqual(view._governance_auth_mode.currentText(), "local_only")
        self.assertIn("query_instance", view._tool_allow.toPlainText())
        self.assertIn("execute_command", view._tool_block.toPlainText())
        self.assertIn("Builder stays local-first", view._governance_note.text())
        view._connector_workspace.setCurrentText("builder-collab")
        view._connector_id.setCurrentText("gmail")
        self.assertTrue(view._connector_enabled.isChecked())
        self.assertEqual(view._connector_account.currentData(), "sales")
        self.assertIn("compose", view._connector_action_allow.toPlainText())
        self.assertIn("cleanup", view._connector_action_block.toPlainText())
        self.assertIn("connector://gmail", view._connector_endpoint_allow.toPlainText())
        self.assertIn("Builder can draft from sales", view._connector_note.text())
        self.assertIn("matches the current machine inventory", view._connector_validation.text())
        self.assertIn("last verify", view._connector_history.text().lower())

        view.set_logs("builder-collab", [])
        self.assertIn("No recent conversation or ops activity yet for workspace builder-collab", view._logs.toPlainText())

    def test_instance_manager_view_tracks_mixed_workspace_role_summary(self):
        view = InstanceManagerView()

        view.set_instances(
            {
                "active_instance": "ops-console",
                "limits": {
                    "configured": 4,
                    "max_configured": 5,
                    "active_runtime": 2,
                    "max_active_runtime": 2,
                },
                "instances": [
                    {"name": "guppy-primary", "type": "user_instance", "status": "active", "mode": "auto", "persona": "guppy", "voice": "default", "description": "Daily work", "last_message": "Morning brief", "governance": {}, "connectors": []},
                    {"name": "builder-collab", "type": "builder_instance", "status": "idle", "mode": "code", "persona": "guppy", "voice": "default", "description": "Builder review", "last_message": "Review the next patch", "governance": {}, "connectors": []},
                    {"name": "reference-desk", "type": "read_only_instance", "status": "idle", "mode": "local", "persona": "guppy", "voice": "default", "description": "Safe reference work", "last_message": "Compare the source docs", "governance": {}, "connectors": []},
                    {"name": "ops-console", "type": "admin_instance", "status": "running", "mode": "auto", "persona": "guppy", "voice": "default", "description": "Diagnostics and recovery", "last_message": "Check runtime health", "governance": {}, "connectors": []},
                ],
                "warnings": [],
            }
        )

        self.assertIn("Daily 1 | Builder 1 | Reference 1 | Ops 1", view._role_mix_lbl.text())
        self.assertIn("Operations workspace", view._collab_lbl.text())
        self.assertIn("Diagnostics and recovery", view._collab_lbl.text())
        self.assertIn("AUTO mode", view._recurring_lbl.text())
        self.assertIn("Check runtime health", view._recurring_lbl.text())

    def test_instance_manager_view_shows_empty_workspace_onboarding_guidance(self):
        view = InstanceManagerView()

        view.set_instances(
            {
                "active_instance": "",
                "limits": {
                    "configured": 0,
                    "max_configured": 5,
                    "active_runtime": 0,
                    "max_active_runtime": 2,
                },
                "instances": [],
                "warnings": [],
            }
        )

        self.assertFalse(view._empty_state_lbl.isHidden())
        self.assertIn("Create a workspace", view._empty_state_lbl.text())
        self.assertTrue(
            any("No workspaces yet." in label.text() for label in view._cards_host.findChildren(QLabel))
        )
        self.assertIn("Pick a workspace to see its saved purpose", view._collab_lbl.text())
        self.assertIn("Pick a workspace to see its saved mode", view._recurring_lbl.text())

    def test_workspace_form_applies_role_specific_presets(self):
        view = InstanceManagerView()

        self.assertEqual(view._name.placeholderText(), "daily-desk")
        self.assertEqual(view._description.text(), "Daily tasks, follow-ups, and recurring requests")
        self.assertEqual(view._mode.currentText(), "auto")

        view._type.setCurrentText("builder_instance")
        self.assertEqual(view._name.placeholderText(), "builder-collab")
        self.assertEqual(view._description.text(), "Planning, review loops, and low-risk drafting")
        self.assertEqual(view._mode.currentText(), "code")
        self.assertIn("builder workspace defaults", view._preset_lbl.text().lower())
        self.assertIn("PLAN NEXT PASS", view._recipe_lbl.text())
        self.assertIn("release-review", view._examples_lbl.text())

        view._description.setText("Custom builder purpose")
        view._type.setCurrentText("read_only_instance")
        self.assertEqual(view._description.text(), "Custom builder purpose")
        self.assertEqual(view._mode.currentText(), "local")
        self.assertIn("SOURCE RESEARCH", view._recipe_lbl.text())
        self.assertIn("source-check", view._examples_lbl.text())

        view._type.setCurrentText("admin_instance")
        self.assertEqual(view._mode.currentText(), "auto")
        self.assertIn("OPS CHECK", view._recipe_lbl.text())
        self.assertIn("ops-console", view._examples_lbl.text())

    def test_agent_tools_view_reflects_instance_restrictions(self):
        view = ToolsView()
        view.set_instance_context(
            {"name": "builder-collab", "type": "read_only_instance"},
            {"limits": {"configured": 5, "max_configured": 5, "active_runtime": 2, "max_active_runtime": 2}},
        )

        states = view.current_tool_states()
        self.assertEqual(states["read_file"], "restricted")
        self.assertEqual(states["query_instance"], "ready")
        self.assertEqual(states["write_file"], "restricted")
        self.assertIn("WORKSPACE:", view._context_lbl.text())
        self.assertIn("Settings > Device & Accounts", view._boundary_lbl.text())
        self.assertIn("tray", view._tray_notice_lbl.text().lower())
        self.assertIn("CONFIG CAP REACHED", view._limits_lbl.text())
        self.assertIn("COLLABORATOR CAP REACHED", view._limits_lbl.text())
        self.assertEqual(view._tool_cards["read_file"]._hint_btn.text(), "PRIME HOME")
        self.assertTrue(view._tool_cards["write_file"]._scope_lbl.isHidden())
        self.assertIn("not available in builder-collab", view._tool_cards["write_file"]._scope_lbl.text().lower())
        self.assertTrue(view._tool_cards["write_file"]._guard_lbl.isHidden())
        self.assertTrue(view._tool_cards["query_instance"]._policy_lbl.isHidden())
        self.assertFalse(view._builder_panel._queue_btn.isEnabled())

        view.set_instance_context(
            {"name": "builder-collab", "type": "builder_instance"},
            {"limits": {"configured": 2, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2}},
        )
        self.assertTrue(view._builder_panel._queue_btn.isEnabled())
        self.assertIn("Automation Test", view._builder_panel._status_lbl.text())
        view._details_btn.click()
        self.assertIn("sign-in mode:", view._tool_cards["write_file"]._guard_lbl.text().lower())
        self.assertIn("sign-in:", view._tool_cards["query_instance"]._policy_lbl.text().lower())
        self.assertIn("local only", view._tool_cards["query_instance"]._policy_lbl.text().lower())

    def test_agent_tools_surface_explains_tray_move(self):
        view = ToolsView()
        self.assertFalse(view._cards_host.isHidden())
        self.assertTrue(view._empty_state_lbl.isHidden())
        self.assertTrue(view._banner.isHidden())
        view._details_btn.click()
        self.assertIn("tray", view._tray_notice_lbl.text().lower())

    def test_settings_operations_panel_updates_diagnostics_and_recovery_status(self):
        view = SettingsOperationsPanel()
        view.set_status_snapshot(
            {
                "status": "healthy",
                "startup_readiness": {"overall": "GO"},
                "voice_tts_backend": "edge",
                "voice_stt_backend": "whisper",
                "resource_envelope": {"state": "ok", "message": "headroom stable"},
            }
        )
        view.set_instance_snapshot(
            {
                "active_instance": "guppy-primary",
                "limits": {"configured": 2, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2},
            }
        )
        view.set_recovery_status("warmup: startup readiness refreshed")

        self.assertIn("API health: HEALTHY", view._health_lbl.text())
        self.assertIn("configured 2/5", view._instances_lbl.text())
        self.assertIn("tts=edge", view._voice_lbl.text())
        self.assertIn("Why the next route was chosen:", view._route_health_lbl.text())
        self.assertIn("headroom stable", view._resource_lbl.text())
        self.assertIn("warmup", view._last_recovery_lbl.text().lower())
        self.assertIn("Recent activity:", view._daily_activity_lbl.text())
        self.assertIn("ready on this pc:", view._windows_install_lbl.text().lower())
        self.assertIn("local ai health:", view._windows_runtime_lbl.text().lower())
        self.assertIn("saved data:", view._windows_paths_lbl.text().lower())
        self.assertTrue(view._connectors_frame.isHidden())
        self.assertTrue(view._workflow_frame.isHidden())
        self.assertTrue(view._operator_logs_frame.isHidden())
        self.assertTrue(view._terminal_frame.isHidden())

    def test_settings_operations_panel_exposes_guided_automation_testing_surface(self):
        view = SettingsOperationsPanel()
        view.set_automation_snapshot(
            {
                "workspace": "Workspace step: active=builder-collab | preferred=builder-collab",
                "queue_counts": "Queue counts: pending=1 | running=0 | awaiting approval=1 | done=2",
                "staged_file": "Latest staged output: runtime/offhours_results/dry_run/sample.md",
                "result_path": "Latest result: docs/generated/sample.md",
                "approval_state": "Latest approval: awaiting approval for Draft regression checklist",
                "report_path": "runtime/offhours_builder_report.json",
                "evidence_pack_path": "runtime/user_test_evidence.md",
                "stress_report_path": "tests/runtime/stress_report_20260417_022711.json",
                "recent_events": "Recent operator notes: INFO start destination applied | INFO workspace onboarding ready",
                "validation_command": launcher_window._AUTOMATION_TEST_VALIDATION_COMMAND,
                "status": "Automation test lane ready",
            }
        )

        self.assertFalse(view._automation_frame.isHidden())
        self.assertIn("builder-collab", view._automation_workspace_lbl.text())
        self.assertIn("awaiting approval=1", view._automation_queue_lbl.text())
        self.assertIn("sample.md", view._automation_staged_lbl.text())
        self.assertIn("APPROVE LATEST STAGED TASK", view._automation_action_buttons["approve_latest_staged_task"].text())
        self.assertIn("REFRESH EVIDENCE PACK", view._automation_action_buttons["open_latest_report"].text())
        self.assertIn("runtime/user_test_evidence.md", view._automation_evidence_lbl.text())
        self.assertIn("stress_report_20260417_022711.json", view._automation_stress_lbl.text())
        self.assertIn("workspace onboarding ready", view._automation_recent_lbl.text().lower())
        self.assertIn(".venv\\Scripts\\python.exe", view._automation_validation_lbl.text())
        self.assertIn("guided launcher test pass", view._automation_summary_lbl.text().lower())
        self.assertIn("guided check flow", view._automation_frame.toolTip().lower() if view._automation_frame.toolTip() else "guided check flow")

    def test_settings_operations_panel_connector_inventory_emits_normalized_actions(self):
        view = SettingsOperationsPanel()
        emitted: list[dict[str, str]] = []
        view.connector_action_requested.connect(emitted.append)
        view.set_connector_inventory(
            [
                {
                    "id": "crm",
                    "auth_kind": "api_key",
                    "auth_state": "partial",
                    "auth_detail": "HubSpot key is stored, but verify has not succeeded yet.",
                    "source": "keyring",
                    "accounts": [],
                    "providers": [
                        {
                            "id": "hubspot",
                            "label": "HubSpot",
                            "auth_state": "partial",
                            "auth_detail": "HubSpot still needs verify confirmation.",
                            "required_fields": ["CRM_API_KEY"],
                            "field_details": [
                                {
                                    "key": "CRM_API_KEY",
                                    "label": "API Key",
                                    "placeholder": "crm-api-key",
                                    "validation_hint": "Use the provider API key value.",
                                    "masked": True,
                                    "present": False,
                                    "missing": True,
                                    "step": 1,
                                    "total_steps": 1,
                                }
                            ],
                            "setup_summary": "Step 1/1: add API Key.",
                            "next_field": {
                                "key": "CRM_API_KEY",
                                "label": "API Key",
                                "placeholder": "crm-api-key",
                                "validation_hint": "Use the provider API key value.",
                                "masked": True,
                                "step": 1,
                                "total_steps": 1,
                            },
                            "scope_label": "contacts + opportunities",
                        }
                    ],
                    "actions_supported": ["verify", "connect", "disconnect"],
                    "secret_fields": ["CRM_API_KEY"],
                    "scope_telemetry": {
                        "summary": "CRM bindings can pin a provider and narrow contact/opportunity actions.",
                        "endpoint_prefixes": ["connector://crm/hubspot", "connector://crm/hubspot/contacts"],
                    },
                    "history": {
                        "last_action": "verify",
                        "last_action_at": "2026-04-15T12:00:00+00:00",
                        "last_result": "CRM verify: partial",
                        "last_event_id": "crm-verify-12345",
                    },
                }
            ]
        )

        self.assertEqual(view._connector_cb.currentData(), "crm")
        self.assertIn("customer records", view._connector_state_lbl.text().lower())
        self.assertIn("Almost ready", view._connector_auth_lbl.text())
        self.assertIn("API Key", view._connector_secret_lbl.text())
        self.assertIn("HubSpot still needs verify confirmation", view._connector_validation_lbl.text())
        self.assertIn("contacts + opportunities", view._connector_scope_lbl.text())
        self.assertIn("last verify", view._connector_history_lbl.text().lower())
        self.assertIn("Recent attempts:", view._connector_recent_lbl.text())
        self.assertIn("Ref:", view._connector_history_lbl.text())
        self.assertIn("Saved details:", view._connector_setup_lbl.text())

        view._connector_provider.setCurrentIndex(1)
        view._connector_secret_key.setCurrentIndex(1)
        view._connector_secret_value.setText("test-secret")
        view._emit_connector_action("save_secret")
        view._emit_connector_action("clear_secret")

        self.assertEqual(emitted[0]["connector"], "crm")
        self.assertEqual(emitted[0]["action"], "connect")
        self.assertEqual(emitted[0]["provider"], "hubspot")
        self.assertEqual(emitted[0]["secret_key"], "CRM_API_KEY")
        self.assertEqual(emitted[0]["secret_value"], "test-secret")
        self.assertEqual(emitted[1]["action"], "disconnect")

    def test_settings_operations_panel_compact_mode_shortens_secondary_actions_and_keeps_tooltips(self):
        view = SettingsOperationsPanel()
        view._apply_density_mode(940)

        self.assertEqual(view._details_btn.text(), "DETAILS")
        self.assertEqual(view._automation_action_buttons["approve_latest_staged_task"].text(), "APPROVE")
        self.assertEqual(view._automation_action_buttons["open_latest_report"].text(), "REFRESH")
        self.assertEqual(view._workflow_load_btn.text(), "LOAD")
        self.assertIn("runtime audit", view._quick_fix_buttons["audit_runtime"].toolTip().lower())
        self.assertIn("embedded terminal", view._workflow_load_btn.toolTip().lower())

    def test_settings_operations_panel_connector_blocks_secret_save_without_value(self):
        view = SettingsOperationsPanel()
        emitted: list[dict[str, str]] = []
        view.connector_action_requested.connect(emitted.append)
        view.set_connector_inventory(
            [
                {
                    "id": "crm",
                    "auth_kind": "provider_secret",
                    "auth_state": "missing",
                    "auth_detail": "Salesforce still needs provider secrets.",
                    "source": "none",
                    "providers": [
                        {
                            "id": "salesforce",
                            "label": "Salesforce",
                            "auth_state": "missing",
                            "auth_detail": "Salesforce still needs access token and org URL.",
                            "required_fields": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
                            "field_details": [
                                {
                                    "key": "SALESFORCE_ACCESS_TOKEN",
                                    "label": "Access Token",
                                    "placeholder": "00D...!....",
                                    "validation_hint": "Use the access token string, not a URL.",
                                    "masked": True,
                                    "present": False,
                                    "missing": True,
                                    "step": 1,
                                    "total_steps": 2,
                                }
                            ],
                            "setup_summary": "Step 1/2: add Access Token.",
                            "next_field": {
                                "key": "SALESFORCE_ACCESS_TOKEN",
                                "label": "Access Token",
                                "validation_hint": "Use the access token string, not a URL.",
                            },
                            "next_step": "App Mgmt: save Access Token for Salesforce, then run Verify.",
                            "fix_target": "App Mgmt > Connector Inventory",
                        }
                    ],
                    "accounts": [],
                    "actions_supported": ["verify", "connect", "disconnect"],
                    "secret_fields": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
                    "next_step": "App Mgmt: save Access Token for Salesforce, then run Verify.",
                    "fix_target": "App Mgmt > Connector Inventory",
                    "history": {"timeline": [], "recent_events": []},
                }
            ]
        )

        view._connector_provider.setCurrentIndex(1)
        view._connector_secret_key.setCurrentIndex(1)
        view._emit_connector_action("save_secret")

        self.assertFalse(emitted)
        self.assertIn("blocked", view._syslog.toPlainText().lower())

    def test_voices_view_surfaces_persistent_readiness_evidence(self):
        view = VoicesView()

        self.assertIn("Ready now:", view._voice_evidence_lbl.text())
        self.assertIn("Default runtime voice stays", view._voice_evidence_lbl.text())

    def test_settings_operations_panel_focus_operator_logs_updates_filter(self):
        view = SettingsOperationsPanel()
        view.focus_operator_logs("WARN", note="opened from quick action")

        self.assertEqual(view._filter_cb.currentText(), "WARN")
        self.assertIn("opened from quick action", view._syslog.toPlainText())
        self.assertFalse(view._operator_logs_frame.isHidden())

    def test_runtime_view_default_route_preview_teaches_next_step(self):
        view = RuntimeRoutingView()

        self.assertIn("Try the kind of question", view._route_preview_lbl.text())

    def test_runtime_view_persists_local_runtime_preferences(self):
        old_settings_path = runtime_profile.SETTINGS_PATH
        old_runtime_dir = runtime_profile.RUNTIME_DIR
        old_backend_flag = models_view_module._RUNTIME_SETTINGS_BACKEND
        old_refresh = models_view_module.ModelsView._refresh

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            runtime_profile.RUNTIME_DIR = runtime_dir
            runtime_profile.SETTINGS_PATH = runtime_dir / "app_settings.json"
            models_view_module._RUNTIME_SETTINGS_BACKEND = True
            models_view_module.ModelsView._refresh = lambda self: None

            try:
                first = RuntimeRoutingView()
                first._runtime_backend_cb.setCurrentText("LEMONADE")
                first._lemonade_base_url_input.setText("http://localhost:13305/api/v1")
                first._lemonade_role_inputs["lemonade_fast_model"].setCurrentText("Llama-3.2-1B-Instruct-GGUF")
                first._lemonade_role_inputs["lemonade_complex_model"].setCurrentText("Llama-3.2-3B-Instruct-GGUF")
                first._save_runtime_settings()

                second = RuntimeRoutingView()
                self.assertEqual(second._runtime_backend_cb.currentText(), "LEMONADE")
                self.assertEqual(second._lemonade_role_inputs["lemonade_fast_model"].currentText(), "Llama-3.2-1B-Instruct-GGUF")
                self.assertEqual(second._lemonade_role_inputs["lemonade_complex_model"].currentText(), "Llama-3.2-3B-Instruct-GGUF")
                self.assertEqual(runtime_profile.load_app_settings().get("local_runtime_backend"), "lemonade")
            finally:
                models_view_module.ModelsView._refresh = old_refresh
                models_view_module._RUNTIME_SETTINGS_BACKEND = old_backend_flag
                runtime_profile.SETTINGS_PATH = old_settings_path
                runtime_profile.RUNTIME_DIR = old_runtime_dir

    def test_runtime_view_lemonade_picker_assigns_downloaded_model_to_selected_role(self):
        old_refresh = models_view_module.ModelsView._refresh
        models_view_module.ModelsView._refresh = lambda self: None
        try:
            view = RuntimeRoutingView()
            view._runtime_backend_cb.setCurrentText("LEMONADE")
            view._on_local_result(
                {
                    "backend": "lemonade",
                    "models": [
                        {"name": "DeepSeek-Qwen3-8B-GGUF", "display": "DeepSeek Qwen3 8B GGUF", "context": "GGUF / OpenAI API", "note": "Downloaded in Lemonade"},
                        {"name": "kokoro-v1", "display": "kokoro-v1", "context": "GGUF / OpenAI API", "note": "Downloaded in Lemonade"},
                    ],
                    "error": "",
                }
            )
            self.assertFalse(view._runtime_library_frame.isHidden())
            self.assertIn("Downloaded models: 2", view._runtime_library_summary_lbl.text())
            view._set_selected_runtime_role("lemonade_complex_model")
            matching = [btn for btn in view._runtime_library_buttons if btn.text() == "DeepSeek-Qwen3-8B-GGUF"]
            self.assertTrue(matching)
            matching[0].click()

            self.assertEqual(
                view._lemonade_role_inputs["lemonade_complex_model"].currentText(),
                "DeepSeek-Qwen3-8B-GGUF",
            )
            self.assertIn("Assigning to HEAVY SLOT", view._runtime_library_target_lbl.text())
        finally:
            models_view_module.ModelsView._refresh = old_refresh

    def test_runtime_view_surfaces_live_runtime_evidence_from_status(self):
        old_refresh = models_view_module.ModelsView._refresh
        models_view_module.ModelsView._refresh = lambda self: None
        try:
            view = RuntimeRoutingView()
            view.set_status_snapshot(
                {
                    "status": "healthy",
                    "local_runtime": {
                        "backend": "lemonade",
                        "state": "PARTIAL",
                        "detail": "Lemonade is reachable, but the default local model alias is not mapped yet.",
                        "requested_model": "guppy",
                        "resolved_model": "guppy-fast",
                        "base_url": "http://localhost:13305/api/v1",
                        "tool_loop": "limited",
                        "available_roles": ["fast", "code"],
                        "missing_roles": ["complex", "teaching", "vault"],
                        "policy": {
                            "runtime_baseline": "ollama",
                            "memory_baseline": "semantic-sqlite",
                            "daily_model_promotion_candidate": "qwen3:8b",
                            "heavy_model_candidate": "mistral-small3.1:24b",
                            "daily_lane_rejected_models": ["qwen3:30b", "qwen2.5:32b"],
                            "runtime_challenger_ids": ["llama.cpp", "lemonade"],
                        },
                    },
                }
            )

            self.assertIn("LIVE LANE: PARTIAL", view._runtime_live_lbl.text())
            self.assertIn("server runtime LEMONADE", view._runtime_live_lbl.text())
            self.assertIn("Missing mapped roles: HEAVY SLOT, TEACHING SLOT, RESEARCH SLOT", view._runtime_live_lbl.text())
            self.assertIn("Available mapped roles: DAILY SLOT, CODING SLOT", view._runtime_live_lbl.text())
            self.assertIn("runtime baseline OLLAMA", view._runtime_policy_lbl.text())
            self.assertIn("daily lane candidate qwen3:8b", view._runtime_policy_lbl.text())
            self.assertIn("qwen3:30b, qwen2.5:32b", view._runtime_policy_lbl.text())
        finally:
            models_view_module.ModelsView._refresh = old_refresh

    def test_settings_operations_panel_windows_ops_feedback_surfaces_fix_guidance(self):
        view = SettingsOperationsPanel()
        view.set_windows_ops_feedback(
            "update_runtime",
            "WINDOWS UPDATE completed | Ref: recipe-1",
            "Refreshes runtime dependencies.",
            ok=True,
            next_step="Package a new desktop build after update verification.",
            fix_target="bin\\build_executable.bat",
            docs_hint="docs/PACKAGING.md",
            entry_point="bin\\build_executable.bat --no-clean",
            artifacts=[
                {"id": "diagnostics", "label": "diagnostics bundle", "path": "runtime/diagnostics_bundle_20260415_120000.json"},
                {"id": "challenger", "label": "challenger snapshot", "path": "runtime/runtime_challenger_snapshot.json"},
            ],
            receipt_path="runtime/windows_release_receipt.json",
            summary_path="runtime/windows_release_summary.md",
            gate_summary="PASS | checks 2/2 | required files OK",
            gate_detail="all dry-run checks passed and required handoff files are present",
            gate_recommendations=["Release gate is green; review the dry-run report, receipt, and summary in that order, then package or hand off the bundle."],
            gate_recommendation_details=[
                {
                    "text": "Release gate is green; review the dry-run report, receipt, and summary in that order, then package or hand off the bundle.",
                    "fix_target": "runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md",
                    "docs_hint": "docs/PACKAGING.md",
                    "entry_point": "python tools/beta_release_dry_run.py",
                }
            ],
        )

        self.assertIn("bin\\build_executable.bat", view._windows_next_lbl.text())
        self.assertIn("docs/PACKAGING.md", view._windows_next_lbl.text())
        self.assertIn("Ref: recipe-1", view._windows_service_lbl.text())
        self.assertIn("PASS | checks 2/2", view._windows_gate_lbl.text())
        self.assertTrue(view._windows_gate_fix_lbl.text().startswith("Review next:"))
        self.assertIn("Release gate is green", view._windows_gate_fix_lbl.text())
        self.assertIn("Review: runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md", view._windows_gate_fix_lbl.text())
        self.assertIn("Doc: docs/PACKAGING.md", view._windows_gate_fix_lbl.text())
        self.assertNotIn("review order=", view._windows_handoff_lbl.text())
        self.assertIn("receipt=runtime/windows_release_receipt.json", view._windows_handoff_lbl.text())
        self.assertIn("summary=runtime/windows_release_summary.md", view._windows_handoff_lbl.text())
        self.assertIn("diagnostics bundle=runtime/diagnostics_bundle_20260415_120000.json", view._windows_handoff_lbl.text())

    def test_settings_operations_panel_terminal_accepts_focus_and_output_append(self):
        view = SettingsOperationsPanel()
        view.focus_terminal("terminal opened")

        self.assertIn("terminal opened", view._terminal_output.toPlainText())

    def test_settings_operations_panel_workflow_recipe_loads_terminal_command(self):
        view = SettingsOperationsPanel()
        view._workflow_cb.setCurrentText("MIDDAY STABILITY")
        view._load_workflow_recipe()

        self.assertEqual(
            view._terminal_input.text(),
            "python tools/verify_logging_health.py --emit-probe --require-fresh-core",
        )
        self.assertIn("MIDDAY STABILITY", view._workflow_status_lbl.text())
        self.assertIn("Next step:", view._workflow_next_step_lbl.text())
        self.assertIn("Outcome: Loaded the first command", view._workflow_outcome_lbl.text())
        self.assertIn("Evidence:", view._workflow_evidence_lbl.text())
        self.assertIn("python tools/verify_ollama_runtime.py --prompt ok", view._terminal_output.toPlainText())

    def test_launcher_windows_ops_recipe_exposes_verify_and_update_commands(self):
        verify_label, verify_commands = launcher_window.LauncherWindow._windows_ops_recipe("verify_runtime")
        update_label, update_commands = launcher_window.LauncherWindow._windows_ops_recipe("update_runtime")
        package_label, package_commands = launcher_window.LauncherWindow._windows_ops_recipe("package_desktop")
        dry_run_label, dry_run_commands = launcher_window.LauncherWindow._windows_ops_recipe("release_dry_run")

        self.assertEqual(verify_label, "WINDOWS VERIFY")
        self.assertTrue(any("verify_ollama_runtime.py --prompt ok" in cmd for cmd in verify_commands))
        self.assertEqual(update_label, "WINDOWS UPDATE")
        self.assertTrue(any("pip install -r requirements.txt" in cmd for cmd in update_commands))
        self.assertTrue(any("validate_build_checks.py" in cmd for cmd in update_commands))
        self.assertTrue(any("verify_runtime_challengers.py" in cmd for cmd in update_commands))
        self.assertEqual(package_label, "WINDOWS PACKAGE")
        self.assertTrue(any("bin\\build_executable.bat --no-clean --ci" in cmd for cmd in package_commands))
        self.assertTrue(any("verify_beta_package_policy.py" in cmd for cmd in package_commands))
        self.assertEqual(dry_run_label, "WINDOWS RELEASE DRY RUN")
        self.assertTrue(any("tools/beta_release_dry_run.py" in cmd for cmd in dry_run_commands))

    def test_launcher_windows_service_snapshot_changes_report_artifact_refresh(self):
        before = {
            "pip_version": "pip 24.0 from before",
            "python_version": "Python 3.12.0",
            "challenger_snapshot": {"path": "runtime/runtime_challenger_snapshot.json", "exists": True, "mtime": "2026-04-15T10:00:00+00:00", "size": 100},
            "diagnostics_bundle": {"path": "runtime/diagnostics_1.json", "exists": True, "mtime": "2026-04-15T10:00:00+00:00", "size": 100},
            "pilot_exit_report": {"path": "runtime/pilot_exit_report.json", "exists": True, "mtime": "2026-04-15T10:00:00+00:00", "size": 100},
        }
        after = {
            "pip_version": "pip 25.0 from after",
            "python_version": "Python 3.12.0",
            "challenger_snapshot": {"path": "runtime/runtime_challenger_snapshot.json", "exists": True, "mtime": "2026-04-15T11:00:00+00:00", "size": 120},
            "diagnostics_bundle": {"path": "runtime/diagnostics_2.json", "exists": True, "mtime": "2026-04-15T11:00:00+00:00", "size": 140},
            "pilot_exit_report": {"path": "runtime/pilot_exit_report.json", "exists": True, "mtime": "2026-04-15T10:00:00+00:00", "size": 100},
        }

        summary = launcher_window.LauncherWindow._windows_service_snapshot_changes(before, after)

        self.assertIn("pip changed", summary)
        self.assertIn("challenger snapshot refreshed", summary)
        self.assertIn("diagnostics bundle refreshed", summary)

    def test_launcher_windows_ops_artifact_refs_include_release_dry_run_report(self):
        snapshot = {
            "beta_release_dry_run_report": {"path": "runtime/beta_release_dry_run_report.json", "exists": True, "mtime": "2026-04-15T12:00:00+00:00", "size": 100},
            "pilot_exit_report": {"path": "runtime/pilot_exit_report.json", "exists": True, "mtime": "2026-04-15T12:01:00+00:00", "size": 200},
            "beta_policy_report": {"path": "runtime/beta_policy_report.json", "exists": True, "mtime": "2026-04-15T12:02:00+00:00", "size": 300},
        }

        artifacts = launcher_window.LauncherWindow._windows_ops_artifact_refs("release_dry_run", snapshot)

        self.assertEqual([item["id"] for item in artifacts], ["release_dry_run", "pilot_exit", "beta_policy"])

    def test_launcher_summarize_release_dry_run_report_surfaces_failed_checks_and_missing_files(self):
        report = {
            "ok": False,
            "checks": [
                {"name": "beta_policy", "ok": True},
                {"name": "pilot_gate", "ok": False},
            ],
            "required_files": [
                {"path": "docs/REMOTE_BETA_EXE_POLICY.md", "exists": True},
                {"path": "docs/archive/planning-history/FINAL_HANDOFF_PREP.md", "exists": False},
            ],
        }

        summary = launcher_window.LauncherWindow._summarize_release_dry_run_report(report)

        self.assertFalse(summary["ok"])
        self.assertIn("FAIL", summary["summary"])
        self.assertIn("pilot_gate", summary["detail"])
        self.assertIn("FINAL_HANDOFF_PREP.md", summary["detail"])
        self.assertEqual(summary["passed_checks"], 1)
        self.assertEqual(summary["total_checks"], 2)
        self.assertEqual(summary["checks"][1]["name"], "pilot_gate")
        self.assertFalse(summary["required_files"][1]["exists"])
        self.assertTrue(summary["recommendations"])
        self.assertIn("pilot gate", summary["recommendations"][0].lower())
        self.assertEqual(summary["recommendation_details"][0]["fix_target"], "tools/pilot_exit_check.py / runtime/pilot_exit_report.json")
        self.assertEqual(summary["recommendation_details"][0]["docs_hint"], "docs/PACKAGING.md")

    def test_launcher_windows_ops_guidance_points_update_failures_at_packaging_fix_path(self):
        guidance = launcher_window.LauncherWindow._windows_ops_guidance("update_runtime", ok=False, phase="completed")

        self.assertIn("requirements.txt", guidance["fix_target"])
        self.assertEqual(guidance["docs_hint"], "docs/PACKAGING.md")
        self.assertIn("bin\\build_executable.bat", guidance["entry_point"])

    def test_launcher_windows_ops_guidance_points_release_dry_run_at_gate_fix_path(self):
        guidance = launcher_window.LauncherWindow._windows_ops_guidance("release_dry_run", ok=False, phase="completed")

        self.assertIn("beta_release_dry_run.py", guidance["fix_target"])
        self.assertEqual(guidance["docs_hint"], "docs/PACKAGING.md")
        self.assertIn("beta_release_dry_run.py", guidance["entry_point"])

    def test_launcher_windows_ops_guidance_points_supervised_api_to_supervision_doc(self):
        guidance = launcher_window.LauncherWindow._windows_ops_guidance("start_supervised_api", ok=False, phase="completed")

        self.assertIn("launch_api_supervised.bat", guidance["fix_target"])
        self.assertEqual(guidance["docs_hint"], "docs/SUPERVISION_WINDOWS.md")
        self.assertIn("launch_api_supervised.bat", guidance["entry_point"])

    def test_launcher_start_supervised_api_action_records_completion(self):
        class _AdvancedStub:
            def __init__(self) -> None:
                self.logs: list[str] = []
                self.feedback: list[dict[str, object]] = []

            def append_log(self, text: str) -> None:
                self.logs.append(text)

            def set_windows_ops_feedback(self, action: str, summary: str, changes: str, ok: bool = True, **kwargs) -> None:
                self.feedback.append({"action": action, "summary": summary, "changes": changes, "ok": ok, **kwargs})

        class _LauncherStub:
            def __init__(self, runtime_dir: Path) -> None:
                self._status_panel = _DummyStatusPanel()
                self._settings_hub_view = _AdvancedStub()
                self._daily: list[str] = []
                self.logged: list[tuple[str, dict[str, object]]] = []
                self._runtime_dir = runtime_dir

            def _windows_ops_state_path(self) -> Path:
                return self._runtime_dir / "windows_ops_state.json"

            def _windows_release_receipt_path(self) -> Path:
                return self._runtime_dir / "windows_release_receipt.json"

            def _windows_release_summary_path(self) -> Path:
                return self._runtime_dir / "windows_release_summary.md"

            def _set_daily_activity(self, text: str) -> None:
                self._daily.append(text)

            def _log_launcher_event(self, event: str, **fields: object) -> None:
                self.logged.append((event, fields))

            def _refresh_api_auth_state(self, _reason: str) -> str:
                return "ready"

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            stub = _LauncherStub(runtime_dir)
            stub._windows_ops_plan = launcher_window.LauncherWindow._windows_ops_plan
            stub._windows_ops_guidance = launcher_window.LauncherWindow._windows_ops_guidance
            stub._windows_ops_artifact_refs = staticmethod(lambda action, snapshot: [{"id": "diagnostics", "label": "diagnostics bundle", "path": "runtime/diagnostics_bundle_20260415_120000.json"}])
            stub._collect_windows_service_snapshot = staticmethod(lambda: {"diagnostics_bundle": {"exists": True, "path": "runtime/diagnostics_bundle_20260415_120000.json", "mtime": "2026-04-15T12:00:00+00:00", "size": 10}})
            stub._write_windows_release_summary = launcher_window.LauncherWindow._write_windows_release_summary
            stub._write_windows_release_receipt = launcher_window.LauncherWindow._write_windows_release_receipt.__get__(stub, _LauncherStub)
            stub._record_windows_ops_state = launcher_window.LauncherWindow._record_windows_ops_state.__get__(stub, _LauncherStub)
            stub._start_supervised_api_subprocess = lambda: (True, "supervised api started and reachable")
            stub._on_windows_ops_requested = launcher_window.LauncherWindow._on_windows_ops_requested.__get__(stub, _LauncherStub)

            stub._on_windows_ops_requested("start_supervised_api")

            payload = __import__("json").loads((runtime_dir / "windows_ops_state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "start_supervised_api")
            self.assertEqual(payload["phase"], "completed")
            self.assertTrue(payload["ok"])
            self.assertIn("launch_api_supervised.bat", payload["entry_point"])
            self.assertEqual(payload["artifacts"][0]["id"], "diagnostics")
            self.assertTrue(payload["release_receipt"].endswith("windows_release_receipt.json"))
            self.assertTrue(payload["release_summary"].endswith("windows_release_summary.md"))
            receipt = __import__("json").loads((runtime_dir / "windows_release_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["action"], "start_supervised_api")
            self.assertEqual(receipt["artifacts"][0]["id"], "diagnostics")
            summary_text = (runtime_dir / "windows_release_summary.md").read_text(encoding="utf-8")
            self.assertIn("# Windows Release Summary", summary_text)
            self.assertIn("- Ref:", summary_text)
            self.assertIn("start_supervised_api", summary_text)
            self.assertTrue(any(event == "windows_ops_completed" for event, _fields in stub.logged))

    def test_settings_operations_panel_terminal_recipe_markers_emit_servicing_payload(self):
        view = SettingsOperationsPanel()
        emitted: list[dict[str, object]] = []
        view.terminal_recipe_finished.connect(emitted.append)

        recipe_id, _wrapped = view._build_tracked_recipe_commands(
            ["python tools/verify_ollama_runtime.py --prompt ok", "python tools/verify_runtime_challengers.py"],
            label="WINDOWS VERIFY",
            recipe_context={"kind": "windows_ops", "action": "verify_runtime", "changes": "Refreshes readiness evidence."},
        )

        self.assertTrue(view._handle_terminal_recipe_marker(f"__GUPPY_RECIPE__|start|{recipe_id}|2|WINDOWS VERIFY"))
        self.assertTrue(view._handle_terminal_recipe_marker(f"__GUPPY_RECIPE__|step|{recipe_id}|1|0"))
        self.assertTrue(view._handle_terminal_recipe_marker(f"__GUPPY_RECIPE__|step|{recipe_id}|2|1"))
        self.assertTrue(view._handle_terminal_recipe_marker(f"__GUPPY_RECIPE__|end|{recipe_id}|1"))

        self.assertTrue(emitted)
        payload = emitted[-1]
        self.assertEqual(payload["action"], "verify_runtime")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["steps_total"], 2)
        self.assertEqual(payload["steps_completed"], 2)
        self.assertTrue(payload["failed_steps"])

    def test_launcher_windows_ops_completion_persists_structured_state(self):
        class _AdvancedStub:
            def __init__(self) -> None:
                self.feedback: list[tuple[str, str, str, bool]] = []
                self.logs: list[str] = []

            def set_windows_ops_feedback(
                self,
                action: str,
                summary: str,
                changes: str,
                ok: bool = True,
                **_kwargs,
            ) -> None:
                self.feedback.append((action, summary, changes, ok))

            def append_log(self, text: str) -> None:
                self.logs.append(text)

        class _LauncherStub:
            def __init__(self, runtime_dir: Path) -> None:
                self._status_panel = _DummyStatusPanel()
                self._settings_hub_view = _AdvancedStub()
                self._daily: list[str] = []
                self.logged: list[tuple[str, dict[str, object]]] = []
                self._runtime_dir = runtime_dir

            def _windows_ops_state_path(self) -> Path:
                return self._runtime_dir / "windows_ops_state.json"

            def _windows_release_receipt_path(self) -> Path:
                return self._runtime_dir / "windows_release_receipt.json"

            def _windows_release_summary_path(self) -> Path:
                return self._runtime_dir / "windows_release_summary.md"

            def _set_daily_activity(self, text: str) -> None:
                self._daily.append(text)

            def _log_launcher_event(self, event: str, **fields: object) -> None:
                self.logged.append((event, fields))

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            stub = _LauncherStub(runtime_dir)
            stub._summarize_windows_recipe_result = launcher_window.LauncherWindow._summarize_windows_recipe_result
            stub._collect_windows_service_snapshot = staticmethod(lambda: {"pip_version": "after"})
            stub._windows_service_snapshot_changes = staticmethod(lambda before, after: "pip changed during servicing")
            stub._windows_ops_artifact_refs = staticmethod(
                lambda action, snapshot: [
                    {"id": "diagnostics", "label": "diagnostics bundle", "path": "runtime/diagnostics_bundle_20260415_120000.json"},
                    {"id": "challenger", "label": "challenger snapshot", "path": "runtime/runtime_challenger_snapshot.json"},
                ]
            )
            stub._windows_ops_guidance = staticmethod(
                lambda action, ok, phase="completed": {
                    "next_step": f"{action} guidance {phase} {'ok' if ok else 'fail'}",
                    "fix_target": "App Mgmt > Windows Ops",
                    "docs_hint": "docs/TROUBLESHOOTING.md",
                    "entry_point": "python src/guppy/cli/launch.py launcher",
                }
            )
            stub._write_windows_release_summary = launcher_window.LauncherWindow._write_windows_release_summary
            stub._write_windows_release_receipt = launcher_window.LauncherWindow._write_windows_release_receipt.__get__(stub, _LauncherStub)
            stub._record_windows_ops_state = launcher_window.LauncherWindow._record_windows_ops_state.__get__(stub, _LauncherStub)
            stub._on_terminal_recipe_finished = launcher_window.LauncherWindow._on_terminal_recipe_finished.__get__(stub, _LauncherStub)

            stub._on_terminal_recipe_finished(
                {
                    "kind": "windows_ops",
                    "action": "verify_runtime",
                    "label": "WINDOWS VERIFY",
                    "ok": True,
                    "id": "recipe-abc123",
                    "commands": ["python tools/verify_ollama_runtime.py --prompt ok"],
                    "steps_completed": 1,
                    "steps_total": 1,
                    "failed_steps": [],
                    "changes": "Refreshes readiness evidence.",
                    "pre_snapshot": {"pip_version": "before"},
                }
            )

            payload = __import__("json").loads((runtime_dir / "windows_ops_state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "verify_runtime")
            self.assertEqual(payload["event_id"], "recipe-abc123")
            self.assertEqual(payload["steps_completed"], 1)
            self.assertNotIn("review_order", payload)
            self.assertEqual(payload["steps_total"], 1)
            self.assertEqual(payload["phase"], "completed")
            self.assertIn("pip changed during servicing", payload["changes"])
            self.assertEqual([item["id"] for item in payload["artifacts"]], ["diagnostics", "challenger"])
            self.assertTrue(payload["release_receipt"].endswith("windows_release_receipt.json"))
            self.assertTrue(payload["release_summary"].endswith("windows_release_summary.md"))
            receipt = __import__("json").loads((runtime_dir / "windows_release_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["action"], "verify_runtime")
            self.assertEqual(receipt["operator_guidance"]["docs_hint"], "docs/TROUBLESHOOTING.md")
            summary_text = (runtime_dir / "windows_release_summary.md").read_text(encoding="utf-8")
            self.assertIn("WINDOWS VERIFY completed", summary_text)
            self.assertIn("- Ref: recipe-abc123", summary_text)
            self.assertTrue(payload["next_step"])
            self.assertTrue(payload["fix_target"])
            self.assertTrue(any(event == "windows_ops_completed" for event, _fields in stub.logged))

    def test_launcher_release_dry_run_completion_persists_gate_summary(self):
        class _AdvancedStub:
            def __init__(self) -> None:
                self.feedback: list[dict[str, object]] = []
                self.logs: list[str] = []

            def set_windows_ops_feedback(self, action: str, summary: str, changes: str, ok: bool = True, **kwargs) -> None:
                self.feedback.append({"action": action, "summary": summary, "changes": changes, "ok": ok, **kwargs})

            def append_log(self, text: str) -> None:
                self.logs.append(text)

        class _LauncherStub:
            def __init__(self, runtime_dir: Path) -> None:
                self._status_panel = _DummyStatusPanel()
                self._settings_hub_view = _AdvancedStub()
                self._daily: list[str] = []
                self.logged: list[tuple[str, dict[str, object]]] = []
                self._runtime_dir = runtime_dir

            def _windows_ops_state_path(self) -> Path:
                return self._runtime_dir / "windows_ops_state.json"

            def _windows_release_receipt_path(self) -> Path:
                return self._runtime_dir / "windows_release_receipt.json"

            def _windows_release_summary_path(self) -> Path:
                return self._runtime_dir / "windows_release_summary.md"

            def _set_daily_activity(self, text: str) -> None:
                self._daily.append(text)

            def _log_launcher_event(self, event: str, **fields: object) -> None:
                self.logged.append((event, fields))

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            stub = _LauncherStub(runtime_dir)
            stub._summarize_windows_recipe_result = launcher_window.LauncherWindow._summarize_windows_recipe_result
            stub._collect_windows_service_snapshot = staticmethod(lambda: {"beta_release_dry_run_report": {"exists": True, "path": "runtime/beta_release_dry_run_report.json", "mtime": "2026-04-15T12:00:00+00:00", "size": 321}})
            stub._windows_service_snapshot_changes = staticmethod(lambda before, after: "beta release dry-run report refreshed")
            stub._windows_ops_artifact_refs = staticmethod(
                lambda action, snapshot: [
                    {"id": "release_dry_run", "label": "release dry-run report", "path": "runtime/beta_release_dry_run_report.json"},
                    {"id": "pilot_exit", "label": "pilot exit report", "path": "runtime/pilot_exit_report.json"},
                ]
            )
            stub._release_dry_run_gate_details = staticmethod(
                lambda: {
                    "summary": "FAIL | checks 1/2 | missing files 1",
                    "detail": "failed checks: pilot_gate | missing: FINAL_HANDOFF_PREP.md",
                    "passed_checks": 1,
                    "total_checks": 2,
                    "failed_checks": ["pilot_gate"],
                    "missing_files": ["docs/archive/planning-history/FINAL_HANDOFF_PREP.md"],
                    "recommendations": [
                        "Fix the pilot gate next by reviewing pilot_exit_check failures and rerunning the release dry-run.",
                        "Restore the required handoff file FINAL_HANDOFF_PREP.md before the next release dry-run.",
                    ],
                    "recommendation_details": [
                        {
                            "text": "Fix the pilot gate next by reviewing pilot_exit_check failures and rerunning the release dry-run.",
                            "fix_target": "tools/pilot_exit_check.py / runtime/pilot_exit_report.json",
                            "docs_hint": "docs/PACKAGING.md",
                            "entry_point": "python tools/pilot_exit_check.py --allow-limited-go",
                        },
                        {
                            "text": "Restore the required handoff file FINAL_HANDOFF_PREP.md before the next release dry-run.",
                            "fix_target": "docs/archive/planning-history/FINAL_HANDOFF_PREP.md",
                            "docs_hint": "docs/PACKAGING.md",
                            "entry_point": "docs/archive/planning-history/FINAL_HANDOFF_PREP.md",
                        },
                    ],
                    "checks": [
                        {"name": "beta_policy", "ok": True, "returncode": 0},
                        {"name": "pilot_gate", "ok": False, "returncode": 1},
                    ],
                    "required_files": [
                        {"path": "docs/REMOTE_BETA_EXE_POLICY.md", "exists": True},
                        {"path": "docs/archive/planning-history/FINAL_HANDOFF_PREP.md", "exists": False},
                    ],
                }
            )
            stub._windows_ops_guidance = staticmethod(
                lambda action, ok, phase="completed": {
                    "next_step": f"{action} guidance {phase} {'ok' if ok else 'fail'}",
                    "fix_target": "tools/beta_release_dry_run.py",
                    "docs_hint": "docs/PACKAGING.md",
                    "entry_point": "python tools/beta_release_dry_run.py",
                }
            )
            stub._write_windows_release_summary = launcher_window.LauncherWindow._write_windows_release_summary
            stub._write_windows_release_receipt = launcher_window.LauncherWindow._write_windows_release_receipt.__get__(stub, _LauncherStub)
            stub._record_windows_ops_state = launcher_window.LauncherWindow._record_windows_ops_state.__get__(stub, _LauncherStub)
            stub._on_terminal_recipe_finished = launcher_window.LauncherWindow._on_terminal_recipe_finished.__get__(stub, _LauncherStub)

            stub._on_terminal_recipe_finished(
                {
                    "kind": "windows_ops",
                    "action": "release_dry_run",
                    "label": "WINDOWS RELEASE DRY RUN",
                    "ok": False,
                    "id": "recipe-release-1",
                    "commands": ["python tools/beta_release_dry_run.py"],
                    "steps_completed": 1,
                    "steps_total": 1,
                    "failed_steps": [{"index": 1, "command": "python tools/beta_release_dry_run.py"}],
                    "changes": "Runs the beta release dry-run gate.",
                    "pre_snapshot": {},
                }
            )

            payload = __import__("json").loads((runtime_dir / "windows_ops_state.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "release_dry_run")
            self.assertIn("FAIL | checks 1/2", payload["gate_summary"])
            self.assertIn("pilot_gate", payload["gate_detail"])
            self.assertEqual(payload["gate_failed_checks"], ["pilot_gate"])
            self.assertTrue(any("FINAL_HANDOFF_PREP.md" in item for item in payload["gate_missing_files"]))
            self.assertTrue(any("pilot gate" in item.lower() for item in payload["gate_recommendations"]))
            self.assertEqual(payload["gate_recommendation_details"][0]["fix_target"], "tools/pilot_exit_check.py / runtime/pilot_exit_report.json")
            self.assertTrue(payload["release_summary"].endswith("windows_release_summary.md"))
            receipt = __import__("json").loads((runtime_dir / "windows_release_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["release_gate"]["summary"], "FAIL | checks 1/2 | missing files 1")
            self.assertEqual(receipt["release_gate"]["failed_checks"], ["pilot_gate"])
            self.assertEqual(receipt["release_gate"]["passed_checks"], 1)
            self.assertEqual(receipt["release_gate"]["total_checks"], 2)
            self.assertEqual(receipt["release_gate"]["checks"][0]["name"], "beta_policy")
            self.assertTrue(any("release dry-run" in item.lower() for item in receipt["release_gate"]["recommendations"]))
            self.assertEqual(receipt["release_gate"]["recommendation_details"][0]["entry_point"], "python tools/pilot_exit_check.py --allow-limited-go")
            self.assertEqual(
                receipt["review_order"],
                [
                    "runtime/beta_release_dry_run_report.json",
                    "runtime/windows_release_receipt.json",
                    "runtime/windows_release_summary.md",
                ],
            )
            summary_text = (runtime_dir / "windows_release_summary.md").read_text(encoding="utf-8")
            self.assertIn("## Release Gate", summary_text)
            self.assertIn("## Review Order", summary_text)
            self.assertIn("## Fix-First", summary_text)
            self.assertIn("- Ref: recipe-release-1", summary_text)
            self.assertIn("1. runtime/beta_release_dry_run_report.json", summary_text)
            self.assertIn("python tools/pilot_exit_check.py --allow-limited-go", summary_text)
            self.assertTrue(any(fields.get("gate_summary") for event, fields in stub.logged if event == "windows_ops_completed"))
            completed_fields = next(fields for event, fields in stub.logged if event == "windows_ops_completed")
            self.assertEqual(completed_fields["gate_failed_checks"], ["pilot_gate"])
            self.assertEqual(completed_fields["gate_passed_checks"], 1)
            self.assertEqual(completed_fields["gate_total_checks"], 2)
            self.assertTrue(any("pilot gate" in item.lower() for item in completed_fields["gate_recommendations"]))
            self.assertEqual(completed_fields["gate_fix_target"], "tools/pilot_exit_check.py / runtime/pilot_exit_report.json")
            self.assertEqual(completed_fields["gate_fix_docs"], "docs/PACKAGING.md")
            self.assertEqual(completed_fields["gate_fix_command"], "python tools/pilot_exit_check.py --allow-limited-go")
            self.assertTrue(str(completed_fields["release_summary"]).endswith("windows_release_summary.md"))

    def test_windows_release_summary_green_path_uses_next_review_step(self):
        with tempfile.TemporaryDirectory() as td:
            summary_path = Path(td) / "windows_release_summary.md"
            launcher_window.LauncherWindow._write_windows_release_summary(
                summary_path,
                {
                    "timestamp": "2026-04-16T12:34:56+00:00",
                    "event_id": "release-pass-1",
                    "release_stage": "release_gate",
                    "action": "release_dry_run",
                    "ok": True,
                    "summary": "WINDOWS RELEASE DRY RUN completed 1/1 servicing step(s).",
                    "changes": "beta release dry-run report refreshed",
                    "review_order": [
                        "runtime/beta_release_dry_run_report.json",
                        "runtime/windows_release_receipt.json",
                        "runtime/windows_release_summary.md",
                    ],
                    "release_gate": {
                        "summary": "PASS | checks 2/2 | required files OK",
                        "detail": "all dry-run checks passed and required handoff files are present",
                        "passed_checks": 2,
                        "total_checks": 2,
                        "recommendations": [
                            "Release gate is green; review the dry-run report, receipt, and summary in that order, then package or hand off the bundle."
                        ],
                        "recommendation_details": [
                            {
                                "text": "Release gate is green; review the dry-run report, receipt, and summary in that order, then package or hand off the bundle.",
                                "fix_target": "runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md",
                                "docs_hint": "docs/PACKAGING.md",
                                "entry_point": "python tools/beta_release_dry_run.py",
                            }
                        ],
                    },
                    "artifacts": [
                        {
                            "id": "release_dry_run",
                            "label": "release dry-run report",
                            "path": "runtime/beta_release_dry_run_report.json",
                            "mtime": "2026-04-16T12:34:10+00:00",
                            "size": 321,
                        }
                    ],
                    "operator_guidance": {
                        "next_step": "Release dry-run passed. Review the dry-run report, receipt, and summary in that order, then package or hand off the reviewer bundle.",
                        "fix_target": "runtime/beta_release_dry_run_report.json",
                        "docs_hint": "docs/PACKAGING.md",
                        "entry_point": "python tools/beta_release_dry_run.py",
                    },
                },
            )

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("- Ref: release-pass-1", summary_text)
            self.assertIn("## Next Review Step", summary_text)
            self.assertIn("Review: runtime/beta_release_dry_run_report.json -> runtime/windows_release_receipt.json -> runtime/windows_release_summary.md", summary_text)
            self.assertIn("release dry-run report: runtime/beta_release_dry_run_report.json (updated 2026-04-16T12:34:10+00:00, 321 B)", summary_text)

    def test_settings_view_persists_persona_builder_config(self):
        old_settings_path = runtime_profile.SETTINGS_PATH
        old_runtime_dir = runtime_profile.RUNTIME_DIR
        old_profile_backend = settings_view_module._PROFILE_BACKEND
        old_personalization_backend = settings_view_module._PERSONALIZATION_BACKEND
        old_persona_path = personalization_config.PERSONA_CONFIG_PATH
        old_provider_path = personalization_config.PROVIDER_REGISTRY_PATH
        old_voice_path = personalization_config.VOICE_BINDINGS_PATH
        old_personalization_runtime = personalization_config.RUNTIME_DIR

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            runtime_profile.RUNTIME_DIR = runtime_dir
            runtime_profile.SETTINGS_PATH = runtime_dir / "app_settings.json"
            personalization_config.RUNTIME_DIR = runtime_dir
            personalization_config.PERSONA_CONFIG_PATH = runtime_dir / "persona_config.json"
            personalization_config.PROVIDER_REGISTRY_PATH = runtime_dir / "provider_registry.json"
            personalization_config.VOICE_BINDINGS_PATH = runtime_dir / "voice_bindings.json"
            settings_view_module._PROFILE_BACKEND = True
            settings_view_module._PERSONALIZATION_BACKEND = True

            try:
                view = settings_view_module.SettingsView()
                view._persona_name.setText("Builder Coach")
                view._scope_cb.setCurrentText("MODEL")
                view._model_binding_cb.setCurrentText("guppy-fast")
                view._tone_cb.setCurrentText("COACH")
                view._verbosity_cb.setCurrentText("HIGH")
                view._style_cb.setCurrentText("STRUCTURED")
                view._system_prompt.setPlainText("You are Builder Coach. Keep output bounded and review-first.")
                view._socratic_slider.setValue(55)
                view._example_slider.setValue(65)
                view._save()

                saved = personalization_config.load_persona_config()
                persona = saved["personas"][0]
                self.assertEqual(persona["name"], "Builder Coach")
                self.assertEqual(persona["scope"], "model")
                self.assertEqual(persona["model"], "guppy-fast")
                self.assertEqual(persona["traits"]["tone"], "coach")
                self.assertIn("BUILDER COACH", view._preview_lbl.text())
            finally:
                runtime_profile.SETTINGS_PATH = old_settings_path
                runtime_profile.RUNTIME_DIR = old_runtime_dir
                settings_view_module._PROFILE_BACKEND = old_profile_backend
                settings_view_module._PERSONALIZATION_BACKEND = old_personalization_backend
                personalization_config.PERSONA_CONFIG_PATH = old_persona_path
                personalization_config.PROVIDER_REGISTRY_PATH = old_provider_path
                personalization_config.VOICE_BINDINGS_PATH = old_voice_path
                personalization_config.RUNTIME_DIR = old_personalization_runtime

    def test_settings_view_rolls_back_persona_when_runtime_save_fails(self):
        old_settings_path = runtime_profile.SETTINGS_PATH
        old_runtime_dir = runtime_profile.RUNTIME_DIR
        old_profile_backend = settings_view_module._PROFILE_BACKEND
        old_personalization_backend = settings_view_module._PERSONALIZATION_BACKEND
        old_persona_path = personalization_config.PERSONA_CONFIG_PATH
        old_provider_path = personalization_config.PROVIDER_REGISTRY_PATH
        old_voice_path = personalization_config.VOICE_BINDINGS_PATH
        old_personalization_runtime = personalization_config.RUNTIME_DIR
        old_save_app_settings = settings_view_module.save_app_settings

        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            runtime_profile.RUNTIME_DIR = runtime_dir
            runtime_profile.SETTINGS_PATH = runtime_dir / "app_settings.json"
            personalization_config.RUNTIME_DIR = runtime_dir
            personalization_config.PERSONA_CONFIG_PATH = runtime_dir / "persona_config.json"
            personalization_config.PROVIDER_REGISTRY_PATH = runtime_dir / "provider_registry.json"
            personalization_config.VOICE_BINDINGS_PATH = runtime_dir / "voice_bindings.json"
            settings_view_module._PROFILE_BACKEND = True
            settings_view_module._PERSONALIZATION_BACKEND = True

            try:
                baseline_settings = {"runtime_profile": "standard", "default_mode": "auto", "default_surface": "guppy"}
                runtime_profile.save_app_settings(baseline_settings)
                personalization_config.save_persona_config(personalization_config.DEFAULT_PERSONA_CONFIG)

                def _fail_for_new_payload(payload):
                    if payload.get("default_mode") == "code":
                        raise OSError("simulated runtime write failure")
                    return runtime_profile.save_app_settings(payload)

                settings_view_module.save_app_settings = _fail_for_new_payload

                view = settings_view_module.SettingsView()
                original_persona = personalization_config.load_persona_config()
                original_settings = runtime_profile.load_app_settings()
                view._persona_name.setText("Rollback Candidate")
                view._cb_mode.setCurrentIndex(4)
                view._save()

                persisted_persona = personalization_config.load_persona_config()
                persisted_settings = runtime_profile.load_app_settings()
                self.assertEqual(persisted_persona, original_persona)
                self.assertEqual(persisted_settings.get("default_mode"), original_settings.get("default_mode"))
                self.assertIn("Save failed", view._persona_status_lbl.text())
            finally:
                settings_view_module.save_app_settings = old_save_app_settings
                runtime_profile.SETTINGS_PATH = old_settings_path
                runtime_profile.RUNTIME_DIR = old_runtime_dir
                settings_view_module._PROFILE_BACKEND = old_profile_backend
                settings_view_module._PERSONALIZATION_BACKEND = old_personalization_backend
                personalization_config.PERSONA_CONFIG_PATH = old_persona_path
                personalization_config.PROVIDER_REGISTRY_PATH = old_provider_path
                personalization_config.VOICE_BINDINGS_PATH = old_voice_path
                personalization_config.RUNTIME_DIR = old_personalization_runtime

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

    def test_tool_prompt_mapping_primes_home_with_task_language(self):
        prompt = launcher_window.LauncherWindow._tool_prompt_for_home("write_file")

        self.assertIn("Prime the write-file workspace tool", prompt)
        self.assertIn("what file should change", prompt)

    def test_route_evidence_summary_stays_launcher_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
            launcher_window._RUNTIME = runtime_dir
            try:
                os.environ.pop("ANTHROPIC_API_KEY", None)
                (runtime_dir / "guppy.status").write_text('{"last_latency_ms": "42"}', encoding="utf-8")

                text = launcher_window.LauncherWindow._route_evidence_summary({"route": "haiku"})

                self.assertEqual(text, "cloud route needs API key; launcher-wide last reply 42 ms")
            finally:
                launcher_window._RUNTIME = old_runtime
                if old_anthropic is None:
                    os.environ.pop("ANTHROPIC_API_KEY", None)
                else:
                    os.environ["ANTHROPIC_API_KEY"] = old_anthropic

    def test_status_panel_recovery_outcome_label_updates(self):
        panel = StatusPanel()
        panel.set_recovery_outcome("warmup", True, "cache refreshed")
        self.assertIn("WARMUP OK", panel._activity_lbl.text())

    def test_status_panel_quick_tools_reflect_ready_and_restricted_states(self):
        panel = StatusPanel()
        panel.set_tool_states({"read_file": "ready", "write_file": "restricted"})

        self.assertTrue(panel._tool_buttons["read_file"].isEnabled())
        self.assertFalse(panel._tool_buttons["write_file"].isEnabled())

    def test_status_panel_hides_extra_slots_until_requested(self):
        panel = StatusPanel()

        self.assertTrue(panel._extras_host.isHidden())
        self.assertEqual(panel._extras_btn.text(), "MORE OPTIONS")

        panel._extras_btn.click()

        self.assertFalse(panel._extras_host.isHidden())
        self.assertEqual(panel._extras_btn.text(), "LESS OPTIONS")

    def test_chat_timeout_for_local_diagnostic_turns_is_extended(self):
        self.assertGreaterEqual(
            launcher_window.LauncherWindow._chat_timeout_for_request("auto", "Let's run a local diagnostic"),
            60.0,
        )

    def test_recovered_command_uses_warm_start_chat_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            old_thread = launcher_window.threading.Thread
            launcher_window._RUNTIME = runtime_dir
            launcher_window.threading.Thread = _ImmediateThread
            try:
                dummy = _DummyLauncher()
                dummy._api_reachable_result = False
                dummy._api_recovery_result = (True, "supervised api started and reachable")
                seen_timeouts: list[float] = []

                def _http_json(path: str, method: str = "GET", payload=None, timeout: float = 8.0, **kwargs):
                    del method, payload, kwargs
                    if path == "/chat":
                        seen_timeouts.append(timeout)
                        return {"response": "ok"}
                    return {}

                dummy._http_json = _http_json  # type: ignore[method-assign]

                launcher_window.LauncherWindow._on_assistant_command(dummy, "status please")

                self.assertTrue(seen_timeouts)
                self.assertGreater(seen_timeouts[0], launcher_window.LauncherWindow._chat_timeout_for_request("auto", "status please"))
                self.assertLessEqual(seen_timeouts[0], 35.0)
            finally:
                launcher_window._RUNTIME = old_runtime
                launcher_window.threading.Thread = old_thread

    def test_refresh_instance_views_skips_heavy_reapply_when_snapshot_is_unchanged(self):
        class _Recorder:
            def __init__(self, windows_snapshot=None):
                self.calls = 0
                self._windows_snapshot = windows_snapshot or {}

            def set_instances(self, _payload):
                self.calls += 1

            def set_instance_snapshot(self, _payload):
                self.calls += 1

            def set_connector_inventory(self, _payload):
                self.calls += 1

            def set_windows_snapshot(self, _payload):
                self.calls += 1

            def windows_ops_snapshot(self):
                return dict(self._windows_snapshot)

        class _ToolsRecorder:
            def __init__(self) -> None:
                self.calls = 0

            def set_instance_context(self, _instance, _snapshot):
                self.calls += 1

        class _AssistantRecorder:
            def set_active_instance(self, *_args, **_kwargs):
                return

        class _TopbarRecorder:
            def set_instances(self, *_args, **_kwargs):
                return

            def set_session(self, *_args, **_kwargs):
                return

        snapshot = {
            "active_instance": "guppy-primary",
            "limits": {"configured": 1, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2},
            "instances": [
                {
                    "name": "guppy-primary",
                    "type": "user_instance",
                    "description": "Primary workspace",
                    "enabled": True,
                }
            ],
        }
        connectors = [{"id": "youtube", "label": "YouTube", "auth_state": "optional"}]
        dummy = type("RefreshDummy", (), {})()
        dummy._fetch_instance_snapshot = lambda force=False: snapshot
        dummy._fetch_connector_inventory = lambda force=False: connectors
        dummy._last_instance_snapshot = {}
        dummy._last_instance_view_signature = ""
        dummy._last_connector_view_signature = ""
        dummy._last_tools_context_signature = ""
        dummy._last_windows_snapshot_signature = ""
        dummy._instance_manager_view = _Recorder()
        dummy._settings_hub_view = _Recorder(windows_snapshot={"runtime": "ready"})
        dummy._tools_view = _ToolsRecorder()
        dummy._assistant_view = _AssistantRecorder()
        dummy._topbar = _TopbarRecorder()
        dummy._instance_histories = {}
        dummy._active_instance_name = "guppy-primary"
        dummy._request_in_flight = False
        dummy._apply_instance_switch = lambda *_args, **_kwargs: None
        dummy._sync_right_tray = lambda *_args, **_kwargs: None
        dummy._sync_automation_test_state = lambda *_args, **_kwargs: None
        dummy._workspace_role_label = lambda *_args, **_kwargs: "daily"
        dummy._on_instance_logs_requested = lambda *_args, **_kwargs: None
        dummy._payload_signature = launcher_window.LauncherWindow._payload_signature

        launcher_window.LauncherWindow._refresh_instance_views(dummy)
        launcher_window.LauncherWindow._refresh_instance_views(dummy)

        self.assertEqual(dummy._instance_manager_view.calls, 1)
        self.assertEqual(dummy._settings_hub_view.calls, 3)
        self.assertEqual(dummy._tools_view.calls, 1)

    def test_refresh_instance_views_propagates_active_workspace_across_shell_surfaces(self):
        class _Recorder:
            def __init__(self, windows_snapshot=None):
                self.calls = 0
                self._windows_snapshot = windows_snapshot or {}

            def set_instances(self, _payload):
                self.calls += 1

            def set_instance_snapshot(self, _payload):
                self.calls += 1

            def set_connector_inventory(self, _payload):
                self.calls += 1

            def set_windows_snapshot(self, _payload):
                self.calls += 1

            def windows_ops_snapshot(self):
                return dict(self._windows_snapshot)

        class _ToolsRecorder:
            def __init__(self) -> None:
                self.active_payloads: list[str] = []

            def set_instance_context(self, active_payload, _snapshot):
                self.active_payloads.append(str(active_payload.get("name", "")))

        class _AssistantRecorder:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def set_active_instance(self, name, **kwargs):
                self.calls.append((str(name), str(kwargs.get("workspace_type", ""))))

        class _TopbarRecorder:
            def __init__(self) -> None:
                self.sessions: list[str] = []
                self.active_sets: list[tuple[list[str], str]] = []

            def set_instances(self, names, active_instance=""):
                self.active_sets.append((list(names), str(active_instance)))

            def set_session(self, label):
                self.sessions.append(str(label))

        snapshots = [
            {
                "active_instance": "builder-collab",
                "limits": {"configured": 3, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2},
                "instances": [
                    {"name": "guppy-primary", "type": "user_instance", "description": "Daily", "enabled": True},
                    {"name": "builder-collab", "type": "builder_instance", "description": "Builder", "enabled": True},
                    {"name": "ops-watch", "type": "admin_instance", "description": "Ops", "enabled": True},
                ],
            },
            {
                "active_instance": "ops-watch",
                "limits": {"configured": 3, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2},
                "instances": [
                    {"name": "guppy-primary", "type": "user_instance", "description": "Daily", "enabled": True},
                    {"name": "builder-collab", "type": "builder_instance", "description": "Builder", "enabled": True},
                    {"name": "ops-watch", "type": "admin_instance", "description": "Ops", "enabled": True},
                ],
            },
        ]
        snapshot_index = {"value": 0}

        def _current_snapshot(force=False):
            del force
            return snapshots[snapshot_index["value"]]

        sync_payloads: list[str] = []
        dummy = type("RefreshActiveDummy", (), {})()
        dummy._fetch_instance_snapshot = _current_snapshot
        dummy._fetch_connector_inventory = lambda force=False: [{"id": "youtube", "label": "YouTube", "auth_state": "optional"}]
        dummy._last_instance_snapshot = {}
        dummy._last_instance_view_signature = ""
        dummy._last_connector_view_signature = ""
        dummy._last_tools_context_signature = ""
        dummy._last_windows_snapshot_signature = ""
        dummy._instance_manager_view = _Recorder()
        dummy._settings_hub_view = _Recorder(windows_snapshot={"runtime": "ready"})
        dummy._tools_view = _ToolsRecorder()
        dummy._assistant_view = _AssistantRecorder()
        dummy._topbar = _TopbarRecorder()
        dummy._instance_histories = {}
        dummy._active_instance_name = "guppy-primary"
        dummy._request_in_flight = False
        dummy._apply_instance_switch = lambda *_args, **_kwargs: None
        dummy._sync_right_tray = lambda payload: sync_payloads.append(str(payload.get("name", "")))
        dummy._sync_automation_test_state = lambda *_args, **_kwargs: None
        dummy._workspace_role_label = launcher_window.LauncherWindow._workspace_role_label
        dummy._on_instance_logs_requested = lambda *_args, **_kwargs: None
        dummy._payload_signature = launcher_window.LauncherWindow._payload_signature

        launcher_window.LauncherWindow._refresh_instance_views(dummy)
        snapshot_index["value"] = 1
        launcher_window.LauncherWindow._refresh_instance_views(dummy, force=True)

        self.assertEqual(dummy._assistant_view.calls[0], ("builder-collab", "builder_instance"))
        self.assertEqual(dummy._assistant_view.calls[-1], ("ops-watch", "admin_instance"))
        self.assertEqual(dummy._tools_view.active_payloads, ["builder-collab", "ops-watch"])
        self.assertEqual(sync_payloads, ["builder-collab", "ops-watch"])
        self.assertIn("Builder collaborator workspace", dummy._topbar.sessions[0])
        self.assertIn("Operations workspace", dummy._topbar.sessions[-1])
        self.assertEqual(dummy._topbar.active_sets[-1][1], "ops-watch")

    def test_bootstrap_instance_switcher_defers_heavy_workspace_hydration(self):
        class _Recorder:
            def __init__(self) -> None:
                self.calls = 0

            def set_instances(self, _payload) -> None:
                self.calls += 1

            def set_instance_snapshot(self, _payload) -> None:
                self.calls += 1

            def windows_ops_snapshot(self) -> dict[str, str]:
                return {"runtime": "ready"}

        class _SettingsHubRecorder:
            def __init__(self) -> None:
                self.calls = 0

            def set_instance_snapshot(self, _payload) -> None:
                self.calls += 1

            def set_windows_snapshot(self, _payload) -> None:
                self.calls += 1

            def windows_ops_snapshot(self) -> dict[str, str]:
                return {"runtime": "ready"}

        class _AssistantRecorder:
            def __init__(self) -> None:
                self.calls = 0
                self.welcomes = 0

            def set_active_instance(self, *_args, **_kwargs) -> None:
                self.calls += 1

            def ensure_welcome_message(self) -> None:
                self.welcomes += 1

        class _TopbarRecorder:
            def __init__(self) -> None:
                self.calls: list[tuple[list[str], str]] = []

            def set_instances(self, names, active_instance="") -> None:
                self.calls.append((list(names), str(active_instance)))

        class _ToolsRecorder:
            def __init__(self) -> None:
                self.calls = 0

            def set_instance_context(self, *_args, **_kwargs) -> None:
                self.calls += 1

        snapshot_flags: list[bool] = []
        connector_fetches: list[bool] = []
        refresh_calls: list[bool] = []
        scheduled: list[tuple[int, object]] = []
        sync_payloads: list[str] = []
        dummy = type("BootstrapDummy", (), {})()
        dummy._instance_histories = {}
        dummy._active_instance_name = "guppy-primary"
        dummy._instance_snapshot_ttl_s = 6.0
        dummy._bootstrap_instance_refresh_pending = False
        dummy._bootstrap_instance_refresh_complete = False
        dummy._last_instance_snapshot = {}
        dummy._instance_snapshot_expires_at = 0.0
        dummy._last_connector_inventory_snapshot = []
        dummy._connector_inventory_expires_at = 0.0
        dummy._connector_inventory_ttl_s = 15.0
        dummy._instance_manager_view = _Recorder()
        dummy._settings_hub_view = _SettingsHubRecorder()
        dummy._assistant_view = _AssistantRecorder()
        dummy._topbar = _TopbarRecorder()
        dummy._tools_view = _ToolsRecorder()
        dummy._rotate_chat_session = lambda *_args, **_kwargs: None
        dummy._set_daily_activity = lambda *_args, **_kwargs: None
        dummy._sync_right_tray = lambda payload: sync_payloads.append(str(payload.get("name", "")))
        dummy._on_instance_logs_requested = lambda *_args, **_kwargs: None
        dummy._refresh_instance_views = lambda *args, **kwargs: refresh_calls.append(bool(kwargs.get("force")))
        dummy._fetch_connector_inventory = lambda force=False: connector_fetches.append(bool(force)) or []
        dummy._load_instance_catalog = lambda snapshot=None: (["guppy-primary"], "guppy-primary")

        def _local_snapshot(*, include_workspace_details: bool = True):
            snapshot_flags.append(include_workspace_details)
            return {
                "active_instance": "guppy-primary",
                "instances": [
                    {
                        "name": "guppy-primary",
                        "type": "user_instance",
                        "description": "Primary workspace",
                        "mode": "auto",
                        "persona": "guppy",
                        "voice": "default",
                        "last_message": "",
                    }
                ],
            }

        dummy._local_instance_snapshot = _local_snapshot
        dummy._complete_bootstrap_instance_switcher = launcher_window.LauncherWindow._complete_bootstrap_instance_switcher.__get__(dummy, type(dummy))

        old_single_shot = launcher_window.QTimer.singleShot
        old_connector_inventory = launcher_window.connector_inventory
        launcher_window.QTimer.singleShot = lambda delay, callback: scheduled.append((delay, callback))
        launcher_window.connector_inventory = lambda: []
        try:
            launcher_window.LauncherWindow._bootstrap_instance_switcher(dummy)

            self.assertEqual(snapshot_flags, [False])
            self.assertEqual(connector_fetches, [])
            self.assertEqual(dummy._tools_view.calls, 0)
            self.assertEqual(sync_payloads, ["guppy-primary"])
            self.assertTrue(dummy._bootstrap_instance_refresh_pending)
            self.assertFalse(dummy._bootstrap_instance_refresh_complete)
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(scheduled[0][0], 0)

            scheduled[0][1]()

            self.assertEqual(refresh_calls, [False])
            self.assertFalse(dummy._bootstrap_instance_refresh_pending)
            self.assertTrue(dummy._bootstrap_instance_refresh_complete)
            self.assertEqual(len(scheduled), 2)
            self.assertEqual(scheduled[1][0], 150)
        finally:
            launcher_window.QTimer.singleShot = old_single_shot
            launcher_window.connector_inventory = old_connector_inventory

    def test_write_user_test_evidence_pack_captures_stress_workspace_and_recent_notes(self):
        with tempfile.TemporaryDirectory() as td:
            runtime_dir = Path(td)
            old_runtime = launcher_window._RUNTIME
            launcher_window._RUNTIME = runtime_dir
            try:
                (runtime_dir / "launcher_events.jsonl").write_text(
                    json.dumps({"event": "workspace_onboarding_ready", "instance": "builder-collab"}) + "\n"
                    + json.dumps({"event": "windows_ops_completed", "summary": "verify_runtime passed"}) + "\n",
                    encoding="utf-8",
                )
                stress_report = runtime_dir / "stress_report_20260417_022711.json"
                stress_report.write_text(json.dumps({"ok": True}), encoding="utf-8")

                class _Label:
                    def __init__(self, text: str) -> None:
                        self._text = text

                    def text(self) -> str:
                        return self._text

                class _AdvancedStub:
                    _automation_status_lbl = _Label("Automation test lane ready")

                    @staticmethod
                    def windows_ops_snapshot() -> dict[str, str]:
                        return {
                            "next": "Next step: run validation after review.",
                            "service": "Recent service action: verify_runtime | OK",
                            "gate": "Release check: clear",
                        }

                class _AssistantStub:
                    _background_event = _Label("Latest activity: Evidence pack refreshed")
                    _workspace_summary = _Label("Active workspace: Builder collaborator workspace.")
                    _runtime_facts = _Label("Ready now: Standard profile, GUPPY model.")
                    _route_facts = _Label("Next reply: builder review.")
                    _recovery_summary = _Label("System health: stable")

                class _LauncherStub:
                    pass

                stub = _LauncherStub()
                stub._last_instance_snapshot = {
                    "instances": [
                        {
                            "name": "builder-collab",
                            "type": "builder_instance",
                            "description": "Planning partner",
                        }
                    ]
                }
                stub._active_instance_name = "builder-collab"
                stub._settings_hub_view = _AdvancedStub()
                stub._assistant_view = _AssistantStub()
                stub._preferred_builder_instance_name = lambda: "builder-collab"
                stub._user_test_evidence_path = launcher_window.LauncherWindow._user_test_evidence_path.__get__(stub, _LauncherStub)
                stub._user_test_evidence_summary_path = launcher_window.LauncherWindow._user_test_evidence_summary_path.__get__(stub, _LauncherStub)
                stub._display_repo_path = launcher_window.LauncherWindow._display_repo_path
                stub._latest_stress_report_path = launcher_window.LauncherWindow._latest_stress_report_path
                stub._recent_launcher_event_summaries = launcher_window.LauncherWindow._recent_launcher_event_summaries.__get__(stub, _LauncherStub)
                stub._write_user_test_evidence_summary = launcher_window.LauncherWindow._write_user_test_evidence_summary

                bundle = launcher_window.LauncherWindow._write_user_test_evidence_pack(
                    stub,
                    report_path=runtime_dir / "offhours_builder_report.json",
                    status="Evidence pack refreshed for the guided tester lane.",
                )

                evidence_json = json.loads((runtime_dir / "user_test_evidence.json").read_text(encoding="utf-8"))
                evidence_md = (runtime_dir / "user_test_evidence.md").read_text(encoding="utf-8")

                self.assertTrue(bundle["summary_path"].endswith("user_test_evidence.md"))
                self.assertTrue(bundle["stress_report_path"].endswith("stress_report_20260417_022711.json"))
                self.assertEqual(evidence_json["active_workspace_name"], "builder-collab")
                self.assertIn("stress_report_20260417_022711.json", evidence_json["latest_stress_report"])
                self.assertIn("workspace onboarding ready", evidence_md.lower())
                self.assertIn("Active workspace: builder-collab", evidence_md)
            finally:
                launcher_window._RUNTIME = old_runtime

    def test_preferred_builder_workspace_skips_disabled_builder_instance(self):
        dummy = type("BuilderPrefDummy", (), {})()
        dummy._last_instance_snapshot = {
            "instances": [
                {"name": "guppy-primary", "enabled": True, "type": "user_instance"},
                {"name": "builder-collab", "enabled": False, "type": "builder_instance"},
            ]
        }
        dummy._active_instance_name = "guppy-primary"
        dummy._available_instance_names = launcher_window.LauncherWindow._available_instance_names.__get__(dummy, type(dummy))

        preferred = launcher_window.LauncherWindow._preferred_builder_instance_name(dummy)

        self.assertEqual(preferred, "guppy-primary")

    def test_automation_snapshot_does_not_reapply_ready_status_when_no_status_is_passed(self):
        dummy = type("AutomationSnapshotDummy", (), {})()
        dummy._active_instance_name = "guppy-primary"
        dummy._last_instance_snapshot = {
            "instances": [
                {"name": "guppy-primary", "enabled": True, "type": "user_instance"},
            ]
        }
        dummy._preferred_builder_instance_name = lambda: "guppy-primary"
        dummy._display_repo_path = launcher_window.LauncherWindow._display_repo_path
        dummy._latest_stress_report_path = lambda: None
        dummy._recent_launcher_event_summaries = lambda limit=4: []
        dummy._user_test_evidence_summary_path = lambda: Path("runtime/user_test_evidence.md")

        snapshot = launcher_window.LauncherWindow._automation_test_snapshot(dummy)

        self.assertEqual(snapshot["status"], "")

    def test_apply_start_destination_opens_guided_automation_flow(self):
        class _AdvancedStub:
            def __init__(self) -> None:
                self.note = ""

            def focus_automation_test(self, note: str = "") -> None:
                self.note = note

        class _AssistantStub:
            def __init__(self) -> None:
                self.event = ""

            def set_background_event(self, text: str) -> None:
                self.event = text

        class _StatusStub:
            def __init__(self) -> None:
                self.lines: list[str] = []

            def append_syslog(self, text: str) -> None:
                self.lines.append(text)

        dummy = type("StartIntentDummy", (), {})()
        dummy._start_destination = "automation-test"
        dummy._settings_hub_view = _AdvancedStub()
        dummy._assistant_view = _AssistantStub()
        dummy._status_panel = _StatusStub()
        dummy._active_tab = None
        dummy._daily_activity = ""
        dummy._logged = None
        dummy._on_tab_change = lambda index: setattr(dummy, "_active_tab", index)
        dummy._set_daily_activity = lambda text: setattr(dummy, "_daily_activity", text)
        dummy._log_launcher_event = lambda event, **fields: setattr(dummy, "_logged", (event, fields))

        launcher_window.LauncherWindow._apply_start_destination(dummy)

        self.assertEqual(dummy._active_tab, 3)
        self.assertIn("Test flow ready", dummy._settings_hub_view.note)
        self.assertIn("Test flow ready", dummy._assistant_view.event)
        self.assertIn("Setup & Health", dummy._daily_activity)
        self.assertEqual(dummy._logged[0], "start_destination_applied")

    def test_workspace_create_opens_new_workspace_for_first_run_onboarding(self):
        class _ManagerStub:
            def __init__(self) -> None:
                self.status = ""

            def set_status(self, text: str, ok: bool = True) -> None:
                del ok
                self.status = text

        class _StatusStub:
            def __init__(self) -> None:
                self.lines: list[str] = []

            def append_syslog(self, text: str) -> None:
                self.lines.append(text)

        class _AssistantStub:
            def __init__(self) -> None:
                self.messages: list[str] = []

            def add_system_message(self, text: str) -> None:
                self.messages.append(text)

        dummy = type("CreateDummy", (), {})()
        dummy._http_json = lambda *args, **kwargs: {"action": "created"}
        dummy._refresh_calls = 0
        dummy._refresh_instance_views = lambda *args, **kwargs: setattr(dummy, "_refresh_calls", dummy._refresh_calls + 1)
        dummy._apply_instance_switch = lambda target, announce=True: setattr(dummy, "_switched_to", (target, announce))
        dummy._instance_manager_view = _ManagerStub()
        dummy._status_panel = _StatusStub()
        dummy._assistant_view = _AssistantStub()
        dummy._daily_activity = ""
        dummy._set_daily_activity = lambda text: setattr(dummy, "_daily_activity", text)
        dummy._logged = None
        dummy._log_launcher_event = lambda event, **fields: setattr(dummy, "_logged", (event, fields))
        dummy._workspace_first_run_recipe = launcher_window.LauncherWindow._workspace_first_run_recipe
        dummy._workspace_role_label = launcher_window.LauncherWindow._workspace_role_label

        launcher_window.LauncherWindow._on_instance_create_requested(
            dummy,
            {"name": "builder-collab", "type": "builder_instance", "description": "Planning workspace"},
        )

        self.assertEqual(dummy._switched_to, ("builder-collab", True))
        self.assertIn("PLAN NEXT PASS", dummy._instance_manager_view.status)
        self.assertIn("PLAN NEXT PASS", dummy._status_panel.lines[-1])
        self.assertIn("Builder collaborator workspace", dummy._assistant_view.messages[-1])
        self.assertIn("Workspace ready: builder-collab", dummy._daily_activity)
        self.assertEqual(dummy._logged[0], "workspace_onboarding_ready")
        self.assertGreaterEqual(dummy._refresh_calls, 2)

    def test_approve_latest_builder_task_uses_safe_approval_flow(self):
        from utils import offhours_builder

        old_root = offhours_builder.ROOT
        old_runtime = offhours_builder.RUNTIME
        old_queue = offhours_builder.QUEUE_PATH
        old_results = offhours_builder.RESULTS_PATH
        old_metrics = offhours_builder.METRICS_PATH
        old_dry_run = offhours_builder.DRY_RUN_DIR
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                runtime = root / "runtime"
                dry_run_dir = runtime / "offhours_results" / "dry_run"
                dry_run_dir.mkdir(parents=True, exist_ok=True)
                staged_file = dry_run_dir / "automation-guide.staged"
                staged_file.write_text("# approved\n", encoding="utf-8")

                offhours_builder.ROOT = root
                offhours_builder.RUNTIME = runtime
                offhours_builder.QUEUE_PATH = runtime / "offhours_task_queue.json"
                offhours_builder.RESULTS_PATH = runtime / "offhours_task_results.jsonl"
                offhours_builder.METRICS_PATH = runtime / "offhours_metrics.jsonl"
                offhours_builder.DRY_RUN_DIR = dry_run_dir
                offhours_builder.QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
                offhours_builder.QUEUE_PATH.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "tasks": [
                                {
                                    "id": "builder_docs_followup_test",
                                    "title": "Draft docs follow-up",
                                    "status": "awaiting_approval",
                                    "output_file_path": "docs/generated/automation-guide.md",
                                    "pending_approval": {
                                        "staged_file": str(staged_file),
                                        "workspace_file": "docs/generated/automation-guide.md",
                                    },
                                }
                            ],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                dummy = type("ApprovalDummy", (), {"_active_instance_name": "builder-collab"})()

                payload = launcher_window.LauncherWindow._approve_latest_builder_task(dummy)

                self.assertEqual(payload["approved_by"], "builder-collab")
                self.assertTrue((root / "docs" / "generated" / "automation-guide.md").exists())
        finally:
            offhours_builder.ROOT = old_root
            offhours_builder.RUNTIME = old_runtime
            offhours_builder.QUEUE_PATH = old_queue
            offhours_builder.RESULTS_PATH = old_results
            offhours_builder.METRICS_PATH = old_metrics
            offhours_builder.DRY_RUN_DIR = old_dry_run

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
            old_secret_store_available = launcher_window._SECRET_STORE_AVAILABLE
            old_secret_store = launcher_window._secret_store
            launcher_window._RUNTIME = runtime_dir
            launcher_window._SECRET_STORE_AVAILABLE = False
            launcher_window._secret_store = None
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
                launcher_window._SECRET_STORE_AVAILABLE = old_secret_store_available
                launcher_window._secret_store = old_secret_store


if __name__ == "__main__":
    unittest.main()
