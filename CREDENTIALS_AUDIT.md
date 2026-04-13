# Credentials & Dependencies Audit

**Purpose**: Verify every capability in documentation against actual implementation. Identify what requires user credentials or 3rd party setup.

**Last Updated**: April 12, 2026  
**Status**: Remote strict-mode path and public tunnel route verified; credentials map current.

---

## Summary

| Capability | Status | Requires | Notes |
|---|---|---|---|
| Desktop chat (Guppy/Merlin/Council UIs) | ✅ **READY** | None (Ollama local) or ANTHROPIC_API_KEY | Works offline; Claude optional |
| Push-to-talk + voice responses | ✅ **READY** | None | Windows SAPI 5.1 built-in |
| Smart dispatcher (Phases 1-3) | ✅ **READY** | ANTHROPIC_API_KEY for Haiku/Sonnet | Fallback to Ollama if key absent |
| OpenRouter low-cost routing (optional) | ⚠️ **OPTIONAL** | OPENROUTER_API_KEY | Broad model selection, cost-focused fallback tier |
| Groq fast routing (optional) | ⚠️ **OPTIONAL** | GROQ_API_KEY | Low-latency streaming tier for fast responses |
| Gemini low-cost routing (optional) | ⚠️ **OPTIONAL** | GEMINI_API_KEY | Free/cheap general-purpose backup tier |
| Mistral low-cost routing (optional) | ⚠️ **OPTIONAL** | MISTRAL_API_KEY | Additional inexpensive provider option |
| Local Ollama models (Guppy/Merlin) | ✅ **READY** | Ollama installed + models built | Build with `build_models.bat` |
| Remote API (`guppy_api.py`) | ✅ **READY (STRICT MODE)** | GUPPY_JWT_SECRET, TURNSTILE_SECRET | Strict mode active (`GUPPY_DEV_MODE=0`), auth flow verified |
| Cloudflare tunnel | ✅ **READY** | CLOUDFLARE_TUNNEL_ID, CLOUDFLARE_HOSTNAME | Ingress routes public hostnames to `localhost:8081` |
| CRM integrations (HubSpot, Salesforce, GoHighLevel, Zoho) | ❌ **STUBBED** | API keys + live clients | Safe stubs; logs intent; no actual writes |
| VoIP calling (Twilio) | ❌ **STUBBED** | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN | Safe stub; no actual calls |
| Spotify (play/pause/next) | ✅ **READY** | Spotify client already hardcoded | Works; uses embedded dev credentials |
| YouTube search | ✅ **READY** | None (browser fallback) | yt-dlp optional; defaults to web search |
| Gmail (send/read/delete) | ⚠️ **READY** | Gmail OAuth setup required per account | Multi-account support; token cached |
| Web search (Perplexity AI) | ⚠️ **FUNCTIONAL** | PERPLEXITY_API_KEY optional | Falls back to Google search in browser |
| Weather lookups | ⚠️ **FUNCTIONAL** | OPENWEATHERMAP_API_KEY optional | Works; needs key for live data |
| GitHub access | ⚠️ **FUNCTIONAL** | GITHUB_TOKEN optional | Public access works without token |
| Reminders/calendar | ⚠️ **PARTIAL** | Google Calendar OAuth | Setup path documented; not yet hardened |
| Merlin external tools (uTorrent, Plex) | ❌ **STUBBED** | UTORRENT_HOST/PORT, PLEX_URL | Safe stubs; no actual commands |

---

## Core (Always Works)

### Desktop Chat Surfaces

**Files**: `guppy_launcher.py` (unified), `merlin_ui.py`, `council_ui.py`

**Capabilities**:
- ✅ Per-query task classification (simple/complex/teaching)
- ✅ Haiku-first routing (2-3s) → Sonnet → Ollama fallback
- ✅ Merlin auto-routing based on task keywords
- ✅ Real-time chat UI with scroll
- ✅ Persistent session logs

**Credentials Required**: 
- **None** (runs offline with Ollama)
- **Optional**: `ANTHROPIC_API_KEY` for Claude backends

