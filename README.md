# Guppy

Guppy is a local-first multi-agent assistant with a unified launcher as the primary daily interface and bounded background collaboration for deeper workflows:

Guppy is built as a Butler-style personal assistant first, with daily-use speed, routing accuracy, and voice ergonomics prioritized over sales or CRM workflows.

- Unified launcher: default front door for assistant, instances, agent tools, app management, Local LLM evidence, model library, and voice library
- Background collaboration: `guppy-primary` foreground plus optional `builder-collab`
- Teaching and coding specialization: routed through `guppy-teach` and `guppy-code` instead of separate desktop windows

## Living Docs

These files should be treated as current project planning and operating documents:

- `instructions/README.md` — canonical operator/developer instructions index
- `documentation/README.md` — canonical architecture/security/truth-audit index
- `docs/PROJECT_BRIEF.md` — condensed one-page status, architecture, and priority snapshot
- `README.md` — setup, architecture, and operating conventions
- `ROADMAP.md` — active priorities and handoff log for ongoing work across agents
- `docs/GOALS.md` — measurable product goals and weekly priorities
- `docs/DAILY_WORKFLOW.md` — day-to-day operating runbook mapped to current build capabilities

## Doc Ownership Contract

1. `docs/PROJECT_BRIEF.md` is the only status owner.
2. `ROADMAP.md` owns queue and dated handoff execution logs.
3. `README.md` is architecture/setup/operations reference only.
4. Session logs and active priority lists must not be maintained in `README.md`.

Other status-heavy markdown files in the repo should be treated as historical notes or deep-dive references, not current release truth.
Archived historical docs now live under `docs/archive/`, split between `root-history/` and `planning-history/`.
`CONTRIBUTING.md` stays in the repo root by convention; operational guides like packaging live under `docs/`.

**Project Focus**: Guppy is a **butler/personal assistant**, not a sales tool. Priority is fast response (<3s), accurate first-time routing, and seamless voice integration for daily use.

## Product Surface

- Primary desktop entry point: `guppy_launcher.py`
- Canonical launcher code: `src/guppy/apps/launcher_app.py` and `ui/launcher/`
- Canonical backend code: `src/guppy/api/server.py` (public module), `src/guppy/api/server_runtime.py` (composition shell), imported routers under `src/guppy/api/routes_*.py`, and shared services/context under `src/guppy/api/services_*.py` plus `server_context.py`
- Canonical routing code: `src/guppy/inference/router.py` and its smaller routing fragments
- Shared backend glue: `guppy_core/`
- Compatibility wrappers and quarantined legacy entrypoints: `compat_shims/`
- Quarantined historical desktop surfaces: `compat_shims/legacy_surfaces/`

The supported product path is the unified launcher plus background instances. Historical specialist windows remain env-gated compatibility material only.

## Product Policy

1. New end-user features ship in the unified launcher first.
2. The launcher is the default daily surface; legacy desktop windows are not part of the recommended path.
3. Root wrappers stay thin; working code lives under `src/guppy/*`, `ui/launcher/*`, `guppy_core/*`, and `utils/*`.
4. Status, milestone progress, and dated handoff notes belong in `docs/PROJECT_BRIEF.md` and `ROADMAP.md`, not here.

## Status And History

- Current product/runtime snapshot: `docs/PROJECT_BRIEF.md`
- Active priorities and dated execution log: `ROADMAP.md`
- Historical planning and superseded deep dives: `docs/archive/planning-history/`

**For complete credentials and dependency auditing, use** `docs/CREDENTIALS_AUDIT.md`.

## Capabilities Snapshot

- Desktop chat through the unified launcher with active-instance switching and bounded inter-instance queries
- Local model plus Claude-backed routing
- Push-to-talk, spoken replies, interruption-aware voice handling, and wake-word path
- FastAPI remote chat, voice route, websocket streaming, and readiness endpoints
- Persistent memory, semantic memory, and daemon-backed context awareness
- CRM-lite and VoIP scaffolding with revenue dashboard support

## Focused References

Keep these as separate docs because they still serve as active operational references rather than status clutter:

- `instructions/OPERATIONS.md` — canonical runtime runbook
- `instructions/DEVELOPMENT.md` — canonical engineering workflow and quality gates
- `documentation/ARCHITECTURE.md` — canonical architecture baseline
- `documentation/SECURITY.md` — canonical security + resilience baseline
- `documentation/TRUTH_AUDIT.md` — verified doc truth and drift notes

- `docs/API.md` — endpoint and integration reference
- `docs/VOICE.md` — voice behavior, troubleshooting, and device notes
- `docs/TROUBLESHOOTING.md` — quick operational recovery steps
- `docs/PACKAGING.md` — build and release packaging guide
- `docs/SUPERVISION_WINDOWS.md` — Windows supervisor/service deployment model for API runtime
- `docs/SEED_VAULT_STORAGE.md` — USB-now / NAS-next snapshot strategy for program + knowledge data

The old broad capability catalog and superseded planning docs have been archived. Current status and execution history live in `docs/PROJECT_BRIEF.md` and `ROADMAP.md`.

