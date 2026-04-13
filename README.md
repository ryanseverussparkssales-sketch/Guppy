# Guppy

Guppy is a local-first multi-agent assistant with a unified launcher as the primary daily interface and advanced specialist surfaces for deeper workflows:

- Unified launcher: default front door for assistant, tools, settings, advanced controls, model library, and voice library
- Merlin: mentor / research specialist surface
- Council: dual-agent orchestration specialist surface

## Living Docs

These files should be treated as current project planning and operating documents:

- `README.md` — current source of truth for setup, architecture, and project state
- `ROADMAP.md` — active priorities and handoff log for ongoing work across agents
- `GOALS.md` — measurable product goals and weekly priorities
- `DAILY_WORKFLOW.md` — day-to-day operating runbook mapped to current build capabilities

Other status-heavy markdown files in the repo should be treated as historical notes or deep-dive references, not current release truth.
Archived historical docs now live under `docs/archive/`, split between `root-history/` and `planning-history/`.
`CONTRIBUTING.md` stays in the repo root by convention; operational guides like packaging live under `docs/`.

**Project Focus**: Guppy is a **butler/personal assistant**, not a sales tool. Priority is fast response (<3s), accurate first-time routing, and seamless voice integration for daily use.

## Current State

### Unified Launcher System (2026-04-12)

- Primary desktop entry point is now `guppy_launcher.py`.
- New modular UI architecture is in `ui/launcher/`:
	- `components/` for reusable UI widgets
	- `views/` for Assistant, Tools, Settings, Advanced, Models, and Voices tabs
	- `launcher_window.py` as the shell that composes sidebar, top bar, stacked views, and right status panel
- Advanced standalone surfaces remain available (`merlin_ui.py`, `council_ui.py`) but are no longer the primary product path.

### Launcher/UI Delivery Summary (Handoff)

Implemented launcher package and entrypoint:

- `guppy_launcher.py` — unified desktop app entry
- `ui/launcher/launcher_window.py` — app shell composition
- `ui/launcher/tokens.py` + `ui/launcher/stylesheet.py` — design tokens and styling

Implemented reusable launcher components:

- `ui/launcher/components/sidebar.py`
- `ui/launcher/components/topbar.py`
- `ui/launcher/components/status_panel.py`
- `ui/launcher/components/agent_card.py`
- `ui/launcher/components/toggle_row.py`
- `ui/launcher/components/sparkline.py`

Implemented launcher tab views:

- `ui/launcher/views/assistant_view.py`
- `ui/launcher/views/tools_view.py`
- `ui/launcher/views/settings_view.py`
- `ui/launcher/views/advanced_view.py`
- `ui/launcher/views/models_view.py`
- `ui/launcher/views/voices_view.py`

Behavior wired in launcher shell:

- Sidebar tab navigation to stacked views
- Runtime status polling to right status panel
- Settings save/apply integration with runtime profiles
- Model and voice selection propagation through environment-backed settings

### Operational Commitments (Now Enforced)

- Strict tool schemas are required for tool definitions and input validation (`guppy_core.py`).
- Tool schema audit report is available via `python tools/audit_tool_schemas.py` (writes `runtime/tool_schema_audit.json` and fails on violations).
- API runtime follows external-supervisor ownership by default:
	- `GUPPY_API_OWNS_DAEMON=0`
	- use `bin\\launch_api_supervised.bat`
	- see `docs/SUPERVISION_WINDOWS.md`
- Packaging defaults to one-folder builds for pilot reliability (`build_executable.bat` default behavior).
- one-file builds are now explicit opt-in (`--onefile`).
- Product telemetry is separated from debug-style logs via a SQLite operational mirror:
	- JSONL streams remain for append-only traces
	- SQLite mirror is written by `utils/operational_telemetry.py`
- Background work has hard low-power ceilings in runtime profiles (`utils/runtime_profile.py`) for daemon polling, ambient checks, and API timeouts.

### Progress Review (2026-04-12)

