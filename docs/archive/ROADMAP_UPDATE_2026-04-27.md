# Guppy Roadmap Update — 2026-04-27

**Status:** P6 Active Execution | June 12 Freeze-Readiness Deadline | Release-Check Green ✅

---

## Executive Summary

Guppy is executing P6 Platform Hardening on schedule, one day ahead of PROJECT_BRIEF (dated 2026-04-21). Release-check passed. Five-hub architecture is stable. **Critical next step: Web UI parity validation before June 12.**

| Metric | Status | Notes |
|--------|--------|-------|
| Release Validation | ✅ PASS | All 8 gates green (last run 2026-04-22) |
| P6 Progress | 🟢 ~75% | Web UI integrated, cloud routing live, voice pipeline pending |
| Architecture Integrity | ✅ INTACT | Five-hub launcher, north-star alignment verified |
| Freeze-Readiness (FR-C) | 🟡 ~60% | C1, C2, C3, C5, C9 done; C4, C6, C7, C8, C10 pending |
| Git State | 🟡 UNCOMMITTED | 2,355 changes; branch needs intent clarity before commit |
| Web UI Parity | 🔴 BLOCKER | Must validate dual web/desktop before June 12 |

---

## Part 1: Current Execution State (as of 2026-04-27)

### What Landed Since 2026-04-22 Evaluation

**Desktop Launcher Enhancements:**
- ✅ MiniCPM-o 4.5 Omni model fully wired (port 8084, Mode A pairing with Pepe)
- ✅ Dispatch auto-start daemon added (5 s delay at Guppy boot)
- ✅ VRAM bar component in BackendsTab (stacked segments, free-GB readout)
- ✅ Cloud routing enhanced: Mistral (`ministral-8b-latest`), Cohere (`command-r7b-12-2024`), Google (`gemini-*` suite)
- ✅ llamacpp offline fallback (port liveness check before forcing local mode)
- ✅ Free-tier model auto-routing (Mistral → Cohere → Claude fallback)

**Web UI & API:**
- ✅ Web nav restructured (Chat / Launch Control / Personas / Instructions / Tools + Settings)
- ✅ SPA routing fixed (catch-all from wildcard to exception handler, fixes Starlette 1.0.0 conflict)
- ✅ Web UI inference controls: Stop button (AbortController), Steer mode toggle, TTS toggle
- ✅ llamacpp agentic tool-call loop rewritten (OpenAI SSE accumulation, max_tool_rounds=6)
- ✅ Bug fixes: provider switch crash, type exports, semantic RAG inversion, del-antipattern (86 instances → 13 files)

**New Tools API:**
- ✅ Full tools management (`routes_tools.py`): GET /tools, POST /tools/:id/enable|disable
- ✅ SQLite-backed, seeded with 8 tools
- ✅ Web UI toggle end-to-end (optimistic spinner + Sonner toast)

**Infrastructure:**
- ✅ Pydantic settings validation (`config.py`) — all env vars typed
- ✅ Structured logging (loguru + rich) — coloured [launch] output
- ✅ Alembic + SQLAlchemy migrations (`migrations/` schema management)
- ✅ React markdown + syntax highlighting (shiki)
- ✅ Sonner toast notifications wired to settings/tools
- ✅ React hotkeys (Ctrl+K, Escape without manual listeners)

**New Surface:**
- ✅ Fishbowl companion widget (PySide6 always-on-top, animated fish, Ctrl+Space hotkey)

### Current Tranche Status (from 2026-04-24 Progress Report)

| Tranche | Target | Status | Impact |
|---------|--------|--------|--------|
| **T1 – Stability & Hardening** | May 1–14 | 🟢 ~85% | Core infra done ahead of schedule |
| **T2 – Web UI Polish** | May 8–21 | 🟡 ~60% | Chat, settings, tools wired; 18 button stubs remain |
| **T3 – Voice I/O** | May 15–28 | 🔴 ~10% | useVoice hook exists; no STT/TTS pipeline ⚠️ |
| **T4 – Tools API** | May 22–Jun 4 | 🟢 ~70% | REST endpoints done; AI function-calling pending |
| **T5 – Credentials** | May 20–Jun 6 | 🟡 ~40% | Store/delete/list working; no encryption at rest |
| **T6 – Admin Panel** | Jun 3–16 | 🟡 ~30% | View exists; no live data feed |
| **T7 – Desktop Launcher** | Jun 10–23 | 🟡 ~20% | Fishbowl added, Qt stable; no auto-update |

