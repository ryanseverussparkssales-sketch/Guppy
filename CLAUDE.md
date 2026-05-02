# Guppy: Claude Code Reference

**Purpose:** Persistent notes on architecture, conventions, known issues, and integration points for Claude (and future agents).

**Last updated:** 2026-05-03 — Two-model core stability checkpoint (Rocinante + Hermes4)

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

2. **Legacy code archived** — `compat_shims/legacy_surfaces/` contains intentional quarantine marker. `src/guppy/merlin/` was archived to `docs/archive/deprecated-modules/merlin/` on 2026-05-01 (was emitting `DeprecationWarning`; no active code referenced it). `compat_shims/launcher_ui/` (93 files) archived to `docs/archive/deprecated-modules/compat_launcher_ui/` on 2026-05-01.

3. **`compat_shims/launcher_ui/` ARCHIVED** — Old Qt desktop UI code fully archived 2026-05-01. Only `compat_shims/legacy_surfaces/` and `compat_shims/__init__.py` remain active as shim roots.

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
- **Ollama:** Not used for inference routing (`can_stream_ollama=False`). Only vault-scraper agent uses Ollama directly.
- **Key env vars:**
  - `GUPPY_DEV_MODE` — Enables dev endpoints, logging (see `src/guppy/api/auth.py:36`)
  - `GUPPY_JWT_SECRET` — JWT signing key (fallback if keyring unavailable)

### Test Structure
- **`tests/smoke/`** — Runtime smoke tests (launcher, API, security)
- **`tests/unit/`** — Fast unit tests
- **`tests/integration/`** — Slower integration tests
- Note: `compat_shims/launcher_ui/tests/` was archived 2026-05-01. All active tests are under `tests/`.

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
- ✅ **Companion voice fast-path** — `is_voice` flag on ChatRequest routes voice transcripts to Rocinante (companion primary) or Hermes3 (fallback); always-on VRAM: embed(1GB) + dispatch(2GB) + phi4-mini(2.5GB) + Hermes3(9GB) + Hermes4(11GB) ≈ 25.5GB; Rocinante on-demand; xLAM on-demand
- ✅ **Companion tool execution** — `POST /api/companion/action` for web_fetch/create_reminder/download_media/memory_write/memory_recall; `<tool_call>` parser in `/chat/stream` two-pass; Hermes tool schema + memory protocol in all personality presets
- ✅ **Ollama removed from routing** — `can_stream_ollama=False`; all local routes go to llamacpp; session summarizer switched from guppy-fast to phi-4-mini at port 8091
- ✅ **Phi-4-mini infrastructure** — registered at port 8091 as true JSON tool_call orchestrator; model file needed to activate
- ✅ **6-gap stability hardening** (2026-04-30):
  - **Surface-locked routing** — `_get_surface_local_model()` reads `surface_config` DB per-surface; companion→rocinante (hermes3 fallback), workspace→hermes4; wired into `/chat` + `/chat/stream`
  - **Per-surface cloud fallback** — `_get_surface_cloud_model()` returns Haiku for companion, Sonnet for workspace/codespace; user override always wins
  - **`workspace_task` companion tool** — companion can hand tasks to workspace via `<tool_call>workspace_task`; `_spawn_task_direct()` in routes_surface bypasses HTTP auth for trusted internal callers
  - **Backend watchdog** — daemon thread in routes_backends monitors ports 8085/8086/8087/8091/8092 every 60 s, auto-restarts crashed always-on models
  - **24/7 background task loop** — asyncio task delivers due reminders as SSE events every 30 s; marks queued tasks stale after 6 h; started via lifespan `background_coroutines`
  - **Strict-local mode** — companion surface checks local model port liveness before streaming; returns honest "Local model offline" error instead of silent cloud escalation
