# Guppy: Claude Code Reference

**Purpose:** Persistent notes on architecture, conventions, known issues, and integration points for Claude (and future agents).

**Last updated:** 2026-04-29 — Phases 1–5 complete

---

## Active Roadmap

**→ See `docs/MASTER_PHASE_PLAN.md` for the active three-surface architecture roadmap.**

Three dedicated surfaces replacing the single AssistantView — **Phases 1–5 ✅ shipped:**
1. **Companion** (`/companion`) — Voice/chat/vision, personality-first, avatar presence ✅
2. **Workspace** (`/workspace`) — 8-tab operations hub: Chat | Agents | CRM | Screen | Files | PC | Reminders | Calls ✅
3. **Codespace** (`/codespace`) — 3-tab: Chat | Sandbox (Docker) | Triage (self-triage + AI fix proposals) ✅

Phase 5 ✅ complete — VoIP, ambient wake mode, screen AI summaries, self-improvement pipeline, avatar upgrade.

---

## Architecture Overview

### Core Topology (PRIMARY SURFACE: Web UI)
```
Web UI (FastAPI + React) ◄─────────── PRIMARY SURFACE
    ↓
launcher_app.py (Qt Wrapper)
    ↓ (spawns server + opens browser)
    localhost:8080 (FastAPI + React)
            ↓
    launcher_application/ (intents, state contracts, services)
            ↓
    experience_config/ (settings, persona, voice)
            ↓
    API backend (inference, providers, workspace state)
```

**Architecture decision (2026-04-28):** Web UI is now the **primary & authoritative surface**. Desktop launcher (`launcher_app.py`) is a **wrapper** that spawns the FastAPI server locally and opens a browser window. Single codebase (FastAPI + React), no dual UI maintenance.

**Surface architecture decision (2026-04-28):** Single `AssistantView` is being replaced by three dedicated surfaces (Companion / Workspace / Codespace). See `docs/MASTER_PHASE_PLAN.md`.

### Three-Surface Architecture — Phases 1–5 Complete (2026-04-29)

**Backend modules (all mounted in server_runtime.py):**
| File | Routes | Purpose |
|---|---|---|
| `src/guppy/api/routes_surface.py` | `/api/surface/*` | State, config, task spawn, SSE event bus |
| `src/guppy/api/routes_companion.py` | `/api/companion/*` | Personality, voice session, vision, tool whitelist |
| `src/guppy/api/routes_workspace_data.py` | `/api/workspace/*` | Contacts/tasks JSON API + pipeline proxy |
| `src/guppy/api/routes_codespace.py` | `/api/codespace/*` | Docker sandbox lifecycle + triage + self-improvement endpoints |
| `src/guppy/codespace/codespace_triage.py` | — | Triage run history, watchdog thread, dev-check runner |
| `src/guppy/api/routes_voip.py` | `/api/voip/*` | Call log CRUD, live Twilio REST calls, webhook |
| `src/guppy/api/routes_screen_monitor.py` | `/api/screen/*` | Timeline aggregation, AI activity summaries, 30-min background job |
| `src/guppy/codespace/self_improve.py` | — | AI fix proposals via Ollama, git branch apply, dev-check validation |
| `src/guppy/api/routes_calendar.py` | `/api/calendar/*` | Local event CRUD + live Google Calendar sync |
| `src/guppy/api/routes_email.py` | `/api/email/*` | Local thread cache + live Gmail sync |
| `src/guppy/api/routes_media.py` | `/api/media/*` | qBittorrent proxy, media catalog, Whisper transcription |
| `src/guppy/api/routes_documents.py` | `/api/documents/*` | Upload, AI analysis, download |
| `src/guppy/api/routes_tasks.py` | `/api/tasks/*` | Task CRUD |
| `src/guppy/api/routes_mcp.py` | `/api/mcp/*` | MCP plugin manager — add/remove/enable/test servers |
| `src/guppy/api/routes_desktop.py` | `/api/desktop/*` | pyautogui screenshot/click/type/drag/scroll |

**New frontend — Companion (`/companion`):**
- `web/src/views/CompanionView.tsx` — PersonalityPicker, wake-word toggle, camera vision, avatar presence, escalate to Workspace, **ambient fullscreen mode** (SSE alerts → TTS)
- `web/src/components/surface/AvatarPresence.tsx` — idle/listening/thinking/speaking animated orb (**Phase 5**: 11-bar waveform, orbit dots, triple-ring pulse, glow bloom)
- `web/src/components/surface/BackendSelector.tsx` — per-surface model picker
- `web/src/components/surface/SurfaceStatusBar.tsx` — cross-surface live SSE chip

