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

## Status and Telemetry

### `GET /status`

- Header: `Authorization: Bearer <jwt>`
- Returns daemon/window context and subsystem availability
- Includes `resource_envelope` snapshot when daemon monitoring is active

### `GET /startup/check`

- Header: `Authorization: Bearer <jwt>`
- Returns startup readiness checks for key API dependencies

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
  - `use_claude` (optional bool)

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

## Smoke Path

Use the current smoke script from the reorganized test tree:

```powershell
python tests/smoke/smoke_api.py
```
