# API Reference (Phase 3)

## Base URL
- Local: `http://127.0.0.1:8081`
- Public: `https://guppy.sparkscuriositystudio.com`

## Auth
### POST /auth/verify
- Body: `{ "token": "<turnstile-token>" }`
- Returns: JWT bearer token

## Status
### GET /status
- Header: `Authorization: Bearer <jwt>`
- Returns daemon/window context and subsystem availability
- Includes `resource_envelope` snapshot when daemon monitoring is active

### GET /startup/check
- Header: `Authorization: Bearer <jwt>`
- Returns startup readiness checks for key API dependencies

### GET /logs/recent
- Header: `Authorization: Bearer <jwt>`
- Returns recent runtime log lines for quick diagnostics

### GET /telemetry/query
- Header: `Authorization: Bearer <jwt>`
- Query params:
  - `stream` (optional): `session_events`, `router_scorecard`, `agent_performance`, `integration_events`, `reminder_events`
  - `event` (optional): exact event name
  - `level` (optional): `info`, `warning`, `error`
  - `since_minutes` (optional, default `1440`)
  - `limit` (optional, default `200`, max `1000`)
  - `backend` (optional): `auto` (default), `sqlite`, `jsonl`
- Returns filtered telemetry events with normalized shape (`ts`, `stream`, `event`, `level`, `payload`)

### GET /telemetry/report
- Header: `Authorization: Bearer <jwt>`
- Query params:
  - `stream` (optional)
  - `since_minutes` (optional, default `1440`)
  - `limit` (optional, default `1000`, max `2000`)
  - `backend` (optional): `auto` (default), `sqlite`, `jsonl`
- Returns aggregated ops report (counts by stream/event/level, latency samples, average and p95)

### GET /revenue/dashboard
- Header: `Authorization: Bearer <jwt>`
- Returns structured CRM-lite pipeline totals, stage counts, weighted forecast, and top open opportunities

### POST /repair
- Header: `Authorization: Bearer <jwt>`
- Header: `X-Repair-Token: <token>`
- Body:
  - `action` in `warmup | restart_daemon | audit_runtime`
  - `dry_run` (optional bool)
- Returns operation result for guarded runtime recovery actions

Repair token notes:
- token is process-scoped and rotated on API restart
- token is stored in OS keyring when available
- fallback file `runtime/repair_token.txt` is used only when keyring is unavailable

### GET /repair-token/refresh
- **Localhost-only** (returns 403 for any non-loopback client)
- No auth header required
- Returns: `{ "repair_token": "<current-token>" }`
- Resolves the restart-lockout scenario: when the API restarts and rotates the repair token, the launcher calls this endpoint on 403+`repair_token_mismatch` to retrieve the new token and retry automatically
- Token lookup order: OS keyring → `runtime/repair_token.txt` → in-memory fallback

## Chat
### POST /chat
- Header: `Authorization: Bearer <jwt>`
- Body:
  - `message` (string)
  - `session_id` (optional)
  - `use_claude` (optional bool)

### POST /chat/voice
- Header: `Authorization: Bearer <jwt>`
- Multipart form-data:
  - `file` (audio)
  - `session_id` (optional)
  - `use_claude` (optional bool)

### WebSocket /ws
- Client first message: `{ "token": "<jwt>" }`
- Then send chat events with:
  - `message`
  - `session_id` (optional)
  - `use_claude` (optional)
- Server emits chunk events and `{ "done": true }`

## External CRM and VoIP Stubs (Tool Layer)

These are currently implemented as safe stubs for future provider activation.
They log intent and validate configuration, but do not execute live writes/calls unless
provider-specific clients are implemented.

### Guppy tools
- `list_external_integrations`
- `crm_upsert_contact`
- `crm_create_opportunity`
- `voip_place_call`
- `get_foundation_readiness`

### Merlin spells
- `survey_portals`
- `bind_external_contact`
- `forge_external_opportunity`
- `summon_call`
- `survey_foundations`

### Planned provider environment variables
- HubSpot: `HUBSPOT_API_KEY`
- Salesforce: `SALESFORCE_ACCESS_TOKEN`, `SALESFORCE_INSTANCE_URL`
- GoHighLevel: `GOHIGHLEVEL_API_KEY`
- Zoho: `ZOHO_ACCESS_TOKEN`
- VoIP (Twilio): `VOIP_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`

### Runtime event log
- Integration requests are recorded in `runtime/integration_events.jsonl` for auditing and future replay.

### Planning board
- Full plan and activation board: `docs/archive/planning-history/FOUNDATION_BOARD.md`
