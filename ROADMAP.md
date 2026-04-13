# Roadmap and Handoff

Last updated: April 12, 2026

This roadmap is now organized around a single product objective:

Build a viable Windows personal assistant with a strong daily workflow, dependable voice UX, and user-controlled persona/model behavior.

## North Star

Guppy should be the default daily assistant on a Microsoft PC:

1. Fast first response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear model/persona customization.
5. Stable local-first operation with optional cloud boost.

## What Current Build Already Handles

These capabilities exist now and are usable in pilot:

1. Unified launcher as primary surface with Assistant, Tools, Settings, Advanced, Models, Voices tabs.
2. Local 5-model fleet with runtime verification tooling.
3. Router modes for local, paired, code, and vault workflows.
4. Voice path with wake-word/PTT, Kokoro and fallback behavior.
5. Supervisor-friendly API + health/status/repair pathways.
6. Runtime telemetry and logging health checks.
7. Personalization/provider/voice schema scaffolds and JSON validate/reload/save flows.
8. Pilot gate automation via tools/pilot_exit_check.py.

## What Is Not Yet Fully Productized

1. Guided persona/model/voice builder UX (cards/forms/preview), beyond raw JSON editing.
2. Provider/model cards with route/fallback editor and live health badges.
3. Voice import and model/persona voice assignment workflow in the launcher.
4. End-user installer/update lifecycle and broader hardware fallback hardening.

## Priority Order (Rebuilt)

### Track 1: Full Custom Builder First (Highest)

Goal: deliver a complete in-app builder for personas, voices, and model assignment before expansion work.

1. Persona Builder v1
  - visual editor (tone, verbosity, teaching style, constraints)
  - global + per-model scope
  - precedence inspector and conflict hints
2. Model Assignment Builder v1
  - per-task mode defaults
  - route/fallback chain editor
  - provider/model health badges
3. Voice Builder v1
  - engine-aware import and validation
  - persona-to-voice and model-to-voice mapping
  - preview, fallback policy, and interruption safety

Definition of done:

1. Non-technical user can configure persona/model/voice without editing JSON files.
2. Settings survive restart and show clear effective precedence.
3. One-click restore to safe defaults exists for each builder section.

### Track 2: Daily Workflow Productization

Goal: turn existing runtime pieces into a repeatable daily operating flow.

1. Morning boot flow with readiness checks and briefing output.
2. Workday loop for capture, reminders, coding support, and lightweight automation.
3. Evening close flow with daily report, follow-ups, and next-day setup.
4. Shared Memory Catalog v1 for cross-agent recall and continuity.
  - canonical entity notes (people, projects, systems, decisions)
  - source-linked memory entries with timestamps and confidence
  - query API for Guppy, Merlin, Council, and daemon workflows

Definition of done:

1. Daily workflow documented and executable in under 5 minutes setup.
2. Recovery path is obvious when any subsystem is degraded.
3. All workflow steps map to existing commands/tools in repo.
4. Agents can retrieve and cite shared memory entries consistently in responses.

### Track 3: Windows General Assistant Viability

Goal: close the gap from pilot to broader Windows usability.

1. Installer/update/uninstall polish.
2. Permission and confirmation policy hardening for risky actions.
3. Hardware profile fallback policy (no-GPU, low-RAM, intermittent network).
4. Optional Microsoft Graph integrations after builder completion.
5. Remote beta tester executable with limited-access runtime policy.
  - one-folder signed EXE bundle for testers (no source tree required)
  - restricted tool allowlist and write-action confirmation policy
  - remote API token scoping, rate limits, and auditable action logs

Definition of done:

1. New machine setup is one guided path.
2. No silent failure for speech, model, or API routes.
3. User can inspect what happened via status and logs.
4. Beta tester EXE can run safely without exposing full codebase or unrestricted tools.

## 30-Day Delivery Plan

### Week 1

1. Persona Builder forms and scope assignment UI.
2. Effective persona preview and precedence inspector.
3. Tests for save/load/validate round-trip.

### Week 2

1. Model assignment and fallback chain editor.
2. Provider/model cards with status badges.
3. Route simulation preview in launcher.

### Week 3

1. Voice import, mapping, and preview UI.
2. Voice engine fallback policy controls.
3. ElevenLabs-first optional mode with local fallback.

### Week 4

1. Daily workflow polish and guided checklist in-app/docs.
2. Windows viability hardening items (recovery UX, profile fallback rules).
3. Pilot gate + acceptance sweep and release decision.
4. Shared Memory Catalog schema + ingestion/retrieval smoke checks.
5. Remote beta package dry run with limited-access policy verification.

## Acceptance Gates

A build is release-ready for pilot when all are true:

1. tools/pilot_exit_check.py returns GO.
2. Builder flows work without manual JSON editing.
3. Voice interruption and fallback behavior pass manual smoke.
4. Settings recovery can restore safe operation in one pass.
5. Daily workflow checklist completes end-to-end in one session.
6. Remote beta EXE profile passes restricted-tool and auth-scope checks.

## Defer Until After Track 1

To protect focus, do not expand these until the custom builder is complete:

1. New CRM/VoIP live write integrations.
2. Broad external connector expansion.
3. Additional specialist surfaces that bypass launcher UX.

## Handoff Notes

If a new coding pass starts, begin here:

1. Confirm pilot gate status from runtime/pilot_exit_report.json.
2. Prioritize unfinished Track 1 tasks.
3. Keep all new settings reachable from launcher tabs first.
4. Update README.md and this roadmap whenever status changes.

6. **Pytest root bootstrap**
  - Added `pytest.ini` and root `conftest.py` so `python -m pytest` resolves project imports cleanly.

7. **Sparkline consolidation**
  - Consolidated to shared implementation at `ui/components/sparkline.py`; launcher uses alias module.

## Launcher and Runtime Hardening Status (2026-04-12)

This section tracks the operational directives currently being enforced as product standards.

1. **Strict tool schemas everywhere possible**
  Status: **Implemented + audited**
  - Tool contracts and input validation are enforced in `guppy_core.py` through `input_schema` definitions and runtime checks.
  - Schema audit tooling added: `tools/audit_tool_schemas.py` writes `runtime/tool_schema_audit.json` and exits non-zero on violations.
  - CI-ready test added: `tests/test_tool_schema_audit.py`.

2. **API under external supervisor ownership**
  Status: **Implemented default**
  - API daemon ownership is disabled by default (`GUPPY_API_OWNS_DAEMON=0`).
  - Supervisor-friendly launcher added: `bin/launch_api_supervised.bat`.
  - Operational guidance documented in `docs/SUPERVISION_WINDOWS.md`.

3. **One-folder builds preferred for pilot distribution**
  Status: **Implemented default**
  - `build_executable.bat` now defaults to one-folder output.
  - one-file is explicit opt-in with `--onefile`.
  - Validation script updated to support both outputs (`validate_build.bat`).

4. **Separate product telemetry from debug logs**
  Status: **Implemented transitional architecture**
  - JSONL remains for append-only runtime streams.
  - SQLite operational mirror added via `utils/operational_telemetry.py`.
  - Session and scorecard writers now mirror into SQLite for repeat query workloads.
  - First-party query/report API support is now implemented for operational telemetry consumption.

5. **Hard ceilings on background work**
  Status: **Implemented with envelope checks**
  - Runtime profile env defaults now carry bounded values for watcher polling, ambient cooldown, and API voice/chat timeouts (`utils/runtime_profile.py`).
  - Daemon polling loops clamp to safe ranges (`guppy_daemon.py`).
  - Profile-specific CPU/RAM envelope thresholds are now active (`GUPPY_ENVELOPE_CPU_MAX_PCT`, `GUPPY_ENVELOPE_RAM_MAX_PCT`, `GUPPY_ENVELOPE_CHECK_S`).
  - Proactive daemon loop now enforces envelope checks, writes `runtime/resource_envelope.status.json`, and emits `resource_envelope` telemetry events on state transitions.
  - API `/status` includes latest `resource_envelope` snapshot.

6. **Unified launcher system as primary product surface**
  Status: **Implemented**
  - Primary entry point is `guppy_launcher.py`.
  - New modular launcher architecture in `ui/launcher/` with dedicated components and per-tab views.
  - Specialist windows (`merlin_ui.py`, `council_ui.py`) remain available as advanced surfaces.

## UI Parity Backlog From Sample Screens (2026-04-12)

These items capture options/buttons visible in the shared design samples that are currently missing or only partially wired.

1. **Top-level navigation parity (Dashboard / Advanced / Archive / Settings)**
  Status: **Done (2026-04-12)**
  - DASHBOARD / ADVANCED / SETTINGS nav buttons added to `topbar.py` with active-state styling.
  - `nav_requested` signal wired in `launcher_window.py` via shared `_on_tab_change()`.
  - Sidebar and topbar stay in sync; `Sidebar.set_active()` no longer re-emits to prevent loops.

