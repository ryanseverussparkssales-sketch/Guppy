# Credentials & Dependencies Audit

**Purpose**: Verify every capability in documentation against actual implementation. Identify what requires user credentials or 3rd party setup.

**Last Updated**: April 13, 2026  
**Status**: Remote strict-mode path and public tunnel route verified; live guidance aligned to the `src/guppy/*` layout.

Compatibility note: `guppy_api.py` remains the root API launch shim. Canonical implementations live under `src/guppy/*`, and historical specialist desktop material is limited to `compat_shims/legacy_surfaces/`. Historical command examples later in this audit should be read as historical unless they are explicitly marked as current verification steps.

---

## Summary

| Capability | Status | Requires | Notes |
|---|---|---|---|
| Desktop launcher and hub surfaces | âœ… **READY** | None (Ollama local) or ANTHROPIC_API_KEY | Works offline; Claude optional |
| Push-to-talk + voice responses | âœ… **READY** | None | Windows SAPI 5.1 built-in |
| Smart dispatcher (Phases 1-3) | âœ… **READY** | ANTHROPIC_API_KEY for Haiku/Sonnet | Fallback to Ollama if key absent |
| OpenRouter low-cost routing (optional) | âš ï¸ **OPTIONAL** | OPENROUTER_API_KEY | Broad model selection, cost-focused fallback tier |
| Groq fast routing (optional) | âš ï¸ **OPTIONAL** | GROQ_API_KEY | Low-latency streaming tier for fast responses |
| Gemini low-cost routing (optional) | âš ï¸ **OPTIONAL** | GEMINI_API_KEY | Free/cheap general-purpose backup tier |
| Mistral low-cost routing (optional) | âš ï¸ **OPTIONAL** | MISTRAL_API_KEY | Additional inexpensive provider option |
| Local Ollama models (Guppy/Merlin) | âœ… **READY** | Ollama installed + models built | Build with `bin/build_models.bat` |
| Remote API (`src/guppy/api/server.py`, wrapper `guppy_api.py`) | âœ… **READY (STRICT MODE)** | GUPPY_JWT_SECRET, TURNSTILE_SECRET | Strict mode active (`GUPPY_DEV_MODE=0`), auth flow verified |
| Cloudflare tunnel | âœ… **READY** | CLOUDFLARE_TUNNEL_ID, CLOUDFLARE_HOSTNAME | Ingress routes public hostnames to `localhost:8081` |
| CRM integrations (HubSpot, Salesforce, GoHighLevel, Zoho) | âŒ **STUBBED** | API keys + live clients | Safe stubs; logs intent; no actual writes |
| VoIP calling (Twilio) | âŒ **STUBBED** | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN | Safe stub; no actual calls |
| Spotify (play/pause/next) | âš ï¸ **READY WITH SETUP** | SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET | Works when Spotify OAuth is configured; media-key fallback covers basic control |
| YouTube search | âœ… **READY** | None (browser fallback) | yt-dlp optional; defaults to web search |
| Gmail (send/read/delete) | âš ï¸ **READY** | Gmail OAuth setup required per account | Multi-account support; token cached |
| Web search (Perplexity AI) | âš ï¸ **FUNCTIONAL** | PERPLEXITY_API_KEY optional | Falls back to Google search in browser |
| Weather lookups | âš ï¸ **FUNCTIONAL** | OPENWEATHERMAP_API_KEY optional | Works; needs key for live data |
| GitHub access | âš ï¸ **FUNCTIONAL** | GITHUB_TOKEN optional | Public access works without token |
| Reminders/calendar | âš ï¸ **PARTIAL** | Google Calendar OAuth | Setup path documented; not yet hardened |
| Merlin external tools (uTorrent, Plex) | âŒ **STUBBED** | UTORRENT_HOST/PORT, PLEX_URL | Safe stubs; no actual commands |

---

## Core (Always Works)

### Desktop Launcher Surfaces

**Files**: `src/guppy/cli/launch.py`, `guppy_launcher.py`, `guppy_hub.py`

