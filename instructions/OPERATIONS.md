# Operations Instructions

Last verified: 2026-04-16

This is the primary operator runbook for the current codebase.

## 1) Startup

1. Activate environment and launch the app:
   - `python src/guppy/cli/launch.py launcher`
   - Automation-test entrypoint: `bin\launch_automation_test.bat`
2. Launcher implementation is in `src/guppy/apps/launcher_app.py`.
3. Wrapper `guppy_launcher.py` is compatibility-only and should stay thin.
4. Use `src/guppy/cli/launch.py` for Hub, API, and GuppyPrime launches.
5. Do not recreate or depend on deleted Merlin/Council desktop entrypoints; use configured launcher instances such as `builder-collab` for background collaboration.

## 2) Runtime Surfaces

- Primary UI: launcher (`ui/launcher/`)
- Background collaboration: configured instances from `config/instances.json` (`guppy-primary`, optional `builder-collab`)
- Historical specialist material: `compat_shims/legacy_surfaces/` and `src/guppy/merlin/` (not active desktop entrypoints)
- API: `src/guppy/api/server.py` (wrapper: `guppy_api.py`)
- Hub app: `src/guppy/apps/hub_app.py` (wrapper: `guppy_hub.py`)

## 3) Fast Health Checks

Run these in order when validating a deployment:

1. `python tools/check_architecture_boundaries.py`
2. `python tools/check_wrapper_integrity.py`
3. `python tools/check_doc_ownership.py`
4. `python tools/check_new_module_line_cap.py`
5. `.venv\Scripts\python.exe -m pytest tests/smoke/test_runtime_smoke.py tests/smoke/test_launcher_interactions_smoke.py tests/unit/test_security_hardening.py tests/unit/test_instance_controls.py tests/unit/test_offhours_builder.py tests/unit/test_smart_dispatch.py -q`
6. `python tests/smoke/smoke_api.py` when validating the API surface manually

## 3a) Builder Validation Pass

Run this after launcher builder, route, or voice changes:

1. Persona save/load/preview:
   - `.venv\Scripts\python.exe -m pytest tests/unit/test_personalization_resolution.py tests/smoke/test_launcher_interactions_smoke.py -q`
2. Model route explainability:
   - `.venv\Scripts\python.exe -m pytest tests/unit/test_models_routes.py tests/smoke/test_runtime_smoke.py -q`
3. Voice binding/import/preview:
   - `.venv\Scripts\python.exe -m pytest tests/unit/test_voices_view_validation.py tests/smoke/test_runtime_smoke.py -q`
4. Off-hours builder queue and approval:
   - `.venv\Scripts\python.exe -m pytest tests/unit/test_offhours_builder.py tests/unit/test_instance_controls.py -q`
5. Launcher workflow shortcuts:
   - Use App Mgmt -> `WORKFLOW LOOPS` to load or run Morning Boot, acceptance snapshot, midday stability, evening close, or overnight low-compute commands without leaving the launcher.
6. Guided automation testing:
   - Use App Mgmt -> `AUTOMATION TEST` for verify, switch-workspace, queue, review, approval, and validation.
   - Use Agent Tools only when you need the raw builder queue surface directly.

## 4) Recovery Flow

If runtime appears degraded:

1. Use App Mgmt `WINDOWS INSTALL / UPDATE / DIAGNOSTICS` recovery actions first.
2. If API is reachable, launcher sends `POST /repair` with `X-Repair-Token`.
3. If the API reports `repair_token_mismatch`, launcher re-syncs through `GET /repair-token/refresh` using localhost plus valid bearer auth.
4. Repair-token source order:
   - OS credential store (`keyring` via `utils/secret_store.py`)
   - Fallback file: `runtime/repair_token.txt` (for headless/no-keyring scenarios)
5. If API is down, launcher direct fallback paths execute warmup/audit/snapshot locally.

## 5) Auth and Secret Handling

1. JWT signing secret resolution (`src/guppy/api/auth.py`):
   - OS credential store key: `jwt_secret`
   - Fallback: `GUPPY_JWT_SECRET` environment variable
2. Repair token lifecycle (`src/guppy/api/server.py`):
   - Generated per process startup
   - Stored in OS credential store when available
   - File fallback with restricted permissions where possible
   - Removed on shutdown

## 6) SQLite Standards

All SQLite access should use `utils/db_utils.py:open_db(...)`.

Baseline applied per connection:

- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=<configured>`
- `PRAGMA busy_timeout=<configured>`
- `PRAGMA foreign_keys=ON`
- `PRAGMA temp_store=MEMORY`

## 7) Overnight / Low-Compute

Suggested commands:

1. `python tools/pilot_exit_check.py --allow-limited-go`
2. `python tools/verify_logging_health.py --emit-probe --require-fresh-core`
3. `python tools/verify_ollama_runtime.py --skip-ping`
4. `python tools/run_overnight_low_compute.py`

## 8) Production Notes

1. Keep `GUPPY_DEV_MODE=0` for production-like runs.
2. Keep telemetry backend as `sqlite+jsonl` unless intentionally testing alternatives.
3. Prefer supervisor-owned API lifecycle for Windows service-style deployments.