**New frontend — Workspace (`/workspace`) — 11-tab icon strip:**
- `web/src/views/WorkspaceView.tsx` — Chat | Agents | CRM | Screen | Files | PC | Tasks | Calls | Calendar | Email | Media
- `web/src/components/workspace/SystemMetricsPanel.tsx` — live CPU/RAM/disk/net gauges
- `web/src/components/workspace/CRMPanel.tsx` — contacts + tasks CRUD
- `web/src/components/workspace/ScreenPanel.tsx` — Screenpipe recent/search/timeline viewer (AI summary Sparkles chip per window)
- `web/src/components/workspace/FilesPanel.tsx` — navigable file browser + text preview
- `web/src/components/workspace/AutomationPanel.tsx` — reminders create/cancel/list
- `web/src/components/workspace/VoIPPanel.tsx` — call log, log-call form, inline note editor, Twilio status badge
- `web/src/components/workspace/CalendarPanel.tsx` — month grid + agenda, local CRUD + Google Calendar sync
- `web/src/components/workspace/EmailPanel.tsx` — inbox, thread reader, draft composer, Gmail sync
- `web/src/components/workspace/MediaLibraryPanel.tsx` — qBittorrent, media catalog, call recordings + Whisper
- `web/src/components/workspace/TaskManagerPanel.tsx` — task CRUD with project/status filters

**New frontend — Codespace (`/codespace`) — 3-tab icon strip:**
- `web/src/views/CodespaceView.tsx` — Chat | Sandbox | Triage tabs
- `web/src/components/codespace/SandboxPanel.tsx` — Docker container lifecycle + SSE terminal
- `web/src/components/codespace/TriagePanel.tsx` — dev-check run history, failure list, output modal, **AI fix proposals with diff viewer** (DiffView + ProposalModal + Apply/Reject)

**Navigation:** Sidebar shows Companion | Workspace | Codespace as primary tabs. Legacy routes (`/assistant`, `/launch-control`, `/agents`, `/instances`, `/models`) redirect to new surfaces. Sidebar auto-collapses on all three primary surfaces.

### Key Modules
- **`src/guppy/cli/launch.py`** — Single entrypoint for all launch modes (launcher, guppyprime, hub, api, agent)
- **`src/guppy/api/`** — FastAPI backend (routes, inference, provider mgmt, workspace persistence) + REST API with JWT auth, repair token, dev mode
- **`src/guppy/launcher_application/`** — Shared workflow catalog, launcher services, state contracts
- **`src/guppy/experience_config/`** — Runtime persona, provider selection, voice settings
- **`src/guppy/apps/`** — UI surfaces: `launcher_app.py` (Qt wrapper, spawns server), `hub_app.py` (legacy, deprecated in favor of web UI)
- **Web UI (React)** — Primary surface, served by FastAPI. Handles chat, workspace management, model selection, settings, tool execution.

### Known Architecture Seams
1. **Desktop launcher is now a wrapper (2026-04-28)** — `launcher_app.py` (Qt) spawns the FastAPI server locally and opens `http://localhost:<port>` in a browser. Not a full UI, just bootstrap. All UI logic lives in the web UI (React). This simplifies maintenance and eliminates dual codebases.

2. **Legacy code quarantined** — `compat_shims/legacy_surfaces/` contains intentional quarantine marker. `src/guppy/merlin/` is deprecated: `__init__.py` emits a `DeprecationWarning` and `check_architecture_boundaries.py` blocks all external imports. No active code references it. `.quarantine/` contains a README only — confirmed intentional archival, not dead code.

3. **`compat_shims/launcher_ui/` in progress** — Old Qt desktop UI code. Being phased out as features migrate to web UI. Will be archived after web UI feature parity complete (currently ✅ parity done, cleanup in progress).

4. **Catalog routes are all production** — `launcher_application/` catalogs (connector, workflow, instance, voice) are active production code. No experimental catalog routes exist.

5. **Single /repair endpoint** — `/repair` and `/repair-token/refresh` live only in `routes_ops.py`, mounted via `build_ops_router()` in `server_runtime.py`. The previously referenced `snapshot_misc_routes.py` and `_server_fragment_routes_core.py` no longer exist.

---

## Build & Test

### Local Development
```powershell
# Activate venv (if not already active)
.venv\Scripts\activate

# Run canonical dev workflow
python tools/dev_workflow.py dev-check --guard-scope delta
python tools/dev_workflow.py test-fast         # Unit tests only
python tools/dev_workflow.py test-default      # Unit + integration
python tools/dev_workflow.py test-smoke        # Smoke coverage
python tools/dev_workflow.py release-check     # Full validation
```

### Bootstrap
If virtual env not detected, run:
```powershell
powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
```