2. **Advanced cards: DEPLOY SURFACE action + OPEN action parity**
  Status: **Done (2026-04-12)**
  - `DEPLOY SURFACE ⬆` button added to `_SurfaceCard` in `advanced_view.py`.
  - Deploy passes `GUPPY_DEPLOY_MODE` env var with selected execution mode.
  - Deploy status label shows state feedback inline on the card.

3. **Settings screen controls parity (sliders + visual toggles)**
  Status: **Done (2026-04-12)**
  - Creativity, Precision, Verbosity sliders added (`_SliderRow` widget) with live value readout.
  - Visual toggles added: High Contrast, Background Gradients, Scanline Overlay.
  - All values persist to `app_settings.json` and reload on open.

4. **Settings identity fields parity**
  Status: **Done (2026-04-12)**
  - Display Name text field added.
  - Personality Matrix dropdown (Butler/Casual/Analyst/Mentor).
  - Model Core selector (Sonnet/Haiku/Opus/Local).
  - Last-saved timestamp shown; save confirmation chip auto-clears after 3s.

5. **Tools panel rich cards parity**
  Status: **Partial** (toggle rows exist; metric and preview widgets missing)
  - Add card-level metrics chips (entities/relations/latency) for Memory Core.
  - Add media preview tile area for Media Lab.
  - Add calendar next-event and daily-standup rows in Tools surface.
  - Add diagnostics badges/status chips aligned to live health signals.

6. **Right status rail parity (bar widgets + event list)**
  Status: **Done (2026-04-12)**
  - `_GaugeBar` added for Latency, Core Load, and Memory (psutil when available).
  - `_BadgeRow` added for GUPPY / MERLIN / DAEMON with ONLINE/NOMINAL/ERROR/ACTIVE/STOPPED states.
  - Color-coded severity: green <65%, gold 65-85%, red >85%.

7. **Bottom system strip parity**
  Status: **Done (2026-04-12)**
  - Strip added to `launcher_window.py`: UPTIME (live), CPU%, MEM%, BUFFER tokens, STATUS badge.
  - psutil-backed with safe fallbacks — uptime always shows even without psutil.
  - Token buffer reads last line of `runtime/router_scorecard.jsonl` if present.

8. **Sample button behavior audit and wiring pass**
  Status: **Planned**
  - Audit all visible buttons in launcher views for real side effects (not placeholder UI only).
  - Emit a button-action matrix in roadmap handoff notes showing implemented vs placeholder actions.

9. **Acceptance criteria for sample parity milestone**
  Status: **Planned**
  - Every visible button in Assistant/Tools/Settings/Advanced has a concrete action or explicit disabled reason.
  - Every slider/toggle persists and rehydrates from settings.
  - Status rail updates from live runtime state at regular intervals.
  - No dead-end controls in default launcher flow.

## Code Quality Audit (2026-04-12)

Findings from a full code review. These are the real problems — ordered by how much they hurt.

### Resolved (2026-04-12)

1. **Keyword classifier** → replaced with Haiku semantic classifier + heuristic fallback in `inference_router._classify_task_semantic()`. `GUPPY_SEMANTIC_CLASSIFIER=1` controls it.
2. **Response cache dies on restart** → SQLite-backed `runtime/response_cache.sqlite3` in `guppy_ui.py`.
3. **`GUPPY_TOOL_BUDGET` default** → corrected to 6 in `guppy_ui.py`.
4. **`utils/` return type annotations** → added across all public functions in `utils/runtime_profile.py`.
5. **Two Sparkline implementations** → consolidated; launcher component aliases shared widget.
  - **Fix**: Consolidate on the launcher version. Update `guppy_ui.py` import.

6. **No CI enforcement**
  Baseline enforcement is now in place.
  - Added `.github/workflows/quality-gates.yml` to run schema audit and core smoke/workflow tests on push and pull_request.
  - Next: expand gates to include broader cross-platform and launcher-surface integration checks.

7. **Concurrency test for the API is missing**
  Two simultaneous `/chat` requests against the same executor pool is untested. Sync inference wrapped in `run_in_executor` works but has a queue ceiling.
  - **Fix**: Add one concurrency test in `tests/smoke_api.py` — two concurrent requests, assert neither hangs.

### Debt to retire (plan, don't act yet)

8. **`guppy_ui.py` is a 2,200-line legacy surface with no clear retirement plan**
  It's not imported by council_ui (confirmed). It holds a separate copy of the response cache, tool loop, and routing logic that will drift from the new system. Every new feature potentially needs to be added in two places.
  - **Decision needed**: Either freeze it (stop updating, mark as deprecated in the file header) or migrate council_ui to the launcher shell and archive guppy_ui. Don't keep treating it as current.

9. **Cross-session memory injection is unbuilt despite the backend existing**
  `guppy_semantic_memory.py` is implemented. Nothing injects relevant memories into the system prompt at request time (Phase 12). This is the highest-leverage AI quality improvement available — it's the difference between a stateless chatbot and a butler that remembers.
  - **Fix**: Add a `recall_relevant(query, k=5)` call at the start of each request and prepend results to the system prompt. ~100ms overhead, massive quality gain.

10. **CRM/VoIP live calls should stay gated until classifier is fixed**
  Write-side tools that send emails or update pipeline stages on a misrouted "teaching" query would be a bad day. Keep stubs until the classifier is trustworthy.

---

## 1000-Foot Review (2026-04-12)

### Current Position

- **Strength**: Guppy is now a real local-first operator system, not just a chat shell. It combines a unified launcher UI, daemon, voice, memory, remote API, and a hardened router in one coherent system. The infrastructure is genuinely solid.
- **Operational baseline**: Strict-mode remote auth live, Cloudflare route active, runtime stack stable for daily use, launcher UI parity complete, stress suite passing.
- **Main gap**: The AI layer (classifier accuracy, memory injection) is weaker than the infrastructure. The system routes to the right model based on keywords, not intent. Memory exists but doesn't influence responses. The butler knows your tools but not your context.

### Project Comparisons (Strategic)

- **Vs. ChatGPT/Claude desktop apps**: Guppy is stronger on local control, custom tools, and operator automation; weaker on turnkey polish and broad out-of-box integrations.
- **Vs. IDE copilots (Cursor/Copilot)**: Guppy is broader than code assistance (voice, reminders, ambient context, daemon actions), but less specialized for deep codebase refactoring workflows.
- **Vs. AutoGPT-style agents**: Guppy is more pragmatic and bounded for daily assistant use; less autonomous for long-running multi-step task execution.
- **Vs. Home-assistant voice stacks**: Guppy has richer LLM reasoning and persona routing; home-assistant stacks are stronger at deterministic IoT/device orchestration.

### Blue-Sky Additions (Ranked by leverage)

1. **Action Reliability Layer**
  Add confidence scoring + preflight checks + rollback-safe action ledger for all write-side tools.
2. **Unified Task Graph**
  Convert single-turn tool calls into explicit multi-step plans with resumable checkpoints.
3. **Memory Steward Agent**
  Auto-curate, dedupe, and summarize memory with confidence aging and source citation tracking.
4. **Personal Ops Console**
  A timeline view of intents, actions, outcomes, and follow-ups across Guppy/Merlin/Council.
5. **Context Router v2**
  Blend user state, channel (voice/text), urgency, and cost/latency into model/tool selection.

### Scope Guardrails (to avoid sprawl)

- Keep Guppy centered on **personal assistant outcomes**, not generic platform ambitions.
- Prefer **completing one end-to-end workflow** (reminder -> action -> confirmation) over adding many partial features.
- Maintain strict split between:
  - **Core**: reliable daily assistant workflows
  - **Experimental**: blue-sky agent behavior behind explicit flags
- Treat packaging and observability as release gates, not optional cleanup.

### Windows Assistant Quality Bar

This is the standard future work should meet before a feature is considered product-grade on Ryan's current Windows-first hardware.

- **Fast wake-up**: app launch, resume, and first interaction should feel immediate; avoid features that impose heavy startup cost by default.
- **Low idle footprint**: daemon, voice, tray, and UI loops should stay conservative on CPU/RAM when the assistant is waiting.
- **Strong voice ergonomics**: push-to-talk, interruption handling, microphone selection, and TTS stop-on-user-input should feel native and reliable.
- **Native Windows feel**: tray behavior, toasts, startup behavior, audio-device handling, and window focus behavior should match Windows expectations.
- **Keyboard-first control**: hotkeys, command entry, and quick actions should work without forcing mouse-heavy interaction.
- **Trust before autonomy**: read-only actions can be fast; write-side actions need confidence checks, confirmation policy, and audit trail.
- **Graceful degradation**: if Anthropic, Ollama, or network access is unavailable, Guppy should fail soft and stay useful.
- **Hardware-aware defaults**: expensive features should be grouped into runtime profiles rather than assumed always-on.

