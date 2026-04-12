# Guppy

Guppy is a local-first multi-agent assistant suite built around three main surfaces:

- Guppy: butler / operator
- Merlin: mentor / research persona
- Council: dual-agent orchestration

## Living Docs

Only these two files should be treated as current project status documents:

- `README.md` — current source of truth for setup, architecture, and project state
- `ROADMAP.md` — active priorities and handoff log for ongoing work across agents

Other status-heavy markdown files in the repo should be treated as historical notes or deep-dive references, not current release truth.
Archived historical docs now live under `docs/archive/`, split between `root-history/` and `planning-history/`.
`CONTRIBUTING.md` stays in the repo root by convention; operational guides like packaging live under `docs/`.

**Project Focus**: Guppy is a **butler/personal assistant**, not a sales tool. Priority is fast response (<3s), accurate first-time routing, and seamless voice integration for daily use.

## Current State

### Implemented

- Desktop UI surfaces: `guppy_ui.py`, `merlin_ui.py`, `council_ui.py`
- Smart dispatcher (Phases 1-3): Task classification → Haiku-first routing with fallback chain
- **Phase 4 voice fast-path**: Wake-word → Haiku-first always (`voice_triggered` flag), <2s latency target
- **Phase 5 response cache**: TTL-based module-level cache for simple/tool-free queries; cache hits skip API entirely
- Local + Claude routing: `guppy_core.py`, `inference_router.py`
- FastAPI remote surface: `guppy_api.py`, `guppy_api_auth.py` — strict mode active, public endpoint live at `guppy.sparkscuriositystudio.com`
- Web client alpha: `web/index.html`, `web/turnstile.js` — Cloudflare Turnstile wired with real site key
- API smoke testing: `tests/smoke_api.py`
- Hub/status surface and runtime logging: `guppy_hub.py`, `runtime/hub.log`
- Hub Orchestrator: `utils/hub_operator.py` — IPC, pattern logging, health checks, scheduled Haiku analysis (15min auto-tick)
- Persistent memory: `guppy_memory.py`
- Semantic memory dual backend: `guppy_semantic_memory.py` — SQLite default, Chroma opt-in (`GUPPY_SEMANTIC_BACKEND=chroma`)
- Voice pipeline with wake-word: `guppy_voice.py` — PTT, Kokoro TTS with SAPI fallback, openwakeword path, RMS VAD silence cutoff (`GUPPY_SILENCE_CUTOFF`, `GUPPY_SPEECH_THRESHOLD`)
- Proactive daemon + ambient watcher: `guppy_daemon.py` — agent health checks, reminder nudges, clipboard/window polling; Haiku semantic gate filters clipboard content before offering
- **Phase 11 ambient banner**: `AmbientBanner` widget in `guppy_ui.py` — non-intrusive offer bar between chat and input; shows Haiku's suggested action; "Ask Guppy" pre-fills input; auto-dismisses 30s
- 73 tools registered in `guppy_core.py` including `run_python`, `notify`, `web_summarize`, `github`, `semantic_remember/recall`, Gmail, Spotify, calendar, and more
- Revenue dashboard route plus CRM/VoIP scaffolding: `guppy_api.py`, `crm_voip_integrations.py`

**For complete credentials & dependencies audit, see** `CREDENTIALS_AUDIT.md`

### Partial / Needs Hardening

- **CRM & VoIP tools**: Safe stubs wired (log intent, validate config); no live calls or writes yet.
- `/status` performance: context gathering is a likely hotspot. Will be addressed in Phase 6.
- **Foundation visibility**: UIs still bypass `inference_router.py` for non-auto modes. Phase 6 will make the router the single inference path and add structured logging/metrics.
- Packaging: `build_executable.bat` significantly improved (venv python, `--no-clean` flag, full hidden-import coverage); still needs clean-machine validation before treating builds as release-ready.
- `web_summarize` tool uses HTTP+Haiku fallback until `FIRECRAWL_API_KEY` is set.

### Not Present

- No iOS client project is currently in the repository

## Capabilities Snapshot

- Desktop chat across Guppy, Merlin, and Council surfaces
- Local model plus Claude-backed routing
- Push-to-talk, spoken replies, interruption-aware voice handling, and wake-word path
- FastAPI remote chat, voice route, websocket streaming, and readiness endpoints
- Persistent memory, semantic memory, and daemon-backed context awareness
- CRM-lite and VoIP scaffolding with revenue dashboard support

## Focused References

Keep these as separate docs because they still serve as active operational references rather than status clutter:

- `docs/API.md` — endpoint and integration reference
- `docs/VOICE.md` — voice behavior, troubleshooting, and device notes
- `docs/TROUBLESHOOTING.md` — quick operational recovery steps
- `docs/PACKAGING.md` — build and release packaging guide

The old broad capability catalog has been archived to `docs/archive/reference-history/FEATURES.md` because its active summary now lives here in `README.md`.

## Architecture

### Entry Points