- Strict remote auth path is live in production mode (`GUPPY_DEV_MODE=0`) with Cloudflare routing active to `localhost:8081`.
- Daily routine is now end-to-end: scheduled triggers, RSS + runtime/manual/task inputs, yesterday-reference, markdown report output, and actionable nudge flow.
- Phase 6 reliability baseline advanced with normalized router scorecard telemetry, SLO tracking, fallback/tool-budget metrics, and Council Merlin tuning controls.
- 6A analyzer is implemented (`runtime/review_router_scorecard.py`) and documented; recommendations become useful as `runtime/router_scorecard.jsonl` accumulates live traffic.
- Extensive stress harness is now in place (`tests/stress_system.py`) with latest passing report at `runtime/stress_report_20260412_233040.json`.
- Stress harness now enforces hot-path latency gates and endpoint p95 visibility (`latency_ms_p95_hotpath`, `latency_ms_p95_by_endpoint`) with default hot-path threshold tightened to `1100ms` after repeated stable passes.
- Unified launcher UI parity pass complete: top-nav buttons, DEPLOY SURFACE action, settings sliders + identity fields, status rail bar gauges + badge states, bottom system strip.
- Codebase audit and cleanup complete: 69 files syntax-clean, UTF-8 BOMs stripped, stale archive docs purged, unused `models/` folder removed, `models/` references in README corrected.
- Recovery and operator self-heal shipped in launcher/API: Settings Recovery actions, guarded `/repair` endpoint (dry-run support), runtime launcher event log, and status rail recovery outcome feedback.
- Personalization schema + runtime scaffold shipped: JSON schemas for personas/providers/voices, startup scaffold initialization, and editable launcher Settings tabs with validate/reload/save flows.

### Local Agent Fleet Update (2026-04-12)

- 5-agent local model roster: `guppy-fast` (7B simple), `vault-scraper` (7B structured extraction), `merlin-code` (coder-14B), `guppy` (32B complex), `merlin` (32B teaching).
- GPU/runtime tuning: `OLLAMA_GPU_OVERHEAD` corrected from 8000 -> 0; `OLLAMA_FLASH_ATTENTION=1` enabled. Live verification should use `ollama show <model>` + `ollama ps` because actual processor split depends on active context and concurrent residency.
- Two new router modes: `local` (tier-aware, no cloud) and `local_paired` (7B sketches intent → 32B refines). Both use 60s timeout.
- New specialist modes: `code` (merlin-code + optional Haiku code-review pass) and `vault` (vault-scraper + optional Haiku enrich pass).
- Haiku boost: each local model can request a targeted Haiku refinement pass — `verify`, `code_review`, `enrich`, or `structure`. Controlled by `GUPPY_HAIKU_BOOST=1` (default on).
- Digital Seed Vault agent: `vault-scraper` outputs structured JSON media metadata (film, music, book, game, podcast, etc.) ready for database ingestion.
- `GuppyPrime` launcher (`bin/launch_guppyprime.bat`) is the recommended daily entry point — starts hub silently, then opens the unified launcher with all 5 agents available.

### Recent AI Quality + Code Health Updates (2026-04-12)

- Semantic classifier added in `inference_router.py` (`_classify_task_semantic`) with strict JSON output and heuristic fallback.
- Persistent response cache added in `guppy_ui.py` using `runtime/response_cache.sqlite3` (survives restarts).
- Semantic memory injection wired into request-time system prompt construction in `guppy_ui.py`.
- `GUPPY_TOOL_BUDGET` fallback default corrected from 8 to 6 in `guppy_ui.py`.
- Public `utils/` functions received explicit type annotations for safer call contracts.
- `pytest.ini` + root `conftest.py` added so `python -m pytest` works from project root.
- Sparkline implementation consolidated to `ui/components/sparkline.py`; launcher component now aliases the shared widget.

### Implemented