### Environment
- **Python:** ≥ 3.12 (see `pyproject.toml`)
- **Ollama:** Must be running on `http://127.0.0.1:11434`
- **Key env vars:**
  - `GUPPY_DEV_MODE` — Enables dev endpoints, logging (see `src/guppy/api/auth.py:36`)
  - `GUPPY_JWT_SECRET` — JWT signing key (fallback if keyring unavailable)

### Test Structure
- **`tests/smoke/`** — Runtime smoke tests (launcher, API, security)
- **`tests/unit/`** — Fast unit tests
- **`tests/integration/`** — Slower integration tests
- Note: Some tests resolve via `compat_shims/launcher_ui/tests/` (pytest compiles them correctly, but literal path `tests/unit/test_...` may be imprecise)

---

## Security & Repair Token

### Auth
- **Endpoint:** `POST /repair` and `GET /repair-token/refresh`
- **Guard:** `X-Repair-Token` header (checked at `src/guppy/api/services_ops.py`)
- **JWT:** Secret resolved from keyring or `GUPPY_JWT_SECRET` env var (see `src/guppy/api/auth.py:36–41`)

### Database (SQLite)
- **Pragmas applied** (see `utils/db_utils.py:89–93`):
  - `journal_mode=WAL` (write-ahead logging)
  - `synchronous=...` (durability)
  - `busy_timeout=...` (concurrency)
  - `foreign_keys=ON` (referential integrity)
  - `temp_store=MEMORY` (temp table performance)

---

## Known Issues & TODOs

### 🟡 Documentation
- [ ] Add architecture diagram to README.md

### 🟡 Credential-gated features (code is live, need env vars to activate)
- Gmail sync — set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`
- Google Calendar sync — same Google env vars (or `GOOGLE_CALENDAR_CREDENTIALS` token file)
- HubSpot live writes — set `HUBSPOT_API_KEY`
- Twilio calls — set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`

### 🟢 Verified Working (2026-04-29)
- ✅ CLI launcher paths (launcher, guppyprime, hub, api, agent)
- ✅ JWT and repair token auth flows
- ✅ Database pragmas and hardening
- ✅ All documented tool scripts and test files
- ✅ `GUPPY_DEV_MODE` env var and logging
- ✅ **Three-surface architecture Phases 1–5 complete** — Companion/Workspace/Codespace fully shipped
- ✅ **Workspace 11-tab hub** — Calendar, Email, Media, Tasks added; all backed by live routes
- ✅ **MCP plugin manager** — add/remove/enable/test MCP servers; MCPView wired
- ✅ **Desktop control API** — pyautogui screenshot/click/type (graceful fallback if pyautogui absent)
- ✅ **Themes** — Dark, Liber Designatum (occult), Fear & Loathing (gonzo), Creem × Rolling Stone (rock mag)
- ✅ **Inference metrics** — persisted to guppy_main.db, visible in AdminPanel `/admin`
- ✅ **Gmail sync** — live via google-api-python-client (needs credentials)
- ✅ **Google Calendar sync** — live, upserts 90-day window (needs credentials)
- ✅ **HubSpot/Salesforce/GHL/Zoho contact + deal upsert** — live REST (needs API keys)
- ✅ **Twilio outbound calling** — live REST call placement (needs credentials)
- ✅ **Desktop launcher** — `Desktop\Guppy Launcher.lnk` updated via `tools/ensure_desktop_launcher.ps1`
- ✅ **Web UI rebuilt** — static assets in `static/` reflect all current views and themes

**For detailed implementation notes on completed initiatives, see `SHIPPING_LOG.md` in the Guppy repo.**

---

## Tools & Utilities

### Build & Dev Workflow
- **`tools/dev_workflow.py`** — Canonical build system. Use this for all CI/local validation.
- **`tools/check_architecture_boundaries.py`** — Verify module import rules
- **`tools/check_wrapper_integrity.py`** — Validate wrapper shims
- **`tools/check_doc_ownership.py`** — Audit doc source of truth
- **`tools/check_new_module_line_cap.py`** — Enforce module size limits
- **`tools/pilot_exit_check.py`** — Graceful shutdown verification
- **`tools/verify_logging_health.py`** — Log system audit
- **`tools/verify_ollama_runtime.py`** — Ollama availability check
- **`tools/verify_voice_runtime.py`** — Voice engine availability check (edge_tts, kokoro, pyttsx3, ElevenLabs)
- **`tools/run_overnight_low_compute.py`** — Off-hours testing

### Desktop Launcher
- **`tools/ensure_desktop_launcher.ps1`** — Updates `Desktop\Guppy Launcher.lnk` to point to dist exe (if built) or repo launcher