- ✅ **7-item 2026 best-practices pass** (2026-04-30):
  - **Workspace tool execution** — two-pass `<tool_call>` for workspace surface; `_execute_workspace_tool()` handles web_search/file_read/file_list/shell_run/contacts_search; wired into `/chat/stream`
  - **Workspace task executor** — `_run_workspace_task()` background worker in routes_surface dequeues queued tasks, calls Hermes4, executes tools, broadcasts SSE progress/completion events
  - **Streaming TTS** — sentence-boundary chunking (`SENTENCE_END_RE`) in CompanionView; `speakQueued()` + `_drainQueue()` in useVoice.ts plays sentences as they arrive instead of waiting for full response
  - **SSE exponential backoff** — `useSurfaceEvents.ts` shared hook; 2→4→8→16→32→60 s backoff, resets after 10 s healthy connection; used by both CompanionView and WorkspaceView
  - **OOM error parsing** — `_parse_oom_error()` in realtime_inference_support detects CUDA/ROCm OOM in llamacpp HTTP error bodies; `_stream_llamacpp_tokens` raises actionable RuntimeError; `local_client.py` logs ERROR-level with restart instruction
  - **Grammar-constrained tool calls** — `_TOOL_CALL_GBNF` constant + `grammar` param on `_stream_llamacpp_tokens`; `_repair_tool_json()` applies trailing-comma/unclosed-brace repairs in all three tool-call parse sites (companion, workspace, task executor)
  - **KV cache auto-warming** — `_warm_kv_cache(port)` sends 1-token prefill to Rocinante (8088), Hermes3 (8087), and Hermes4 (8086) on first confirmed liveness; integrated into watchdog, re-warms after crash+restart; reduces first-response latency ~30-50%
- ✅ **MCP plugin manager** — add/remove/enable/test MCP servers; MCPView wired
- ✅ **Desktop control API** — pyautogui screenshot/click/type (graceful fallback if pyautogui absent)
- ✅ **Themes** — Dark, Liber Designatum (occult), Fear & Loathing (gonzo), Creem × Rolling Stone (rock mag)
- ✅ **Inference metrics** — persisted to guppy_main.db, visible in AdminPanel `/admin`
- ✅ **Gmail sync** — live via google-api-python-client (needs credentials)
- ✅ **Google Calendar sync** — live, upserts 90-day window (needs credentials)
- ✅ **HubSpot/Salesforce/GHL/Zoho contact + deal upsert** — live REST (needs API keys)
- ✅ **Twilio outbound calling** — live REST call placement (needs credentials)
- ✅ **Desktop launcher** — `Desktop\Guppy Launcher.lnk` updated via `tools/ensure_desktop_launcher.ps1`
- ✅ **Phase 6 hardening round 1** (2026-05-01):
  - **Stream timeout + disconnect cleanup** — `_generate_with_heartbeat()` enforces `GUPPY_STREAM_TIMEOUT_SECONDS` wall-clock cap (default 300 s); `request.is_disconnected()` polled each iteration; generator `aclose()`d on timeout or disconnect
  - **`shell_run` injection fix** — `shlex.split()` + `shell=False`; prevents metacharacter injection through the safe-prefix allowlist
  - **`ensure_column` DDL allowlist** — `_ALLOWED_MEMORY_TABLES` frozenset in `memory_db.py` + `memory_store.py` raises `ValueError` for unlisted table names
  - **Deprecated module archival** — `src/guppy/merlin/` + `compat_shims/launcher_ui/` (97 files total) archived to `docs/archive/deprecated-modules/`
  - **Surface-locked routing** — `_get_surface_local_model()` reads `surface_config` DB per-surface; companion→hermes3, workspace→hermes4 by default; wired into `/chat` + `/chat/stream`
  - **Per-surface cloud fallback** — `_get_surface_cloud_model()` returns Haiku for companion, Sonnet for workspace/codespace; user override always wins
  - **`workspace_task` companion tool** — companion can hand tasks to workspace via `<tool_call>workspace_task`; `_spawn_task_direct()` in routes_surface bypasses HTTP auth for trusted internal callers
  - **Backend watchdog** — daemon thread in routes_backends monitors ports 8085/8087/8086 every 60 s, auto-restarts crashed always-on models
  - **24/7 background task loop** — asyncio task delivers due reminders as SSE events every 30 s; marks queued tasks stale after 6 h; started via lifespan `background_coroutines`
  - **Strict-local mode** — companion surface checks local model port liveness before streaming; returns honest "Local model offline" error instead of silent cloud escalation