- Desktop UI surfaces: `guppy_launcher.py` (unified), `merlin_ui.py`, `council_ui.py`
- Smart dispatcher (Phases 1-3): Task classification → Haiku-first routing with fallback chain
- **Phase 4 voice fast-path**: Wake-word → Haiku-first always (`voice_triggered` flag), <2s latency target
- **Phase 5 response cache**: TTL-based module-level cache for simple/tool-free queries; cache hits skip API entirely
- Local + Claude routing: `guppy_core.py`, `inference_router.py`
- FastAPI remote surface: `guppy_api.py`, `guppy_api_auth.py` — strict mode active, public endpoint live at `guppy.sparkscuriositystudio.com`
- Supervisor-first API lifecycle: app-managed daemon startup/shutdown is disabled by default; external supervisor is preferred on Windows
- Web client alpha: `web/index.html`, `web/turnstile.js` — Cloudflare Turnstile wired with real site key
- API smoke testing: `tests/smoke_api.py`
- Hub/status surface and runtime logging: `guppy_hub.py`, `runtime/hub.log`
- Router scorecard telemetry: `runtime/router_scorecard.jsonl` captures normalized route/task/model/fallback/tool/SLO metrics per request
- Operational telemetry mirror: key runtime events are mirrored into `runtime/ops_telemetry.sqlite3` for repeat querying
- Hub Orchestrator: `utils/hub_operator.py` — IPC, pattern logging, health checks, scheduled Haiku analysis (15min auto-tick)
- Persistent memory: `guppy_memory.py`
- Semantic memory dual backend: `guppy_semantic_memory.py` — SQLite default, Chroma opt-in (`GUPPY_SEMANTIC_BACKEND=chroma`)
- Voice pipeline with wake-word: `guppy_voice.py` — PTT, Kokoro TTS with SAPI fallback, openwakeword path, RMS VAD silence cutoff (`GUPPY_SILENCE_CUTOFF`, `GUPPY_SPEECH_THRESHOLD`)
- Proactive daemon + ambient watcher: `guppy_daemon.py` — agent health checks, reminder nudges, clipboard/window polling; Haiku semantic gate filters clipboard content before offering
- Daily activity + world-news diary: `guppy_daemon.py` compiles a daily markdown report from RSS headlines, runtime logs, memory/tasks, manual events, and yesterday's report reference (saved to `runtime/daily_reports/YYYY-MM-DD.md`)
- Scheduled news briefs: `guppy_daemon.py` also generates world-news reports at `12:00`, `18:00`, and `22:00` (saved as `runtime/daily_reports/YYYY-MM-DD-news-HH00.md`)
- **Phase 11 ambient banner**: `AmbientBanner` widget in `guppy_ui.py` — non-intrusive offer bar between chat and input; shows Haiku's suggested action; "Ask Guppy" pre-fills input; auto-dismisses 30s
- 73 tools registered in `guppy_core.py` including `run_python`, `notify`, `web_summarize`, `github`, `semantic_remember/recall`, Gmail, Spotify, calendar, and more
- Revenue dashboard route plus CRM/VoIP scaffolding: `guppy_api.py`, `crm_voip_integrations.py`
- Tool-loop guardrails: capped tool budgets in `guppy_ui.py` and `council_ui.py` to prevent runaway long-tail latency
- Council performance tuning: Merlin panel now uses tuned local inference defaults (`COUNCIL_MERLIN_TIMEOUT`, `COUNCIL_MERLIN_NUM_PREDICT`) for faster completion under load

**For complete credentials & dependencies audit, see** `CREDENTIALS_AUDIT.md`

### Partial / Needs Hardening

- **CRM & VoIP tools**: Safe stubs wired (log intent, validate config); no live calls or writes yet. Do not wire live calls until classifier accuracy is validated.
- **`guppy_ui.py` legacy surface**: 2,200 lines, standalone, not imported by council_ui. Diverging from the new launcher. Needs a retirement decision (freeze vs. migrate to launcher).
- **Vault agent schema**: `vault-scraper` Modelfile has base schema; production use needs a per-media-type schema registry and dedup logic.
- **CI quality gates**: Workflow added at `.github/workflows/quality-gates.yml` to run schema audit and core smoke/workflow tests on push/PR.
- Packaging: one-folder distribution is now the default path for pilot builds; one-file packaging remains optional.
- `web_summarize` tool uses HTTP+Haiku fallback until `FIRECRAWL_API_KEY` is set.
- Async FastAPI handlers wrap sync inference via `run_in_executor` — acceptable at butler scale, but concurrent API requests will queue against the thread pool.

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
- `docs/SUPERVISION_WINDOWS.md` — Windows supervisor/service deployment model for API runtime
- `docs/SEED_VAULT_STORAGE.md` — USB-now / NAS-next snapshot strategy for program + knowledge data

