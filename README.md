# Guppy

Windows-first, local-first personal assistant workspace. This README is the stable setup, launch, and operator-reference entrypoint; use `docs/PROJECT_BRIEF.md` for active status and roadmap updates.

## Model Roster

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
python src/guppy/cli/launch.py launcher --start automation-test
python src/guppy/cli/launch.py guppyprime
python src/guppy/cli/launch.py hub
python src/guppy/cli/launch.py api
python -m src.guppy.cli.agent

# Supervisor-friendly API launch
bin\\launch_api_supervised.bat

# Guided automation-test entrypoint
bin\\launch_automation_test.bat
```

Supported desktop shortcut path:

```powershell
powershell -ExecutionPolicy Bypass -File tools\ensure_desktop_launcher.ps1
```

That refreshes `Desktop\Guppy Launcher.lnk` and `Desktop\Applications\Guppy Launcher.bat`. When a packaged build exists, the shortcut points to `dist\Guppy\Guppy.exe`; otherwise it falls back to the repo launcher helper in `bin\Guppy.bat`.

Historical specialist surface code is quarantined for migration reference and is not a supported launcher path.

VS Code tasks in this workspace also cover the main launch flows.

## Doc Ownership Contract

`docs/PROJECT_BRIEF.md` is the single active status, roadmap, and handoff source.

`README.md` is architecture/setup/operations reference only.

`documentation/` owns canonical technical architecture, security, and truth-audit material.

`docs/archive/` is historical only.

## Build Truth Path

Use `tools/dev_workflow.py` as the canonical local and CI command surface.

```powershell
# Use the repo virtualenv or activate it first.
.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta
.venv\Scripts\python.exe tools/dev_workflow.py test-fast
.venv\Scripts\python.exe tools/dev_workflow.py test-default
.venv\Scripts\python.exe tools/dev_workflow.py test-smoke
.venv\Scripts\python.exe tools/dev_workflow.py release-check
```

- `dev-check` runs the build guardrails and audits.
- `test-fast` runs the unit-focused fast path.
- `test-default` runs the default `tests/unit` + `tests/integration` suite.
- `test-smoke` runs launcher/runtime/security smoke coverage.
- `release-check` bundles release-oriented validation and writes a JSON receipt plus a short text summary under `.tmp/dev-workflow/reports/`.

The command entrypoint keeps temp, cache, and pytest scratch data inside `.tmp/dev-workflow/` so local runs and CI do not depend on machine-global temp locations.

## Architecture Seams

The active refactor path now has a small typed seam layer under `src/guppy/`:

- `src/guppy/launcher_application/` holds launcher-facing intents, state contracts, connector-facing launcher services, and the shared workflow catalog.
- `src/guppy/experience_config/` holds runtime settings, persona, provider, and voice helpers so launcher personalization/config logic can move out of the Qt shell in small, typed slices.
- `src/guppy/workspace_governance/` holds workspace, connector inventory, governance normalization, and capability-policy helpers.
- `src/guppy/runtime_application/` holds runtime and startup-readiness contracts.

New launcher-facing behavior should prefer these seams over adding more direct UI imports into runtime or `utils/` internals. App Mgmt workflow recipes should come from `src/guppy/launcher_application/workflows.py`, not inline view literals.

## Verification

### Useful Checks

```powershell
# Canonical workflow commands
.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline
.venv\Scripts\python.exe tools/dev_workflow.py test-default
.venv\Scripts\python.exe tools/dev_workflow.py test-smoke

# Targeted/manual checks
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
- Live architecture map: `docs/LIVE_ARCHITECTURE.md`
- Build and CI truth path: `docs/BUILD_TRUTH_PATH.md`
- Legacy quarantine rules: `docs/LEGACY_SURFACES.md`
- Current active work, roadmap, and handoff notes: `docs/PROJECT_BRIEF.md`

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

If voice behavior drifts, treat `src/guppy/voice/voice.py` plus `docs/PROJECT_BRIEF.md` as the current product-status reference, and `docs/VOICE.md` as the deeper operator reference.

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

For active priorities, checkpoints, and short handoff notes, use `docs/PROJECT_BRIEF.md`.

## Working Style For Multi-Agent Sessions

When multiple agents are touching the repo in parallel:

- Use `README.md` for the stable project picture.
- Use `docs/PROJECT_BRIEF.md` for active priorities, open questions, and handoff notes.
- Add short dated notes to the handoff section there instead of creating another status markdown file.
- Treat older handoff, planning, or completion docs as archive material unless they are being deliberately refreshed; archived docs live under `docs/archive/`.