**Capabilities**:
- âœ… Per-query task classification (simple/complex/teaching)
- âœ… Haiku-first routing (2-3s) â†’ Sonnet â†’ Ollama fallback
- âœ… Merlin auto-routing based on task keywords
- âœ… Real-time chat UI with scroll
- âœ… Persistent session logs

Historical specialist surface code remains under `compat_shims/legacy_surfaces/` for migration reference only and is not part of the supported desktop launch path.

**Credentials Required**: 
- **None** (runs offline with Ollama)
- **Optional**: `ANTHROPIC_API_KEY` for Claude backends

**Verification**:
```powershell
python src/guppy/cli/launch.py launcher
```
Works immediately if Ollama is running.

---

### Push-to-Talk & Voice I/O

**Files**: `src/guppy/voice/voice.py`

**Capabilities**:
- âœ… PTT (hold-to-talk) via UI button
- âœ… Microphone auto-detect (Windows audio devices)
- âœ… Google STT transcription (16kHz mono WAV)
- âœ… Response TTS via Windows SAPI 5.1 (no external dependency)
- âœ… Interruption on user typing

**Credentials Required**: 
- **None** (Windows SAPI is built-in)

**Verification**:
```powershell
python tests/integration/test_ptt.py
```
Lists audio devices and validates microphone access.

---

### Local Model Support (Ollama)

**Files**: `guppy_core/`, `src/guppy/inference/router.py`, `config/local_llm/modelfiles/`

**Models Configured**:
- `guppy` (local inference)
- `merlin` (local Socratic teaching model)

**Credentials Required**: 
- **None** (models are local)
- **Requires**: Ollama daemon running on `http://127.0.0.1:11434`

**Setup**:
```powershell
ollama serve
# In another terminal:
bin\build_models.bat  # or manually:
ollama create guppy -f config\local_llm\modelfiles\Modelfile.guppy
ollama create merlin -f config\local_llm\modelfiles\Modelfile.merlin
```

**Verification**:
```powershell
ollama list
python -c "from guppy_core import query_local; print(query_local('Hello'))"
```

---

## Optional (Cloud APIs)

### Anthropic Claude (Haiku & Sonnet)

**Environment Variables**:
```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6          # Default
ANTHROPIC_BACKUP_MODEL=claude-haiku-4-5    # For Haiku-first
```

**Capabilities**:
- âœ… Haiku via `query_haiku()` (~$0.80/1M tokens)
- âœ… Sonnet via `query_sonnet()` (~$3.00/1M tokens)
- âœ… Full smart dispatch with task classification
- âœ… Fallback chain (if offline, uses Ollama)

**Impact if Missing**:
- Smart dispatcher falls back to Ollama (slow, local-only)
- Desktop UIs still work (Ollama fallback)

**How to Get**:
1. Visit `console.anthropic.com`
2. Create API key
3. Set environment variable:
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

**Verification**:
```powershell
python -c "from src.guppy.inference.router import resolve_ui_route; print('router ok')"
python -c "from src.guppy.inference.router import query_haiku; print(query_haiku('test'))"
```

---

### Spotify (Music Playback)