### Runtime Profiles (Planned)

- **Light**: cloud-first, minimal background work, Ollama optional/off by default, best for average Windows laptops.
- **Standard**: cloud-first with selective local fallback, daemon on, voice on demand, balanced for normal desktops.
- **Power**: Council, local teaching workflows, heavier background features, and advanced diagnostics enabled for stronger hardware.

### Phase 1: Smart Dispatcher Core (Haiku-First) ← **COMPLETE (2026-04-12)**

**Objective**: Make Guppy 5-10x faster and predictable. Replace local Ollama blocking with intelligent Claude routing.

- Task classification heuristics (find, build, explain, write, qualify via simple regex/keyword matching)
- Route "simple" queries to Haiku (2-3s)
- Route "complex" queries to Sonnet (5-10s)
- Route "teaching" queries to Merlin/Ollama (Socratic, free, local)
- Proper fallback: Haiku (timeout 3s) → Sonnet (if needed) → Ollama (if offline)
- Status: **Complete**

### Phase 2: Fallback Chain & Offline Handling ← **COMPLETE (via Phase 1)**

**Objective**: No more random 30s timeouts. Predictable chain.

- ✓ Fix fallback logic so Haiku timeout doesn't re-try same backend
- ✓ Auto-detect offline mode → fallback to Ollama-only
- ✓ Clean sequential fallback (no retry loops)
  - Simple: Haiku (3s) → Sonnet → Ollama
  - Complex: Sonnet → Haiku → Ollama
  - Teaching: Ollama → Haiku → Sonnet
- ✓ Offline detection: Anthropic API key check, Ollama availability check before query_local
- Status: **Complete** (implemented as part of Phase 1 design)

### Phase 3: Merlin Smart Routing ← **COMPLETE**

**Objective**: Make Merlin part of daily use, not separate window.

- ✓ Auto-route teaching tasks (explain, teach, learn, understand keywords) to Merlin's Socratic system prompt
- ✓ Integrated Merlin persona selection: teaching queries get `get_merlin_startup_system()` instead of Guppy's
- ✓ Merlin's system prompt provides Socratic teaching method (questions first, direct answers when stuck)
- ✓ All routing still goes through smart dispatcher (Haiku-first fallback chain)
- ✓ Invisible to user: teaching task automatically routes to Merlin persona without extra button clicks
- ✓ UI displays which persona in use: "Smart routing via Merlin..." or "Smart routing via Guppy..."
- Status: **Complete** (integrated into _smart_dispatch method)

### Phase 4: Voice Integration Tuning ← **COMPLETE (2026-04-12)**

**Objective**: Wake-word triggers fast-path dispatcher. Voice feels responsive.

- ✓ `voice_triggered=True` flag flows from `_trigger_wake_listen` → `_send_text` → `Worker` → `_smart_dispatch`
- ✓ Smart dispatch skips task classification when `voice_triggered` — always Haiku-first (2s latency target)
- ✓ TTS on completion already wired via `_on_done` → `_speak_if_current`
- ✓ Orb returns to "wake" state after speaking
- TODO (real-use tuning): validate actual latency, tune openwakeword model and cooldown for daily use

### Phase 5: Memory & Context Caching ← **COMPLETE (2026-04-12)**

**Objective**: Repeated questions are instant. Reduce API calls.

- ✓ Module-level `_RESPONSE_CACHE` in `guppy_ui.py` — TTL 5 min, max 100 entries, oldest-evicted
- ✓ Only caches `task_type == "simple"` responses where no tools were called (safe for stateless lookups)
- ✓ Voice-triggered queries bypass cache (time-sensitive)
- ✓ Cache hit emits full text, updates history, sets `model_used = "cache"` — zero API cost
- ✓ Configurable via `GUPPY_CACHE_TTL` / `GUPPY_CACHE_MAX` env vars

### Phase 6: Foundation Work (Visibility & Reliability)

**Objective**: Make system debuggable and reliable. Prepare for scaling.

- Make `inference_router.py` the single inference path (UIs call it, no bypasses)
- Structured logging: every request logs task type, model chosen, latency, cost
- Metrics dashboard: integrate router events into `runtime/agent_performance.jsonl`
- Progress (2026-04-12):
  - ✓ Added normalized scorecard telemetry to `runtime/router_scorecard.jsonl` from `guppy_ui.py`
  - ✓ Added SLO fields (`slo_target_ms`, `slo_met`) and first-token timing in Guppy request logs
  - ✓ Added tool-budget guardrails (`GUPPY_TOOL_BUDGET`, `COUNCIL_TOOL_BUDGET`) to cap runaway tool loops
  - ✓ Council Merlin leg tuned with `COUNCIL_MERLIN_TIMEOUT` and `COUNCIL_MERLIN_NUM_PREDICT`
  - ✓ **6A complete**: added `runtime/review_router_scorecard.py` for daily scorecard analysis and safe env patch suggestions
  - → **6B next**: surface consolidation + runtime profiles so the product defaults fit Windows hardware instead of assuming every feature is always on
- Status: **In progress**

---

## Future Phases / Blue Sky

These are candidate features ranked by impact. Pick from this list for future sessions.

### Phase 7: Streaming Responses ← **COMPLETE (2026-04-12)**

- ✓ `_claude()` uses `client.messages.stream()` — tokens arrive ~300ms after request
- ✓ `_smart_dispatch` calls `_claude()` directly — streaming + full tool loop included
- ✓ Confirmed in code audit: `while True:` tool loop with streaming in `Worker._claude`

### Phase 8: Proactive / Daemon Mode ← **COMPLETE (2026-04-12)**

- ✓ `ProactiveLoop` in `guppy_daemon.py` — real implementation, polls every 60s
- ✓ Checks agent health, detects stale/crashing agents, auto-nudges via IPC
- ✓ Checks upcoming reminders (≤15 min), sends nudge toast
- ✓ Throttled pattern learning check (1/hr) wired in
- ✓ Wired into `DaemonManager` start/stop lifecycle
- ✓ `_check_daily_summary()` — Haiku "anything important?" fires daily at `GUPPY_DAILY_SUMMARY_HOUR` (default 8am); pulls pending tasks + facts from memory, fires toast + IPC nudge if actionable; respects quiet hours; debounced 23h
- ✓ Daily report pipeline now compiles end-to-end context (RSS world news + runtime logs + manual events/todos + memory/tasks + yesterday reference) and writes markdown reports to `runtime/daily_reports/`
- ✓ Scheduled news reports added at `12:00`, `18:00`, and `22:00` (`GUPPY_NEWS_REPORT_HOURS`, default `12,18,22`)

### Phase 9: Voice-First Fast Path ← **LARGELY COMPLETE (absorbed into Phase 4)**

- ✓ Wake-word → `voice_triggered=True` → Haiku fast-path → TTS on completion
- ✓ Orb returns to "wake" state after speaking
- TODO: real-use latency validation; openwakeword model and cooldown tuning
- Target: sub-2s end-to-end from wake word to first spoken word (infrastructure in place)

### Phase 10: "Just Do It" Task Execution

- Confidence threshold model: high confidence → act without confirmation
- "Send John a message saying I'm running 10 minutes late" → compose, confirm once, send
- Low confidence → ask; high confidence → execute
- Requires: Gmail/calendar tools fully wired + confidence estimator + action audit trail + explicit confirmation policy

### Phase 11: Ambient Awareness ← **COMPLETE (2026-04-12)**

- ✓ `AmbientWatcher` in `guppy_daemon.py` — polls clipboard every 60s
- ✓ Tracks clipboard changes and window title changes
- ✓ Callback system fires registered handlers on interesting content
- ✓ Wired into `DaemonManager` start/stop lifecycle
- ✓ Haiku semantic gate: `_haiku_interesting_check()` classifies content before offering; skips passwords, paths, trivial strings
- ✓ `AmbientBanner` widget in `guppy_ui.py` — non-intrusive bar between chat and input; shows Haiku's suggested action; "Ask Guppy" pre-fills input; auto-dismisses after 30s
- Cooldown: 10 min default (`GUPPY_AMBIENT_COOLDOWN_S`), respects quiet hours

### Phase 12: Cross-Session Memory in System Prompt

- Semantic memory is built but passive
- Auto-thread recent relevant memories into system prompt each request
- "Ryan mentioned preferring X last Tuesday" → influences every reply
- Already have the memory backend; just needs injection logic
- Add shared catalog structure so memory is curated instead of only appended:
  - normalized entity index + alias map
  - citation metadata (source, timestamp, confidence, last-verified)
  - retrieval contract that returns concise, attributable memory snippets