## Architecture

### Entry Points

- `bin/launch_guppyprime.bat` — **recommended daily launcher** (hub + unified UI with the full local model stack)
- `src/guppy/cli/launch.py` — canonical Python launcher for all surfaces
- `guppy_launcher.py` — unified desktop launcher UI (thin wrapper)
- `src/guppy/cli/agent.py` — terminal / CLI surface
- `guppy_api.py` — remote API server (thin wrapper)
- `guppy_hub.py` — system hub / tray (thin wrapper)

### Launcher Layout

- Left sidebar: Home, Workspaces, Tools, App Mgmt, Local LLM, Models, Voices
- Top bar: session controls + search
- Center stack: active surface view
- Right status panel: live runtime state and recent system log

### Core Modules

- `guppy_core/` — routing, tools, model behavior, shared runtime glue (split into `tool_registry`, `tool_runner`, `system_prompt`, `tool_metrics`)
- `src/guppy/merlin/core.py` — legacy Merlin persona content still used for teaching-style prompt behavior and compatibility helpers
- `src/guppy/voice/voice.py` — TTS, STT, wake-word, interruption control
- `src/guppy/daemon/daemon.py` — reminders, window awareness, background services
- `src/guppy/memory/memory.py` — persistent storage and dashboard data
- `src/guppy/memory/semantic.py` — semantic memory backend layer
- `src/guppy/integrations/crm_voip.py` — external business-system stubs and readiness helpers

## Quick Start

### Install

1. Create or activate the project virtual environment.
1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

1. Install optional extras only if you need the wake-word fast path or Chroma backend:

```powershell
python -m pip install -r requirements-optional.txt
```

1. Optional but common environment setup:

```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "your-key", "User")
```

### Local Model Setup

1. Install Ollama.
1. Start Ollama via the optimised startup script (sets GPU overhead + Flash Attention):

```powershell
%LOCALAPPDATA%\Ollama\start_ollama.bat
```

1. Build all 5 persona models (pulls missing base models automatically):

```powershell
bin/build_models.bat
```

Model roster:

| Agent | Base | VRAM | Role |
| --- | --- | --- | --- |
| `guppy-fast` | qwen2.5:7b | ~5 GB | Fast butler, simple queries |
| `vault-scraper` | qwen2.5:7b | shared blob | Digital Seed Vault extraction |
| `guppy-code` | qwen2.5-coder:14b | ~9 GB | Code review / debug |
| `guppy` | qwen2.5:32b | ~20 GB | Complex butler tasks |
| `guppy-teach` | qwen2.5:32b | shared blob | Socratic teaching |

1. Ensure Ollama is serving on `http://127.0.0.1:11434`.

### Run

```powershell
python src/guppy/cli/launch.py launcher
python src/guppy/cli/launch.py guppyprime
python src/guppy/cli/launch.py hub
python src/guppy/cli/launch.py api
python -m src.guppy.cli.agent

# Supervisor-friendly API launch
bin\\launch_api_supervised.bat
```

Legacy specialist surfaces remain available only behind `GUPPY_ENABLE_LEGACY_SURFACES=1`.

VS Code tasks in this workspace also cover the main launch flows.

## Verification

### Useful Checks

```powershell
# Use the repo virtualenv or activate it first; system Python may not have pytest installed.
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe tests/integration/test_ptt.py
.venv\Scripts\python.exe tests/smoke/smoke_api.py
.venv\Scripts\python.exe tools/verify_ollama_runtime.py
.venv\Scripts\python.exe tools/verify_runtime_challengers.py
.venv\Scripts\python.exe tools/verify_provider_runtime.py
.venv\Scripts\python.exe tools/verify_logging_health.py --emit-probe
```

### Runtime Truth Sources

- API behavior and readiness: `src/guppy/api/server.py`, `src/guppy/api/server_runtime.py`, `src/guppy/api/routes_*.py`, and `src/guppy/api/services_*.py` (wrapper: `guppy_api.py`)
- Auth behavior: `src/guppy/api/auth.py`
- Routing behavior: `src/guppy/inference/router.py` plus router fragments
- Tool surface: `guppy_core/tool_registry.py`, `guppy_core/tool_runner.py`
- Current active work and handoff notes: `ROADMAP.md`

### Router Scorecard Review (6A)

Use the scorecard analyzer to summarize routing quality and generate safe tuning suggestions:

```powershell
python tools/review_router_scorecard.py --days 7
python tools/review_router_scorecard.py --days 7 --write-patch
```

When `--write-patch` is used, suggested overrides are written to:

- `runtime/router_tuning_patch.env`

Review that file before copying any values into `.env`.

## Daily Diary Inputs

The proactive daily report pipeline can ingest manual notes and TODOs without API changes.

- Manual event inputs (optional, read if present under `runtime/`):
  - `manual_events.jsonl` (preferred; fields like `ts`, `text`)
  - `manual_events.txt`
  - `daily_manual_events.md`
- Manual todo inputs (optional):
  - `todo.txt`
  - `todo.md`