### Known Tech Debt

| Item | File | Severity | Notes |
|------|------|----------|-------|
| Dead code `useSettings` | `useApi.ts` | 🟡 Minor | Duplicate hook name; should rename or delete |
| Fishbowl untested | `fishbowl_app.py` | 🟡 Medium | Animation, chat, hotkey not E2E tested |
| DB consolidation | Multiple route files | 🟡 Medium | Alembic manages `guppy_main.db` but routes create silos |
| Button stubs | Web UI | 🔴 Medium | 18 stubs: Command Palette (3), LibraryView actions (3+), TopBar (3+) |
| Voice pipeline | T3 | 🔴 High | Not started; blocking calm-start flow |

---

## Part 2: P6 Platform Hardening — Acceptance Criteria Status

### 1. Stable Local/Cloud Chat
**Goal:** Route changes, provider availability changes, auth refresh must not break daily chat  
**Status:** 🟡 In progress

- ✅ Free-tier auto-routing implemented (Mistral → Cohere → Claude)
- ✅ llamacpp offline fallback (port liveness check)
- 🟡 Need: Broader validation of route stability under real usage
- 📋 Action: Run daily chat stress test across local/cloud transitions

### 2. Stable Model Switching
**Goal:** MAIN/SUB A/SUB B lanes sync across launcher/web/API  
**Status:** 🟡 In progress

- ✅ Models hub (desktop) consolidation complete
- ✅ Web UI model picker integrated
- 🔴 **BLOCKER:** Web UI parity not yet validated (must use shared inventory)
- 📋 Action: Validate Web UI `GET /api/models` against launcher state

### 3. Accurate Statistics
**Goal:** User-visible counts/labels from runtime truth, not placeholders  
**Status:** 🟡 In progress

- ✅ Tools endpoint (`/api/tools`) backed by SQLite
- ✅ Models endpoint reflects active catalog
- 🟡 Need: Library item counts, workspace statistics validation
- 📋 Action: Audit Web UI stats against API endpoints

### 4. Guarded PC-Control
**Goal:** Local PC control is real but not a competing product center  
**Status:** ✅ Architecture intact

- ✅ Tools/Settings remain implementation hubs, not primary nav
- ✅ Home Chat is calm daily surface
- ✅ No diagnostic noise in primary path

### 5. North-Star Completion
**Goal:** Chat/Workspaces/Library/Settings primary; Models/Tools subordinate  
**Status:** ✅ Strong alignment

- ✅ Five-hub launcher verified
- ✅ Web nav maps: Chat → Home, Personas → Library, Tools → Tools Hub, Settings
- ✅ No new product centers introduced

### 6. Dual Web/Desktop Parity
**Goal:** Both surfaces use shared contracts, no inventory drift  
**Status:** 🔴 **CRITICAL BLOCKER**

- ✅ Web UI integrated and functional
- 🔴 **NOT VALIDATED:** Web UI must use same API endpoints as desktop for models, tools, connectors, workspace state
- 📋 Action: **MUST COMPLETE BEFORE JUNE 12**

---

## Part 3: Freeze-Readiness Tranches (FR-C1–C10)

### Completed
- ✅ **FR-C1** — API snapshot decomposition (launcher_snapshot.py split into modular exports)
- ✅ **FR-C2** — Launcher shell reduction (~500 lines removed from main window)
- ✅ **FR-C3** — Models hub split (local_llm_view.py, voices_view.py decoupled)
- ✅ **FR-C5** — Settings panels split (device, accounts, operations, terminal decomposed)
- ✅ **FR-C9** — Runtime/request lane reduction (launcher_application service layer stabilized)

