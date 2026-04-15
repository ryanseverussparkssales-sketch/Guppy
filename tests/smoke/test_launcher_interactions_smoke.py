import os
import tempfile
import unittest
from pathlib import Path
from queue import SimpleQueue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    from ui.launcher.components.agent_card import AgentCard
    from ui.launcher.components.sidebar import Sidebar
    from ui.launcher.components.status_panel import StatusPanel
    from ui.launcher.components.topbar import TopBar
    from ui.launcher.views.assistant_view import AssistantView
    from ui.launcher.views.advanced_view import AdvancedView
    from ui.launcher.views.instance_manager_view import InstanceManagerView
    from ui.launcher.views.local_llm_view import LocalLLMView
    from ui.launcher.views.models_view import ModelsView
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

    def test_assistant_mode_dropdown_excludes_internal_vault_mode(self):
        assistant = AssistantView()
        modes = [assistant._cb_mode.itemText(i) for i in range(assistant._cb_mode.count())]

        self.assertEqual(modes, ["AUTO", "CLAUDE", "OLLAMA", "LOCAL", "CODE", "TEACHING"])
        self.assertNotIn("VAULT", modes)

    def test_topbar_instance_switcher_emits_selection(self):
        topbar = TopBar()
        selected: list[str] = []
        topbar.instance_selected.connect(lambda name: selected.append(name))

        nav_labels = [btn.text() for btn in topbar._nav_btns]
        self.assertIn("HOME", nav_labels)
        self.assertIn("WORKSPACES", nav_labels)

        topbar.set_instances(["guppy-primary", "builder-collab"], active_instance="guppy-primary")
        topbar.set_active_instance("builder-collab")

        self.assertEqual(topbar._instance_cb.currentText(), "builder-collab")
        self.assertEqual(selected, [])

        topbar._instance_cb.setCurrentText("guppy-primary")
        self.assertTrue(selected)
        self.assertEqual(selected[-1], "guppy-primary")

    def test_sidebar_exposes_dedicated_local_llm_surface(self):
        sidebar = Sidebar()
        labels = [item._label.text() for item in sidebar._items]
        self.assertIn("LOCAL LLM", labels)

    def test_local_llm_view_loads_repo_artifacts_without_touching_home(self):
        view = LocalLLMView()
        view.refresh()
        self.assertIn("Latest run", view._summary_lbl.text())
        self.assertIn("guppy-fast", view._manifest_lbl.text())

    def test_topbar_quick_actions_emit_for_live_buttons(self):
        topbar = TopBar()
        actions: list[str] = []
        topbar.quick_action.connect(actions.append)

        topbar._notif_btn.click()
        topbar._term_btn.click()

        self.assertEqual(actions, ["notifications", "terminal"])

    def test_topbar_notification_badge_updates_count_and_severity(self):
        topbar = TopBar()

        topbar.set_notification_badge(3, severity="warn")
        self.assertEqual(topbar._notif_badge.text(), "3")
        self.assertFalse(topbar._notif_badge.isHidden())

        topbar.set_notification_badge(0, severity="info")
        self.assertTrue(topbar._notif_badge.isHidden())

    def test_agent_card_offline_shows_wired_initialize_button(self):
        card = AgentCard("GUPPY")
        card.update_status(online=False, last_seen="now", load_pct=None)

        init_button = card._btn_init
        self.assertFalse(init_button.isHidden())
        self.assertTrue(init_button.isEnabled())  # wired — emits init_requested signal
        self.assertTrue(init_button.toolTip().strip())

    def test_assistant_home_surface_shows_instance_and_background_context(self):
        assistant = AssistantView()

        assistant.set_active_instance("builder-collab")
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
        self.assertIn("Active agent switched to GUPPY", assistant._hero_subtitle.text())
        self.assertIn("Active workspace:", assistant._workspace_summary.text())
        self.assertIn("GUPPY model", assistant._runtime_facts.text())
        self.assertIn("EDGE TTS from persona voice", assistant._runtime_facts.text())
        self.assertIn("Why: simple task classification", assistant._route_facts.text())
        self.assertIn("Evidence: cloud route needs API key; launcher-wide last reply 42 ms", assistant._route_facts.text())
        self.assertIn("warmup complete", assistant._recovery_summary.text().lower())
        self.assertIn("Start here in builder-collab", assistant._entry_hint.text())
        self.assertEqual(assistant._cb_persona.currentText(), "GUPPY")

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
        self.assertIn("Starter loaded: BUILDER REVIEW", assistant._hero_subtitle.text())
        self.assertIn("BUILDER REVIEW is ready", assistant._starter_summary.text())
        self.assertEqual(loaded[-1][0], "builder_review")

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

        self.assertIn("Configured workspaces: 2 / 5", view._summary_lbl.text())
        self.assertIn("Roles:", view._summary_lbl.text())
        self.assertIn("Live workspaces: 1 / 2", view._limits_lbl.text())
        self.assertIn("Role mix:", view._role_mix_lbl.text())
        self.assertIn("Builder 1", view._role_mix_lbl.text())
        self.assertIn("Active workspace fit:", view._collab_lbl.text())
        self.assertIn("Warnings: 1", view._summary_lbl.text())
        self.assertEqual(view._governance_workspace.currentText(), "guppy-primary")
        self.assertIn("runtime_default", view._governance_status.text())
        self.assertIn("hello", view._logs.toPlainText())

        view._governance_workspace.setCurrentText("builder-collab")
        self.assertEqual(view._governance_auth_mode.currentText(), "local_only")
        self.assertIn("query_instance", view._tool_allow.toPlainText())
        self.assertIn("execute_command", view._tool_block.toPlainText())
        self.assertIn("Builder stays local-first", view._governance_note.text())
        view._connector_workspace.setCurrentText("builder-collab")
        view._connector_id.setCurrentText("gmail")
        self.assertTrue(view._connector_enabled.isChecked())
        self.assertEqual(view._connector_account.text(), "sales")
        self.assertIn("compose", view._connector_action_allow.toPlainText())
        self.assertIn("cleanup", view._connector_action_block.toPlainText())
        self.assertIn("connector://gmail", view._connector_endpoint_allow.toPlainText())
        self.assertIn("Builder can draft from sales", view._connector_note.text())

        view.set_logs("builder-collab", [])
        self.assertIn("No recent conversation or ops activity yet for workspace builder-collab", view._logs.toPlainText())

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
        self.assertIn("ACTIVE WORKSPACE:", view._context_lbl.text())
        self.assertIn("APP MGMT", view._boundary_lbl.text())
        self.assertIn("right tray", view._tray_notice_lbl.text().lower())
        self.assertIn("CONFIG CAP REACHED", view._limits_lbl.text())
        self.assertIn("COLLABORATOR CAP REACHED", view._limits_lbl.text())
        self.assertEqual(view._tool_cards["read_file"]._hint_btn.text(), "PRIME HOME")
        self.assertIn("cannot use write file right now", view._tool_cards["write_file"]._scope_lbl.text().lower())
        self.assertIn("governance policy", view._tool_cards["write_file"]._guard_lbl.text().lower())
        self.assertIn("auth mode:", view._tool_cards["query_instance"]._policy_lbl.text().lower())
        self.assertIn("local only", view._tool_cards["query_instance"]._policy_lbl.text().lower())
        self.assertFalse(view._builder_panel._queue_btn.isEnabled())

        view.set_instance_context(
            {"name": "builder-collab", "type": "builder_instance"},
            {"limits": {"configured": 2, "max_configured": 5, "active_runtime": 1, "max_active_runtime": 2}},
        )
        self.assertTrue(view._builder_panel._queue_btn.isEnabled())

    def test_agent_tools_surface_explains_tray_move(self):
        view = ToolsView()
        self.assertFalse(view._cards_host.isHidden())
        self.assertTrue(view._empty_state_lbl.isHidden())
        self.assertIn("right tray", view._tray_notice_lbl.text().lower())

    def test_app_management_view_updates_diagnostics_and_recovery_status(self):
        view = AdvancedView()
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

        self.assertIn("API: HEALTHY", view._health_lbl.text())
        self.assertIn("configured 2/5", view._instances_lbl.text())
        self.assertIn("tts=edge", view._voice_lbl.text())
        self.assertIn("Route evidence:", view._route_health_lbl.text())
        self.assertIn("headroom stable", view._resource_lbl.text())
        self.assertIn("warmup", view._last_recovery_lbl.text().lower())
        self.assertIn("Latest activity:", view._daily_activity_lbl.text())
        self.assertIn("installed surface:", view._windows_install_lbl.text().lower())
        self.assertIn("configured local runtime:", view._windows_runtime_lbl.text().lower())
        self.assertIn("data paths:", view._windows_paths_lbl.text().lower())

    def test_app_management_connector_inventory_emits_normalized_actions(self):
        view = AdvancedView()
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
                    "providers": [{"id": "hubspot", "label": "HubSpot"}],
                    "actions_supported": ["verify", "connect", "disconnect"],
                    "secret_fields": ["CRM_API_KEY"],
                }
            ]
        )

        self.assertEqual(view._connector_cb.currentText(), "crm")
        self.assertIn("Auth kind: api_key", view._connector_state_lbl.text())
        self.assertIn("PARTIAL", view._connector_auth_lbl.text())
        self.assertIn("KEYRING", view._connector_auth_lbl.text())
        self.assertIn("CRM_API_KEY", view._connector_secret_lbl.text())

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

    def test_voices_view_surfaces_persistent_readiness_evidence(self):
        view = VoicesView()

        self.assertIn("Ready now:", view._voice_evidence_lbl.text())
        self.assertIn("Default runtime voice stays", view._voice_evidence_lbl.text())

    def test_app_management_focus_operator_logs_updates_filter(self):
        view = AdvancedView()
        view.focus_operator_logs("WARN", note="opened from quick action")

        self.assertEqual(view._filter_cb.currentText(), "WARN")
        self.assertIn("opened from quick action", view._syslog.toPlainText())

    def test_models_view_default_route_preview_teaches_next_step(self):
        view = ModelsView()

        self.assertIn("Try the kind of question", view._route_preview_lbl.text())

    def test_models_view_persists_local_runtime_preferences(self):
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
                first = models_view_module.ModelsView()
                first._runtime_backend_cb.setCurrentText("LEMONADE")
                first._lemonade_base_url_input.setText("http://localhost:13305/api/v1")
                first._lemonade_role_inputs["lemonade_fast_model"].setCurrentText("Llama-3.2-1B-Instruct-GGUF")
                first._lemonade_role_inputs["lemonade_complex_model"].setCurrentText("Llama-3.2-3B-Instruct-GGUF")
                first._save_runtime_settings()

                second = models_view_module.ModelsView()
                self.assertEqual(second._runtime_backend_cb.currentText(), "LEMONADE")
                self.assertEqual(second._lemonade_role_inputs["lemonade_fast_model"].currentText(), "Llama-3.2-1B-Instruct-GGUF")
                self.assertEqual(second._lemonade_role_inputs["lemonade_complex_model"].currentText(), "Llama-3.2-3B-Instruct-GGUF")
                self.assertEqual(runtime_profile.load_app_settings().get("local_runtime_backend"), "lemonade")
            finally:
                models_view_module.ModelsView._refresh = old_refresh
                models_view_module._RUNTIME_SETTINGS_BACKEND = old_backend_flag
                runtime_profile.SETTINGS_PATH = old_settings_path
                runtime_profile.RUNTIME_DIR = old_runtime_dir

    def test_models_view_surfaces_live_runtime_evidence_from_status(self):
        old_refresh = models_view_module.ModelsView._refresh
        models_view_module.ModelsView._refresh = lambda self: None
        try:
            view = models_view_module.ModelsView()
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
                    },
                }
            )

            self.assertIn("LIVE LANE: PARTIAL", view._runtime_live_lbl.text())
            self.assertIn("server runtime LEMONADE", view._runtime_live_lbl.text())
            self.assertIn("Missing mapped roles: COMPLEX, TEACHING, VAULT", view._runtime_live_lbl.text())
            self.assertIn("Available mapped roles: FAST, CODE", view._runtime_live_lbl.text())
        finally:
            models_view_module.ModelsView._refresh = old_refresh

    def test_app_management_terminal_accepts_focus_and_output_append(self):
        view = AdvancedView()
        view.focus_terminal("terminal opened")

        self.assertIn("terminal opened", view._terminal_output.toPlainText())

    def test_app_management_workflow_recipe_loads_terminal_command(self):
        view = AdvancedView()
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

        self.assertEqual(verify_label, "WINDOWS VERIFY")
        self.assertTrue(any("verify_ollama_runtime.py --prompt ok" in cmd for cmd in verify_commands))
        self.assertEqual(update_label, "WINDOWS UPDATE")
        self.assertTrue(any("pip install -r requirements.txt" in cmd for cmd in update_commands))

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

    def test_chat_timeout_for_local_diagnostic_turns_is_extended(self):
        self.assertGreaterEqual(
            launcher_window.LauncherWindow._chat_timeout_for_request("auto", "Let's run a local diagnostic"),
            60.0,
        )

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
