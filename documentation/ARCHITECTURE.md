# Architecture

Last verified: 2026-04-16

## 1) Runtime Entry Points

- Canonical launcher app: `src/guppy/apps/launcher_app.py`
- Canonical hub app: `src/guppy/apps/hub_app.py`
- Canonical launch CLI: `src/guppy/cli/launch.py`
- Canonical API server: `src/guppy/api/server.py`
- Canonical API auth: `src/guppy/api/auth.py`
- Canonical inference router: `src/guppy/inference/router.py`
- Canonical daemon: `src/guppy/daemon/daemon.py`

Thin root compatibility wrappers now remain only for stable front-door launch paths:

- `guppy_launcher.py`, `guppy_hub.py`, `guppy_api.py`
- secondary migrated shims now live under `compat_shims/`

## 2) UI Architecture

### Primary daily UI

- Shell: `ui/launcher/launcher_window.py`
- Views: `ui/launcher/views/`
- Components: `ui/launcher/components/`

### Background collaboration and historical compatibility

- Supported daily path: unified launcher plus configured instances from `config/instances.json`
- Default runtime instances: foreground `guppy-primary` and optional background `builder-collab`
- Guided internal automation testing uses the same launcher shell, with `bin/launch_automation_test.bat` or `--start automation-test` routing directly into App Mgmt
- Historical specialist material is retained under `compat_shims/legacy_surfaces/` and `src/guppy/merlin/`, but not as active desktop entrypoints

## 3) Core Runtime Packages

- `guppy_core/` - tool registry, runner, prompts, metrics, policy
- `src/guppy/inference/` - routing and dispatch policy
- `src/guppy/merlin/` - teaching-persona content and legacy compatibility helpers
- `src/guppy/memory/` - persistent and semantic memory
- `utils/personalization_config.py` - persona defaults, prompt overlays, and the seeded `main_guppy` profile-summary path
- `src/guppy/voice/` - TTS/STT and wake-word handling
- `src/guppy/daemon/` - reminders, ambient watcher, proactive loop
- `src/guppy/tools/` - GitHub/media helper modules
- `src/guppy/integrations/` - CRM/VoIP stubs
- `src/guppy/debug/` - debug console
- `src/guppy/ui/` - theme and shared UI-specific logic

## 4) Background Services and Telemetry

- Hub orchestration: `src/guppy/hub/`
- Session/event logs: `runtime/*.jsonl`
- Operational telemetry mirror: `runtime/ops_telemetry.sqlite3`
- Review utilities: `tools/review_agent_performance.py`, `tools/review_router_scorecard.py`

## 5) Security-Critical Flows

### JWT auth

- Module: `src/guppy/api/auth.py`
- Secret source order:
  1. OS credential store key `jwt_secret` via `utils/secret_store.py`
  2. Fallback `GUPPY_JWT_SECRET` environment variable

### Repair endpoint auth

- Endpoint: `POST /repair`
- Guard: `_require_repair_token` in `src/guppy/api/server.py`
- Token generated per API process startup
- Storage source order:
  1. OS credential store key `repair_token`
  2. Fallback `runtime/repair_token.txt`
- Launcher request path: `ui/launcher/launcher_window.py` adds `X-Repair-Token`
- Refresh path: `GET /repair-token/refresh` requires both localhost origin and a valid bearer token
- Launcher refresh path: `ui/launcher/launcher_window.py` re-syncs the repair token with bearer auth after a mismatch response

### Concurrent launcher chat safety

- UI request sequence id: `self._active_request_seq`
- Worker events carry request sequence
- Event drain discards stale responses to prevent cross-stream completions

### Launcher auth handshake safety

- Endpoint: `GET /auth/self-check`
- Launcher performs one-time auth self-check when API becomes reachable
- Event log includes token source and reason-coded error detail on failure

## 5a) Personalization and Memory Continuity

- Default persona config lives in `runtime/persona_config.json`
- Default voice bindings live in `runtime/voice_bindings.json`
- `main_guppy` is the seeded default persona and includes a curated `profile_summary` injected through `utils/personalization_config.py`
- `src/guppy/memory/memory.py` promotes user-authored durable preferences, decisions, and scope cues into semantic memory after chat persistence

## 6) Database Architecture

Connection policy is centralized in `utils/db_utils.py`.

Modules using shared connection policy include:

- `utils/operational_telemetry.py`
- `src/guppy/api/server.py` telemetry query path
- `src/guppy/memory/memory.py`
- `src/guppy/memory/semantic.py`
- `src/guppy/debug/console.py`

SQLite defaults:

- WAL journaling
- Configurable synchronous mode
- Configurable busy timeout
- Foreign key enforcement
- Memory temp store

## 7) Test Layout

- `tests/unit/` - default fast regression suite
- `tests/integration/` - runtime or hardware-adjacent tests
- `tests/smoke/` - manual or broader smoke/stress validation

`pytest.ini` runs `tests/unit` and `tests/integration` by default.

## 8) Quality Guardrails

Current architecture checks:

1. `tools/check_architecture_boundaries.py`
2. `tools/check_wrapper_integrity.py`
3. `tools/check_new_module_line_cap.py`
4. `tools/check_doc_ownership.py`
5. `tools/check_core_surface_integrity.py`
6. `tools/check_runtime_artifact_hygiene.py`

These checks are exercised in CI guardrail matrix scope (`delta`, `baseline`) with runtime artifact hygiene enforced on `delta` scope.
