# Operations Instructions

Last verified: 2026-04-13

This is the primary operator runbook for the current codebase.

## 1) Startup

1. Activate environment and launch the app:
   - `python src/guppy/cli/launch.py launcher`
2. Launcher implementation is in `src/guppy/apps/launcher_app.py`.
3. Wrapper `guppy_launcher.py` is compatibility-only and should stay thin.
4. Use `src/guppy/cli/launch.py` for Hub, API, and GuppyPrime launches.
5. Treat Merlin and Council as compatibility/debug surfaces only. Launch them directly only when you intend to opt into legacy behavior.

## 2) Runtime Surfaces

- Primary UI: launcher (`ui/launcher/`)
- Specialist surfaces: `merlin_ui.py`, `council_ui.py`, legacy `guppy_ui.py` (compatibility-only)
- API: `src/guppy/api/server.py` (wrapper: `guppy_api.py`)
- Hub app: `src/guppy/apps/hub_app.py` (wrapper: `guppy_hub.py`)

## 3) Fast Health Checks

Run these in order when validating a deployment:

1. `python tools/check_architecture_boundaries.py`
2. `python tools/check_wrapper_integrity.py`
3. `python tools/check_doc_ownership.py`
4. `python tools/check_new_module_line_cap.py`
5. `python -m pytest tests/unit tests/integration -v`
6. `python tests/smoke/smoke_api.py` when validating the API surface manually

## 4) Recovery Flow

If runtime appears degraded:

1. Use launcher Settings recovery actions first.
2. If API is reachable, launcher sends `POST /repair` with `X-Repair-Token`.
3. Repair-token source order:
   - OS credential store (`keyring` via `utils/secret_store.py`)
   - Fallback file: `runtime/repair_token.txt` (for headless/no-keyring scenarios)
4. If API is down, launcher direct fallback paths execute warmup/audit/snapshot locally.

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
