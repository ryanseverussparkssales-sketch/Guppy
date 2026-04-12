# Foundation Board

## Objective
Lay all planned feature and connection foundations now so account linking can be done later without architecture churn.

## Foundation Status at a Glance
- Tooling foundation: ready
- Data layer foundation: ready
- API surface foundation: ready
- Connection activation: pending account credentials

## Planned Connections and Readiness

### CRM providers
- HubSpot: stub ready, env scaffolded
- Salesforce: stub ready, env scaffolded
- GoHighLevel: stub ready, env scaffolded
- Zoho: stub ready, env scaffolded

### VoIP providers
- Twilio: stub ready, env scaffolded
- Generic VoIP: stub ready, env scaffolded

### Existing and planned media and ops connections
- Spotify: live-supported with credentials
- YouTube API: scaffolded key support
- Gmail: live-supported with credentials path
- Google Calendar: env scaffolded, orchestration planned
- uTorrent: live-supported via WebUI credentials
- Plex: partial stub foundation

## New Foundation Tools

### Guppy tools
- list_external_integrations
- crm_upsert_contact
- crm_create_opportunity
- voip_place_call
- get_foundation_readiness

### Merlin spells
- survey_portals
- bind_external_contact
- forge_external_opportunity
- summon_call
- survey_foundations

## Runtime Audit Trail
- External integration and call intents are logged to runtime/integration_events.jsonl
- Designed for review, replay planning, and safe rollout

## Activation Checklist
1. Populate .env values for your chosen providers
2. Run list_external_integrations and get_foundation_readiness
3. Confirm readiness gaps are closed
4. Keep dry_run true until each provider is validated
5. Enable live execution per provider in phased rollouts

## Suggested Rollout Order
1. HubSpot CRM contact sync
2. HubSpot opportunity sync
3. Twilio outbound call initiation
4. Salesforce and Zoho adapters
5. GoHighLevel adapter
6. Calendar orchestration

## Next Build Layer
- Provider-specific live adapters behind current stub interface
- OAuth/token refresh helpers where needed
- Per-provider retry and error categorization
- UI onboarding wizard for credential validation