The old broad capability catalog and historical handoff/completion docs have been archived and purged. Active summary lives here in `README.md`.

## Architecture

### Entry Points

- `bin/launch_guppyprime.bat` — **recommended daily launcher** (hub + unified UI, all 5 agents)
- `guppy_launcher.py` — unified desktop launcher UI (direct Python entry)
- `guppy_agent.py` — terminal / CLI surface
- `merlin_ui.py` — Merlin desktop UI (standalone specialist surface)
- `council_ui.py` — dual-agent UI (standalone specialist surface)
- `guppy_api.py` — remote API server
- `guppy_hub.py` — system hub / tray

### Launcher Layout

- Left sidebar: Assistant, Tools, Settings, Advanced, Models, Voices
- Top bar: session controls + search
- Center stack: active surface view
- Right status panel: live runtime state and recent system log

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
2. Start Ollama via the optimised startup script (sets GPU overhead + Flash Attention):

```powershell
%LOCALAPPDATA%\Ollama\start_ollama.bat
```

3. Build all 5 persona models (pulls missing base models automatically):

```powershell
build_models.bat
```

Model roster:

| Agent | Base | VRAM | Role |
|---|---|---|---|
| `guppy-fast` | qwen2.5:7b | ~5 GB | Fast butler, simple queries |
| `vault-scraper` | qwen2.5:7b | shared blob | Digital Seed Vault extraction |
| `merlin-code` | qwen2.5-coder:14b | ~9 GB | Code review / debug |
| `guppy` | qwen2.5:32b | ~20 GB | Complex butler tasks |
| `merlin` | qwen2.5:32b | shared blob | Socratic teaching |

4. Ensure Ollama is serving on `http://127.0.0.1:11434`.

### Run

```powershell
python guppy_launcher.py
python guppy_agent.py
python merlin_ui.py
python council_ui.py
python guppy_hub.py

# Supervisor-friendly API launch
bin\\launch_api_supervised.bat

# Local direct API launch (development)
python guppy_api.py
```

VS Code tasks in this workspace also cover the main launch flows.

## Verification

### Useful Checks

```powershell
python tests/test_ptt.py
python tests/smoke_api.py
python tools/verify_ollama_runtime.py
python tools/verify_provider_runtime.py
python tools/verify_logging_health.py --emit-probe
```

### Runtime Truth Sources

- API behavior and readiness: `guppy_api.py`
- Auth behavior: `guppy_api_auth.py`
- Routing behavior: `inference_router.py`
- Tool surface: `guppy_core.py`
- Current active work and handoff notes: `ROADMAP.md`

### Router Scorecard Review (6A)

Use the scorecard analyzer to summarize routing quality and generate safe tuning suggestions:

