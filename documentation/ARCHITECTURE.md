# Architecture

Last verified: 2026-04-13

## 1) Runtime Entry Points

- Launcher wrapper: `guppy_launcher.py` (thin compatibility wrapper)
- Launcher app: `src/guppy/apps/launcher_app.py`
- Hub wrapper: `guppy_hub.py`
- Hub app: `src/guppy/apps/hub_app.py`
- API server: `guppy_api.py`
- CLI surface: `guppy_agent.py`

## 2) UI Architecture

### Primary daily UI

- Shell: `ui/launcher/launcher_window.py`
- Views: `ui/launcher/views/`
- Components: `ui/launcher/components/`

### Specialist and legacy surfaces

- Specialist: `merlin_ui.py`, `council_ui.py`
- Legacy monolith: `guppy_ui.py`

## 3) Background Services

- Daemon: `guppy_daemon.py`
- Hub orchestration: `src/guppy/hub/`
- Session/event logs: `runtime/*.jsonl`
- Operational telemetry mirror: `runtime/ops_telemetry.sqlite3`

## 4) Security-Critical Flows

### JWT auth

- Module: `guppy_api_auth.py`
- Secret source order:
  1. OS credential store key `jwt_secret` via `utils/secret_store.py`
  2. Fallback `GUPPY_JWT_SECRET` environment variable

### Repair endpoint auth

- Endpoint: `POST /repair`
- Guard: `_require_repair_token` in `guppy_api.py`
- Token generated per API process startup
- Storage source order:
  1. OS credential store key `repair_token`
  2. Fallback `runtime/repair_token.txt`
- Launcher request path: `ui/launcher/launcher_window.py` adds `X-Repair-Token`

### Concurrent launcher chat safety

- UI request sequence id: `self._active_request_seq`
- Worker events carry request sequence
- Event drain discards stale responses to prevent cross-stream completions

### Launcher auth handshake safety

- Endpoint: `GET /auth/self-check`
- Launcher performs one-time auth self-check when API becomes reachable
- Event log includes token source and reason-coded error detail on failure

## 5) Database Architecture

Connection policy is centralized in `utils/db_utils.py`.

Modules using shared connection policy:

- `utils/operational_telemetry.py`
- `guppy_api.py` telemetry query path
- `guppy_memory.py`
- `guppy_semantic_memory.py`
- `guppy_ui.py` response cache
- `debug_console.py` DB access

SQLite defaults:

- WAL journaling
- Configurable synchronous mode
- Configurable busy timeout
- Foreign key enforcement
- Memory temp store

## 6) Quality Guardrails

Current architecture checks:

1. `tools/check_architecture_boundaries.py`
2. `tools/check_wrapper_integrity.py`
3. `tools/check_new_module_line_cap.py`
4. `tools/check_doc_ownership.py`
5. `tools/check_core_surface_integrity.py`
6. `tools/check_runtime_artifact_hygiene.py`

These checks are exercised in CI guardrail matrix scope (`delta`, `baseline`) with runtime artifact hygiene enforced on `delta` scope.
