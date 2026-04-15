# API Reference

Canonical implementation lives in `src/guppy/api/server.py` with auth helpers in `src/guppy/api/auth.py`.
Root files `guppy_api.py` and `guppy_api_auth.py` are compatibility shims.

## Base URL

- Local: `http://127.0.0.1:8081`
- Public: `https://guppy.sparkscuriositystudio.com`

## Auth

### `POST /auth/verify`

- Body: `{ "token": "<turnstile-token>" }`
- Returns: JWT bearer token

### `GET /auth/self-check`

- Header: `Authorization: Bearer <jwt>`
- Returns token-source diagnostics used by the launcher auth handshake

## Core Status

### `GET /`

- No auth header required
- Returns a minimal API liveness payload

### `GET /metrics`

- Header: `Authorization: Bearer <jwt>`
- Returns request counts, status-code buckets, slow-request totals, and average latency
- Useful for operator diagnostics without reading raw logs

### `GET /status`

- Header: `Authorization: Bearer <jwt>`
- Returns daemon/window context and subsystem availability
- Includes `local_runtime`, `startup_readiness`, and `resource_envelope` snapshots
- Includes `resource_envelope` snapshot when daemon monitoring is active

### `GET /startup/check`

- Header: `Authorization: Bearer <jwt>`
- Returns startup readiness checks for key API dependencies
- `checks.local_runtime` reports the currently selected local backend (`ollama` or `lemonade`)

## Instances

### `GET /instances`

- Header: `Authorization: Bearer <jwt>`
- Returns configured workspaces/instances, active instance, limits, normalization warnings, and per-workspace `governance` summaries
- Each `governance` summary now includes:
  - `auth_mode`
  - `auth_mode_label`
  - `tool_allow`
  - `tool_block`
  - `endpoint_allow`
  - `endpoint_block`
  - `policy_note`
  - `capabilities` (`read`, `write`, `execute`, `network`)

### `POST /instances`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `name` (string, required)
  - `description` (optional string)
  - `mode` (optional string, default `auto`)
  - `persona` (optional string, default `guppy`)
  - `voice` (optional string, default `default`)
  - `enabled` (optional bool, default `true`)
  - `type` (optional string, default `user_instance`)
- Creates or updates an instance and returns updated limit accounting

### `POST /instances/{name}/activate`

- Header: `Authorization: Bearer <jwt>`
- Marks the named instance as active and updates runtime state

### `POST /instances/{name}/governance`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `auth_mode` (string: `runtime_default | workspace_token_required | local_only | disabled`)
  - `tool_allow` (optional list of tool ids)
  - `tool_block` (optional list of tool ids)
  - `endpoint_allow` (optional list of endpoint filter patterns)
  - `endpoint_block` (optional list of endpoint filter patterns)
  - `policy_note` (optional string)
- Saves workspace governance policy and returns the normalized `governance` payload now active for that workspace

### `DELETE /instances/{name}`

- Header: `Authorization: Bearer <jwt>`
- Deletes an instance unless it is the last configured instance

### `GET /instances/{name}/logs`

- Header: `Authorization: Bearer <jwt>`
- Query params:
  - `limit` (optional, default `50`)
- Returns recent per-instance log entries plus a summary block

### `POST /instances/{name}/query`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `message` (string, required)
  - `source_instance` (optional string, default `launcher`)
  - `timeout_s` (optional float, capped at `5.0`)
- Runs a bounded cross-instance query and can return `busy`, `timeout`, or a completed response
- The same endpoint-aware workspace governance used by launcher tools is enforced here before the bridge runs

## Logs and Telemetry

### `GET /logs/recent`

- Header: `Authorization: Bearer <jwt>`
- Returns recent runtime log lines for quick diagnostics

### `GET /telemetry/query`

- Header: `Authorization: Bearer <jwt>`
- Query params:
  - `stream` (optional): `session_events`, `router_scorecard`, `agent_performance`, `integration_events`, `reminder_events`
  - `event` (optional): exact event name
  - `level` (optional): `info`, `warning`, `error`
  - `since_minutes` (optional, default `1440`)
  - `limit` (optional, default `200`, max `1000`)
  - `backend` (optional): `auto` (default), `sqlite`, `jsonl`

### `GET /telemetry/report`

- Header: `Authorization: Bearer <jwt>`
- Returns aggregated ops report (counts by stream/event/level, latency samples, average and p95)

### `GET /revenue/dashboard`

- Header: `Authorization: Bearer <jwt>`
- Returns structured CRM-lite pipeline totals, stage counts, weighted forecast, and top open opportunities

## Recovery

### `POST /repair`

- Header: `Authorization: Bearer <jwt>`
- Header: `X-Repair-Token: <token>`
- Body:
  - `action` in `warmup | restart_daemon | audit_runtime`
  - `dry_run` (optional bool)
- Returns guarded runtime recovery results

Repair token notes:

- token is process-scoped and rotated on API restart
- token is stored in OS keyring when available
- fallback file `runtime/repair_token.txt` is used only when keyring is unavailable

### `GET /repair-token/refresh`

- Localhost-only
- No auth header required
- Returns: `{ "repair_token": "<current-token>" }`
- Used by the launcher after a `repair_token_mismatch` response to re-sync and retry

## Chat

### `POST /chat`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `message` (string)
  - `session_id` (optional)
  - `mode` (optional: `auto | claude | ollama | local | code | teaching | vault`)
  - `persona` (optional)
  - `history` (optional list of `{role, content}` items)
  - `use_claude` (optional bool)
  - `idempotency_key` (optional string)

### `POST /chat/voice`

- Header: `Authorization: Bearer <jwt>`
- Multipart form-data:
  - `file` (audio)
  - `session_id` (optional)
  - `use_claude` (optional bool)

### `WebSocket /ws`

- Client first message: `{ "token": "<jwt>" }`
- Then send chat events with `message`, `session_id` (optional), `use_claude` (optional)
- Server emits chunk events and `{ "done": true }`
