# Extraction Seams Analysis for Hotspot Files
## TR54-A1: Detailed Seam Contracts for Decomposition

### File: ui/launcher/launcher_window.py (1947 lines)

**Current Role**: Main QMainWindow shell — orchestrates Sidebar, TopBar, StatusPanel, unified launcher stack, and system strip.

**Key Concerns** (grouped by extraction lane):

#### Lane A: Launcher Shell Orchestration (TR54-B1)
**Methods to Extract**:
- `_build_ui()` (lines 279-387) — Layout assembly
- `_wire_signals()` (lines 391-408) — Signal routing hub
- `_on_tab_change()` (lines 517-520) — Tab navigation
- `_apply_start_destination()` (lines 520-522) — Startup routing
- `_resolve_stack_index()` (lines 490-492) — Stack index resolution
- `_visible_nav_index()` (lines 494-497) — Navigation visibility logic

**Extract To**: `ui/launcher/orchestration/launcher_shell_orchestrator.py`
**Contract**: 
- Input: Configuration (nav indices, start destination, embedded mode flag)
- Output: Signal handlers dict, tab change callbacks
- Dependencies: tokenizer, stylesheet, component factories
- Keep in window: Instance state, main loop lifecycle

#### Lane A: Polling & Startup Coordination (TR54-D1, TR54-D4)
**Methods to Extract**:
- `_start_status_poll()` (lines 449-454) — Poll initialization
- `_poll_status()` (lines 455-462) — Main poll loop
- `_complete_startup_phase()` (lines 463-465) — Phase timing
- `_sync_topbar_model_context()` (lines 469-477) — Topbar sync
- `_sync_recovery_outcome()` (lines 466-468) — Recovery state sync
- Related state: `_startup_phase_started`, `_startup_phase_durations_ms`, `_startup_over_budget`, `_poll_warn_ts`

**Extract To**: `ui/launcher/orchestration/launcher_poll_orchestration_impl.py`
**Contract**:
- Input: Health snapshot from runtime, timeout config
- Output: Poll tick events (topbar update, recovery sync, phase completion)
- Dependencies: orchestrate_status_poll (orchestration module)
- Polling interval: 250ms (from current code pattern)
- Startup budget: configurable via GUPPY_STARTUP_PHASE_WARN_MS (default 3000ms)

#### Lane C: Chat & Request Management (TR54-B4 refining)
**Methods to Extract**:
- `_rotate_chat_session()` (lines 755-771) — Session rotation
- `_on_chat_context_changed()` (lines 772-774) — Context change handling
- `_apply_chat_context()` (lines 775-777) — Apply context to runtime
- `_on_cancel_assistant_request()` (lines 781-783) — Request cancellation
- `_finish_request_ui()` (lines 778-780) — UI state finalization
- `_drain_assistant_events()` (lines 734-736) — Event queue draining
- Related state: `_request_in_flight`, `_pending_chat_context`, `_canceled_request_seqs`, `_active_request_seq`, `_chat_session_id`

**Extract To**: `ui/launcher/chat/launcher_chat_orchestration.py`
**Contract**:
- Input: Command string, mode, persona selection, model selection
- Output: Assistant events, request seq tracking
- Max events per tick: 12 (from _MAX_ASSISTANT_EVENTS_PER_TICK)
- Dependencies: launcher_command_flow module

#### Lane D: Instance & Connector Snapshot Management (TR54-B5 refining)
**Methods to Extract**:
- `_fetch_instance_snapshot()` (lines 555-557) — Instance state fetch
- `_load_instance_catalog()` (lines 568-570) — Instance list load
- `_refresh_instance_views()` (lines 571-574) — Instance view refresh
- `_load_instance_history_from_logs()` (lines 561-567) — Log history
- `_fetch_connector_inventory()` (lines 558-560) — Connector inventory
- `_local_instance_snapshot()` (lines 548-554) — Local snapshot build
- `_instances_config_path()` (lines 538-540) — Config path resolution
- `_instance_state_path()` (lines 541-544) — State path resolution
- Related state: `_last_instance_snapshot`, `_instance_snapshot_expires_at`, `_last_connector_inventory_snapshot`, `_connector_inventory_expires_at`, `_instance_histories`