```powershell
python runtime/review_router_scorecard.py --days 7
python runtime/review_router_scorecard.py --days 7 --write-patch
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
- Built-in task inputs: pending tasks from `guppy_memory.py`
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

## Session Log (2026-04-12)

All items from the previous execution sprint are complete. See `ROADMAP.md` for the current prioritised work queue.

**Completed this session:**
- Launcher UI parity pass: top-nav buttons, DEPLOY SURFACE action, settings sliders + identity fields, status rail gauges + badge states, bottom system strip
- Codebase audit: 69 files syntax-clean, UTF-8 BOMs stripped, stale docs/archive purged, empty `models/` removed
- Code quality fixes: `set_input_text()` indentation bug, `recommend_runtime_profile()` return type, `test_router_smoke.py` hardcoded path, README model paths
- Latest stress report: `runtime/stress_report_20260412_233040.json`

**Completed in latest follow-up:**
- Added API operational telemetry query/report endpoints and launcher-side visibility hooks.
- Hardened API hot paths (`/status`, `/startup/check`) with cache-first behavior and deep-check mode.
- Added guarded API repair endpoint (`/repair`) with dry-run support and actions for warmup, daemon restart, and runtime audit.
- Added launcher Recovery section actions in Settings and status-rail recovery outcome line.
- Added personalization schemas and runtime scaffold (`utils/personalization_config.py`) with tests (`tests/test_personalization_config_scaffold.py`).
- Added pre-cruise runtime verifier scripts:
	- `tools/verify_ollama_runtime.py`
	- `tools/verify_provider_runtime.py`
	- `tools/verify_logging_health.py`
- Added coding ops tool surface in `guppy_core.py`: `test_targeted`, `lint_fix`, `typecheck_targeted`, `git_patch_summary`.
- Added provider/coding dependencies for cheap/free routing paths and local quality checks (`openai`, `google-generativeai`, `mistralai`, `ruff`, `mypy`, `pytest-xdist`).

**Useful runtime commands:**

```powershell
# Router scorecard analysis
python runtime/review_router_scorecard.py --days 7 --write-patch

# Stress suite
set PYTHONPATH=.
python -m tests.stress_system --api-requests 900 --api-workers 35 --route-iterations 14000 --reminders 900 --log-events 8000

# Test suite
python -m tests.test_smart_dispatch
python -m tests.test_router_smoke
python -m tests.test_reminder_workflow
python -m tests.test_runtime_smoke
```

## API Surface

The remote/API layer already exists and should be treated as alpha, not planned work.

- Base URL: `http://127.0.0.1:8081`
- Auth: `POST /auth/verify`
- Health and readiness: `GET /status`, `GET /startup/check`, `GET /logs/recent`
- Chat: `POST /chat`, `POST /chat/voice`, `WebSocket /ws`
- Business reporting: `GET /revenue/dashboard`

Recommended validation paths:

```powershell
# Full authenticated smoke path (set local JWT env first)
# $env:GUPPY_JWT_SECRET = "<same-secret-used-by-api>"
python tests/smoke_api.py

# Strict-mode public auth sanity (expected 400 for dummy Turnstile token)
Invoke-WebRequest https://guppy.sparkscuriositystudio.com/auth/verify -Method POST -Body '{"token":"dummy"}' -ContentType 'application/json'
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

1. **Semantic classifier** — Replace keyword bag-of-words in `inference_router._classify_task()` with a Haiku-backed structured output classifier. Fixes known false-positive routing on "what is X" queries.
2. **Persistent response cache** — Back `_RESPONSE_CACHE` with SQLite so warm-path cache survives daily restarts. Already have `ops_telemetry.sqlite3` as a model.
3. **Cross-session memory injection** — Wire `guppy_semantic_memory` recall into the system prompt on every request (Phase 12). Backend exists; injection logic is the gap.
4. **CI baseline** — Add `conftest.py` + `pytest.ini`; wire at least `test_smart_dispatch`, `test_router_smoke`, `test_reminder_workflow` to run on `python -m pytest`.
5. **Type annotations on `utils/`** — Annotate return types on all public functions in `utils/` to prevent caller type assumption bugs.
6. **`guppy_ui.py` retirement plan** — Define the path: either archive as frozen or migrate council_ui.py off it. Stop updating it as a peer to the launcher.
7. **Voice tuning** — Validate wake-word → Haiku fast-path latency in real use; tune openwakeword cooldown.
8. **CRM workflow** — Only after classifier accuracy is validated; convert one stub to a complete end-to-end flow.

## Working Style For Multi-Agent Sessions

When multiple agents are touching the repo in parallel:

- Use `README.md` for the stable project picture.
- Use `ROADMAP.md` for active priorities, open questions, and handoff notes.
- Add short dated notes to the handoff log instead of creating another status markdown file.
- Treat older handoff, planning, or completion docs as archive material unless they are being deliberately refreshed; archived docs live under `docs/archive/`.