### In Progress / Pending
- 🟡 **FR-C4** — Home chat coordinator (continuity_summary surface integration)
- 🟡 **FR-C6** — Library/voice decomposition (voice engine isolation from lib player)
- 🟡 **FR-C7** — Connector manager extraction (connector lifecycle decoupled from settings)
- 🟡 **FR-C8** — Personalization config service (experience_config isolated)
- 🟡 **FR-C10** — Freeze audit (final validation of hotspot limits, waiver justifications)

### Hotspot State (Shrinking on Track)

| Module | Initial | Current | Status |
|--------|---------|---------|--------|
| `server_runtime_snapshot.py` | 2232 | 1990 | ✅ Shrinking |
| `launcher_window.py` | 3354 | 3069 | ✅ Shrinking |
| `models_view.py` | 1542 | 1298 | ✅ Shrinking |
| Other 9 modules | ~22k | ~19k | ✅ Collective reduction |

---

## Part 4: Git State & Uncommitted Changes

### Current Branch Status
- **Branch:** master
- **Uncommitted:** 2,355 files (2,346 modified, 4 new, 1 deleted)
- **State:** Not release-ready; intent pending

### What's Staged for Commit

**Documentation & Config:**
- ✅ Updated CLAUDE.md (architecture reference)
- ✅ Quarantine wave README (cleanup intent clarified)
- ✅ Various planning docs (PROGRESS_2026_04_24.md, strategic assessments)

**Code Changes:**
- ✅ Web UI: nav restructure, SPA routing fix, inference controls
- ✅ Desktop: MiniCPM wiring, dispatch daemon, VRAM bar, cloud routing
- ✅ API: tools endpoint, settings routes, history routes
- ✅ Infrastructure: pydantic settings, loguru, alembic, hotkeys

**Test Files:**
- ✅ New unit tests (models hub ownership)
- ✅ Vitest E2E scaffold (Playwright config)

### Recommended Commit Strategy

1. **Commit 1 (Infrastructure):** Updated CLAUDE.md, quarantine docs, test files
   - Messages: "docs: architecture reference + quarantine protocol"
   - Benefit: Freezes documentation state, unblocks clarity

2. **Commit 2 (Desktop enhancements):** MiniCPM, dispatch, VRAM, cloud routing
   - Message: "feat(desktop): MiniCPM-o + dispatch auto-start + cloud routing"
   - Benefit: Major feature delivery for P6

3. **Commit 3 (Web UI fixes):** Nav restructure, SPA routing, inference controls
   - Message: "feat(web): nav restructure, SPA routing fix, inference controls"
   - Benefit: Web UI parity groundwork

4. **Commit 4 (API & tools):** Routes, tools endpoint, settings consolidation
   - Message: "feat(api): tools endpoint + settings validation + bugfixes"
   - Benefit: Enables parity validation testing

**Testing Gate:** Run `release-check` before each commit to ensure no regressions.

---

## Part 5: Immediate Priorities (Next 2 Weeks)

### 🔴 Must-Do (Blocking June 12 Deadline)

1. **Web UI Parity Validation** — Test matrix to confirm dual-surface uses shared API
   - Desktop models hub ↔ Web model picker (same `/api/models` endpoint)
   - Desktop tools hub ↔ Web tools toggle (same `/api/tools` endpoint)
   - Desktop workspace state ↔ Web workspace topbar (same `/api/workspaces` endpoint)
   - Expected outcome: Parity test suite passes, no inventory drift detected
   - Owner: `P0_PARITY_TESTING_PLAN_2026-04-23.md` (4-section plan ready)

2. **Wire Button Stubs (T1 closure)** — Unblock command palette + library actions
   - Command Palette: Initialize Node, Start Node, Halt All Nodes → `POST /api/instances`
   - New Instance: InstancesView "+ New Instance" → instance creation flow
   - LibraryView: copy, edit, delete on hover
   - Expected outcome: All primary buttons fire (no console.log stubs)

3. **Run Pilot Gates** — Validate release-readiness
   - Command: `python tools/dev_workflow.py release-check`
   - Expected: All 8 gates green

### 🟡 High Priority (This Week)

4. **Voice Pipeline Sprint** — Unblock T3
   - Evaluate STT options (Whisper, Web Speech API)
   - Implement TTS skeleton (ElevenLabs or system TTS)
   - Wire interruption handling
   - Target: Functional voice input/output by week-end

