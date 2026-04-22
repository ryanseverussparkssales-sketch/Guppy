# M2 Implementation Backlog

This backlog is sequenced to satisfy the precondition for M2 work: launcher chat and builder flows must be working first.

## Phase 0: Pre-M2 Stabilization

### Exit Criteria
- Launcher assistant chat can submit and receive a successful response from `/chat`.
- Guided persona builder and guided provider routing save valid runtime configs and reload cleanly.
- Hub/API bootstrap failures are surfaced as actionable diagnostics rather than silent offline states.
- Tool execution no longer fails with the `_TOOL_GUARD_LOCK` regression.

### Last-Session Failures To Resolve First
1. Launcher chat returned repeated `HTTP Error 401: Unauthorized` after embedded session initialization.
2. Recovery repeatedly reported `api process started but not yet reachable` and stale/missing heartbeat files.
3. Hub startup failed once with `'list' object has no attribute 'get'`.
4. Runtime request logging recorded `name '_TOOL_GUARD_LOCK' is not defined` for a failed Guppy request.
5. Hub logs show repeated fast crash/restart loops for `guppy`, `merlin`, and `council`.

### Workstream 0.1: Restore Launcher Auth Handshake
Goal: make launcher chat reliably authenticate against the local API.

File order:
1. `ui/launcher/launcher_window.py`
   - Rebuild bearer token after daemon/API restart attempts.
   - Retry auth self-check when it fails instead of permanently setting `_auth_self_checked`.
   - On `401` from `/chat`, invalidate token, rebuild it once, and retry once.
   - Log auth error codes separately from generic command failures.
2. `src/guppy/api/auth.py` (`compat_shims/guppy_api_auth.py` retained only as a fallback shim)
   - Keep launcher-local token mint/verify contract deterministic.
   - Add a small helper or clearer error code path if the JWT secret is unavailable or mismatched.
3. `src/guppy/api/server.py` (wrapper: `guppy_api.py`)
   - Confirm `/auth/self-check` and `/chat` use the same auth dependency behavior.
   - If needed, add a launcher-safe local diagnostics path that explains auth mismatch without weakening security.
4. `tests/unit/test_security_hardening.py`
   - Extend existing launcher token coverage to include post-restart or token-refresh behavior.
5. `tests/smoke/smoke_api.py`
   - Add an explicit launcher-auth smoke path for local verification.

### Workstream 0.2: Stabilize Builder And Runtime Config Shape
Goal: ensure guided builder flows cannot poison startup/runtime state.

File order:
1. `utils/personalization_config.py`
   - Add normalization for legacy or malformed JSON shapes before `.get(...)` usage reaches the rest of the app.
   - Return validated dict payloads or reset to safe defaults with diagnostics.
2. `ui/launcher/views/settings_view.py`
   - Harden guided persona/provider load and save flows against malformed configs.
   - Show validation failures inline with the exact file and reason.
   - Reload builder state from normalized config after save.
3. `guppy_api.py`
   - Validate personalization scaffold at startup and log a specific bootstrap failure instead of generic offline symptoms.
4. `tests/test_personalization_config_scaffold.py`
   - Add malformed-input regression cases for list/object mismatches.
5. `runtime/persona_config.json`
6. `runtime/provider_registry.json`
   - Verify current runtime examples still satisfy the stricter validation path.

### Workstream 0.3: Fix Tool Runner Regression
Goal: eliminate runtime failures caused by the tool metrics/circuit-breaker path.

File order:
1. `guppy_core/tool_metrics.py`
   - Verify lock import/state cannot fail under current import order.
   - Add defensive fallback or clearer exception reporting if the metrics state is unavailable.
2. `guppy_core/debug_flags.py`
   - Keep the shared metrics/lock state authoritative in one module.
3. `guppy_core/tool_runner.py`
   - Guard error-reporting path so a metrics failure cannot mask the underlying tool result.
4. `guppy_core/__init__.py`
   - Confirm re-export order does not introduce circular import hazards.
5. `tests/`
   - Add a targeted regression test for tool metrics initialization and `run_tool()` failure handling.

### Workstream 0.4: Validate Runtime Recovery
Goal: make recovery buttons useful once chat/auth/bootstrap are fixed.

File order:
1. `ui/launcher/launcher_window.py`
   - Distinguish `API unreachable`, `auth failed`, and `runtime stale` in recovery outcomes.
2. `guppy_api.py`
   - Confirm `/repair`, `/status`, and `/startup/check` remain reachable after restart.
3. `guppy_hub.py` or hub supervisor module used by startup path
   - Fix any remaining crash-loop classification gaps if process exits are being mislabeled.
4. `runtime/launcher_events.jsonl`
5. `runtime/hub.log`
   - Re-run validation and confirm the repeated stale/offline loop is gone.

## Phase 1: Home Chat As Primary Surface

Only begin after Phase 0 exit criteria are met.