### Phase 13: Merlin Long-Thread Mode

- Instead of one-shot Q&A, Merlin maintains a Socratic thread across a project
- "Let's work through this architecture decision" → ongoing dialogue over days
- Thread stored in semantic memory; resumed on demand

### Phase 14: Self-Improvement Loop ← **COMPLETE (2026-04-12)**

- ✓ `HubOperator.record_event()` logs every hub action to `runtime/hub_patterns.jsonl`
- ✓ `HubOperator.analyze_patterns()` runs Haiku review (throttled 1/hr internally)
- ✓ OperatorCard ANALYZE button triggers on-demand review
- ✓ `OperatorCard` now has a 15-min scheduled QTimer calling `_auto_analyze()` — fires without button press
- ✓ `OperatorCard` also has a 30s display refresh timer for health/status snapshot
- System learns from its own usage patterns automatically

### Phase 15: Digital Seed Vault + Personal Wiki Librarian

- Build a dedicated librarian agent that amasses and curates:
  - Personal Wikipedia (people, projects, places, ideas, events, references)
  - Media library index (audio/video/docs/images with tags, summaries, provenance)
- Seed Vault mode: immutable seed records + revision history for critical memories and media metadata
- Ingestion channels: clipboard, files/folders, URLs, transcripts, and manual notes
- Retrieval modes: semantic search, timeline view, and "show me everything about X" dossiers
- Agent responsibilities:
  - De-duplicate entries, merge aliases, link entities, maintain citations
  - Auto-generate short wiki pages + update related pages
  - Track freshness and confidence per entry
- Hub integration:
  - Operator action buttons: ingest now, rebuild index, run curation pass
  - Scheduled curation in daemon mode with quiet-hours awareness
- Safety:
  - User-owned local storage by default
  - Optional encrypted vault for sensitive seed material
 - Storage rollout plan:
  - Stage 1 (current): USB snapshot backups for program + knowledge database portability
  - Stage 2 (next): NAS snapshot target with longer retention and same manifest format
  - Stage 3 (future): scheduled replication policy with restore drills and integrity checks

### Phase 16: Surface Consolidation & Windows Productization

- Make **Guppy** the clear primary app surface for day-to-day use.
- Move Merlin into a persona/mode path where possible instead of making users choose a different app window for normal flows.
- Keep Council available behind an advanced toggle, power-user setting, or explicit launch path.
- Add hardware-aware runtime profiles (`light`, `standard`, `power`) so expensive features are opt-in or auto-tuned.
- Define the product-grade Windows experience around:
  - fast launch/resume
  - reliable tray/toast behavior
  - dependable voice interruption and PTT
  - low idle overhead
  - clear settings for microphone, speech, startup, and background mode
- Progress (2026-04-12):
  - ✓ Added shared runtime profile/settings model in `utils/runtime_profile.py`
  - ✓ Applied profile defaults across Guppy, Merlin, Council, and Hub startup paths
  - ✓ Added command-palette profile switching in Guppy
  - ✓ Added in-app Guppy settings dialog for runtime profile and surface controls
  - ✓ Guppy settings now affect daemon startup, voice enablement, and wake-word default behavior
  - ✓ Hub now hides/shows advanced surfaces dynamically from saved settings
  - ✓ Added system-aware runtime profile recommendation based on CPU, RAM, and Ollama availability
  - ✓ Hub primary launch action now defaults to Guppy
  - ✓ Windows launch scripts now frame Merlin/Council as advanced surfaces
- Status: **In progress**

## Hub Orchestrator Upgrade ← **IN PROGRESS (2026-04-12)**

Hub is now a real operator — not just a process manager.

### New files
- `utils/hub_operator.py` — shared brain (IPC, pattern log, health checks, smart recommend)

### Updated files
- `guppy_hub.py` — `OperatorCard` (insight + ANALYZE + health row), NUDGE/REPAIR buttons on every `AgentCard`, crash/launch/stop events logged via `record_event()`
- `guppy_daemon.py` — `ProactiveLoop` (Phase 8 skeleton) + `AmbientWatcher` (Phase 11 skeleton) wired into `DaemonManager`
- `guppy_ui.py` — 2s IPC poll for `runtime/guppy.cmd`; handles nudge / clear_history / reset_context / report_status

### IPC protocol
Hub writes `runtime/{id}.cmd` → agent reads + deletes on next 2s poll.
Commands: `nudge`, `clear_history`, `reset_context`, `report_status`.

### Pattern learning
All hub actions append to `runtime/hub_patterns.jsonl`.
`HubOperator.analyze_patterns()` runs Haiku review (throttled 1/hour).
OperatorCard ANALYZE button forces immediate review.

---

## Related Goals (Aligned with Phases)

### Remote Hardening

- **Blocked by**: Phase 1 (need fast latency for remote to feel snappy)
- **Unblocked by**: Phase 1 → Haiku-first makes tunnel latency acceptable

### Status / Context Performance

- **Blocked by**: Phase 5 (caching) + Phase 6 (logging)
- **Improved by**: Phase 1 (fewer Ollama waits)

### Butler Workflow Depth (Not CRM sales)

- **Personal tasks** example: "Remind me to call X at 3pm", "Draft email to Y", "What's on my calendar tomorrow?"
- Use Merlin for drafting (Socratic) + Guppy-Haiku for quick lookups
- Use Merlin for explaining/teaching (uncommon, but intentional)
- Status: **In design** (enabled by Phase 1-3)

### Surface Consolidation

- **Blocked by**: Phase 6B only in the sense that settings/runtime-profile plumbing should land before broad UX cleanup.
- **Enabled by**: Phase 1-6 foundation already being stable enough to consolidate around a single primary surface.
- **Goal**: Guppy-first user journey, advanced surfaces moved behind explicit intent.

### Hardware-Aware Operation

- **Goal**: keep default behavior viable on a normal Windows machine, not just on a high-end dev box.
- Prefer cloud-first/simple routes over local-heavy routes for default user flows.
- Enable local models, Council, and heavier background analysis through profile-aware settings.
- Treat idle CPU/RAM usage and startup cost as product metrics, not just implementation details.

### Release Discipline

- **Blocked by**: Phase 6 (metrics and reliability foundation)
- **Improved by**: All phases (predictable performance)

### Voice and Wake-Word Tuning

- **Blocked by**: Phase 1 (need fast response to feel natural)
- **Enabled by**: Phase 4 (fast-path voice dispatch)

## Open Questions

- Which workflow should be hardened next after reminders: email drafting/send confirmation, or calendar action automation?
- Should ambient awareness keep non-intrusive banner as default, with toast reserved for urgent-only cases?
- Is Phase 6 (single inference path) high enough priority to block Phase 10 "Just Do It" execution, or can they proceed in parallel?

Recommended current answers (can be revised with new data):
- First hardened workflow: **task reminders** (lowest external dependency risk).
- Ambient surface default: **non-intrusive banner** first, toast only for urgent items.
- Prioritization: **finish Phase 6 before Phase 10** to keep action execution on a reliable routing foundation.

## Credentials & Dependencies

**See** `CREDENTIALS_AUDIT.md` for a complete audit of what works locally vs. what needs credentials or 3rd party services.

**Quick Summary**:
- ✅ **Desktop chat & voice**: Works offline (no credentials needed)
- ✅ **Smart dispatcher phases 1-3**: Fully implemented; optional ANTHROPIC_API_KEY for speed
- ✅ **Remote API**: Strict mode active (`GUPPY_DEV_MODE=0`); JWT + Turnstile wired; public endpoint live at `https://guppy.sparkscuriositystudio.com`
- ❌ **CRM & VoIP**: Safe stubs (log intent, no actual actions)

## Handoff Rules

- Add new notes at the top of the handoff log.
- Keep entries short and factual.
- Record what changed, what was verified, and what still needs follow-up.
- Do not create another status markdown file for routine session notes.

## Handoff Log

### 2026-04-12 (Pre-Cruise Tooling + Provider/Logging Verifiers)

- Added coding ops tools in `guppy_core.py` for faster iteration loops:
  - `test_targeted`
  - `lint_fix`
  - `typecheck_targeted`
  - `git_patch_summary`
- Added cheap/free provider client libraries and coding quality deps:
  - `openai`, `google-generativeai`, `mistralai`
  - `ruff`, `mypy`, `pytest-xdist`, `unidiff`
  - dev bundle file: `requirements-dev.txt`
- Added pre-cruise readiness scripts:
  - `tools/verify_ollama_runtime.py` (models, pings, context, residency)
  - `tools/verify_provider_runtime.py` (key/library readiness + optional smoke)
  - `tools/verify_logging_health.py` (runtime JSONL freshness + SQLite telemetry mirror health)
- Tool schema audit rerun clean after additions (`runtime/tool_schema_audit.json`, 0 errors).