**Extract To**: `ui/launcher/orchestration/launcher_snapshot_cache.py`
**Contract**:
- Input: Force refresh flag, snapshot type (instance, connector, hybrid)
- Output: Cached snapshots with TTL expiry
- Cache TTL: snapshot_expires_at tracking (likely 30-60s)
- Dependencies: workspace_snapshot_support module

#### Lane E: Library & First-Run Management (TR54-B8, TR54-B4)
**Methods to Extract**:
- `_sync_assistant_library_context()` (lines 600-602)
- `_ensure_library_workflow()` (lines 603-606)
- `_on_library_context_requested()` through `_on_library_context_removed()` (lines 610-625)
- `_on_library_root_requested()` through `_on_library_artifact_updated()` (lines 631-643)
- `_refresh_library_surface()` (lines 628-630)
- `_refresh_first_run_banner()` (lines 575-577)
- `_on_first_run_action_requested()` (lines 578-584)
- Related state: `_last_library_context_signature`

**Extract To**: `ui/launcher/chat/launcher_library_orchestration.py`
**Contract**:
- Input: Library action (context, item, workflow request), item kind/path
- Output: Composed message, library surface refresh events
- Dependencies: launcher_library_handlers, library chat submission builder

#### Lane F: Settings & Tool Management (TR54-C4, TR54-C5)
**Methods to Extract**:
- `_on_settings_saved()` (lines 719-721)
- `_on_voice_bindings_changed()` (lines 722-724)
- `_load_tool_states()` (lines 725-727)
- `_on_tool_state_changed()` (lines 728-730)
- `_on_tool_hint_requested()` (lines 787-794)
- `_on_tool_management_requested()` (lines 795-798)
- Related state: `_last_tools_context_signature`

**Extract To**: `ui/launcher/tools/launcher_tools_state_machine.py`
**Contract**:
- Input: Tool key, enabled/disabled flag, settings dict, tool management action
- Output: Tool state change events, runtime updates
- Dependencies: launcher_tools_coordination module

#### Lane G: Connector Action Orchestration (TR54-B10)
**Methods to Extract**:
- `_on_connector_action_requested()` (lines 706-708)
- `_on_connector_guided_link_requested()` (lines 709-711)
- `_run_connector_action_request()` (lines 694-696)
- `_start_connector_action_async()` (lines 697-699)
- `_start_connector_guided_link_async()` (lines 700-702)
- `_drain_connector_action_events()` (lines 703-705)
- Related state: `_connector_action_events`

**Extract To**: `ui/launcher/accounts/launcher_connector_orchestration.py`
**Contract**:
- Input: Connector action payload (type, account_id, action_type)
- Output: Action events with success/failure status
- Async: Runs in background thread with event queue
- Dependencies: launcher_connector_handlers

#### Lane H: Recovery & Diagnostics (TR54-E5, TR54-D5)
**Methods to Extract**:
- `_on_recovery_requested()` (lines 939-941)
- `_run_recovery_request()` (lines 942-944)
- `_drain_recovery_events()` (lines 784-786)
- `_push_recovery_outcome()` (lines 485-489)
- `_classify_recovery_summary()` (lines 478-481)
- `_format_recovery_summary()` (lines 482-484)
- Related state: `_recovery_events`, `_last_recovery_signature`

**Extract To**: `ui/launcher/diagnostics/launcher_recovery_orchestration.py`
**Contract**:
- Input: Recovery action name, recovery event dict
- Output: Recovery outcome with classification, formatted summary
- Max events per tick: 12 (from _MAX_RECOVERY_EVENTS_PER_TICK)
- Dependencies: recovery_coordination module

#### Lane I: Instance Operations (TR54-B11)
**Methods to Extract**:
- `_on_instance_delete_requested()` (lines 712-714)
- `_on_instance_logs_requested()` (lines 715-718)
- `_available_instance_names()` (lines 802-810)
- `_preferred_builder_instance_name()` (lines 811-814)

**Extract To**: `ui/launcher/instances/launcher_instance_operations.py`
**Contract**:
- Input: Instance name, action type (delete, logs)
- Output: Confirmation/status events
- Dependencies: launcher_instance_handlers

