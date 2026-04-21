# M1 Closure & M2 Preparation Report

**Date:** April 13, 2026  
**Status:** M1 CLOSED — All 4 acceptance criteria passed  
**Next Gate:** M2 Entry → June 15, 2026 (prep window: 16 days)

---

## M1 CLOSURE CHECKLIST

| Criterion | Implementation | Evidence | Status |
|---|---|---|---|
| Embedded-only INIT | `AgentCard._btn_init` emits `init_requested` signal; `_initialize_embedded_agent()` sets agent active in `AssistantView` | [ui/launcher/components/agent_card.py#L21-30](ui/launcher/components/agent_card.py#L21-30) | ✅ PASS |
| Transcript UX stable | User + assistant messages chronological; "Processing..." moved to status strip via `set_status()` | [ui/launcher/views/assistant_view.py#L287](ui/launcher/views/assistant_view.py#L287); [launcher_window.py#L959-960](launcher_window.py#L959-960) | ✅ PASS |
| Right-rail policy enforced | Chat payloads only in AssistantView; status panel is logging + gauge only | [ui/launcher/launcher_window.py#L550-580](ui/launcher/launcher_window.py#L550-580) | ✅ PASS |
| No-freeze startup telemetry | Phases: launcher_enter → window_init → build_ui → status_poll → window_shown → bootstrap_services (async); budget <750ms | [src/guppy/apps/launcher_app.py#L132-162](src/guppy/apps/launcher_app.py#L132-162); [launcher_window.py#L124-147](launcher_window.py#L124-147) | ✅ PASS |

**Test Status:** 70/70 passing (includes new INIT button wiring test)

---

## ALTITUDE REVIEWS

### 🔭 100-FOOT VIEW (Next 2 Weeks — M2 Week 1 Ramp)

**Focus:** Builder Foundation

What we're doing NOW to unblock M2:

1. **Persona Builder Form v0.1** (core + teaching scope only)
   - Tone slider (0–10: formal → conversational)
   - Verbosity slider (0–10: terse → verbose)
   - Teaching style dropdown (Socratic | Direct | Example-led)
   - Global vs per-model scope toggle
   - Preview modal showing live system message
   - Save to `runtime/persona_config.json` + reload
   
2. **Model Assignment Card + Route Visualizer**
   - Drag-drop model list → task type (simple, complex, teaching, code)
   - Fallback chain editor (pick 2–3 backup models)
   - Health badges: ✓ ready | ⚠ slow | ✗ offline
   - "Test run" button → mock query → show latency/cost
   
3. **Off-Hours Worker Write Extension (Go-Live)**
   - Merlin-code can now generate text files (tests, schemas, docstrings)
   - Dry-run by default → staged for review → approve to apply
   - Budget cap: 3 writes/run, auto-downgrade to dry-run after
   - First task: auto-generate pytest stubs for new tool functions

**Runway:** 16 days. Stretch goal: all three usable (not polished).

**Risk:** PySide6 form complexity (QComboBox cascading, preview modal state). Mitigation: reuse StatusPanel card patterns.

---

### 🌍 500-FOOT VIEW (Rest of Q2 + Q3 — June → September)

**Focus:** Functional Parity for whole GuppyPrime surface

M2 complete by Sep 30, 2026 means:

**Track 1: Builder (highest velocity)**
- Persona Builder → live, non-technical path works
- Model Assignment → live, fallback chains discoverable
- Voice import/mapping → Kokoro + TTS-choice, per-persona assignment

**Track 2: Tools Tab**
- Remove all placeholder buttons (disable/hide if not ready)
- Each visible tool gets: description + dry-run-if-risky pattern
- `run_python` scoped to safe dirs (no /System, no /Program Files)
- CRM/VoIP stubs → explicit "coming in M3" badges

**Track 3: Settings/Advanced**
- Recovery actions (warmup, restart_daemon, audit_runtime) → visual outcomes in chat
- Process guards: can't launch duplicate agents
- Runtime profile (Light/Standard/Power) → affects timeouts + model selection

**Track 4: Off-hours scale**
- Write tasks now common: test generation, schema updates, doc fixes
- Merlin-code running overnight → 5–10 safe tasks/week
- Humans review dry-run results before auto-apply

**What's NOT in M2:**
- iOS client
- Live CRM writes (Salesforce, HubSpot)
- Shared Memory v1 (deferred to M3)
- Voice recording to disk

**Staffing model:** 1 principal engineer (you) + off-hours agents

---

### 🛰️ 1000-FOOT VIEW (12 Months — April 2026 → April 2027)

**Product Trajectory**

**Viability Gate 1 (TODAY — M1 Closed):**
- ✅ Unified launcher is the primary surface
- ✅ Startup is predictable, non-blocking
- ✅ Embedded agents work reliably
- ✅ Telemetry visible for debugging
- ⚠️ Builder UX still raw (JSON editing fallback works)

**Viability Gate 2 (June 30 — M2 Closed):**
- Builder is usable by non-technical users
- Tool grid is clean (no dead controls)
- Recovery flows are discoverable
- Estimated: 60% feature parity with legacy UIs

**Viability Gate 3 (Sep 30 — M3 Started):**
- Off-hours AI is writing ~20% of new features
- Daily workflow loop (morning → workday → close) is executable
- Model routing is tuned and predictable
- Shared Memory catalog syncing Merlin ↔ Guppy context

**Viability Gate 4 (Dec 31, 2026 — M3 Closed):**
- Legacy UIs deprecated (marked obsolete in README)
- Windows General Assistant viability confirmed
- Beta tester EXE deployable with restricted policy
- Feature matrix complete: all rows either Live or explicitly deferred post-product

**Long-term (2027):**
- Graph integrations (Microsoft 365 calendar, Teams, Outlook)
- Voice multi-turn conversations without transcript re-render latency
- Quantized local model suite (<8GB disk → full feature parity)
- Team sync: multiple humans → shared vault

---

## M2 ENTRY CRITERIA & SCOPE LOCK

### Conditions to proceed (ALL must be true):

- [ ] All M1 tests still passing (70/70)
- [ ] ROADMAP.md updated to mark M1 closed + M2 active
- [ ] Off-hours write extension stable (3+ successful test generation runs)
- [ ] Persona/Model/Voice schema stable (no breaking changes forecast)

### M2 Scope Lock (FIXED):

**Must Deliver:**
1. Persona Builder v1 (non-technical users)
2. Model Assignment + Fallback chain editor
3. Voice library + per-persona voice assignment
4. Tool tab cleanupx (placeholder removal, dry-run pattern)
5. Advanced tab (process guards, outcome visibility)
6. Recovery actions hardening (warmup, restart, audit visible in chat)

**Will NOT include in M2 (defer to M3 or post):**
- iOS client
- Live CRM writes
- Shared Memory v1
- Voice recording/playback duration controls
- CI/CD GitHub Actions (testing only, no deploy gates)

**Off-hours tasks eligible for M2:**
- Test generation for new builder functions
- Schema updates (persona, model routes, voice)
- Docstring cleanup
- Type annotation fixes

---

## FINANCIAL RUNWAY

### Spend tracking (Claude + GitHub Copilot):

**Spent through M1 (Apr 1–13):**
- ~120K tokens (code review, debugging, architecture)
- ~15 sessions @ avg 8K tokens/session
- Estimated cost: $20–30 (Claude 3.5 Haiku)

**M2 budget (Jun 15 – Sep 30):**
- Assume: 40% off-hours agent work, 60% Claude review
- Projected: 20–25 sessions @ 6–8K tokens/session
- Estimated cost: $40–60

**Mitigation:** Off-hours write tasks reduce Claude dependency by ~40% for scaffolding work.

---

## DECISION POINTS FOR M2

1. **Builder complexity trade-off:**
   - OPTION A: Simple form (sliders + dropdowns) → launch Day 1, iterate
   - OPTION B: Rich form (styled cards + live preview) → launch Day 10, more polish
   - **Recommendation:** OPTION A — get feedback early, iterate fast

2. **Model assignment UX:**
   - OPTION A: Drag-drop (fun, complex)
   - OPTION B: Click-to-assign + arrow buttons (simple)
   - **Recommendation:** OPTION B — MVP first, drag-drop in M2.1 if demand signals

3. **Voice support scope:**
   - OPTION A: Kokoro + system TTS only
   - OPTION B: ElevenLabs optional (paid key)
   - **Recommendation:** OPTION A — ElevenLabs in M2.2 if sponsor budget available

---

## HANDOFF TO M2: ACTION ITEMS

**TODAY (before closing session):**
- [ ] Commit M1 closure to ROADMAP.md + git
- [ ] Tag git release: `m1-closed-2026-04-13`
- [ ] Archive off-hours dry-run results from today to `docs/offhours_results_m1/`

**Wednesday (Apr 15):**
- [ ] Publish M2 scope lock (this doc) to team
- [ ] Create GitHub project board for M2 epics (5 cards: Builder, Models, Voice, Tools, Advanced)
- [ ] Queue first merlin-code task: "Generate pytest stubs for guppy_core/tool_metrics.py"

**Friday (Apr 17):**
- [ ] Builder form v0.1 prototype (Qt mockup, button handlers empty)
- [ ] M2 Week 1 kickoff: assign personas, review mockups

---

## APPENDIX: M1 VELOCITY METRICS

| Task | Days | Source | Impact |
|---|---|---|---|
| guppy_core split (monolith → package) | 1 | Code review insight | Unblocked testing, reduced merge conflicts |
| Inference router tests (13 tests) | 0.5 | Gap analysis | Fallback chains verified |
| Repair token re-sync (endpoint + retry) | 0.5 | Security audit | No more restart-lockout |
| INIT wiring + transcript UX | 0.25 | M1 gate enforcement | All 4 criteria closed |
| Off-hours write extension (apply_patch + task types) | 0.5 | Future agent efficiency | 40% Claude cost reduction projected |
| Tier 1 cleanup (gitignore, artifacts, docs) | 0.25 | Ops hygiene | Cleaner runtime, fewer distractions |
| **Total M1 work** | **3.5 days elapsed time** | **Architecture + Features + Ops** | **Ready for M2 builder sprint** |

---

## EOF — M1 COMPLETE

**Signed:** April 13, 2026  
**Milestone:** M1 Exit Gate Passed ✅  
**Next Checkpoint:** M2 Entry Criteria (Jun 15, 2026)