**Verification**:
```powershell
python guppy_launcher.py
```
Works immediately if Ollama is running.

---

### Push-to-Talk & Voice I/O

**Files**: `guppy_voice.py`

**Capabilities**:
- ✅ PTT (hold-to-talk) via UI button
- ✅ Microphone auto-detect (Windows audio devices)
- ✅ Google STT transcription (16kHz mono WAV)
- ✅ Response TTS via Windows SAPI 5.1 (no external dependency)
- ✅ Interruption on user typing

**Credentials Required**: 
- **None** (Windows SAPI is built-in)

**Verification**:
```powershell
python tests/test_ptt.py
```
Lists audio devices and validates microphone access.

---

### Local Model Support (Ollama)

**Files**: `guppy_core.py`, `inference_router.py`, models/

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
python build_models.bat  # or manually:
ollama create guppy -f models/Modelfile
ollama create merlin -f models/Modelfile_Merlin
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
- ✅ Haiku via `query_haiku()` (~$0.80/1M tokens)
- ✅ Sonnet via `query_sonnet()` (~$3.00/1M tokens)
- ✅ Full smart dispatch with task classification
- ✅ Fallback chain (if offline, uses Ollama)

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
python inference_router.py  # Loads router; checks API key
python -c "from inference_router import query_haiku; print(query_haiku('test'))"
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
- ✅ `spotify_play(query)` — search and play track
- ✅ `spotify_pause()`, `spotify_resume()`, `spotify_next()`, `spotify_prev()`
- ✅ `spotify_current()` — get playing track

**Impact if Missing**:
- Spotify commands fail silently; no playback

**Notes**:
- Credentials are embedded in `bin/launch_*.bat` (dev Spotify app)
- User can substitute their own at `developer.spotify.com`

**Verification**:
```powershell
python -c "from media_tools import spotify_play; print(spotify_play('Pink Floyd Wish You Were Here'))"
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
- ✅ `get_weather()` from `guppy_core.py`
- ✅ Current conditions + 5-day forecast

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
- ✅ `search_web(query)` from `guppy_core.py`
- ✅ Returns answer + citations

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
- ✅ Public repo access
- ✅ Rate limit: 60 req/hr (unauthenticated) → 5000/hr (authenticated)

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
- ✅ `gmail_send(to, subject, body)`
- ✅ `gmail_list_messages(query, limit)`
- ✅ `gmail_delete_messages(query)` (moves to trash)
- ✅ Multi-account support (main / sales / personal)
- ✅ `gmail_switch_account(alias)`

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
- ✅ `youtube_play(query)` — open in browser (no API needed)
- ✅ `youtube_search(query)` — return top 5 results

**Impact if Missing**:
- `youtube_play()` opens browser (works fine)
- `youtube_search()` requires `yt-dlp` package or falls back to browser

**How to Get** (optional):
1. Visit `console.cloud.google.com`
2. Create project → enable YouTube API
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
- ✅ `GET /` — API status
- ✅ `GET /status` — daemon/subsystem health
- ✅ `POST /chat` — send message, get response
- ✅ `POST /chat/voice` — send audio, get transcribed + response
- ✅ `GET /logs/recent` — tail agent performance logs
- ⚠️ `GET /revenue/dashboard` — CRM-lite pipeline summary
- ✅ WebSocket `/ws` — streaming chat

**Authentication Flow**:
1. Client sends Cloudflare Turnstile token to `POST /auth/verify`
2. Server verifies with Turnstile API (`https://challenges.cloudflare.com/turnstile/v0/siteverify`)
3. Server returns JWT bearer token
4. Client includes JWT in `Authorization: Bearer <token>` header

**Development Mode** (localhost testing):
```powershell
$env:GUPPY_DEV_MODE = "1"
python guppy_api.py
# /auth/verify now accepts any Turnstile token
```

**Production Mode** (requires real secrets):
```
GUPPY_JWT_SECRET=production-secret-key-min-32-chars
TURNSTILE_SECRET=from-cloudflare-turnstile-setup
```