- ✅ **Phase 6 hardening round 2** (2026-05-02):
  - **`/repair-token/refresh` JWT auth** — endpoint now requires JWT Bearer via `Depends(verify_token)`; unauthenticated localhost requests no longer allowed
  - **Semantic fallback unit tests** — `tests/unit/test_semantic_fallback.py` 4/4 pass; covers lexical fallback when embed server offline
  - **Docker app container** — `Dockerfile` + `docker-compose.yml` for production FastAPI container; `GUPPY_JWT_SECRET` required
  - **Test security imports fixed** — `tests/test_security_hardening.py` conditional `launcher_window` import + `skipIf` on 4 archived Qt test classes; 29 pass, 10 skip, 0 fail
- ✅ **Routing stability + tool hardening** (2026-05-03, commit 911c40f):
  - **asyncio heartbeat queue** — replaced `asyncio.shield` pattern (caused `ValueError: async generator already running` after one heartbeat) with queue-drain producer/consumer; streams now stay alive for full response
  - **Rocinante as companion default** — `_SURFACE_LOCAL_DEFAULTS["companion"]` = `llamacpp-rocinante`; cascade tries Rocinante first, falls through to Hermes3; identity updated in context_injection
  - **XML tool call normalization** — `_normalize_tool_calls()` pre-parser converts `<name>/<arguments>` XML format (emitted by some models) to JSON-in-tags before `_TOOL_CALL_RE` matching
  - **Pass-2 stripped prompt** — workspace tool synthesis (pass-2) strips `_WORKSPACE_TOOL_SCHEMA` to prevent context overflow; was hitting 32K limit → "No backend available"
  - **Companion `/action` fallback** — added `_execute_companion_tool` catch-all; previously 4 of 9 tools (get_time, list_workspace_tasks, etc.) returned HTTP 400
  - **0-token fallthrough detection** — `router_surface.py` tracks `_yielded` tokens; raises `RuntimeError` on 0-token response to cascade to next model
- ✅ **Memory noise reduction + surface-aware injection** (2026-05-03, commit d1fb886):
  - **Exact-key recall** — `_recall_sqlite` short-circuits on exact/prefix key match before embedding I/O; no fuzzy noise when querying named keys directly
  - **Recall depth n=8 → n=4** — halves semantic context injected per turn
  - **User preferences direct SQL scan** — replaced `recall_semantic("", category=user_preference)` (empty-string embedding = random results) with `SELECT ... WHERE category='user_preference'`
  - **Garbage filter** — `build_semantic_prompt_context` drops results where all content lines < 10 chars (spurious lexical fallback noise)
  - **Structured session summarizer** — fact-extraction bullet prompt replaces vague paragraph summary; extracts preferences, outcomes, entities, topics
  - **Surface-aware file tree** — `_inject_workspace_context_async` skipped for companion; opt-in for workspace/codespace when query contains file-related keywords
  - **Companion surface state gate** — `_inject_surface_state_async` skipped for companion unless query references tasks/agents/status
  - **Context budget guard** — post-injection check: if `system + history > 85% of context window`, trims history to most-recent half and rebuilds without expensive injections