---

## Launcher Patterns

### One-Click Launchers
- `Guppy_WebUI_Launcher.bat` → `bin/launch_web_ui.bat` (local Web UI)
- `OpenAI_WebUI_Launcher.bat` → `launch_openai_webui.ps1` (Docker OpenAI surface)

### Supervisor-Friendly
- `bin/launch_api_supervised.bat` — For external monitoring/restart on crash
- `bin/launch_automation_test.bat` — Guided automation test entrypoint

### Model Roster (Ollama)
| Model | Base | VRAM | Role |
|-------|------|------|------|
| `guppy-fast` | qwen2.5:7b | ~5 GB | Fast butler, simple queries |
| `vault-scraper` | qwen2.5:7b | shared | Digital Seed Vault extraction |
| `guppy-code` | qwen2.5-coder:14b | ~9 GB | Code review, debug |
| `guppy` | qwen2.5:32b | ~20 GB | Complex butler tasks |
| `guppy-teach` | qwen2.5:32b | shared | Socratic teaching |

### Model Roster (llama.cpp — ROCm/HIP)
| Backend key | Model | Port | VRAM | Role |
|-------------|-------|------|------|------|
| `llamacpp-gemma` | Gemma 4 E4B Heretic ARA | 8080 | ~8.5 GB | Vision — **PLE issue in llama.cpp #22243: silently degraded output** |
| `llamacpp-pepe` | Assistant Pepe 8B Q8_0 | 8082 | ~8.5 GB | Fast chat, Mode A |
| `llamacpp-qwen3` | Qwen3 35B-A3B MoE | 8083 | ~19 GB | Reasoning, Mode B (solo only) |
| `llamacpp-minicpm` | MiniCPM-o 4.5 Omni | 8084 | ~9 GB | Vision+speech, needs mmproj |
| `llamacpp-dispatch` | Qwen2.5-3B-Instruct Q4_K_M | 8085 | ~2 GB | Orchestrator, auto-starts |
| `llamacpp-hermes4` | Hermes 4 14B Q5_K_M | 8086 | ~11 GB | Tools + uncensored (primary recommended) |
| `llamacpp-hermes3` | Hermes 3 8B Lorablated Q8_0 | 8087 | ~9 GB | Fast tools + uncensored |
| `llamacpp-rocinante` | Rocinante X 12B Q5_K_M | 8088 | ~10 GB | Creative writing / roleplay |
| `llamacpp-xlam` | xLAM-2-8B-fc-r Q4_K_M | 8089 | ~5 GB | Tool-call specialist (#1 BFCL ≤8B); auto-routed on task_type=tool_call |
| `llamacpp-chat` | Llama 3.3 70B Instruct Q4_K_M | 8090 | 0 VRAM (~42 GB RAM) | CPU-only flagship chat; ~4-6 tok/s on Ryzen 9 9900X |

**Gemma 4 E4B PLE warning:** llama.cpp issue #22243 — PLE (Per-Layer Embeddings) architecture not fully implemented; output quality is silently degraded. The `gemma-4-heretic-ara` fine-tune shares this issue. Use Hermes or Rocinante for tool-capable or quality-sensitive tasks. Gemma 4 26B-A4B or 31B work correctly.

---

## Config

### instances.json
Located at `config/instances.json`. Defines available runtime instances:
- `guppy-primary` (enabled) — Default instance
- `builder-collab` (enabled: false) — Optional builder collaboration instance

---

## When to File Issues

- Architecture questions → Check `.builder/docs/`
- Build/test failures → Run `python tools/dev_workflow.py dev-check`
- Missing paths → Verify against canonical brief in `docs/PROJECT_BRIEF.md`
- Security concerns → Review `src/guppy/api/auth.py` and repair token flow
- Performance → Profile with `tools/verify_ollama_runtime.py`

---

## For Claude Agents

**Read in this order before starting work:**
1. **Your memory** (`MEMORY.md` in workspace) — Current state, roadmap, active tasks
2. **This file** (CLAUDE.md) — Architecture, modules, patterns
3. **Project docs** (`docs/PROJECT_BRIEF.md` = roadmap/status; `docs/LIVE_ARCHITECTURE.md` = architecture deep-dive)

**When making changes:**
- Update CLAUDE.md (this file) if you change architecture or add modules
- Add tests (unit or integration, in `tests/`)
- Run: `python tools/dev_workflow.py dev-check --guard-scope delta`

**When debugging:**
1. Enable `GUPPY_DEV_MODE` env var
2. Check Ollama is running on `http://127.0.0.1:11434`
3. Review logs from `src/guppy/api/auth.py` (dev mode logging)