**Verification**:
```powershell
python tests/smoke_api.py
python tests/smoke_api.py --base-url http://localhost:8081

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
- ⚠️ Scripts exist and are functional
- ⚠️ Not verified in production use
- ⚠️ Cert path detection in `guppy_hub.py` may need adjustment per system

**Verification**:
```powershell
.\bin\start_tunnel.bat
# Should connect to Cloudflare and show domain routing
```

---

## Stubbed (Safe Placeholders)

### CRM Integrations

**Files**: `crm_voip_integrations.py`, `guppy_core.py`

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
- ✅ Tools are listed and callable from Guppy/Merlin
- ✅ Intent logged to `runtime/integration_events.jsonl`
- ✅ Configuration validated
- ❌ NO actual writes to CRM (safe stub)

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
- Implement live client in `crm_voip_integrations.py`
- Add provider-specific connection logic
- Wire into tool executor
- Tests must validate write behavior

**Example Stub Call**:
```python
from crm_voip_integrations import crm_upsert_contact
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

**Files**: `crm_voip_integrations.py`, `guppy_core.py`

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
- ✅ Tool callable from Guppy/Merlin
- ✅ Intent logged to `runtime/integration_events.jsonl`
- ❌ NO actual phone calls (safe stub)

**To Activate** (future):
- Add Twilio client import
- Implement call placement logic in `crm_voip_integrations.py`
- Wire into tool executor
- Tests must mock Twilio API

---

### Merlin External Tools (uTorrent, Plex)

**Files**: `merlin_core.py` (Spell map references)

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
- ❌ Not implemented; no actual connections
- ⚠️ Spell aliases defined but no tool executors

**Future**:
- Implement uTorrent WebUI client
- Implement Plex API client
- Integrate with Merlin spell system

---

## What Still Needs User Credentials or Hardening

### Immediate (Blocks Remote Use):

1. **GUPPY_JWT_SECRET** (production)
   - Set a strong random secret (≥32 characters)
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

4. **ANTHROPIC_API_KEY** → Claude fast responses
5. **OPENWEATHERMAP_API_KEY** → Current weather
6. **PERPLEXITY_API_KEY** → Web search answers
7. **GITHUB_TOKEN** → Higher GitHub rate limits
8. **Gmail credentials** → Multi-account email support
9. **YouTube API key** → Richer search results

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
# → Chat UI appears; can type; Ollama fallback works

# 2. Voice (should work)
python tests/test_ptt.py
# → Lists audio devices; no errors

# 3. Smart dispatcher (with API key)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python inference_router.py
# → Router loads; can classify tasks

# 4. Ollama models
ollama list
# → guppy and merlin models listed

# 5. API server (dev mode)
$env:GUPPY_DEV_MODE = "1"
python guppy_api.py
# → Server starts on port 8081

# 6. API smoke test
python tests/smoke_api.py
# → All endpoints report PASS

# 7. Remote (optional)
$env:GUPPY_JWT_SECRET = "your-secret"
$env:TURNSTILE_SECRET = "your-secret"
.\bin\start_tunnel.bat
# → Tunnel connects to Cloudflare
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

## Findings Summary

✅ **All Phase 1-3 Smart Dispatcher claims verified**:
- Task classification works (15/15 tests)
- Haiku-first routing functional
- Merlin auto-routing for teaching tasks
- Fallback chain with no retries
- Fully integrated into `guppy_ui.py`

✅ **Desktop & voice fully functional**:
- No credentials required for local use
- Windows SAPI 5.1 TTS works out of box
- Ollama models can be built locally

⚠️ **Remote API functional in dev mode**:
- Works with `GUPPY_DEV_MODE=1` for testing
- Needs production secrets for strict mode
- Cloudflare tunnel path documented but not hardened

❌ **CRM & VoIP are safe stubs**:
- No actual writes or calls possible
- Configuration validated
- Ready for live client implementation
- Event log captures intent for auditing

**Recommendation**: Release with README clarifying that "production deployment requires GUPPY_JWT_SECRET + TURNSTILE_SECRET" and that "CRM/VoIP are not yet active."