#### Lane J: Model & Mode Management (TR54-B5)
**Methods to Extract**:
- `_on_model_selected()` (lines 945-947)
- `_on_runtime_settings_saved()` (lines 948-950)
- `_shell_model_loadout_summary()` (lines 498-511)
- `_sync_shell_model_summary()` (lines 512-516)
- `_assistant_model_id()` (lines 749-751)
- `_validate_mode_ready()` (lines 752-754)
- `_required_local_model_for_mode()` (lines 745-748)
- Related state: `_embedded_online`

**Extract To**: `ui/launcher/models/launcher_model_orchestration.py`
**Contract**:
- Input: Model ID, mode string, active model override
- Output: Model loadout summary, readiness status
- Dependencies: launcher_command_flow module

#### Lane K: Misc Command Handlers (TR54-B2, TR54-B3)
**Methods to Extract**:
- `_on_search()` (lines 951-954)
- `_on_quick_action()` (lines 979-981)
- `_on_home_starter_requested()` (lines 966-968)
- `_on_assistant_command()` (lines 969-978)
- `_refresh_notification_badge()` (lines 982-984)
- `_on_mic_requested()` (lines 992-994)
- `_toggle_status_panel()` (lines 526-528)
- `_toggle_sidebar()` (lines 529-531)
- `_set_status_panel_visible()` (lines 523-525)

**Extract To**: `ui/launcher/commands/launcher_command_dispatch.py`
**Contract**:
- Input: Command string, action string, query string
- Output: View state changes, topbar updates
- Dependencies: launcher_shell_support (QuickActionPlan), launcher_nav_handlers

#### Lane L: Personalization & Signal Setup (TR54-B2)
**Methods to Extract**:
- `_bootstrap_personalization_scaffold_worker()` (lines 388-390)
- `_wire_signals()` (already in Lane A) — Also handles personalization signal wiring
- `_wire_tools_trace_adapter()` (lines 394-408)
- `_refresh_personalization_state()` (lines 424-430)
- `_refresh_tools_debug_surface()` (lines 409-413)
- `_update_route_preview()` (lines 431-434)
- `_set_daily_activity()` (lines 435-437)
- `_sync_right_tray()` (lines 438-441)

**Extract To**: `ui/launcher/orchestration/launcher_signal_setup.py`
**Contract**:
- Input: Preferred persona, component references (topbar, sidebar, views)
- Output: Signal connections registered, tray synced, preview updated
- Dependencies: launcher_signal_personalization module

#### Lane M: Automation Testing & Debugging (TR54-F1)
**Methods to Extract**:
- `_automation_test_snapshot()` (lines 851-871)
- `_sync_automation_test_state()` (lines 872-890)
- `_queue_builder_task()` (lines 891-907)
- `_write_automation_report()` (lines 908-914)
- `_approve_latest_builder_task()` (lines 915-917)
- `_on_builder_task_requested()` (lines 918-924)
- `_on_automation_action_requested()` (lines 925-932)
- `_drain_deferred_syslog()` (lines 414-423)
- Related state: `_last_command`

**Extract To**: `ui/launcher/testing/launcher_automation_harness.py`
**Contract**:
- Input: Action string, builder workspace preference, evidence pack request
- Output: Automation snapshot, task approval, test report paths
- Max syslog per tick: 24 (from _MAX_DEFERRED_SYSLOG_PER_TICK)
- Dependencies: automation_test_coordination module

#### Lane N: Windows-Specific Operations
**Methods to Extract**:
- `_on_windows_ops_requested()` (lines 963-965)
- `_windows_ops_plan()` (lines 955-958)
- `_windows_ops_recipe()` (lines 959-962)
- Related state: `_active_windows_ops_chain`

**Extract To**: Handled by `LauncherWindowsOpsMixin` (already extracted)

