# API Reference

Canonical implementation lives in `src/guppy/api/server.py`, which now exposes the public FastAPI surface backed by `src/guppy/api/server_runtime.py`, imported route modules, and shared service/context layers.
Auth helpers live in `src/guppy/api/auth.py`.
`guppy_api.py` remains the root launch shim. `compat_shims/guppy_api_auth.py` remains only as a fallback compatibility shim.

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
- Returns configured workspaces/instances, active instance, limits, normalization warnings, per-workspace `governance` summaries, and per-workspace connector summaries under `connectors`
- Each `governance` summary now includes:
  - `auth_mode`
  - `auth_mode_label`
  - `tool_allow`
  - `tool_block`
  - `endpoint_allow`
  - `endpoint_block`
  - `policy_note`
  - `capabilities` (`read`, `write`, `execute`, `network`)
- Each connector summary now includes:
  - `id`
  - `category`
  - `auth_kind`
  - `auth_state`
  - `auth_detail`
  - `source`
  - `accounts`
  - `providers`
  - `actions_supported`
  - `binding`

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

### `GET /instances/{name}/connectors`

- Header: `Authorization: Bearer <jwt>`
- Returns the connector summary rows for the named workspace, including machine-level auth state plus the workspace binding payload currently in effect

### `POST /instances/{name}/connectors/{connector}`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `enabled` (optional bool)
  - `account_id` (optional string)
  - `provider` (optional string)
  - `action_allow` (optional list of connector action ids)
  - `action_block` (optional list of connector action ids)
  - `endpoint_allow` (optional list of connector endpoint filters)
  - `endpoint_block` (optional list of connector endpoint filters)
  - `note` (optional string)
- Saves the workspace connector binding in `config/connector_bindings.json` and returns the updated workspace connector rows

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

## Connectors

Connector auth remains machine-level. Workspace-specific connector access is layered on top through workspace bindings and the coarse workspace governance policy.

### `GET /connectors`

- Header: `Authorization: Bearer <jwt>`
- Returns the machine-level connector inventory across the currently shipped connector families:
  - `gmail`
  - `calendar`
  - `spotify`
  - `youtube`
  - `crm`
  - `voip`
- Each connector row includes:
  - `id`
  - `category`
  - `auth_kind`
  - `auth_state`
  - `auth_detail`
  - `source` (`env`, `keyring`, `file`, `token_cache`, `mixed`, or `none`)
  - `accounts`
  - `providers`
  - `actions_supported`
  - `secret_fields`
  - `history`
- Provider-backed connectors now also expose guided setup metadata under each provider row:
  - `field_details` with per-field labels, placeholders, validation hints, masking guidance, and presence state
  - `setup_state`
  - `setup_summary`
  - `next_field`
  - `verify_check_summary`
  - `next_step`
  - `fix_target`
- `history` now includes queryable action references:
  - `last_event_id`
  - `last_verify_event_id`
  - `last_action_record`
  - `last_verify_record`
  - `recent_events`
  - `timeline`
  - `recent_summary`

### `POST /connectors/{id}/verify`

- Header: `Authorization: Bearer <jwt>`
- Optional body:
  - `provider`
  - `account_id`
- Runs a non-destructive readiness check and returns the refreshed connector status
- Response includes:
  - `ok`
  - `summary`
  - `status`
  - `history`
  - `event_id`
  - `result_code`
  - `next_step`
  - `fix_target`
- `history.last_action_record.event_id` is the stable operator-facing reference for the verify attempt and matches the integration telemetry event payload.

### `POST /connectors/{id}/connect`

- Header: `Authorization: Bearer <jwt>`
- Optional body:
  - `provider`
  - `account_id`
  - `secret_key`
  - `secret_value`
- Starts or updates machine-level connector auth. For API-key style connectors this can also persist a secret through the OS keyring-backed secret store when available.
- For provider-secret connectors with multiple required fields, the connector inventory exposes the next required field and validation guidance so the launcher can step operators through setup one field at a time.
- Response includes `history.last_action_record.event_id` plus refreshed provider readiness, including remaining missing fields when setup is still incomplete.
- The same response also returns `result_code`, `next_step`, and `fix_target` so operator surfaces can point directly at the next repair action.

### `POST /connectors/{id}/reconnect`

- Header: `Authorization: Bearer <jwt>`
- Optional body:
  - `provider`
  - `account_id`
- Re-runs the connect path for connectors that support reconnect semantics, primarily OAuth/file-backed flows

### `POST /connectors/{id}/disconnect`

- Header: `Authorization: Bearer <jwt>`
- Optional body:
  - `provider`
  - `account_id`
  - `secret_key`
- Clears or detaches machine-level connector auth state where supported
- Responses include the refreshed `history` payload and stable action reference ids in the last-action record.

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
- Integration connector actions are queryable here with:
  - `stream=integration_events`
  - `event=connector.verify | connector.connect | connector.reconnect | connector.disconnect | connector.policy_denied | connector.auth_state_changed | workspace.connector_binding_saved`
- Connector action payloads now include:
  - `event_id`
  - `connector`
  - `action`
  - `provider`
  - `account_id`
  - `secret_key` (field name only, never the secret value)
  - `auth_state`
  - `ok`
  - `summary`
  - `result_code`
  - `next_step`
  - `fix_target`
  - `provider_auth_state`
  - `verify_check_summary`
- JSONL fallback and SQLite-backed telemetry both normalize integration events so the same filters work in either backend mode.

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