**Environment Variables** (already configured in launch scripts):
```
SPOTIFY_CLIENT_ID=d6729bd17c664ca289974001ea790136
SPOTIFY_CLIENT_SECRET=4eba85477e3a4174ad73e741353b85d3
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

**Capabilities**:
- âœ… `spotify_play(query)` â€” search and play track
- âœ… `spotify_pause()`, `spotify_resume()`, `spotify_next()`, `spotify_prev()`
- âœ… `spotify_current()` â€” get playing track

**Impact if Missing**:
- Spotify commands fail silently; no playback

**Notes**:
- Credentials are embedded in `bin/launch_*.bat` (dev Spotify app)
- User can substitute their own at `developer.spotify.com`

**Verification**:
```powershell
python -c "from src.guppy.tools.media import spotify_play; print(spotify_play('Pink Floyd Wish You Were Here'))"
```

---

### Weather (OpenWeatherMap)

**Environment Variables**:
```
OPENWEATHERMAP_API_KEY=
WEATHER_LOCATION=Dallas,TX,US
WEATHER_UNITS=imperial
```

**Capabilities**:
- âœ… `get_weather()` from `guppy_core.py`
- âœ… Current conditions + 5-day forecast

**Impact if Missing**:
- Weather queries return "API not configured"

**How to Get**:
1. Visit `openweathermap.org/api`
2. Sign up (free tier: 1000 calls/day)
3. Copy API key to environment

**Verification**:
```powershell
python -c "import os; os.environ['OPENWEATHERMAP_API_KEY']='your-key'; from guppy_core import get_weather; print(get_weather())"
```

---

### Web Search (Perplexity AI)

**Environment Variables**:
```
PERPLEXITY_API_KEY=
```

**Capabilities**:
- âœ… `search_web(query)` from `guppy_core.py`
- âœ… Returns answer + citations

**Impact if Missing**:
- Falls back to browser search (Google in new tab)
- Works but slower; requires manual interaction

**How to Get**:
1. Visit `pplx.ai/api`
2. Sign up (free tier: 5 requests/min)
3. Copy API key

**Verification**:
```powershell
python -c "from guppy_core import search_web; print(search_web('what is the capital of france'))"
```

---

### GitHub API

**Environment Variables**:
```
GITHUB_TOKEN=
```

**Capabilities**:
- âœ… Public repo access
- âœ… Rate limit: 60 req/hr (unauthenticated) â†’ 5000/hr (authenticated)

**Impact if Missing**:
- GitHub tools work; just hit rate limits faster

**How to Get**:
1. Visit `github.com/settings/tokens`
2. Create classic PAT with `repo` scope
3. Set environment variable

---

### Gmail (Multi-Account)

**Environment Variables**:
```
GMAIL_CREDENTIALS_PATH=
GOOGLE_CALENDAR_CREDENTIALS_PATH=
```

**Capabilities**:
- âœ… `gmail_send(to, subject, body)`
- âœ… `gmail_list_messages(query, limit)`
- âœ… `gmail_delete_messages(query)` (moves to trash)
- âœ… Multi-account support (main / sales / personal)
- âœ… `gmail_switch_account(alias)`

**Impact if Missing**:
- Gmail commands not available; no error on first run

**Setup (Per Account)**:
1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth credentials (Desktop app type)
4. Download as `gmail_credentials.json`
5. Place at `~/gmail_credentials.json` (or set `GMAIL_CREDENTIALS_PATH`)
6. First run opens browser for one-time consent
7. Token cached at `~/.guppy_gmail_token.json`

**Multiple Accounts**:
Tokens cached per alias:
- `~/.guppy_gmail_token_main.json`
- `~/.guppy_gmail_token_sales.json`
- `~/.guppy_gmail_token_personal.json`

**Verification**:
```powershell
python -c "from media_tools import gmail_list_accounts; print(gmail_list_accounts())"
```

---

### YouTube Integration

**Environment Variables**:
```
YOUTUBE_API_KEY=
```

**Capabilities**:
- âœ… `youtube_play(query)` â€” open in browser (no API needed)
- âœ… `youtube_search(query)` â€” return top 5 results

**Impact if Missing**:
- `youtube_play()` opens browser (works fine)
- `youtube_search()` requires `yt-dlp` package or falls back to browser

**How to Get** (optional):
1. Visit `console.cloud.google.com`
2. Create project â†’ enable YouTube API
3. Create API key
4. Set environment variable

---

## Remote & Auth (Production-Verified Core + Hardening Tail)

### API Server (`guppy_api.py`)

**Environment Variables** (REQUIRED for production):
```
GUPPY_JWT_SECRET=change-me-in-production
TURNSTILE_SECRET=from-cloudflare-dashboard
```

**Capabilities**:
- âœ… `GET /` â€” API status
- âœ… `GET /status` â€” daemon/subsystem health
- âœ… `POST /chat` â€” send message, get response
- âœ… `POST /chat/voice` â€” send audio, get transcribed + response
- âœ… `GET /logs/recent` â€” tail agent performance logs
- âš ï¸ `GET /revenue/dashboard` â€” CRM-lite pipeline summary
- âœ… WebSocket `/ws` â€” streaming chat

**Authentication Flow**:
1. Client sends Cloudflare Turnstile token to `POST /auth/verify`
2. Server verifies with Turnstile API (`https://challenges.cloudflare.com/turnstile/v0/siteverify`)
3. Server returns JWT bearer token
4. Client includes JWT in `Authorization: Bearer <token>` header

