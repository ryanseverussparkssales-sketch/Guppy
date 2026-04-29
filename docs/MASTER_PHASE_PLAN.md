# Guppy Master Phase Plan — Three-Surface Architecture

**Created:** 2026-04-28
**Updated:** 2026-04-29 — Phases 1–5 complete
**Status:** Phases 1–5 ✅ shipped.
**Authority:** This document owns the surface architecture roadmap. CLAUDE.md owns module/routing facts.

---

## Verified Current State

This section is ground-truth as of 2026-04-28, based on direct code review.

### Backend Routes (all mounted, all active)

| Route Prefix | File | Notes |
|---|---|---|
| `/api/chat` | `routes_realtime.py` | Main inference — SSE streaming, WebSocket |
| `/api/agents` | `routes_agents.py` | Agent registry CRUD; seeded with fast/code/deep |
| `/api/library/*` | `routes_library.py` | Collections + items, full CRUD |
| `/api/booklet/*` | `routes_booklet.py` | Booklet sections |
| `/api/drop/*` | `routes_drop.py` | GuppyDrop watchdog + SSE push |
| `/api/files/*` | `routes_files.py` | File read/browse/info |
| `/api/system/*` | `routes_files.py` | psutil system info, processes, disk, network |
| `/api/clipboard` | `routes_files.py` | Clipboard read/write |
| `/api/screenpipe/*` | `routes_screenpipe.py` | External Screenpipe daemon bridge (port 3030) |
| `/api/voices` | `routes_voice.py` | TTS/STT management |
| `/api/backends/llamacpp` | `routes_backends.py` | llamacpp backend management |
| `/api/pipeline/*` | `routes_pipeline.py` | CRM pipeline |
| `/api/reminders/*` | `routes_reminders.py` | Reminders |
| `/api/calibre/*` | `routes_calibre.py` | Calibre/Kindle ebook integration |
| `/api/acquisition/*` | `routes_acquisition.py` | Acquisition tracking |
| `/api/tier3/*` | `routes_tier3.py` | Tier3 features |
| `/api/workspaces/*` | `routes_workspaces.py` | Workspace management |
| `/api/instances/*` | `routes_instances.py` | Instance management |
| `/api/models/*` | `routes_models.py` | Model management |
| `/api/providers/*` | `routes_providers.py` | Provider management |
| `/api/queue/*` | `routes_queue.py` | Queue management |
| `/api/settings/*` | `routes_settings.py` | Settings |
| `/api/tools/*` | `routes_tools.py` | Tool registry (seeded with file/system/clipboard tools) |
| `/api/chat-history/*` | `routes_chat_history.py` | Conversation history |
| `/api/inference/metrics` | `routes_inference_metrics.py` | Inference metrics |
| `/api/launcher/*` | `routes_launcher.py` | Launcher control |

### Voice System (active)

- **STT chain:** faster-whisper → Google SpeechRecognition → SAPI
- **TTS chain:** kokoro → ElevenLabs → Windows SAPI PowerShell
- **Wake word:** openwakeword (when `GUPPY_OWW_MODEL` set) or transcription loop fallback
- **API:** `/api/voices` — status, settings, speak (returns audio bytes), transcribe, stop
- **Modes:** push-to-talk (`listen_once`), hold-to-talk, wake word continuous

### Inference Router (active)

- **Task types:** simple, complex, teaching, agentic, tool_call
- **Modes:** auto, claude, ollama, local, code, teaching, vault, local_paired
- **Classifier:** Haiku semantic + heuristic fallback (controlled by `GUPPY_SEMANTIC_CLASSIFIER`)
- **llamacpp backends:** pepe (8082), qwen3 (8083), minicpm (8084), dispatch (8085), hermes4 (8086), hermes3 (8087), rocinante (8088), xlam (8089)
- **Ollama models:** guppy-fast (7B), guppy (32B), guppy-teach (32B), guppy-code (14B), vault-scraper (7B)
- **Auto-routing:** `task_type=tool_call` → xlam; `task_type=agentic` → hermes4/qwen3

### Screen Monitoring (partial — external daemon)