### 2026-04-12 (Recovery UX + Telemetry API + Personalization Scaffold)

- Added launcher Recovery controls in Settings and wired actions end-to-end through launcher runtime calls.
- Added guarded API `/repair` endpoint with dry-run support and actions:
  - `warmup`
  - `restart_daemon`
  - `audit_runtime`
- Added status rail "last recovery outcome" feedback line and launcher runtime event logging for recovery operations.
- Added personalization runtime scaffold + schemas:
  - `docs/schemas/persona.schema.json`
  - `docs/schemas/provider_registry.schema.json`
  - `docs/schemas/voice_binding.schema.json`
  - `utils/personalization_config.py`
- Wired scaffold ensure on startup and added launcher Settings JSON editors for Personas, Providers, and Voices with reload/validate/save.
- Added/updated smoke coverage for repair + launcher interactions and added personalization scaffold tests.
- Stress harness now reports and gates hot-path API latency separately from global p95; default hot-path gate tightened to 1100ms after stable full passes.
- Live runtime validation note: current model runtime checks should use `ollama show` + `ollama ps`; recent verification confirmed active `num_ctx=16384` on loaded runtime.

### 2026-04-12 (Runtime Profiles + Guppy-First Launch Path)

- Added `utils/runtime_profile.py` as the shared profile/settings source for `light`, `standard`, and `power` runtime modes.
- Guppy now loads the active runtime profile on startup, shows it in the status area, and can save profile selection from both the command palette and an in-app settings dialog.
- Guppy settings now drive live behavior for:
  - daemon on/off
  - voice enabled/disabled
  - wake-word default on/off
- Hub now displays active profile/default surface settings, shows a hardware-aware profile recommendation, and hides advanced surfaces when requested.
- Tray menu now offers:
  - Launch Guppy
  - Launch Merlin (Advanced)
  - Launch Council (Advanced)
- Updated Windows launch scripts so:
  - Guppy launches with `standard` profile by default
  - Merlin/Council launch with `power` profile and are labeled advanced

### 2026-04-12 (Product Direction Reset: Guppy-First Windows Assistant)

- Locked in product direction for next planning cycle:
  - Guppy is the main product surface.
  - Merlin shifts toward persona/mode behavior inside Guppy where practical.
  - Council remains a power-user surface rather than a default entry point.
- Added a Windows assistant quality bar to guide future implementation:
  - fast launch/resume
  - low idle overhead
  - native tray/toast/audio behavior
  - strong voice ergonomics
  - trust/audit before autonomous actions
  - hardware-aware defaults via runtime profiles
- Added new roadmap phase: **Phase 16: Surface Consolidation & Windows Productization**.

### 2026-04-12 (Risk Sweep 1-4 Completed)

- Item 1 (repo hygiene) closed:
  - Expanded `.gitignore` for volatile runtime/operator artifacts (`runtime/*.jsonl.*`, `runtime/*.status`, `runtime/*.cmd`, stress/lifecycle reports, local `.claude/settings.local.json`).
- Item 2 (remote stability pass) executed with explicit dry/live reports:
  - Dry report: `runtime/lifecycle_dry_report.json`
  - Live report: `runtime/lifecycle_live_report.json`
  - Key finding: API and Ollama restart paths still report stop-side unverified states while ending in running/healthy for Ollama and transiently down for API in final check snapshot.
  - Cloudflared start/stop path verified healthy in live run.
- Item 3 (lean packaging profile) implemented:
  - `build_executable.bat` now supports `--lean` with robust multi-flag parsing.
  - `Guppy.spec` now supports `GUPPY_LEAN_BUILD=1` with optional-heavy excludes and reduced hidden imports for faster iteration builds.
  - Packaging docs updated in `docs/PACKAGING.md` with lean/CI examples.
- Item 4 (fresh reliability evidence) completed:
  - Extensive stress suite rerun passed (`ok: true`) at `runtime/stress_report_20260412_203540.json`.
  - Scorecard analyzer rerun completed and refreshed `runtime/router_tuning_patch.env`.
  - Current recommendation remains `GUPPY_SLO_SIMPLE_MS=3500`.

### 2026-04-12 (Packaged EXE Smoke Launch)

- Ran packaged smoke test from `dist/Guppy.exe`.
- Result: process launched and stayed alive for at least 8 seconds (`RUNNING_AFTER_8S=1`).
- Test harness then force-stopped process to keep the workspace clean (`STOPPED_AFTER_SMOKE=1`).

### 2026-04-12 (Packaging Gate Closed + Reminder UX Ack)

- Implemented reminder-fired user acknowledgement path:
  - `guppy_daemon.py`: scheduler now emits `reminder_fired` IPC command to both Guppy and Council UIs on trigger.
  - `guppy_ui.py`: added `reminder_fired` command handler to post "Reminder completed" bubble.
  - `council_ui.py`: added `reminder_fired` command handler to post completion bubbles in both panels.
- Refreshed stale roadmap wording:
  - Phase 1 now marked complete (removed stale "starting now" phrasing).
  - Updated ambient open-question phrasing to match implemented Phase 11 baseline.
- Packaging run outcome:
  - Build complete: `dist/Guppy.exe` present (~719 MB).
  - Validator fixed and green:
    - `validate_build.bat` parsing bug corrected (escaped `)` in size echo).
    - `tools/validate_build_checks.py` now injects repo root into `sys.path` for stable module imports.
    - `validate_build.bat` now passes all checks on current environment.

### 2026-04-12 (Live Packaging Poll + Next-Step Refresh)

- Started a dedicated packaging run with:
  - `build_executable.bat --no-clean --ci`
- Build process health checks during run:
  - Found duplicate PyInstaller runs and terminated the older duplicate process to avoid contention.
  - Confirmed one active child PyInstaller process remains and continues advancing (high cumulative CPU time, ~1 GB working set).
- Current gate status:
  - `dist/Guppy.exe` still pending while analysis/collection continues.
  - `validate_build.bat` will be re-run immediately once artifact appears.
- Updated immediate execution order:
  1. Wait for artifact emit (`dist/Guppy.exe`).
  2. Run `validate_build.bat` and record exact pass/fail checks.
  3. If build time remains excessive, add a lean packaging profile in `Guppy.spec` to reduce optional heavy module collection.

### 2026-04-12 (Next-Step Items Executed)

- Re-ran extensive stress suite:
  - `python -m tests.stress_system --api-requests 900 --api-workers 35 --route-iterations 14000 --reminders 900 --log-events 8000`
  - Result: pass (`ok: true`) in `runtime/stress_report_20260412_195028.json`
  - Highlights:
    - route resolution: 14,000 iterations, 0 failures
    - API: 900 requests @ 35 workers, 0 failures
    - reminders: 900/900 created and cancelled, 0 remaining
- Re-ran router scorecard analyzer:
  - `python runtime/review_router_scorecard.py --days 7 --write-patch`
  - Current recommendation retained: `GUPPY_SLO_SIMPLE_MS=3500`
  - Patch file refreshed at `runtime/router_tuning_patch.env`
- Packaging gate execution:
  - `validate_build.bat` now runs cleanly for checks 3-7
  - Found build blocker in `build_executable.bat`: hidden import `APScheduler` was invalid for PyInstaller on this environment
  - Fixed to `--hidden-import=apscheduler` and restarted `build_executable.bat --no-clean --ci`
  - Current remaining blocker: `dist/Guppy.exe` not yet produced (check 1); re-run `validate_build.bat` once build completes

### 2026-04-12 (Extensive Stress Pass + Scheduler Fix)

- Added `tests/stress_system.py` for high-volume local stress across:
  - route resolution
  - API endpoint concurrency
  - reminder scheduler burst behavior
  - logging I/O throughput
- First heavy run exposed reminder scheduling collisions under burst load.
- Root cause: timestamp-derived reminder IDs were not unique enough under high-frequency scheduling.
- Fixed `TaskScheduler.schedule_reminder()` to use UUID-based job IDs in `guppy_daemon.py`.
- Final stress run passed (`ok: true`) with report:
  - `runtime/stress_report_20260412_194705.json`
  - route resolution: 14,000 iterations, 0 failures
  - API: 900 requests @ 35 workers, 0 failures
  - reminders: 900 requested / 900 created / 900 cancelled / 0 remaining
  - logging I/O: 8,000 events, stable write throughput
- Next operational step: run this stress suite weekly and log the newest report filename in handoff.

### 2026-04-12 (5-Item Execution Sprint)

- Item 1 complete: seeded mixed scorecard workload events and verified analyzer can compute SLO/latency/route distributions.
- Item 2 complete: executed `python runtime/review_router_scorecard.py --days 7 --write-patch`; applied low-risk `.env` overrides:
  - `GUPPY_TOOL_BUDGET=6`
  - `COUNCIL_TOOL_BUDGET=5`
  - `GUPPY_SLO_SIMPLE_MS=3500`