- `guppy_ui.py` — main desktop UI
- `guppy_agent.py` — terminal / CLI surface
- `merlin_ui.py` — Merlin desktop UI
- `council_ui.py` — dual-agent UI
- `guppy_api.py` — remote API server
- `guppy_hub.py` — launcher / status hub

### Core Modules

- `guppy_core.py` — routing, tools, model behavior, shared runtime glue
- `merlin_core.py` — Merlin spell aliases and persona-specific behavior
- `guppy_voice.py` — TTS, STT, wake-word, interruption control
- `guppy_daemon.py` — reminders, window awareness, background services
- `guppy_memory.py` — persistent storage and dashboard data
- `guppy_semantic_memory.py` — semantic memory backend layer
- `crm_voip_integrations.py` — external business-system stubs and readiness helpers

## Quick Start

### Install

1. Create or activate the project virtual environment.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Optional but common environment setup:

```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "your-key", "User")
```

### Local Model Setup

1. Install Ollama.
2. Create the local persona models:

```powershell
ollama create guppy -f models/Modelfile
ollama create merlin -f models/Modelfile_Merlin
```

3. Ensure Ollama is serving on `http://127.0.0.1:11434`.

### Run

```powershell
python guppy_ui.py
python guppy_agent.py
python merlin_ui.py
python council_ui.py
python guppy_api.py
python guppy_hub.py
```

VS Code tasks in this workspace also cover the main launch flows.

## Verification

### Useful Checks

```powershell
python tests/test_ptt.py
python tests/smoke_api.py
```

### Runtime Truth Sources

- API behavior and readiness: `guppy_api.py`
- Auth behavior: `guppy_api_auth.py`
- Routing behavior: `inference_router.py`
- Tool surface: `guppy_core.py`
- Current active work and handoff notes: `ROADMAP.md`

## API Surface

The remote/API layer already exists and should be treated as alpha, not planned work.

- Base URL: `http://127.0.0.1:8081`
- Auth: `POST /auth/verify`
- Health and readiness: `GET /status`, `GET /startup/check`, `GET /logs/recent`
- Chat: `POST /chat`, `POST /chat/voice`, `WebSocket /ws`
- Business reporting: `GET /revenue/dashboard`

The safest validation path is:

```powershell
python tests/smoke_api.py
```

Treat external auth, tunnel, and websocket validation as the release gate for remote use.

## Voice Summary

The voice stack supports push-to-talk, spoken responses, interruption on user typing, and a wake-word path.

- Input path: PTT via `guppy_voice.py`
- Primary transcription path: Google STT
- Additional backend support exists for local/fallback paths already wired into the project
- TTS: Kokoro when available, otherwise Windows SAPI fallback
- Wake-word path: implemented, still needs tuning and real-use validation

Useful voice checks:

```powershell
python tests/test_ptt.py
python -c "import sounddevice as sd; import json; print(json.dumps(sd.query_devices(), indent=2))"
```

If voice behavior drifts, treat `guppy_voice.py` plus `ROADMAP.md` as the current truth, and `docs/VOICE.md` as a deeper reference.

## Troubleshooting Quick Hits

- Cloudflare tunnel cert issues: run the Cloudflare login flow again via `bin/cloudflare_terminal.ps1 -Action login`
- API auth failures: verify `GUPPY_JWT_SECRET` and `TURNSTILE_SECRET`, or use `GUPPY_DEV_MODE=1` only for local development
- Voice transcription 400s: test with clear spoken audio and confirm the machine has working STT dependencies
- Ollama failures: verify `ollama serve` is running and confirm models with `ollama list`
- UI slowness: inspect `runtime/agent_performance.jsonl` and run `python runtime/review_agent_performance.py`

Use `docs/TROUBLESHOOTING.md` when the quick summary is not enough.

## Packaging Summary

- Primary packaging doc: `docs/PACKAGING.md`
- Quick build path: `build_executable.bat`
- Current packaging goal: pass a clean-machine validation flow before treating builds as release-ready
- Packaging remains a hardening item, not a closed release system

Use `docs/PACKAGING.md` for full build, installer, signing, and distribution details.

## Active Priorities

1. **Phase 6** — Make `inference_router.py` the single inference path; add structured per-request logging (task type, model, latency, cost).
2. **Voice tuning** — Validate wake-word → Haiku fast-path latency in real use; tune openwakeword model and cooldown.
3. **CRM workflow** — Convert at least one CRM-lite stub into a complete end-to-end flow (e.g. log a call, update pipeline stage, send follow-up email).
4. **Packaging** — Pass a clean-machine validation before treating builds as release-ready.
5. **`/status` performance** — Profile and reduce context-gathering overhead.

## Working Style For Multi-Agent Sessions

When multiple agents are touching the repo in parallel:

- Use `README.md` for the stable project picture.
- Use `ROADMAP.md` for active priorities, open questions, and handoff notes.
- Add short dated notes to the handoff log instead of creating another status markdown file.
- Treat older handoff, planning, or completion docs as archive material unless they are being deliberately refreshed; archived docs live under `docs/archive/`.