#### Lane O: Misc Utilities & Helpers
**Methods to Extract**:
- `_humanize_chat_error()` (lines 737-740)
- `_chat_timeout_for_request()` (lines 741-744)
- `_build_launcher_state_snapshot()` (lines 585-599)
- `_build_sys_strip()` (lines 442-444)
- `_update_sys_strip()` (lines 445-448)
- `_log_launcher_event()` (lines 731-733)
- `_tool_prompt_for_home()` (lines 799-801)
- `_user_test_evidence_path()` (lines 815-817)
- `_user_test_evidence_summary_path()` (lines 818-821)
- `_display_repo_path()` (lines 822-825)
- `_latest_stress_report_path()` (lines 826-828)
- `_recent_launcher_event_summaries()` (lines 829-832)
- `_write_user_test_evidence_summary()` (lines 833-835)
- `_write_user_test_evidence_pack()` (lines 836-850)
- `_event_level()` (lines 208-210)
- `_default_governance_snapshot()` (lines 545-547)
- `_initialize_embedded_agent()` (lines 933-935)
- `_on_agent_init_requested()` (lines 936-938)

**Extract To**: Multiple utility modules (see specific lane assignments)
- Voice/system: `ui/launcher/voice/launcher_voice_support.py`
- Snapshots: `ui/launcher/orchestration/launcher_snapshot_builders.py`
- Telemetry: `ui/launcher/testing/launcher_telemetry_support.py`

---

### File: ui/launcher/views/settings_view.py (643 lines)

**Current Role**: Settings hub UI — tabs, section routing, edit/save behavior, persona management.

**Key Concerns** (grouped by extraction):

#### Lane F: Settings Form Management (TR54-B9)
**Methods to Extract**:
- `_build_ui()` (lines 81-154) — Layout assembly (~80 lines)
- `_set_settings_section()` (lines 172-192) — Section routing
- `_load()` (lines 193-196) — Form data load
- `show_settings_section()` (lines 161-171) — Public interface
- `set_embed_mode()` (lines 155-160) — Embedding control
- Tab management state

**Extract To**: `ui/launcher/views/settings_shell_view.py`
**Contract**:
- Input: Section string, embed mode flag
- Output: Tab signal, section visibility control
- Depends on: child panel components (accounts, device, operations, snapshot, terminal, workflow)

#### Lane F: Persona Management (TR54-B9)
**Methods to Extract**:
- `_persona_items()` (lines 278-281)
- `_refresh_persona_lists()` (lines 282-311)
- `_selected_persona()` (lines 312-317)
- `_populate_persona_form()` (lines 318-342)
- `_on_persona_selected()` (lines 347-350)
- `_on_scope_changed()` (lines 351-355)
- `_next_persona_id()` (lines 356-365)
- `_create_persona()` (lines 366-391)
- `_delete_persona()` (lines 392-407)
- `_build_persona_config()` (lines 408-481)

**Extract To**: `ui/launcher/views/settings_persona_manager.py`
**Contract**:
- Input: Persona ID, scope (selected), form values
- Output: Persona list model, updated persona config
- Depends on: persona options from runtime settings

#### Lane F: Runtime & Model Settings (TR54-B9, TR54-C4)
**Methods to Extract**:
- `_load_runtime_settings()` (lines 197-217)
- `_load_model_binding_options()` (lines 247-258)
- `_set_persona_controls_enabled()` (lines 259-277)
- `_refresh_preview()` (lines 482-500)
- `_save()` (lines 501-570)
- Settings state management

**Extract To**: `ui/launcher/views/settings_runtime_config.py`
**Contract**:
- Input: Settings dict, save/load triggers
- Output: Saved settings dict, validation errors
- Depends on: launcher_tools_coordination (_on_settings_saved)

#### Lane F: Misc Settings Helpers
**Methods to Extract**:
- `set_hardware_label()` (lines 571-573)
- `set_recovery_status()` (lines 574-576)
- Static helpers: `_deepcopy_json()`, `_slugify()`

**Extract To**: Keep in settings_view.py as utility methods (< 10 lines each)

---

### File: ui/launcher/views/models_view.py (603 lines)

**Current Role**: Models hub UI — model selection, runtime/library source UI, operation/health display.

**Key Concerns** (grouped by extraction):

#### Lane D: Models Hub Shell (TR54-B5)
**Methods to Extract**:
- `_build_ui()` — Layout assembly
- View mode state management
- Runtime/Library toggle
- Status display