- ✅ **Two-model core stability checkpoint** (2026-05-03, commit 8315900):
  - **Tool primer always-injected** — `_inject_tool_primer()` moved to `realtime_inference_support.py` injection chain, fires unconditionally; decoupled from `skip_tools` flag which now only suppresses OpenAI-format schema objects — Rocinante on pass-1 (`skip_tools=True`) now always sees tool descriptions
  - **Pass-2 tool-loop guard** — companion and workspace pass-2 synthesis calls now pass `skip_tools=True` plus explicit "Do NOT emit `<tool_call>`" instruction; prevents synthesis-turn tool loops
  - **Companion history limit 15→20** — `_SURFACE_HISTORY_LIMITS["companion"]` raised; Rocinante has 16K context (not Hermes3's 8K where 15 was set)
  - **Windows file lock fix** — `_inject_user_preferences` SQLite conn explicitly closed in `finally`; context manager is commit-only on Windows
  - **22-test integration suite** — `tests/integration/test_two_model_core.py`; all green; covers tool primer injection, XML→JSON normalization, context budget math, messages-array history path, semantic memory pipeline

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
- **`tools/verify_local_model_runtime.py`** — Local model runtime availability check
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

### Model Role Registry

→ See `docs/MODEL_ROUTING.md` for full table.

**Always-on stack (~25.5 GB VRAM):**
| Surface role | Key | Port | Model |
|---|---|---|---|
| Companion watchdog fallback | `llamacpp-hermes3` | 8087 | Hermes 3 8B Q8_0 |
| Companion primary (on-demand) | `llamacpp-rocinante` | 8088 | Rocinante X 12B Q5_K_M |
| Workspace/codespace reasoning | `llamacpp-hermes4` | 8086 | Hermes 4 14B Q5_K_M |
| Orchestrator / summarizer | `llamacpp-phi4-mini` | 8091 | Phi-4-mini-instruct Q4_K_M |
| Semantic embedding | `llamacpp-nomic-embed` | 8092 | nomic-embed-text-v1.5 |

**Ollama is removed from routing.** `can_stream_ollama=False`. All local routes go to llamacpp.

### Model Roster (llama.cpp — ROCm/HIP)
| Backend key | Model | Port | VRAM | Role |
|-------------|-------|------|------|------|
| `llamacpp-gemma` | Gemma 4 E4B Heretic ARA | 8080 | ~8.5 GB | Vision — **PLE issue in llama.cpp #22243: silently degraded output** |
| `llamacpp-pepe` | Assistant Pepe 8B Q8_0 | 8082 | ~8.5 GB | Fast chat, Mode A |
| `llamacpp-qwen3` | Qwen3 35B-A3B MoE | 8083 | ~19 GB | Reasoning, Mode B (solo only) |
| `llamacpp-minicpm` | MiniCPM-o 4.5 Omni | 8084 | ~9 GB | Vision+speech, needs mmproj |
| `llamacpp-dispatch` | Qwen2.5-3B-Instruct Q4_K_M | 8085 | ~2 GB | Lightweight router fallback |
| `llamacpp-hermes4` | Hermes 4 14B Q5_K_M | 8086 | ~11 GB | Tools + uncensored (primary recommended) |
| `llamacpp-hermes3` | Hermes 3 8B Lorablated Q8_0 | 8087 | ~9 GB | Fast tools + uncensored |
| `llamacpp-rocinante` | Rocinante X 12B Q5_K_M | 8088 | ~10 GB | Creative writing / roleplay |
| `llamacpp-xlam` | xLAM-2-8B-fc-r Q4_K_M | 8089 | ~5 GB | Tool-call specialist (#1 BFCL ≤8B); on-demand |
| `llamacpp-chat` | Llama 3.3 70B Instruct Q4_K_M | 8090 | 0 VRAM (~42 GB RAM) | CPU-only flagship chat; ~4-6 tok/s on Ryzen 9 9900X |
| `llamacpp-phi4-mini` | Phi-4-mini-instruct Q4_K_M | 8091 | ~2.5 GB | True JSON tool_call orchestrator (always-on); model file needed |

**Gemma 4 E4B PLE warning:** llama.cpp issue #22243 — PLE (Per-Layer Embeddings) architecture not fully implemented; output quality is silently degraded. Use Hermes or Rocinante for tool-capable or quality-sensitive tasks.

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
- Performance → Profile with `tools/verify_local_model_runtime.py`

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
2. Check llamacpp backends are running: `curl http://localhost:8087/health` (Hermes3), `curl http://localhost:8086/health` (Hermes4)
3. Review logs from `src/guppy/api/auth.py` (dev mode logging)
