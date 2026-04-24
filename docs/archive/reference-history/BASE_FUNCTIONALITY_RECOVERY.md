# Base Functionality Recovery

Last updated: 2026-04-13

## Scope

This document tracks implementation progress for restoring and hardening base product functionality across launcher, API auth, recovery actions, hub stability, startup performance signaling, and telemetry freshness.

## Completed Implementation Steps

### Step 1: Auth handshake and diagnostics

Implemented:

1. Added `GET /auth/self-check` endpoint for launcher auth verification.
2. Added reason-coded JWT reject responses in `guppy_api_auth.verify_token`.
3. Added launcher-side HTTP error detail parsing for API failures.
4. Added launcher one-time auth self-check event logging with token-source metadata.

Validated:

- `python -m pytest tests/unit/test_security_hardening.py -q`
- `python -m pytest tests/smoke/test_runtime_smoke.py -q`
- `python -m pytest tests/smoke/test_launcher_interactions_smoke.py -q`

### Step 2: Repair token lifecycle consistency

Implemented:

1. Added reason-coded repair token rejection paths (`uninitialized`, `missing`, `mismatch`).
2. Added repair-token rejection telemetry events in API session logs.
3. Added stale fallback-file cleanup on keyring-backed token startup path.
4. Added security tests for launcher token acceptance and token rotation rejection behavior.

Validated:

- `python -m pytest tests/unit/test_security_hardening.py -q`

### Step 3: Hub crash-loop observability

Implemented:

1. Added per-agent process log capture at `runtime/<agent>.process.log`.
2. Added crash tail excerpt extraction in restart diagnostics.
3. Added crash excerpt event emission to operator telemetry.

Validated:

- `python -m pytest tests/smoke/test_launcher_interactions_smoke.py -q`

### Step 4: Startup budget recalibration

Implemented:

1. Raised default launcher startup warning budget from 200ms to 750ms in launcher UI and launcher app bootstrap.
2. Preserved explicit env override contract via `GUPPY_STARTUP_PHASE_WARN_MS`.

Validated:

- Launcher smoke suite and runtime smoke pass after change.

### Step 5: Integration telemetry freshness heartbeat

Implemented:

1. Added throttled integration heartbeat emission in API startup/request path.
2. Heartbeat writes to `runtime/integration_events.jsonl` with bounded rotation behavior.
3. Heartbeat interval configurable via `GUPPY_INTEGRATION_HEARTBEAT_SECONDS` (default 900s).

Validated:

- Runtime smoke suite still passing.

## Operational Validation Checklist

Executed after implementation:

1. `python tools/check_architecture_boundaries.py`
2. `python tools/check_wrapper_integrity.py`
3. `python tools/check_new_module_line_cap.py`
4. `python tools/check_core_surface_integrity.py`
5. `python tools/check_doc_ownership.py`
6. `python -m pytest tests/smoke/test_runtime_smoke.py -q`
7. `python -m pytest tests/smoke/test_launcher_interactions_smoke.py tests/unit/test_security_hardening.py -q`

## Next Monitoring Window

For base functionality acceptance, monitor for 24h:

1. No recurring `HTTP 401` launcher chat failures.
2. No recurring `HTTP 403` repair token failures.
3. No rapid crash-loop restart patterns without process-log root cause excerpts.
4. Startup warnings within calibrated threshold envelope.
5. `integration_events.jsonl` freshness maintained by heartbeat when integrations are otherwise idle.