**Extract To**: `ui/launcher/views/models_hub_shell.py`
**Contract**:
- Input: View mode (runtime/library), filter state
- Output: Model selection signal, view mode change signal
- Depends on: child panels (models_library_panel, models_runtime_library, etc.)

#### Lane D: Model Selection & Filtering (TR54-B5)
**Methods to Extract**:
- Model list rendering
- Selection callbacks
- Filter/search logic
- Runtime/library model sync

**Extract To**: `ui/launcher/views/models_selection_panel.py`
**Contract**:
- Input: Model list, selected model ID, mode (runtime/library)
- Output: Selection change signal, model info update
- Depends on: models section support modules

---

### File: ui/launcher/views/voices_view.py (600 lines)

**Current Role**: Voice configuration UI — voice assignment controls, backend evidence, diagnostics.

**Key Concerns** (grouped by extraction):

#### Lane D: Voice Assignment Controls (TR54-B6)
**Methods to Extract**:
- Voice binding UI
- Assignment form
- Save/load voice settings
- Validation logic

**Extract To**: `ui/launcher/views/voices_assignment_panel.py`
**Contract**:
- Input: Voice bindings dict, available voices list
- Output: Updated bindings, validation status
- Depends on: launcher_voice_strip module

#### Lane D: Voice Diagnostics & Evidence (TR54-B6)
**Methods to Extract**:
- Voice capture testing
- Microphone diagnostics
- Voice model evidence display
- Health status

**Extract To**: `ui/launcher/views/voices_diagnostics_panel.py`
**Contract**:
- Input: Voice health snapshot, capture enable flag
- Output: Test results, diagnostic status
- Depends on: GuppyVoice backend

---

### File: ui/launcher/views/models_sections.py (594 lines)

**Current Role**: Model sections UI — library UI, runtime source UI, route evidence, operation/health.

**Key Concerns** (grouped by extraction):

#### Lane D: Library Model Rendering (TR54-B5)
**Methods to Extract**:
- Library model card rendering
- Model metadata display
- Library-specific operations

**Extract To**: `ui/launcher/views/models_library_section.py`
**Contract**:
- Input: Library model list, selected model
- Output: Model card selection, library action signal
- Depends on: models_library_panel

#### Lane D: Runtime Model Evidence (TR54-B5)
**Methods to Extract**:
- Runtime model status display
- Health/operation evidence
- Background job tracking

**Extract To**: `ui/launcher/views/models_runtime_evidence_panel.py`
**Contract**:
- Input: Runtime health snapshot, worker list
- Output: Model readiness status, operation evidence
- Depends on: models_runtime_support, models_runtime_workers

---

## Merge Choreography Plan (TR54-A3)

### Wave 1: Foundation Extraction (Week 1-2)
1. **Snapshot Cache Layer** (`launcher_snapshot_cache.py`)
   - Extracted from: `launcher_window.py` (snapshot/cache methods)
   - No dependencies on other new modules
   - Baseline test: Cache TTL, refresh semantics

2. **Polling Orchestration** (`launcher_poll_orchestration_impl.py`)
   - Extracted from: `launcher_window.py` (polling methods)
   - Depends on: snapshot cache (for health refresh)
   - Baseline test: Poll tick rate, startup phase timing

3. **Signal Setup** (`launcher_signal_setup.py`)
   - Extracted from: `launcher_window.py` (signal wiring, personalization)
   - Depends on: components (topbar, sidebar, views)
   - Baseline test: Signal connections established, no cycles

### Wave 2: Orchestration Modules (Week 2-3)
4. **Shell Orchestrator** (`launcher_shell_orchestrator.py`)
   - Extracted from: `launcher_window.py` (build_ui, tab change, nav)
   - Depends on: signal setup, snapshot cache
   - Baseline test: Tab navigation, start destination routing

5. **Chat Orchestration** (`launcher_chat_orchestration.py`)
   - Extracted from: `launcher_window.py` (chat/session/context methods)
   - Depends on: shell orchestrator (for view access)
   - Baseline test: Session rotation, context application

