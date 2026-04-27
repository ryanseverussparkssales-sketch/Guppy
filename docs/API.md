# API Reference

Canonical implementation lives in `src/guppy/api/server.py`, which now exposes the public FastAPI surface backed by `src/guppy/api/server_runtime.py`, imported route modules, and shared service/context layers.
Auth helpers live in `src/guppy/api/auth.py`.
`guppy_api.py` remains the root launch shim. Canonical auth/runtime code lives under `src/guppy/api/*`.

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

### Canonical Contract Baseline (BE-102)

This section is the baseline contract for the core public endpoints as implemented in `src/guppy/api/routes_core.py` and `src/guppy/api/routes_realtime.py`.

#### Core Endpoints

1. `GET /`
   - Auth: none
   - Success payload:
     - `message` (string)
     - `status` (string, currently `healthy`)
2. `GET /status`
   - Auth: `Authorization: Bearer <jwt>`
   - Success payload (normal path):
     - `status` (string: `healthy | degraded | error`)
     - `timestamp` (ISO datetime string)
     - `context` (object)
     - `memory_available` (bool)
     - `voice_available` (bool)
     - `voice_tts_backend` (string)
     - `voice_stt_backend` (string)
     - `voice_status` (object)
     - `daemon_available` (bool)
     - `daemon_runtime` (object)
     - `startup_readiness` (object)
     - `local_runtime` (object)
     - `resource_envelope` (object)
   - Runtime note: this route may also return `{ "status": "error", "message": "..." }` when status building fails.
3. `GET /startup/check`
   - Auth: `Authorization: Bearer <jwt>`
   - Query: `deep` (optional bool)
   - Success payload:
     - `overall` (string)
     - `checks` (object) including `auth`, `ollama`, `local_runtime`, `voice`, `daemon`, `memory`
4. `POST /chat`
   - Auth: `Authorization: Bearer <jwt>`
   - Success payload (standard):
     - `response` (string)
     - `session_id` (string or null)
   - Additional success fields (optional by path):
     - `brief` (bool, morning-brief path)
     - `cached` (bool, response-cache hit)
5. `POST /chat/voice`
   - Auth: `Authorization: Bearer <jwt>`
   - Present in current runtime (`routes_realtime.py`)
   - Success payload:
     - `transcription` (string)
     - `response` (string)
     - `session_id` (string or null)

#### Envelope Baseline

1. Success envelope
   - There is no global `{ ok, data }` wrapper in current runtime.
   - Success responses are route-native JSON objects with top-level fields listed above.
2. Error envelope
   - Canonical API errors use FastAPI/HTTPException shape:
     - `{ "detail": <string-or-object> }`
   - Validation errors also return `detail` (typically a list of validation issue objects).
   - Exception: `GET /status` may return HTTP 200 with `{ "status": "error", "message": "..." }` when internal status assembly fails.

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
- Header: `Authorization: Bearer <jwt>`
- Returns: `{ "repair_token": "<current-token>" }`
- Used by the launcher after a `repair_token_mismatch` response to re-sync and retry
- Returns `401` when the bearer token is missing or invalid
- Returns `403` for non-localhost callers even with a valid bearer token

## Chat

### `POST /chat`

- Header: `Authorization: Bearer <jwt>`
- Body:
  - `message` (string)
  - `session_id` (optional)
  - `mode` (optional: `auto | claude | ollama | local | code | teaching | vault | steer`)
  - `persona` (optional)
  - `history` (optional list of `{role, content}` items)
  - `use_claude` (optional bool)
  - `idempotency_key` (optional string)

### `POST /chat/stream`

- Header: `Authorization: Bearer <jwt>`
- Same body as `POST /chat`
- Returns: `text/event-stream` (SSE) — each event is a JSON object `{"token": "..."}`, terminated with `{"done": true}`
- This is the primary path used by the Web UI chat interface

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

## Providers & Model Selection

### `GET /providers`

