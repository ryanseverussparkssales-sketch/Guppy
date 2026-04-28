# Guppy Repository Review — Executive Summary
**Date:** 2026-04-27  
**Prepared for:** Cowork session  
**Status:** ✅ Review complete; roadmap updated; memory refreshed

---

## Current State at a Glance

| Dimension | Status | Evidence |
|-----------|--------|----------|
| **Execution** | 🟢 P6 Active, 1 day ahead | TR55+ shipping MiniCPM, dispatch, cloud routing |
| **Release Validation** | ✅ PASS | All 8 gates green (2026-04-22) |
| **Architecture** | ✅ Five-hub intact | Chat/Models/Tools/Library/Settings verified |
| **North-Star Alignment** | ✅ STRONG | Chat-first, calm, persistent all verified |
| **Git State** | 🟡 Uncommitted | 2,355 changes; ready for 4-wave commit strategy |
| **Critical Blocker** | 🔴 Web UI Parity | MUST validate before June 12 deadline |

---

## What's Landed Since 2026-04-22

✅ **MiniCPM-o 4.5 Omni** — Model fully wired, port 8084, dual-mode pairing  
✅ **Dispatch auto-start** — 5s boot delay daemon thread  
✅ **VRAM bar** — BackendsTab stacked segments + free-GB readout  
✅ **Cloud routing** — Mistral (free) + Cohere (free) + Google Gemini  
✅ **llamacpp offline fallback** — Port liveness check before local fallback  
✅ **Web UI nav** — Restructured (Chat / Launch / Personas / Instructions / Tools)  
✅ **SPA routing fix** — Starlette 1.0.0 wildcard conflict resolved  
✅ **Web inference controls** — Stop, Steer mode, TTS toggles  
✅ **Tools API** — Full CRUD endpoint (`GET /api/tools`, `POST /enable|disable`)  
✅ **Infrastructure** — Pydantic settings, loguru, Alembic migrations  
✅ **Fishbowl widget** — PySide6 always-on-top companion  

---

## P6 Acceptance Criteria (June 12 Gate)

### ✅ Green Lights (On Track)
- Release-check validation
- North-star alignment (Chat-first, calm)
- Guarded PC-control (architecture intact)
- Freeze-readiness tranches (C1, C2, C3, C5, C9 done; hotspots shrinking)

### 🟡 Yellow Lights (In Progress)
- Stable chat (auto-routing live; needs broader validation)
- Stable model switching (desktop hub done; web parity pending)
- Accurate statistics (tools endpoint done; library/workspace counts TBD)
- Button stubs (18 stubs identified; 3 critical for T1)
- Voice pipeline (T3 at ~10%; not started)

### 🔴 Red Lights (Blockers)
- **Web UI Parity** — MUST validate shared API contracts before June 12
  - Models API: Web UI uses same endpoint as desktop?
  - Tools API: Web UI toggles sync with desktop state?
  - Workspace state: Web UI topbar reflects desktop changes?
  - Test plan ready: `P0_PARITY_TESTING_PLAN_2026-04-23.md` (4 sections)

---

## Immediate Action Items (Next 2 Weeks)

### Priority 1: Unblock June 12
1. **Web UI Parity Test** — Execute parity validation matrix (plan ready)
2. **Wire 3 Button Stubs** — Command Palette Initialize/Start/Halt + New Instance
3. **Run Pilot Gates** — `python tools/dev_workflow.py release-check`

### Priority 2: P6 Progress
4. **Voice Pipeline** — STT + TTS core (allocate 3 days for T3 sprint)
5. **FR-C4, C6, C7** — Hotspot reduction tranches (target 2–3 of 3)
6. **Commit Wave** — 4-tranche commit strategy (docs → desktop → web UI → API)

### Priority 3: Risk Mitigation
7. **Database consolidation** — Routes creating silos; defer if time-tight
8. **Tech debt audit** — Button stubs, dead code (`useSettings`), untested Fishbowl

---

## Roadmap & Documentation

### In Repo
- **ROADMAP_UPDATE_2026-04-27.md** — Full roadmap (timeline, tranches, criteria)
- **CLAUDE.md** — Architecture reference (updated to current state)
- **P0_PARITY_TESTING_PLAN_2026-04-23.md** — Parity test matrix (ready to execute)

### In Memory
- **guppy_roadmap_2026-04-27.md** — Current execution snapshot
- **guppy_overview.md** — Models, surfaces, architecture (archived)
- **MEMORY.md** — Index updated with pointers

---

## Git Commit Strategy

**Wave 1 (Docs & Infrastructure)**
- CLAUDE.md, quarantine docs, test files
- Message: "docs: architecture reference + quarantine protocol"

**Wave 2 (Desktop Features)**
- MiniCPM, dispatch daemon, VRAM bar, cloud routing
- Message: "feat(desktop): MiniCPM-o + dispatch + cloud routing"

**Wave 3 (Web UI)**
- Nav restructure, SPA routing, inference controls
- Message: "feat(web): nav restructure, SPA routing fix, controls"

**Wave 4 (API)**
- Tools endpoint, settings routes, bugfixes
- Message: "feat(api): tools + settings validation + bugfixes"

**Test gate:** `release-check` before each commit

---

## Why This Matters

**Web UI parity is critical** because PROJECT_BRIEF §6 requires "Dual web UI + desktop without surface conflict." If the web UI doesn't use the same model inventory, tool state, or workspace state as the desktop launcher, the P6 acceptance criteria fails on June 12. The test plan is ready; execution is what's missing.

**Voice pipeline is lower priority** because it starts May 15, but it's blocking calm-start UX. If time allows, 3 days for core STT+TTS before then.

**Button stubs are quick wins** for T1 closure. Small scope (18 identified, 3 critical); should finish in 1–2 days.

---

## Key Contacts & Resources

- **PROJECT_BRIEF.md** — Single source of truth (dated 2026-04-21)
- **docs/archive/2026-04/** — All recent session docs
- **CLAUDE.md** — Architecture, build, known issues
- **Memory system** — Persistent context across sessions

---

## Success Definition

By June 12, 2026:
1. Web UI parity test suite passes (no inventory drift)
2. Release-check passes (all 8 gates green)
3. Button stubs wired (18 → 0 stubs)
4. Voice pipeline core shipped (T3 functional)
5. FR-C tranches progressing (C4, C6, C7 landed)
6. Pilot gates pass (smoke tests green)

---

**Review completed:** 2026-04-27  
**Next session:** Execute parity validation matrix + wire button stubs + run pilot gates