**Development Mode** (localhost testing):
```powershell
$env:GUPPY_DEV_MODE = "1"
python src/guppy/cli/launch.py api
# /auth/verify now accepts any Turnstile token
```

**Production Mode** (requires real secrets):
```
GUPPY_JWT_SECRET=production-secret-key-min-32-chars
TURNSTILE_SECRET=from-cloudflare-turnstile-setup
```

**Verification**:
```powershell
python tests/smoke/smoke_api.py
python tests/smoke/smoke_api.py --base-url http://localhost:8081

# Strict-mode public check (expected: 400 Invalid Turnstile token for dummy token)
Invoke-WebRequest https://guppy.sparkscuriositystudio.com/auth/verify -Method POST -Body '{"token":"dummy"}' -ContentType 'application/json'
```

---

### Cloudflare Tunnel (Remote Access)

**Current State**: Live and routing to `localhost:8081`.
**Hardening Tail**: Keep cert/bootstrap setup documented and validate after credential or host changes.

1. Install cloudflared:
```powershell
# Already in bin/cloudflared.exe
```

2. Authenticate with Cloudflare:
```powershell
.\bin\cloudflared.exe tunnel login
```

3. Create tunnel:
```powershell
.\bin\cloudflared.exe tunnel create guppy
# Copy the UUID output
```

4. Set environment variables:
```
CLOUDFLARE_TUNNEL_ID=<uuid-from-above>
CLOUDFLARE_HOSTNAME=guppy.yourdomain.com
```

5. Route DNS:
```powershell
.\bin\cloudflared.exe tunnel route dns guppy guppy.yourdomain.com
```

6. Start tunnel:
```powershell
.\bin\start_tunnel.bat
```

**Status**: 
- âš ï¸ Scripts exist and are functional
- âš ï¸ Not verified in production use
- âš ï¸ Cert path detection in `guppy_hub.py` may need adjustment per system

**Verification**:
```powershell
.\bin\start_tunnel.bat
# Should connect to Cloudflare and show domain routing
```

---

## Stubbed (Safe Placeholders)

### CRM Integrations

**Files**: `src/guppy/integrations/crm_voip.py`, `guppy_core/`

**Stubbed Providers**:
- HubSpot
- Salesforce  
- GoHighLevel
- Zoho

**Stubbed Tools**:
```
- crm_upsert_contact(name, email, phone, company, status, notes)
- crm_create_opportunity(contact_id, title, amount, stage, close_date)
- list_external_integrations()
```

**Behavior**:
- âœ… Tools are listed and callable from Guppy/Merlin
- âœ… Intent logged to `runtime/integration_events.jsonl`
- âœ… Configuration validated
- âŒ NO actual writes to CRM (safe stub)

**Environment Variables** (optional for now):
```
HUBSPOT_API_KEY=
SALESFORCE_ACCESS_TOKEN=
SALESFORCE_INSTANCE_URL=
GOHIGHLEVEL_API_KEY=
ZOHO_ACCESS_TOKEN=
```

**When Set**:
- Configuration checks pass; event log notes "ready"
- Stub still does not execute writes (intentional)

**To Activate** (future):
- Implement live client in `src/guppy/integrations/crm_voip.py`
- Add provider-specific connection logic
- Wire into tool executor
- Tests must validate write behavior