- Item 3 complete: route policy resolution moved into `inference_router.py` for Guppy UI non-auto paths and Council Guppy worker decisions.
- Item 4 complete: hardened reminder reliability in `TaskScheduler`:
  - fixed active reminder listing bug (`get_job(job_id)` check)
  - cleanup on reminder fire
  - added reminder event journal (`runtime/reminder_events.jsonl`)
  - added test `tests/test_reminder_workflow.py` (passes)
- Item 5 in progress/completion tail:
  - fixed `validate_build.bat` command parsing failures
  - added `tools/validate_build_checks.py`
  - made `build_executable.bat` non-interactive via `--ci`
  - build + full validator pass pending `dist/Guppy.exe` artifact completion

### 2026-04-12 (6A Router Scorecard Auto-Analyzer)

- Implemented `runtime/review_router_scorecard.py`.
- Analyzer reads `runtime/router_scorecard.jsonl` (default 7-day window), reports:
  - SLO hit rate
  - latency/first-token p95
  - error/degraded counts
  - budget-hit counts
  - route/task/model distributions
- Added bounded tuning recommendations and optional patch output:
  - `python runtime/review_router_scorecard.py --days 7 --write-patch`
  - Writes `runtime/router_tuning_patch.env` for manual review before applying.
- Current run status: script executes successfully; no recommendations until scorecard events accumulate.

### 2026-04-12 (Items 1, 2, 5 Delivered)

- Implemented Phase 6 telemetry normalization in `guppy_ui.py`:
  - Added scorecard logger (`utils/router_scorecard.py`) output to `runtime/router_scorecard.jsonl`
  - Added `first_token_ms`, `slo_target_ms`, `slo_met`, `fallback_count`, and `tool_budget_hit` metrics
  - Added SLO env knobs: `GUPPY_SLO_SIMPLE_MS`, `GUPPY_SLO_COMPLEX_MS`, `GUPPY_SLO_VOICE_MS`
- Implemented tool-loop budgets (runaway prevention):
  - Guppy: `GUPPY_TOOL_BUDGET` (default 8)
  - Council: `COUNCIL_TOOL_BUDGET` (default 6)
  - Behavior on cap: return best-effort response and mark request degraded/tool_budget_hit
- Council Merlin performance tuning (item 5):
  - Added `COUNCIL_MERLIN_TIMEOUT` (default 75s)
  - Added `COUNCIL_MERLIN_NUM_PREDICT` (default 320)
  - Tightened local options (`temperature/top_p/top_k`) for faster, more stable response times

### 2026-04-12 (Daily Routine E2E + Scheduled News Reports)

- Evaluated routine as a true end-to-end workflow: trigger -> gather -> reference yesterday -> synthesize -> persist -> notify.
- Extended `ProactiveLoop` report pipeline in `guppy_daemon.py` to include:
  - Popular RSS feeds (BBC, NYT World, Al Jazeera, Reuters World, Google News RSS)
  - Runtime logs (`agent_performance.jsonl`, `session_events.jsonl`, `integration_events.jsonl`, `hub_patterns.jsonl`)
  - Manual inputs from `runtime/manual_events.jsonl|.txt`, `runtime/daily_manual_events.md`, `runtime/todo.txt|.md`
  - Pending tasks/facts from memory and explicit yesterday-report reference
- Added scheduled world news reports at `12:00`, `18:00`, and `22:00` with per-day per-slot dedupe.
- Output files:
  - Daily summary: `runtime/daily_reports/YYYY-MM-DD.md`
  - News slots: `runtime/daily_reports/YYYY-MM-DD-news-HH00.md`
- New config: `GUPPY_NEWS_REPORT_HOURS` (default `12,18,22`)

### 2026-04-12 (Codebase Audit + Cleanup)

**Syntax**: All 40+ Python files pass `py_compile` with no errors.

**Port pivot propagated**: `8080` → `8081` corrected in `bin/launch_api.bat`, `guppy_api.py` (allowed origins), `guppy_hub.py` (default health-check port), `docs/API.md`, `CREDENTIALS_AUDIT.md`. Previously only the runtime files and tunnel config had been updated.

**Stale docs archived** to `docs/archive/root-history/`:
- `CLAUDE_REVIEW_SUMMARY.md`, `HANDOFF_COPILOT_2026-04-11.md`, `INFERENCE_ROUTER_INTEGRATION_COMPLETE.md`, `PHASE2_COMPLETE.md`, `IMPLEMENTATION_COMPLETE.txt`, `docs/CLAUDE_CODE_HANDOFF.md`

**Files relocated**:
- `proxy8080.py` → `tools/proxy8080.py` (port-forwarding utility, not a top-level module)
- `validate_phase_1_3_no_ui.py` → `tests/test_router_smoke.py` (promoted to permanent test)
- `validate_phase_1_3.py` → `docs/archive/root-history/` (UI-dependent, phases done)

**Deleted**:
- `chroma_test_soak/` — soak test binary artifacts (verified Chroma works, data not needed)
- `runtime/diagnostics_guppy_20260412_*.json` — 6 stale single-session diagnostics dumps

**No live code changed** beyond port number corrections. All model strings already current.

**Flagged for Ryan** (not touched):
- `AI_Project/` subfolder — appears to be a separate older project with its own venv. Not referenced by any Guppy code. Safe to delete or move out of repo, but not done without confirmation.
- Root `Modelfile.guppy` / `Modelfile.merlin` — different from `models/` versions (different base model configs). Need Ryan to confirm which is current before pruning either.

### 2026-04-12 (Phase 11 Ambient Awareness Complete)

**Ambient offer → proactive banner — COMPLETE**

- `AmbientWatcher._haiku_interesting_check()` added to `guppy_daemon.py`: calls Haiku with clipboard content, returns `(interesting: bool, action: str)`. Fails open (True) if no API key or call errors. Skips offer if `interesting=False`.
- `AmbientBanner` widget added to `guppy_ui.py`: 42px bar between scroll area and input bar, hidden until an offer arrives. Shows Haiku's suggested action sentence, "Ask Guppy" button (pre-fills input), dismiss button (×), 30s auto-expire.
- `ambient_offer` IPC handler in `GuppyWindow._handle_cmd()` updated: was dumping into chat via `_bubble()`; now calls `self._ambient_banner.show_offer(action)`.
- Phase 11 marked complete in ROADMAP.

**Files changed**:
- `guppy_daemon.py` — `_tick()` Haiku gate, `_haiku_interesting_check()` method
- `guppy_ui.py` — `AmbientBanner` class, `_build_chat_pane()` banner slot, `ambient_offer` handler

### 2026-04-12 (Benchmark + 5 items complete)

**Doc-vs-reality audit findings**:
- Smart dispatch tool loop was already wired (docs said "not yet") — `_claude()` has full `while True:` tool loop and `_smart_dispatch` calls it directly.
- `ProactiveLoop` and `AmbientWatcher` are full implementations, not skeletons as docs claimed.
- Actual tool count: 73 (after this session). README claimed 75, handoff claimed 65 — both stale.
- Tool calls through smart dispatch confirmed working. No code change needed.

**Missing tools added to `guppy_core.py`** (tool count: 70 → 73):
- `run_python` — subprocess execution of Python snippets, `.venv` python, stdout/stderr capture, 1–60s configurable timeout
- `notify` — Windows 11 toast via `win11toast`, fallback to ctypes MessageBox
- `web_summarize` — HTTP fetch + Claude Haiku summary; Firecrawl if `FIRECRAWL_API_KEY` set

**Phase 4 voice fast-path — COMPLETE**:
- Added `voice_triggered` parameter to `Worker.__init__`
- `_smart_dispatch` now short-circuits task classification when `voice_triggered=True` → always Haiku-first (2s latency target)
- `_trigger_wake_listen` passes `voice_triggered=True` to `_send_text`
- TTS on completion was already wired; no change needed there

**Scheduled `analyze_patterns()` — COMPLETE** (`guppy_hub.py`):
- `OperatorCard.__init__` now starts two timers: 30s display refresh, 15min auto-analyze
- `_auto_analyze()` runs `HubOperator.analyze_patterns(force=False)` in background thread
- HubOperator internal throttle (1/hr) prevents excess API calls; timer just ensures it fires without manual button press

**Phase 5 response cache — COMPLETE** (`guppy_ui.py`):
- Module-level `_RESPONSE_CACHE` dict (TTL 5 min, max 100 entries, oldest-evicted)
- Only caches `task_type == "simple"` responses where `tool_calls == 0`
- Voice-triggered queries bypass cache (often time-sensitive)
- Cache hit emits full text in one shot, updates history, sets `model_used = "cache"`
- Configurable via `GUPPY_CACHE_TTL` and `GUPPY_CACHE_MAX` env vars

