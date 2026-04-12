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
- Local + Claude routing: `guppy_core.py`, `inference_router.py`
- FastAPI remote surface: `guppy_api.py`, `guppy_api_auth.py`
- Web client alpha: `web/index.html`, `web/turnstile.js`
- API smoke testing: `tests/smoke_api.py`
- Hub/status surface and runtime logging: `guppy_hub.py`, `runtime/hub.log`
- Persistent memory and semantic memory: `guppy_memory.py`, `guppy_semantic_memory.py`
- Voice pipeline with wake-word support path: `guppy_voice.py`
- Revenue dashboard route plus CRM/VoIP scaffolding: `guppy_api.py`, `crm_voip_integrations.py`

### Partial / Needs Hardening

- **Inference latency**: Ollama bottleneck (30s timeout potential) blocks responsive butler experience. Smart dispatcher (Haiku-first) in progress to replace with <3s predictable response.
- **Merlin utilization**: Built but rarely used. Smart routing (Phase 3) will auto-dispatch teaching/explanation tasks to Merlin instead of requiring manual selection.
- **Remote production path**: auth, tunnel, and external validation are not fully closed out. Unblocked by Phase 1 (latency improvement makes remote feel snappy).
- `/status` performance: readiness is present, but context gathering is still a likely hotspot. Will be addressed in Phase 5-6.
- **Foundation visibility**: UIs bypass inference router instead of calling it. Phase 6 will make router the single path and add structured logging/metrics.
- Packaging and release checks: not yet locked into a clean-machine release path (Phase 6 prep).
- Wake-word and voice quality: implemented, but latency tuning (Phase 4) needed for natural voice feel.

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

- Base URL: `http://127.0.0.1:8080`
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

1. Finish remote hardening across API, websocket, auth, and tunnel flows.
2. Reduce `/status` overhead around enhanced context gathering.
3. Convert CRM-lite scaffolding into at least one complete business workflow.
4. Add release-grade startup checks and packaging validation.
5. Tune wake-word and voice defaults for real daily use.

## Working Style For Multi-Agent Sessions

When multiple agents are touching the repo in parallel:

- Use `README.md` for the stable project picture.
- Use `ROADMAP.md` for active priorities, open questions, and handoff notes.
- Add short dated notes to the handoff log instead of creating another status markdown file.
- Treat older handoff, planning, or completion docs as archive material unless they are being deliberately refreshed; archived docs live under `docs/archive/`.