`routes_screenpipe.py` already integrates with the Screenpipe daemon (https://github.com/mediar-ai/screenpipe). It provides:
- `GET /api/screenpipe/status` — daemon health
- `GET /api/screenpipe/search` — search screen/audio history by keyword or time range
- `GET /api/screenpipe/recent` — last N minutes of screen activity

The Screenpipe daemon itself does continuous screen capture, OCR, and Whisper transcription, storing everything locally in SQLite. **This is the 24/7 screen monitoring infrastructure** — it already exists.

### Memory System (active)

- SQLite-backed: facts (key-value), contacts, tasks, pipeline/CRM, session summaries, conversation history
- Semantic: ChromaDB or SQLite backend with `nomic-embed-text` embeddings via Ollama
- `promote_durable_chat_memory()` — extracts preferences, identity, decisions, scope
- `get_startup_context()` — memory briefing injected at conversation start

### Existing Web UI Views

| View | Route | Notes |
|---|---|---|
| `AssistantView.tsx` | `/assistant` | Current primary chat surface |
| `LaunchpadView.tsx` | `/launch-control` | Agent/instance management |
| `PersonasView.tsx` | `/personas` | Personas + library |
| `LibraryView.tsx` | `/library` | Full CRUD, wired to API |
| `ToolsView.tsx` | `/tools` | Tool registry |
| `SettingsView.tsx` | `/settings` | Settings |
| `ModelsView.tsx` | `/models` | Model management |
| `AgentsView.tsx` | `/agents` | Agent management |
| `InstancesView.tsx` | `/instances` | Instance management |
| `VoicesView.tsx` | `/voices` | Voice management |
| `DesktopView.tsx` | `/desktop` | Desktop tools (stub) |
| `DashboardView.tsx` | (not primary) | Dashboard (stub) |

### What's Already Infrastructure for the New Vision

| New Surface Need | Existing Infrastructure |
|---|---|
| Voice input/output | Full STT/TTS stack + `/api/voices` |
| 24/7 screen monitoring | Screenpipe daemon + `routes_screenpipe.py` |
| CRM / Pipeline | `routes_pipeline.py` + memory contacts/tasks |
| Agent registry | `routes_agents.py` (CRUD exists) |
| File drop intake | `routes_drop.py` + watchdog |
| System monitoring | `routes_files.py` + `system_tool.py` (psutil) |
| PC file access | `routes_files.py` + `file_tool.py` |
| Reminders / automations | `routes_reminders.py` |
| Library / document storage | `routes_library.py` |

---

## Navigation Principle

The main nav is **three tabs only**: Companion | Workspace | Codespace. Each surface owns its own chrome and backend selector. Secondary destinations (Settings, Library, Tools, Models, Voices) are accessible from within each surface as sub-navigation, not as peer tabs. The sidebar collapses to icon-only on all three primary surfaces to maximize working area.

Each surface exposes a **backend selector** (llamacpp / ollama / cloud API) directly in its header or settings panel. Config is stored per-surface in `surface_config` SQLite table. Switching backends does not affect other surfaces.

## Concurrent Silo Model

With 98GB RAM and a large GPU, all three surfaces can run simultaneously without model swapping:

| Silo | Backend | Models pre-loaded | VRAM |
|---|---|---|---|
| Companion | llamacpp | minicpm + rocinante + dispatch | ~22 GB |
| Workspace | llamacpp + ollama | hermes4 + xlam + guppy on demand | ~16 GB + demand |
| Codespace | ollama + llamacpp | guppy-code + hermes3 + qwen3 on demand | ~9 GB + demand |
| Cloud API | Anthropic/OpenAI/etc. | zero local VRAM | 0 GB |

All three surfaces can accept user input simultaneously. The inference router respects per-surface backend config — a Companion voice query goes to llamacpp-minicpm while a Workspace agent task runs hermes4, and a Codespace code gen uses guppy-code, all concurrently with no contention.

Cloud API (Claude, OpenAI, etc.) can be enabled globally in Settings and becomes available as a backend option in any surface's backend selector. Useful for tasks that exceed local model capability.

---

## The Three-Surface Architecture

### Decision

The single `AssistantView` is replaced by three functionally distinct surfaces, each with dedicated model affinity, tool access, and UX character. They share a common substrate: the same memory store, the same SSE event bus, and the same backend API.

### Surface Map

```
╔══════════════════════╗
║     COMPANION        ║  /companion
║  Voice · Chat        ║  Fast, personal, uncensored
║  Vision · Avatar     ║  Minimal tools
║  Personality-first   ║  Escalates → Workspace
╚══════════════════════╝
           │ escalates tasks
           ▼
╔══════════════════════╗     feeds code tasks     ╔══════════════════════╗
║     WORKSPACE        ║ ──────────────────────► ║     CODESPACE        ║
║  Operations Hub      ║                          ║  Docker Sandbox      ║
║  Agents · CRM · VoIP ║ ◄── results/summaries ── ║  Self-triage         ║
║  Screen · PC · Files ║                          ║  Project creation    ║
╚══════════════════════╝                          ╚══════════════════════╝

Shared substrate: SQLite memory · Semantic memory · SSE event bus · surface_state table
```

---

### Surface 1: Companion (`/companion`)

**Character:** Fast, personal, uncensored. The face of Guppy — what you talk to every day.
Voice-first with text fallback. Vision capable. Has a persistent personality. Never dumps diagnostics.

**Model affinity:**
| Priority | Model | Why |
|---|---|---|
| Primary | `llamacpp-minicpm` (9GB) | Native voice + vision in one model |
| Personality | `llamacpp-rocinante` (12GB) | Creative, uncensored, character |
| Fast fallback | `llamacpp-hermes3` (9GB) | Speed + uncensored when depth not needed |
| Orchestration | `llamacpp-dispatch` (2.5GB) | Lightweight task classification |

**Tools allowed:** Web search, memory read/write, surface_state read (see what Workspace is doing).
**Tools blocked:** File writes, code execution, CRM mutations, agentic loops.
**Can spawn Workspace tasks:** Yes — packages task description + context, POSTs to `/api/surface/spawn`.

**UI components:**
- Clean single-column chat (no sidebar clutter)
- Animated avatar/presence area (waveform minimum, animated avatar long-term)
- Voice indicator (recording, speaking, thinking states)
- Workspace status chip ("Workspace: running 2 agents")
- "Kick to Workspace" button on any message

---

### Surface 2: Workspace (`/workspace`)

**Character:** Operational command center. Not a chat surface — a management surface. You come here to direct, monitor, and review. Chat exists but is subordinate to the task panels.

**Model affinity:**
| Use case | Model |
|---|---|
| Tool calls / automations | `llamacpp-xlam` (5GB) |
| Multi-step agentic tasks | `llamacpp-hermes4` (11GB) |
| Complex reasoning | `llamacpp-qwen3` (19GB) |
| Heavy Ollama tasks | `guppy` (32B Ollama) |

**Capabilities:**
- **Agent task panel** — running/queued/completed agents, live SSE output, cancel/inspect
- **Document display** — inline PDF rendering, spreadsheet view, image display (not raw text blobs)
- **Visualizations** — charts/graphs from data, live system metrics
- **Screen monitoring** — Screenpipe timeline UI (what's been on screen, searchable by keyword/time)
- **PC management** — processes, disk, network (live from psutil routes)
- **CRM/Pipeline** — contacts, tasks, pipeline board (from existing `routes_pipeline.py` + memory)
- **Automations** — reminders, scheduled jobs, file watchers, drop folder management
- **VoIP** — call log, click-to-call, call notes → CRM (Twilio/SIP integration)
- **Desktop/file access** — full file browser, not just single-file reads
- **Feeds context to Companion and Codespace** via surface_state + SSE

**UI layout:** Sidebar navigation between panels (Agents, Screen, CRM, Files, PC, VoIP). Chat panel always accessible but not the default view.

---

### Surface 3: Codespace (`/codespace`)

**Character:** The system's workshop. Where code gets written, tested, and deployed in isolation. Also where Guppy works on itself.

**Model affinity:**
| Use case | Model |
|---|---|
| Code generation | `guppy-code` (14B Ollama) |
| Architecture decisions | `llamacpp-qwen3` (35B) |
| Tool-assisted code tasks | `llamacpp-hermes4` (14B) |
| Fast edits | `llamacpp-hermes3` (8B) |

**Capabilities:**
- **Docker sandbox** — create/exec/destroy isolated containers per project or task
- **Code execution** — run code in sandbox, stream stdout/stderr via SSE
- **Project scaffolding** — generate new project structures, Dockerized environments
- **Self-triage** — file watcher on `src/guppy/`, auto-runs `dev_workflow.py dev-check` on changes, analyzes failures, drafts fixes
- **Error pattern memory** — stores recurring failures in semantic memory, surfaces trends
- **Receives tasks from Workspace** — Workspace escalates code-specific agent tasks here
- **Returns results to Workspace** — code output, fix proposals, new project records

---

### Shared Substrate

All three surfaces share these without duplication:

**`surface_state` table** (new, ~5 lines of schema):
```sql
CREATE TABLE IF NOT EXISTS surface_state (
    surface     TEXT PRIMARY KEY,  -- 'companion' | 'workspace' | 'codespace'
    status      TEXT NOT NULL DEFAULT 'idle',  -- 'idle' | 'active' | 'agent_running'
    current_task TEXT,
    agent_count  INTEGER NOT NULL DEFAULT 0,
    last_context TEXT,             -- short summary of what this surface last did
    updated_at  TEXT NOT NULL
);
```

**`/api/surface/*`** (new router, Phase 1):
- `GET /api/surface/state` — all three surfaces' current status
- `POST /api/surface/spawn` — spawn a task to a specific surface
- `GET /api/surface/events` — SSE stream of cross-surface events

**Memory:** All surfaces call `memory.get_startup_context()` at turn 0 and `memory.promote_durable_chat_memory()` after each exchange. Same SQLite + semantic store. No duplication.

---

## Phase Plan

---

### Phase 1 — Surface Split + Foundation ✅ COMPLETE (commit 427f0c3)
**Goal:** Three routes exist. Model affinity is wired. Cross-surface plumbing exists. Zero regression on existing functionality.

**Backend:**
- [x] `routes_surface.py` — new router with `/api/surface/state`, `/api/surface/spawn`, `/api/surface/events` (SSE)
- [x] `surface_state` + `surface_config` + `surface_tasks` tables — SQLite schema, R/W helpers, mounted
- [x] Model affinity config — per-surface defaults seeded (companion→minicpm, workspace→hermes4, codespace→guppy-code)
- [x] Per-surface config stored in `surface_config` table, exposed via `/api/surface/config/{surface}`

**Frontend:**
- [x] `/companion` route → `CompanionView.tsx`
- [x] `/workspace` route → `WorkspaceView.tsx`
- [x] `/codespace` route → `CodespaceView.tsx`
- [x] Navigation — three primary tabs; secondary = Library/Personas/Tools/Instructions/Settings
- [x] `SurfaceStatusBar.tsx` — live SSE-connected chip showing other surface states
- [x] `BackendSelector.tsx` — per-surface model selector reading/writing surface_config
- [x] Sidebar auto-collapses on all three primary surfaces

**Acceptance:**
- All three routes render without errors
- Companion chat uses minicpm/rocinante/hermes3 affinity
- Workspace chat uses hermes4/xlam affinity
- Codespace chat uses guppy-code/hermes4 affinity
- Existing `/assistant`, `/library`, `/settings`, `/tools` routes still work (no regression)
- `GET /api/surface/state` returns current status of all three surfaces
- Posting a task from Companion creates a record in Workspace's agent panel

---

### Phase 2 — Companion: Voice, Vision, Personality ✅ COMPLETE (commit 84e9f93)
**Goal:** Companion is genuinely voice-first with a distinct personality, vision capability, and avatar presence.

**Backend:**
- [x] `routes_companion.py` — personality presets, vision endpoint, voice session lifecycle, tool whitelist check
- [x] `/api/companion/voice/session` — start/stop wake-word voice session
- [x] `/api/companion/vision` — multipart form → minicpm backend for vision queries
- [x] `/api/companion/personality` — set personality preset (sharp/hermes3, creative/rocinante, voice/minicpm, thinking/qwen3)
- [x] Tool whitelist: only web_search, memory_read, memory_write, memory_recall allowed

**Frontend:**
- [x] `AvatarPresence.tsx` — animated orb, waveform bars (listening/speaking), spinning ring (thinking), pulse ring
- [x] PersonalityPicker dropdown in CompanionView
- [x] Wake-word toggle → `/api/companion/voice/session`
- [x] Camera button + hidden file input for image → base64 → vision query
- [x] Image preview with remove button
- [x] "Escalate to Workspace" button → `/api/surface/spawn`

**Acceptance:**
- Push-to-talk works in Companion, transcribes via Whisper, responds with TTS audio
- Wake word activates Companion from idle
- Dropping an image into Companion chat triggers vision analysis via minicpm
- Escalating a task from Companion creates a live task in Workspace agent panel
- Companion cannot execute file writes or agentic tool chains — server returns 403 if attempted

---

### Phase 3 — Workspace: Operations Hub ✅ COMPLETE (commit 2772cf8)
**Goal:** Workspace is a functional PC management and operations surface. Agents run here. CRM lives here. Screen history is queryable.

**Backend:**
- [x] `routes_workspace_data.py` — JSON API over memory SQLite: contacts (GET/POST/DELETE), tasks (GET/POST/PUT complete/DELETE), pipeline history + templates proxy
- [x] Existing infrastructure reused: `/api/screenpipe/*`, `/api/reminders`, `/api/files/*`, `/api/system/*`, `/api/pipeline/*`

**Frontend:**
- [x] `SystemMetricsPanel.tsx` — live CPU/RAM/disk/net gauges + top-process table (polled every 4s)
- [x] `CRMPanel.tsx` — contacts list with search + add/delete; tasks board with pending/completed filter
- [x] `ScreenPanel.tsx` — Screenpipe viewer (Recent tab + Search tab with content-type filter); offline banner
- [x] `FilesPanel.tsx` — navigable file browser from drive roots, breadcrumb, text preview overlay
- [x] `AutomationPanel.tsx` — reminders list with overdue highlight, add by delay or datetime, cancel
- [x] `WorkspaceView.tsx` restructured — 7-tab icon strip: Chat | Agents | CRM | Screen | Files | PC | Reminders
- [x] Agents panel extracted as standalone tab; Chat tab has collapsible AgentTaskPanel sidebar

**Acceptance:**
- A task spawned from Companion appears in AgentTaskPanel with live output streaming
- Screenpipe status shows in Workspace; recent screen activity is searchable
- CRM board shows contacts and pipeline from memory module
- A dropped file (via GuppyDrop) appears as a document in the Workspace document viewer
- System metrics live-update every 5 seconds
- At least one automation trigger works end-to-end (e.g., time-based reminder fires + notifies Companion)

---

### Phase 4 — Codespace: Docker Sandbox + Self-Triage ✅ COMPLETE (commit f3e8a30)
**Goal:** Codespace can execute code in isolated Docker containers and watch/improve the Guppy codebase itself.

**Backend:**
- [x] `routes_codespace.py` — sandbox lifecycle: GET/POST/DELETE `/api/codespace/sandbox`, POST `/api/codespace/sandbox/{id}/exec` (SSE stream); triage: GET/POST `/api/codespace/triage/runs`, POST `/api/codespace/triage/trigger`, GET `/api/codespace/triage/status`
- [x] `src/guppy/codespace/codespace_triage.py` — SQLite triage run history (runtime/triage.db); `run_triage()` runs dev-check + parses failures; `trigger_triage_async()` non-blocking; `start_watchdog()` polls src/guppy/ + tools/ every 5s, 60s debounce, auto-triggers on changes
- [x] Triage watchdog started at server boot via server_runtime.py

**Frontend:**
- [x] `SandboxPanel.tsx` — sandbox list, create form (image selector), in-browser SSE terminal, Docker offline banner
- [x] `TriagePanel.tsx` — run history cards (pass/fail/running), failure list per run, full-output modal, manual trigger, pass-rate badge, auto-polls while running
- [x] `CodespaceView.tsx` restructured — 3-tab icon strip: Chat | Sandbox | Triage; tertiary color language

**Acceptance:**
- `POST /api/codespace/sandbox/create` spins up a real Docker container
- `exec` endpoint runs a Python script and streams stdout line by line via SSE
- Saving a change to any `src/guppy/` file triggers triage within 10 seconds
- Triage output is parsed and displayed in TriagePanel with pass/fail summary
- A proposed fix from Codespace can be viewed as a diff and accepted/rejected

---

### Phase 5 — Advanced Surface Capabilities ✅ COMPLETE (commits 62a0dad→a9c0f4e)
**Goal:** The system is ambient, self-improving, and genuinely functions as a personal operations platform.

**Backend:**
- [x] VoIP full implementation — `routes_voip.py`: SQLite call log, manual CRUD, Twilio StatusCallback webhook stub, GET /api/voip/status
- [x] Screen monitoring AI summaries — `routes_screen_monitor.py`: `_generate_ai_summary()` calls guppy-fast via Ollama after every 30-min snapshot; stores `summary` column; exposed in timeline API + DB migration for existing tables
- [x] Self-improvement pipeline — `src/guppy/codespace/self_improve.py`: `propose_fix()` calls guppy-code→guppy-fast, extracts unified diff, `apply_fix()` creates branch + runs dev-check, `reject_fix()` / `get_proposals()` / `get_proposal()`
- [x] Ambient wake mode — CompanionView SSE subscription fires TTS on `task_spawned`/`task_updated` events

**Frontend:**
- [x] Enhanced avatar animation — `AvatarPresence.tsx`: 11-bar bell-curve waveform, 3-dot orbit thinking, triple-ring listening pulse, per-state glow bloom
- [x] Screen monitoring timeline — `ScreenPanel.tsx` Timeline tab: hourly windows, AI summary chip (Sparkles icon), app pills, text highlights, "Capture now" button
- [x] Self-improvement review UI — `TriagePanel.tsx` ProposalModal: DiffView with per-line +/- coloring, Apply/Reject footer, test result panel, branch name display; GitBranch button on failed runs
- [x] Companion ambient mode — fullscreen overlay, wake label, Workspace alert banner with TTS, Maximize2/Minimize2 toggle

**New routes (all mounted via `routes_codespace.py`):**
- `POST /api/codespace/triage/runs/{id}/propose-fix`
- `GET  /api/codespace/proposals`
- `GET  /api/codespace/proposals/{id}`
- `POST /api/codespace/proposals/{id}/apply`
- `POST /api/codespace/proposals/{id}/reject`

**New routes (mounted via `routes_voip.py`):**
- `GET/POST /api/voip/calls`, `PATCH/DELETE /api/voip/calls/{id}`
- `POST /api/voip/webhook/twilio`, `GET /api/voip/status`

**New routes (mounted via `routes_screen_monitor.py`):**
- `GET /api/screen/timeline`, `GET /api/screen/timeline/today`
- `POST /api/screen/timeline/snapshot`, `GET /api/screen/status`

**Acceptance:**
- ✅ Screenpipe summaries appear in Workspace screen timeline with AI-generated "you were working on X" labels
- ✅ Codespace proposes and presents self-fix diffs; user can apply (creates branch, runs dev-check) or reject
- ✅ Companion speaks Workspace alerts without user initiation when ambient wake mode is active
- ✅ VoIP call log CRUD + Twilio webhook stub wired and persisted

---

## Docs That Need Updating

| Document | Status | Action |
|---|---|---|
| `docs/GUPPY_PRODUCT_NORTH_STAR.md` | Outdated (2026-04-18) — explicitly says "not Jarvis, not automation OS" | Revise to reflect expanded vision or archive and replace |
| `docs/LIVE_ARCHITECTURE.md` | Partially outdated — misses web UI, inference routing, new routes | Update with current backend map after Phase 1 |
| `docs/PROJECT_BRIEF.md` | Current through 2026-04-28 but five-hub surface map no longer applies | Add P7 Three-Surface Architecture as active execution track |
| `CLAUDE.md` | Current — update after each phase with new module locations | Update at end of each phase |

---

## Build Order Within Each Phase

For each phase, work in this order:
1. Backend routes + schema first (unblocks frontend)
2. Shared substrate changes (surface_state, SSE bus) before any surface-specific work
3. Frontend shell (route + empty component) before UI details
4. Integration test (end-to-end flow works) before styling/polish

---

## Hardware Budget (98GB RAM + Large GPU)

All models can stay warm simultaneously. No swapping needed.

| Surface | Primary Model | VRAM |
|---|---|---|
| Companion | minicpm + rocinante | 9 + 10 GB |
| Workspace | hermes4 + xlam | 11 + 5 GB |
| Codespace | hermes3 + qwen3 (on demand) | 9 + 19 GB |
| Always-on | dispatch (orchestrator) | 2.5 GB |
| **Reserve** | | **~33 GB** |

The reserve covers Ollama models (guppy-code, guppy) that load on demand for specific task types.

---

## What Phase 1 Looks Like When Done

The user opens Guppy. Nav shows three destinations: Companion, Workspace, Codespace. The current `/assistant` route redirects to `/companion`. Workspace contains what was the assistant view but with an agent panel stub. Codespace shows a clean code-focused chat. All three share memory context. A message typed in Companion with the "Escalate" button sends it to Workspace's agent queue. The surface_state endpoint returns live status for all three. Everything in the existing nav (Library, Settings, Tools, Models) is still accessible from secondary nav within each surface.