**Example Stub Call**:
```python
from src.guppy.integrations.crm_voip import crm_upsert_contact
result = crm_upsert_contact(
    name="John Doe",
    email="john@example.com",
    phone="555-1234",
    company="Acme",
    status="lead",
    notes="Met at conference"
)
# Returns: { "status": "stub", "logged": True, "action": "upsert_contact", ... }
# Actual CRM unchanged
```

---

### VoIP Calling (Twilio)

**Files**: `src/guppy/integrations/crm_voip.py`, `guppy_core/`

**Stubbed Tool**:
```
- voip_place_call(to_number, from_number, contact_name, purpose, dry_run=True)
```

**Environment Variables** (optional):
```
VOIP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

**Behavior**:
- âœ… Tool callable from Guppy/Merlin
- âœ… Intent logged to `runtime/integration_events.jsonl`
- âŒ NO actual phone calls (safe stub)

**To Activate** (future):
- Add Twilio client import
- Implement call placement logic in `src/guppy/integrations/crm_voip.py`
- Wire into tool executor
- Tests must mock Twilio API

---

### Merlin External Tools (uTorrent, Plex)

**Files**: `src/guppy/merlin/core.py` (spell map references)

**Stubbed Spells**:
- `invoke_torrent` (uTorrent remote control)
- `summon_plex` (Plex media control)

**Environment Variables**:
```
UTORRENT_HOST=localhost
UTORRENT_PORT=8080
UTORRENT_USER=admin
UTORRENT_PASS=
PLEX_URL=
```

**Status**:
- âŒ Not implemented; no actual connections
- âš ï¸ Spell aliases defined but no tool executors

**Future**:
- Implement uTorrent WebUI client
- Implement Plex API client
- Integrate with Merlin spell system

---

## What Still Needs User Credentials or Hardening

### Immediate (Blocks Remote Use):

1. **GUPPY_JWT_SECRET** (production)
   - Set a strong random secret (â‰¥32 characters)
   - Used to sign JWT tokens
   - Without it: dev mode only (`GUPPY_DEV_MODE=1`)

2. **TURNSTILE_SECRET** (production)
   - Cloudflare Turnstile dashboard
   - Used to verify client tokens
   - Without it: dev mode only

3. **Cloudflare Tunnel** (optional, for remote access)
   - Run `bin/cloudflared.exe tunnel login`
   - Create tunnel, capture UUID
   - Set `CLOUDFLARE_TUNNEL_ID` and `CLOUDFLARE_HOSTNAME`

### Optional (Enhances Features):

4. **ANTHROPIC_API_KEY** â†’ Claude fast responses
5. **OPENWEATHERMAP_API_KEY** â†’ Current weather
6. **PERPLEXITY_API_KEY** â†’ Web search answers
7. **GITHUB_TOKEN** â†’ Higher GitHub rate limits
8. **Gmail credentials** â†’ Multi-account email support
9. **YouTube API key** â†’ Richer search results

### CRM/VoIP (Not Yet Implemented):

10. **HubSpot**, **Salesforce**, **GoHighLevel**, **Zoho** API keys
11. **Twilio** account SID/token
12. **uTorrent**, **Plex** connection info

---

## Verification Checklist

Use this to validate your setup:

```powershell
# 1. Core (should always work)
python guppy_launcher.py
# â†’ Chat UI appears; can type; Ollama fallback works

# 2. Voice (should work)
python tests/test_ptt.py
# â†’ Lists audio devices; no errors

# 3. Smart dispatcher (with API key)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python -c "from src.guppy.inference.router import resolve_ui_route; print('router ok')"
# â†’ Router loads; can classify tasks

# 4. Ollama models
ollama list
# â†’ guppy and merlin models listed

# 5. API server (dev mode)
$env:GUPPY_DEV_MODE = "1"
python src/guppy/cli/launch.py api
# â†’ Server starts on port 8081

# 6. API smoke test
python tests/smoke/smoke_api.py
# â†’ All endpoints report PASS