Status: partially complete as of 2026-04-14.
Completed in repo now:
1. Home is the default launcher surface.
2. Active-instance, background activity, runtime facts, and recovery summary are routed into Home.
3. Right rail is trimmed toward background ops instead of primary chat context.
4. Navigation labels now follow the Home, Instance Manager, Agent Tools, App Mgmt model.
5. Agent Tools and App Mgmt now have distinct launcher surfaces instead of legacy mixed placeholders.
Remaining in this phase:
1. Finish moving any leftover mixed operational detail out of Home-adjacent legacy surfaces.
2. Keep refining the split so Agent Tools gains invocation flow while App Mgmt stays app-scoped.

File order:
1. `ui/launcher/launcher_window.py`
   - Make assistant/home the canonical entry surface and route background status into it.
2. `ui/launcher/views/assistant_view.py`
   - Add explicit active-instance context, session state, and background-task visibility.
3. `ui/launcher/components/status_panel.py`
   - Rebalance status detail so the home chat remains primary, not secondary.
4. `ui/launcher/components/topbar.py`
   - Align navigation labels with the new tab model.
5. `tests/ui_launcher_*`
   - Add smoke coverage for default-tab and active-agent switching.

## Phase 2: Instance Manager Foundation

Status: foundation now live as of 2026-04-14.
Completed in repo now:
1. `config/instances.json` and `runtime/instance_state.json` are persisted and normalized.
2. `GET /instances`, `POST /instances`, `POST /instances/{name}/activate`, `DELETE /instances/{name}`, and `GET /instances/{name}/logs` exist.
3. Launcher has a dedicated `InstanceManagerView` wired into the main stack.
4. Launcher chat and bounded inter-instance query paths now write per-instance JSONL logs.
Remaining in this phase:
1. Add richer lifecycle affordances beyond the current inline create or update form.
2. Expand server-side inter-instance orchestration beyond bounded single-query M2.0 behavior.
3. Enforce the 5 configured / 2 runtime-active bounds deeper than the current API + launcher feedback layer.

File order:
1. `config/instances.json`
   - Add persisted instance definitions.
2. `runtime/instance_state.json`
   - Add runtime state snapshot for active/background instances.
3. `guppy_api.py`
   - Add bounded instance CRUD and instance status endpoints.
4. `ui/launcher/launcher_window.py`
   - Register the new Instance Manager view and route status updates into it.
5. `ui/launcher/views/instance_manager_view.py`
   - New view for configured vs active instances, logs, and lifecycle actions.
6. `tests/`
   - API and UI coverage for the 5 configured / 2 active bounds.

## Phase 3: Split Agent Tools From App Management

Status: first-pass split now live as of 2026-04-14.
Completed in repo now:
1. `ui/launcher/views/tools_view.py` is now an instance-scoped Agent Tools catalog.
2. `ui/launcher/views/advanced_view.py` has been repurposed into App Management.
3. Recovery actions, diagnostics, and operator logs are no longer presented as mixed instance tooling.
Remaining in this phase:
1. Add real tool invocation cards and dry-run UI for write/code tools.
2. Tie tool visibility to server-side capability enforcement.
3. Remove or further isolate any remaining legacy compatibility affordances.

File order:
1. `ui/launcher/views/tools_view.py`
   - Refactor current tool controls into `Agent Tools`.
2. `ui/launcher/views/advanced_view.py`
   - Either repurpose to `App Management` or replace with a dedicated view.
3. `ui/launcher/components/sidebar.py`
   - Update navigation labels and ordering.
4. `ui/launcher/launcher_window.py`
   - Replace old Advanced tab wiring.
5. `tests/`
   - Update launcher tab expectations.

## Phase 4: Server-Side Capability Enforcement

File order:
1. `config/tool_permissions.json`
2. `guppy_core/tool_runner.py`
3. `guppy_core/tool_registry.py`
4. `guppy_api.py`
5. `tests/test_security_hardening.py`

Implement server-side permission checks here before any UI-only tool gating is considered complete.

## Phase 5: Inter-Instance Query MVP

File order:
1. `guppy_api.py`
   - Add bounded synchronous `POST /instances/{name}/query`.
2. `runtime/logs/`
   - Add per-instance structured logging with redaction policy.
3. `ui/launcher/views/assistant_view.py`
   - Expose query-to-instance from the home surface.
4. `ui/launcher/views/instance_manager_view.py`
   - Show busy/timeout/ok state.
5. `tests/`
   - Cover `ok|busy|timeout` contract and single in-flight limit.

## Phase 6: Polish, Launch Gates, And Docs

File order:
1. `M2_LAUNCH_CHECKLIST.md`
2. `M2_UI_ARCHITECTURE_GUIDE.md`
3. `M2_UI_QUICK_REFERENCE.md`
4. `M2_SCOPE_LOCK.md`
5. `ROADMAP.md`

Update these only after implementation reality is verified.

## Recommended Execution Rhythm

1. Finish all Phase 0 work and rerun chat/builder smoke tests.
2. Merge Phase 1 and Phase 2 only after Phase 0 is stable for at least one full launcher session.
3. Delay Phase 5 until Phase 4 capability enforcement is in place.
4. Treat docs as trailing artifacts after code and tests pass.