5. **Freeze-Readiness Tranches C4, C6, C7** — Reduce hotspots
   - FR-C4: Home chat coordinator integration
   - FR-C6: Library/voice engine separation
   - FR-C7: Connector manager extraction
   - Target: Complete 2 of 3 tranches

6. **Credentials Encryption** — T5 progress
   - Add encryption-at-rest for stored API keys
   - Test end-to-end credential lifecycle (add, update, delete)

### 🟢 Nice-to-Have (Lower Priority)

7. Admin Panel live data (T6 progress)
8. Playwright E2E test for chat happy path
9. Desktop launcher auto-update capability
10. Consolidate database silos (single guppy_main.db)

---

## Part 6: Key Dependencies & Risks

### External Dependencies
- **Ollama:** Must be running on `http://127.0.0.1:11434` for local inference
- **MiniCPM-o runtime:** Requires `--mmproj` flag; model files from openbmb/MiniCPM-o-4_5-gguf
- **Voice engines:** edge_tts, kokoro, pyttsx3, ElevenLabs (all optional; verify runtime at startup)
- **Cloud providers:** Anthropic API, OpenAI, Mistral, Cohere, Google (credentials in Settings)

### Known Risks
| Risk | Impact | Mitigation |
|------|--------|-----------|
| Web UI parity not validated before June 12 | 🔴 P6 blocker | Start parity test immediately (plan ready) |
| Voice pipeline not started | 🟡 Affects calm-start UX | Allocate 3 days to T3 core (STT + TTS) |
| Button stubs not wired | 🟡 Incomplete T1 | Small scope; should finish this week |
| Database consolidation pending | 🟡 Tech debt | Non-blocking for June 12; defer to Q3 |

---

## Part 7: Roadmap Timeline (June 12 Deadline)

```
2026-04-27 (Today)     Start
    ↓ 4 days
2026-05-01             Commit wave 1–2; Web UI parity validation begins
    ↓ 7 days
2026-05-08             T2 Web UI Polish checkpoint; voice pipeline core done
    ↓ 7 days
2026-05-15             FR-C4, C6, C7 landed; button stubs complete
    ↓ 7 days
2026-05-22             T4/T5/T6 progress checkpoints; pilot gates re-run
    ↓ 14 days
2026-06-05             Final validation: chat stability, model switching, stats, parity
    ↓ 7 days
2026-06-12             Freeze-readiness deadline ⏰
```

---

## Part 8: Success Criteria (June 12 Gate)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Release-check passes | ✅ Ready | Last run: 2026-04-22 (all 8 gates green) |
| Web UI parity validated | 🔴 BLOCKER | Parity test suite passing, no inventory drift |
| Stable chat (local/cloud) | 🟡 WIP | Broader validation needed; auto-routing live |
| Stable model switching | 🟡 WIP | Desktop hub ready; web parity pending |
| Accurate statistics | 🟡 WIP | Tools API live; library/workspace counts TBD |
| Guarded PC-control | ✅ Ready | Architecture verified |
| North-star alignment | ✅ Ready | Five-hub, chat-first, calm verified |
| All button stubs wired | 🟡 WIP | 18 stubs identified; 3 critical for T1 |
| Hotspot tranches C4–C10 | 🟡 WIP | C1–C3, C5, C9 done; shrinking on track |
| Pilot gates pass | 🟡 WIP | Ready to run; scheduled for May 1+ |

---

## Conclusion

Guppy is executing P6 on schedule, one day ahead of timeline. **Web UI parity validation is the critical blocker for the June 12 freeze-readiness deadline.** All infrastructure is in place; next 2 weeks focus on validation, voice pipeline, and final hotspot reduction.

**Next action:** Start Web UI parity test matrix immediately (plan in `P0_PARITY_TESTING_PLAN_2026-04-23.md`).

---

**Document created:** 2026-04-27  
**Last updated:** 2026-04-27  
**Prepared by:** Claude (Cowork session)  
**Against:** PROJECT_BRIEF (2026-04-21), PROGRESS_2026_04_24.md, CLAUDE.md (in-repo)