- Built-in task inputs: pending tasks from the memory layer (`src/guppy/memory/memory.py`)
- Built-in log inputs: `agent_performance.jsonl`, `session_events.jsonl`, `integration_events.jsonl`, `hub_patterns.jsonl`
- Built-in news inputs: popular RSS feeds (configurable via `GUPPY_DAILY_RSS_FEEDS`)

Useful env knobs:

- `GUPPY_DAILY_RSS_FEEDS` (comma-separated RSS URLs)
- `GUPPY_DAILY_RSS_ITEMS` (items per feed, default 4)
- `GUPPY_DAILY_LOG_LINES` (tail lines per log source, default 8)
- `GUPPY_DAILY_MANUAL_LINES` (tail lines per manual file, default 20)
- `GUPPY_DAILY_SUMMARY_HOUR` (hour of daily run, default 8)
- `GUPPY_NEWS_REPORT_HOURS` (comma-separated hours for news briefs, default `12,18,22`)

End-to-end routine definition:

1. Trigger on schedule (daily summary hour + news brief hours)
2. Gather inputs (RSS feeds, runtime logs, memory/tasks, manual events/todos)
3. Reference yesterday's report (`runtime/daily_reports/YYYY-MM-DD.md`)
4. Synthesize summary + markdown report
5. Persist report to `runtime/daily_reports/`
6. Notify/nudge Guppy with report path when actionable

## API Surface

The remote/API layer already exists and should be treated as alpha, not planned work.

- Base URL: `http://127.0.0.1:8081`
- Auth: `POST /auth/verify`
- Health and readiness: `GET /status`, `GET /startup/check`, `GET /logs/recent`
- Workspace management: `GET /instances`, `POST /instances`, `POST /instances/{name}/activate`, `POST /instances/{name}/governance`, `GET /instances/{name}/logs`, `POST /instances/{name}/query`
- Connector management: `GET /connectors`, `POST /connectors/{id}/verify|connect|reconnect|disconnect`, `GET /instances/{name}/connectors`, `POST /instances/{name}/connectors/{connector}`
- Chat: `POST /chat`, `POST /chat/voice`, `WebSocket /ws`
- Business reporting: `GET /revenue/dashboard`

Recommended validation paths:

```powershell
# Full authenticated smoke path (set local JWT env first)
# $env:GUPPY_JWT_SECRET = "<same-secret-used-by-api>"
python tests/smoke/smoke_api.py

# Strict-mode public auth sanity (expected 400 for dummy Turnstile token)
Invoke-WebRequest https://guppy.sparkscuriositystudio.com/auth/verify -Method POST -Body '{"token":"dummy"}' -ContentType 'application/json'
```

Treat external auth, tunnel, and websocket validation as the release gate for remote use.

## Voice Summary

The voice stack supports push-to-talk, spoken responses, interruption on user typing, and a wake-word path.

- Input path: PTT via `src/guppy/voice/voice.py`
- Primary transcription path: Google STT
- Additional backend support exists for local/fallback paths already wired into the project
- TTS: Kokoro when available, otherwise Windows SAPI fallback
- Wake-word path: implemented, still needs tuning and real-use validation

Useful voice checks:

```powershell
python tests/integration/test_ptt.py
python -c "import sounddevice as sd; import json; print(json.dumps(sd.query_devices(), indent=2))"
```

Set `GUPPY_PTT_INTERACTIVE=1` only when you want the microphone capture smoke to run.

If voice behavior drifts, treat `src/guppy/voice/voice.py` plus `ROADMAP.md` as the current truth, and `docs/VOICE.md` as the deeper operator reference.

## Troubleshooting Quick Hits

- Cloudflare tunnel cert issues: run the Cloudflare login flow again via `bin/cloudflare_terminal.ps1 -Action login`
- API auth failures: verify `GUPPY_JWT_SECRET` and `TURNSTILE_SECRET`, or use `GUPPY_DEV_MODE=1` only for local development
- Voice transcription 400s: test with clear spoken audio and confirm the machine has working STT dependencies
- Ollama failures: verify `ollama serve` is running and confirm models with `ollama list`
- UI slowness: inspect `runtime/agent_performance.jsonl` and run `python tools/review_agent_performance.py`

Use `docs/TROUBLESHOOTING.md` when the quick summary is not enough.

## Packaging Summary

- Primary packaging doc: `docs/PACKAGING.md`
- Quick build path: `bin/build_executable.bat`
- Current packaging goal: pass a clean-machine validation flow before treating builds as release-ready
- Packaging remains a hardening item, not a closed release system

Use `docs/PACKAGING.md` for full build, installer, signing, and distribution details.

## Current Work Pointer

For active priorities and dated execution history, use `ROADMAP.md`.

## Working Style For Multi-Agent Sessions

When multiple agents are touching the repo in parallel:

- Use `README.md` for the stable project picture.
- Use `ROADMAP.md` for active priorities, open questions, and handoff notes.
- Add short dated notes to the handoff log instead of creating another status markdown file.
- Treat older handoff, planning, or completion docs as archive material unless they are being deliberately refreshed; archived docs live under `docs/archive/`.