- No auth required (rate-limited)
- Returns all configured AI providers with model catalogs, active model, and liveness state
- Response shape:
  ```json
  {
    "anthropic": { "configured": true, "active_model": "claude-sonnet-4-6", "models": [...] },
    "openai":    { "configured": false, "active_model": "gpt-4o-mini", "models": [...] },
    "google":    { "configured": true,  "active_model": "gemini-2.0-flash", "models": [...] },
    "cohere":    { "configured": true,  "active_model": "command-r7b-12-2024", "models": [...] },
    "mistral":   { "configured": true,  "active_model": "ministral-8b-latest", "models": [...] },
    "local": {
      "configured": true,
      "backend": "ollama",
      "active_model": "guppy:latest",
      "models": [{ "id": "...", "name": "...", "tier": "local", "tags": [...], "alive": true }],
      "backends": { "ollama": { "alive": true, "label": "Ollama" }, "llamacpp-pepe": { "alive": false, "label": "Pepe 8B" } }
    }
  }
  ```
- Model entries may include `"free": true` for free-tier API models

### `GET /providers/models`

- No auth required (rate-limited)
- Returns a flat list of every model across all configured providers
- Response: `{ "models": [{ "provider": "...", "id": "...", "name": "...", "tier": "...", "configured": true }], "total": N }`

### `POST /providers/{provider}/active-model`

- No auth required (rate-limited)
- Path: `provider` in `anthropic | openai | google | cohere | mistral | local`
- Body: `{ "model_id": "claude-sonnet-4-6" }`
- Persists the selected model and hot-reloads the inference registry

## Settings & Credentials

### `GET /api/settings`

- No auth required (rate-limited)
- Returns `{ "active_provider": "local", "credentials": { "anthropic": { "configured": false }, ... } }`

### `PUT /api/settings`

- No auth required (rate-limited)
- Body: `{ "active_provider": "mistral" }` (or other settings keys)

### `GET /api/settings/credentials`

- No auth required (rate-limited)
- Returns configured status for all 5 cloud providers (no API keys exposed)

### `POST /api/settings/credentials`

- No auth required (rate-limited)
- Body: `{ "provider": "mistral", "api_key": "sk-..." }`
- Valid providers: `anthropic | openai | google | cohere | mistral`
- Stores the key in the local SQLite settings DB (encrypted at rest in production)

### `DELETE /api/settings/credentials/{provider}`

- No auth required (rate-limited)
- Removes stored credentials for the named provider

### `GET /api/settings/provider`

- No auth required (rate-limited)
- Returns `{ "active_provider": "local" }`

### `POST /api/settings/provider`

- No auth required (rate-limited)
- Body: `{ "provider": "mistral" }`
- Sets the globally active inference provider

## llamacpp Backends

### `GET /api/backends/llamacpp`

- No auth required (rate-limited)
- Returns all known llama.cpp backend configurations with liveness state
- Response includes per-backend: `name`, `label`, `alive`, `port`, `default_url`, `vram_gb`, `auto_start`, `mode`

### `POST /api/backends/llamacpp/{backend}/start`

- No auth required (rate-limited)
- Starts the named llama.cpp backend process (launches the `.bat` file)
- Returns `{ "started": true, "backend": "llamacpp-pepe" }` or error if already running

### `POST /api/backends/llamacpp/{backend}/stop`

- No auth required (rate-limited)
- Stops the named backend process

### `GET /api/backends/llamacpp/vram`

- No auth required (rate-limited)
- Returns VRAM usage per running backend and total free VRAM
- Response: `{ "total_gb": 24, "used_gb": 8.5, "free_gb": 15.5, "backends": { "llamacpp-pepe": { "vram_gb": 8.5, "alive": true } } }`

## Workspaces

### `GET /workspaces`

- No auth required (rate-limited)
- Returns all workspaces with `id`, `name`, `created_at`
- Response: `{ "workspaces": [...], "active_workspace_id": "..." }`

### `POST /workspaces`

- No auth required (rate-limited)
- Body: `{ "name": "My Workspace" }`
- Creates a new workspace

### `POST /workspaces/{workspace_id}/activate`

- No auth required (rate-limited)
- Makes the named workspace the active one