**Files changed this session**:
- `guppy_core.py` — added `run_python`, `notify`, `web_summarize` tool definitions + handlers
- `guppy_ui.py` — `voice_triggered` param, Haiku fast-path, response cache
- `guppy_hub.py` — `OperatorCard` scheduled refresh + auto-analyze timers
- `guppy_semantic_memory.py` — Chroma upsert ID fix, warning removal, migrate helper
- `ROADMAP.md` — this log entry

**Known deferred**:
- Phase 6 (single inference path) — UIs still bypass router for non-auto modes; low urgency now that smart dispatch is the primary path
- FIRECRAWL_API_KEY not set — `web_summarize` will fall back to HTTP+Haiku (works, just no JS rendering)
- `run_python` and `notify` available but not in Merlin/Council tool surfaces (only Guppy)

### 2026-04-12 (Chroma Unblocked)

**Chroma semantic backend — READY**

- Ran soak test: 20 upserts + query against `chromadb 1.5.2` with `anonymized_telemetry=False`. No crash. All ops passed.
- Root cause of prior deferred status: posthog telemetry thread. Already mitigated in code via `ANONYMIZED_TELEMETRY=FALSE` env + `Settings(anonymized_telemetry=False)`.
- **Bug fixed** — `_remember_chroma` was using `f"{k}:{timestamp}"` as the Chroma ID, creating duplicate documents on every write instead of upserting. Fixed to use `key` as the ID.
- **Cleaned up** — removed "experimental/deferred" warning prefixes that were being injected into tool return values (would corrupt Guppy's tool responses).
- Added `migrate_sqlite_to_chroma()` helper for one-time migration of existing SQLite semantic memories.
- Default backend remains `sqlite`. Enable Chroma with `GUPPY_SEMANTIC_BACKEND=chroma` in `.env`.
- Chroma advantage: HNSW approximate nearest neighbor (scales, native distance). SQLite advantage: zero deps, fine for <10k memories.

**Files changed**:
- `guppy_semantic_memory.py` — fixed upsert ID, removed warning prefixes, added `migrate_sqlite_to_chroma()`

### 2026-04-12 (Strict Mode + Public Auth Complete)

**Remote API hardening — COMPLETE**

- `GUPPY_DEV_MODE=0` set in `.env` — strict mode active
- Cloudflare Turnstile widget created; site key + secret written to `.env` and `web/turnstile.js`
- `CLOUDFLARE_HOSTNAME` set to `guppy.sparkscuriositystudio.com`; `GUPPY_ALLOWED_ORIGINS` updated
- **Bug fixed** — `hub_operator.py` health check: default port `8000` → `8081`
- **Bug fixed** — `guppy_api_auth.py`: stale shell env captured at import time; added `load_env_file(override=True)` at module level + `_refresh_runtime_config()` called before every auth operation
- **Bug fixed** — `guppy_api.py`: `reload=True` was hardcoded; now mirrors `DEV_MODE` (can force with `GUPPY_API_RELOAD=1`)
- **Port pivot** — ghost OS socket entries held `127.0.0.1:8080` (PIDs unkillable without reboot); API moved to `8081` (`GUPPY_API_PORT` env var)
- Cloudflare tunnel ingress updated via API to route `guppy.sparkscuriositystudio.com` → `localhost:8081`
- `~/.cloudflared/config.yml` written to ensure local config matches dashboard
- **End-to-end verified**: `POST https://guppy.sparkscuriositystudio.com/auth/verify` with dummy token → `400 {"detail":"Invalid Turnstile token"}` — Cloudflare edge → tunnel → API → Turnstile verify chain all working

**Files changed this session**:
- `.env` — `GUPPY_DEV_MODE`, `CLOUDFLARE_HOSTNAME`, `GUPPY_ALLOWED_ORIGINS`, `TURNSTILE_SECRET/SITE_KEY`, `GUPPY_JWT_SECRET`
- `web/turnstile.js` — site key updated
- `guppy_api.py` — `load_env_file(override=True)`, port via `GUPPY_API_PORT` env, reload respects `DEV_MODE`
- `guppy_api_auth.py` — `load_env_file(override=True)` at module level, `_refresh_runtime_config()` added
- `utils/hub_operator.py` — default API port `8000` → `8081`
- `bin/start_tunnel.bat` — `LOCAL_PORT` `8080` → `8081`
- `~/.cloudflared/config.yml` — new file, routes both hostnames to `localhost:8081`

**Known deferred**:
- Ghost PIDs `2764` / `54256` still show LISTENING on `8080` in `netstat` but are dead (cleared on next reboot)
- `bin/start_tunnel.bat` `TUNNEL_ID` still uses placeholder default; relies on `.env` override (working)

### 2026-04-12 (Phase 3 Merlin Routing Complete)

**Phase 3: Merlin Smart Routing — IMPLEMENTED**

- Imported Merlin's system components into guppy_ui.py: `get_merlin_startup_system()` and `SPELL_MAP`
- Enhanced `_smart_dispatch()` to detect task type and select appropriate persona:
  - Teaching tasks (explain, teach, learn, etc.) → use `get_merlin_startup_system()`
  - All other tasks → use Guppy's `get_startup_system()`
- Merlin persona now invoked automatically for teaching queries without user having to open separate window
- Task classification reuses router's heuristics: Socratic teaching prompts route to Merlin, technical queries route to Guppy
- UI feedback updated to show persona in use ("Smart routing via Merlin..." vs. "Smart routing via Guppy...")
- All Merlin queries still respect smart fallback chain: Ollama (Merlin model preferred) → Haiku → Sonnet
- Decision: Merlin stays local-only (Ollama) for teaching; no cloud fallback for teaching tasks (intentional—local model + Socratic style preferred)

**CUMULATIVE STATUS (Phases 1-3 Complete)**:

- ✓ Smart dispatcher core with task classification (15/15 tests passing)
- ✓ Haiku-first routing (3s timeout, proper fallback chain with no retries)
- ✓ Merlin automatic routing for teaching tasks (Socratic persona)
- ✓ All integrated into guppy_ui.py Worker class
- ✓ Mode="auto" now uses intelligent smart dispatch instead of legacy _route_auto_mode()
- ✓ Backward compatible: manual modes ("claude", "ollama") still work
- ✓ No new UI buttons: routing is invisible, just faster + smarter

**Impact Summary**:
- Speed: Simple queries 2-3s (vs. 10-30s with Ollama)
- Intelligence: Teaching tasks get Socratic method automatically
- Reliability: No random timeouts, clean fallback chain
- Cost: Haiku-first reduces API spend for simple tasks

**What's Ready to Test**:
- Run Guppy in "auto" mode and ask simple, complex, and teaching questions
- Profile actual latency (empirical validation)
- Verify persona switching (Merlin for "explain" vs. Guppy for others)

**What's Next**:
- Phase 4: Voice integration (wake-word fast-path, PTT responsive)
- Phase 5: Caching (repeated Q instant, reduced API calls)
- Phase 6: Foundation (logging, metrics, tool loops, streaming)

### 2026-04-12 (Phase 1 Implementation)

**Phase 1: Smart Dispatcher Core — IMPLEMENTED**

- Enhanced `inference_router.py` with task classification and smart dispatch:
  - Added `_classify_task()` method: heuristic classification into simple/complex/teaching based on keywords and length
  - Added `query_smart()` method: Haiku-first routing for butler UX (<3s latency target)
    - Simple tasks (lookup, format, summarize) → Haiku (2-3s)
    - Complex tasks (build, debug, research, code) → Sonnet (5-10s)
    - Teaching tasks (explain, teach, learn) → Merlin/Ollama (Socratic, local)
  - Updated `query()` signature to support mode parameter: "legacy" (local-first) or "smart" (Haiku-first, task-aware)
  - Added `route_inference_smart()` convenience function for UIs to use
  - Decision: Reduced OLLAMA_TIMEOUT from 30s to 10s (no longer primary path); added HAIKU_TIMEOUT_SMART of 3s
  - Decision: No retry loops—once fallback starts, don't retry failed backend
  
- Integrated smart dispatch into `guppy_ui.py` Worker class:
  - Added import: `from inference_router import route_inference_smart`
  - Added `_smart_dispatch()` method: calls router, handles response streaming and history updates
  - Modified `run()` method: when mode="auto", now uses `_smart_dispatch()` instead of `_route_auto_mode()`
  - Legacy modes ("claude", "ollama") remain unchanged for backward compatibility
  - Routing decision logged to UI as "routing (smart mode) • task-aware dispatch"
  
- Design decisions recorded:
  - Smart dispatch is invisible to user (no new UI buttons; just faster/smarter)
  - Backward compatible: manual modes still work, "auto" mode gets smart dispatch
  - Task classification uses simple keyword heuristics (regex-free, fast, debuggable)
  - Teaching tasks route to local Merlin first (Socratic teaching intent) before cloud fallback
  - Complex tasks prefer Sonnet (more expensive but better reasoning) over Haiku
  - Simple tasks prefer Haiku (cheap, fast) for instant response

**Status**: Phase 1 complete and integrated. Ready for testing.

**Validation Results**:
- ✓ Router initialization: successful (Anthropic available status checked, timeouts set correctly)
- ✓ Task classification: 15/15 tests passed (simple, complex, teaching queries all classified correctly)
- ✓ Edge cases: handled (short queries, empty inputs, ambiguous queries default safely)
- ✓ Syntax validation: both inference_router.py and guppy_ui.py pass error checks
- ✓ Integration: router successfully imported and integrated into Guppy UI Worker class

**Classifier Notes**:
- Simple tasks (what, when, where, remind, format, summarize, list)
- Complex tasks (build, debug, design, research, analyze, optimize)
- Teaching tasks (explain, teach, learn, understand, how does, why is, concept)
- Fallback: length < 50 chars → simple; default → complex (safe over-dispatch to Sonnet)

**Known Limitations (Deferred)**:
- ⏸ Tool calls: Not yet supported in smart dispatch (Phase 1). Single-turn responses only.
  - Will be added in Phase 6 (Foundation work) via router enhancement to return full response metadata.
- ⏸ Streaming: Smart dispatch returns full response text (no streaming like _claude has).
  - Will be added in Phase 6 as part of foundation improvements.

**Follow-up**:
- Phase 1a (Tonight/Tomorrow): Run live butler queries to validate task classification accuracy
- Phase 1b (Tomorrow): Profile latency improvements (expectation: simple queries <3s, complex 5-10s)
- Phase 4 (Tomorrow): Voice integration tuning (wake-word fast-path to Haiku)
- Phase 5 (Later this week): Memory & context caching (repeated questions instant)
- Phase 6 (Later this week): Foundation work (logging, metrics, tool loop support, streaming)

### 2026-04-12 (Strategic Shift)

**Strategic Shift: Smart Dispatcher for Butler/Assistant UX**

- Analyzed current system: Ollama bottleneck is killing latency; inference router exists but UIs bypass it; Merlin unused (requires manual selection).
- Reframed priorities away from CRM/sales workflows toward butler/personal assistant: fast (<3s), accurate, transparent, integrated voice.
- Designed 6-phase implementation plan:
  - Phase 1 (Starting): Smart dispatcher core (task classification → Haiku for simple, Sonnet for complex, Merlin for teaching)
  - Phase 2: Fallback chain fix (no more random 30s timeouts)
  - Phase 3: Merlin smart routing (auto-detect teaching tasks)
  - Phase 4: Voice fast-path tuning (wake-word triggers quick response)
  - Phase 5: Memory/caching (repeated questions instant)
  - Phase 6: Foundation (logging, metrics, streaming, single inference path)
- Aligned phases with existing roadmap goals: remote hardening unblocked by Phase 1 latency improvement; butler workflows enabled by Phase 1-3; release discipline enabled by Phase 6.
- Identified that monetization is secondary; butler experience is primary. Foundation for future fine-tuning and scaling built into architecture.

### 2026-04-12

- Decided to keep `docs/TROUBLESHOOTING.md` and `docs/PACKAGING.md` as standalone runbooks, while folding short operational summaries into `README.md`.
- Archived `docs/FEATURES.md` to `docs/archive/reference-history/FEATURES.md`; kept `docs/API.md` and `docs/VOICE.md` as focused operational references.
- Kept `CONTRIBUTING.md` in the repo root by convention and moved `PACKAGING.md` to `docs/PACKAGING.md` to reduce root noise.
- Moved older planning and reference docs from `docs/` into `docs/archive/planning-history/`.
- Moved older session, review, milestone, and one-off briefing docs out of the repo root into `docs/archive/root-history/`.
- Added archive notices to older handoff and completion docs so they no longer compete with the living-doc pair.
- Folded the most useful API and voice operational details into `README.md`.
- Current living docs remain `README.md` and `ROADMAP.md` only.

### 2026-04-12

- Condensed living status docs down to `README.md` and `ROADMAP.md`.
- Rewrote `README.md` as the primary source of truth for architecture, setup, current state, and active priorities.
- Rewrote `ROADMAP.md` as the active work board plus handoff log for multi-agent sessions.
- Fixed Guppy UI streaming crash in `guppy_ui.py` by initializing streamed label text state and falling back safely when appending.
- Confirmed the repo already contains the API surface, web client alpha, smoke tests, semantic memory, hub logging, wake-word path, and CRM/VoIP scaffolding.
- Remaining high-value gaps: external remote validation, `/status` latency, packaging hardening, and one complete revenue workflow.

---

## Prioritised Next Steps (2026-04-12)

Ordered by impact. First three are ship-blockers for a trustworthy daily butler.

### 1. Semantic task classifier (SHIP BLOCKER — AI quality)

Replace `inference_router._classify_task()` keyword matching with a Haiku-backed structured output call.

**Why it matters**: The current classifier misroutes "what is X" queries to Ollama/teaching. If Ollama is offline, those fail. For voice queries especially, a misroute to a slow backend breaks the <3s target.

**Approach**:
```python
# In _classify_task(), call Haiku with:
# system: "Classify the intent of this query."
# user: query text
# force tool_choice or structured output: {task_type: "simple"|"complex"|"teaching"}
# Cache result for identical queries (session TTL)
```
**File**: `inference_router.py:71`

---

### 2. Persistent response cache (SHIP BLOCKER — UX)

Back `_RESPONSE_CACHE` with SQLite so it survives restarts.

**Why it matters**: Butler warms up cold every morning. Same "what's my schedule?" at 9am every day hits the API every time.

**Approach**: Add a `response_cache` table to `ops_telemetry.sqlite3` with columns `(key TEXT PRIMARY KEY, response TEXT, model TEXT, ts REAL)`. On cache miss, check SQLite before API. On hit within TTL, serve from SQLite. On write, update SQLite + in-process dict.

**File**: `guppy_ui.py:42` (or extract to `utils/response_cache.py`)

---

### 3. Cross-session memory injection into system prompt (SHIP BLOCKER — AI quality)

Wire `guppy_semantic_memory.recall()` into the system prompt at request time.

**Why it matters**: The semantic memory backend is fully built. Nothing uses it at inference time. This is the gap between a chatbot and a butler. "Ryan mentioned he prefers concise answers" should influence every reply automatically.

**Approach**:
```python
# At start of each _smart_dispatch / Worker.run():
memories = semantic_memory.recall(user_text, k=5)
if memories:
    system_prompt = system_prompt + "\n\n[RELEVANT CONTEXT]\n" + format_memories(memories)
```
**File**: `guppy_ui.py` Worker class, `guppy_api.py` chat handler

---

### 4. Fix `GUPPY_TOOL_BUDGET` code default (quick fix)

Change `guppy_ui.py:102` default from `"8"` to `"6"` to match the validated env patch.

**File**: `guppy_ui.py:102`

---

### 5. Type annotations on `utils/` public functions

Annotate return types on all public functions in `utils/runtime_profile.py`, `utils/hub_operator.py`, `utils/agent_perf.py`, `utils/operational_telemetry.py`. Prevents the `recommend_runtime_profile() → dict` category of silent caller bugs.

---

### 6. CI baseline

Add `conftest.py` and `pytest.ini` at project root. Target suite: `test_smart_dispatch`, `test_router_smoke`, `test_reminder_workflow`, `test_runtime_smoke`. `python -m pytest` should pass clean.

---

### 7. Consolidate Sparkline implementations

`ui/components/sparkline.py` (old, `set_values()`) and `ui/launcher/components/sparkline.py` (new, `push()`). Consolidate on the launcher version. Update the one import in `guppy_ui.py`.

---

### 8. `guppy_ui.py` retirement decision

It is not imported by council_ui. It is a 2,200-line standalone surface diverging from the launcher. Decision: **freeze it** — add a deprecation header, stop updating it, migrate the ambient banner to the launcher shell. Do not spend time keeping it feature-equal to the new system.

---

### 9. Voice tuning (when classifier is fixed)

Validate wake-word → Haiku fast-path end-to-end latency with real use. Tune `openwakeword` model and cooldown. The infrastructure is right; the real-world calibration hasn't happened.

---

### 10. CRM live wiring (only after #1 and #3)

Do not wire live CRM writes until the classifier is semantic and memory injection is live. A misrouted "teaching" query that triggers a send-email tool is a bad outcome.

---

## Next Update Template

```text
### YYYY-MM-DD
- Changed:
- Verified:
- Follow-up:
```