6. **Library Orchestration** (`launcher_library_orchestration.py`)
   - Extracted from: `launcher_window.py` (library methods)
   - Depends on: shell orchestrator
   - Baseline test: Library context update, surface refresh

### Wave 3: State Machine Modules (Week 3-4)
7. **Tools State Machine** (`launcher_tools_state_machine.py`)
   - Extracted from: `launcher_window.py` (tool state, settings)
   - Depends on: chat orchestration (for context refresh)
   - Baseline test: Tool enable/disable, settings propagation

8. **Model Orchestration** (`launcher_model_orchestration.py`)
   - Extracted from: `launcher_window.py` (model selection, mode validation)
   - Depends on: tools state machine (for tool readiness)
   - Baseline test: Model selection, mode readiness check

9. **Connector Orchestration** (`launcher_connector_orchestration.py`)
   - Extracted from: `launcher_window.py` (connector action handling)
   - Depends on: snapshot cache (for connector inventory)
   - Baseline test: Action async execution, event draining

### Wave 4: Operations & Diagnostics (Week 4-5)
10. **Instance Operations** (`launcher_instance_operations.py`)
    - Extracted from: `launcher_window.py` (instance CRUD, logs)
    - Depends on: connector orchestration (for linked account context)
    - Baseline test: Instance delete, log retrieval

11. **Recovery Orchestration** (`launcher_recovery_orchestration.py`)
    - Extracted from: `launcher_window.py` (recovery flow)
    - Depends on: polling orchestration (for health context)
    - Baseline test: Recovery action dispatch, outcome classification

12. **Command Dispatch** (`launcher_command_dispatch.py`)
    - Extracted from: `launcher_window.py` (command handlers)
    - Depends on: shell orchestrator, tools state machine, model orchestration
    - Baseline test: Quick action resolution, search dispatch

### Wave 5: View-Level Decomposition (Week 5-6)
13. **Settings Views** (per-file extraction)
    - `settings_shell_view.py`, `settings_persona_manager.py`, `settings_runtime_config.py`
    - Extracted from: `settings_view.py`
    - Depends on: tools state machine (for settings save)

14. **Models Views** (per-file extraction)
    - `models_hub_shell.py`, `models_selection_panel.py`
    - Extracted from: `models_view.py`
    - Depends on: model orchestration

15. **Voices Views** (per-file extraction)
    - `voices_assignment_panel.py`, `voices_diagnostics_panel.py`
    - Extracted from: `voices_view.py`
    - Depends on: model orchestration (for readiness)

16. **Models Sections Views** (per-file extraction)
    - `models_library_section.py`, `models_runtime_evidence_panel.py`
    - Extracted from: `models_sections.py`
    - Depends on: model orchestration, snapshot cache

### Wave 6: Testing & Automation Harness (Week 6-7)
17. **Automation Harness** (`launcher_automation_harness.py`)
    - Extracted from: `launcher_window.py` (test/automation methods)
    - Depends on: all above modules (for snapshot generation)
    - Baseline test: Test snapshot generation, report writing

### Integration Points

**launcher_window.py** remains as the main window class with:
- Init and teardown lifecycle
- Main event loop integration
- Component instantiation
- Top-level state coordination (time tracking, request sequencing)

**Signal Flow Order**:
1. Window init → signal setup → personalization bootstrap
2. First poll tick → snapshot cache refresh → poll orchestration
3. User action → command dispatch → appropriate state machine
4. State machine → orchestration module → view update signal

**Testing Strategy**:
- Unit tests per extracted module (mocked dependencies)
- Integration tests per wave (real dependency chains)
- Smoke tests on launcher_window main loop (full integration)
- Regression suite on view decomposition (UI responsiveness)

---

## Success Criteria

- [ ] All seam contracts document: Input, output, dependencies, timing/rate constraints
- [ ] Merge choreography prevents broken intermediate states
- [ ] Each extracted module < 550 lines (target: < 450 lines)
- [ ] launcher_window.py reaches < 800 lines after Wave 1-2
- [ ] No cyclic dependencies between extracted modules
- [ ] All signal connections remain functional through decomposition
- [ ] Startup timing budget respected at each wave
- [ ] Zero regression in automation test support