# 7. Remote (optional)
$env:GUPPY_JWT_SECRET = "your-secret"
$env:TURNSTILE_SECRET = "your-secret"
.\bin\start_tunnel.bat
# â†’ Tunnel connects to Cloudflare
```

---

## Quick Reference: Environment Setup

**Minimal** (works offline):
```powershell
# Nothing required; Ollama-only mode
```

**Recommended** (butler with cloud speed):
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
[System.Environment]::SetEnvironmentVariable("OPENWEATHERMAP_API_KEY", "your-key", "User")
[System.Environment]::SetEnvironmentVariable("PERPLEXITY_API_KEY", "your-key", "User")
```

**Full Local** (remote API + tunnel):
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
[System.Environment]::SetEnvironmentVariable("GUPPY_JWT_SECRET", "change-me", "User")
[System.Environment]::SetEnvironmentVariable("TURNSTILE_SECRET", "change-me", "User")
[System.Environment]::SetEnvironmentVariable("CLOUDFLARE_TUNNEL_ID", "uuid", "User")
[System.Environment]::SetEnvironmentVariable("CLOUDFLARE_HOSTNAME", "guppy.yourdomain.com", "User")
```

---

---

## Provider Registry (PL-C4)

Introduced in PL-C4. The registry lives at `src/guppy/launcher_application/provider_registry.py` and is consumed by the onboarding presenter (`onboarding_presenter.py`) and the Settings connector panel.

| Provider ID | Label | Secret Fields Required | Verify Supported | Next Step Hint |
| --- | --- | --- | --- | --- |
| `gmail` | Gmail | _(none — OAuth file token)_ | Yes | Try asking Guppy to check your inbox or draft a reply. |
| `calendar` | Google Calendar | _(none — OAuth file token)_ | Yes | Ask Guppy what's on your calendar this week. |
| `spotify` | Spotify | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` | Yes | Say "Play something relaxing" to try Spotify now. |
| `youtube` | YouTube | `YOUTUBE_API_KEY` (optional) | Yes | Ask Guppy to find a YouTube video on any topic. |
| `crm` | CRM | `HUBSPOT_API_KEY` / `SALESFORCE_ACCESS_TOKEN` / `SALESFORCE_INSTANCE_URL` / `GOHIGHLEVEL_API_KEY` / `ZOHO_ACCESS_TOKEN` | Yes | Try asking Guppy to look up a contact or log a note. |
| `voip` | VoIP / Calling | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Yes | Ask Guppy to place a test call to confirm the setup. |

**Connection status** is resolved at runtime via `connector_manager.connector_status()` — no static "connected/not-configured" label is stored here because state changes as users add credentials.

**Onboarding summary** is surfaced via `get_onboarding_summary(connector_inventory)` in `onboarding_presenter.py`.

**Next step label** appears in the Settings > Device & Accounts panel immediately after a connector reaches `ready` or `optional` auth state.

---

## Findings Summary

âœ… **All Phase 1-3 Smart Dispatcher claims verified**:
- Task classification works (15/15 tests)
- Haiku-first routing functional
- Merlin auto-routing for teaching tasks
- Fallback chain with no retries
- Fully integrated into the launcher-first path, with legacy `guppy_ui` material retained only under `compat_shims/legacy_surfaces/`

âœ… **Desktop & voice fully functional**:
- No credentials required for local use
- Windows SAPI 5.1 TTS works out of box
- Ollama models can be built locally

âš ï¸ **Remote API functional in dev mode**:
- Works with `GUPPY_DEV_MODE=1` for testing
- Needs production secrets for strict mode
- Cloudflare tunnel path documented but not hardened

âŒ **CRM & VoIP are safe stubs**:
- No actual writes or calls possible
- Configuration validated
- Ready for live client implementation
- Event log captures intent for auditing

**Recommendation**: Release with README clarifying that "production deployment requires GUPPY_JWT_SECRET + TURNSTILE_SECRET" and that "CRM/VoIP are not yet active."

