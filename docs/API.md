# API Reference (Phase 3)

## Base URL
- Local: `http://127.0.0.1:8081`

## Auth
### POST /auth/verify
- Body: `{ "token": "<turnstile-token>" }`
- Returns: JWT bearer token

## Status
### GET /status
- Header: `Authorization: Bearer <jwt>`
- Returns daemon/window context and subsystem availability

### GET /revenue/dashboard
- Header: `Authorization: Bearer <jwt>`
- Returns structured CRM-lite pipeline totals, stage counts, weighted forecast, and top open opportunities

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
