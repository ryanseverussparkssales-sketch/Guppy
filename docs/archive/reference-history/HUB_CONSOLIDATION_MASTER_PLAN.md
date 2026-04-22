# 5-Hub Architecture: Master Implementation Plan

**Date Approved:** April 19, 2026  
**Authority:** [PROJECT_BRIEF.md](PROJECT_BRIEF.md) — 5-hub architecture is canonical product model  
**Status:** Three implementation plans complete, ready for code execution

---

## Executive Summary

The Guppy application has adopted a 5-hub surface model to achieve the architectural mandate:
> "One place of truth in each category: one place for settings, API keys, account creds, and user tools. One clean, excellent home chat window that can use all those places without cluttering the chat surface."

This document compiles three specialist agent plans that detail the phased implementation of hub consolidations. All three consolidations are **low-risk, dark-launch capable migrations** with no persistence schema changes.

### Consolidation Sequence
1. **Settings Hub** — Consolidates `my_pc_view`, `advanced_view`, `connector_panel`, `advanced_terminal_panel` (Medium risk, foundational)
2. **Models Hub** — Consolidates `local_llm_view`, `voices_view`, `models_runtime_library` (Low risk, self-contained)
3. **Home Chat** — Removes operator UI fragments from `assistant_view` (Low risk, mostly removal work)

### Parallelization
- Settings Hub and Models Hub can proceed in parallel (no shared state)
- Home Chat cleanup can proceed in parallel (only depends on new hubs being ready to absorb operator features)
- Library Hub and Tools Hub are deferred (planning phase pending)

---

## Plan 1: Settings Hub Consolidation

**Owner:** settings_view.py consolidates `my_pc_view.py`, `advanced_view.py`, `connector_panel.py`, `advanced_terminal_panel.py`

**Current State:** Partial settings surface exists; operator surfaces scattered across multiple views

### 7-Phase Migration

| Phase | Action | Duration | Risk Level |
|-------|--------|----------|------------|
| 0 | Baseline freeze: document current ownership matrix | 1 day | Low |
| 1 | IA definition: define sections & ownership boundaries | 2 days | Low |
| 2 | Controller/presenter seams: extract controller layers | 3 days | Medium |
| 3 | Unified hub shell (dark launch): activate feature flag | 2 days | Medium |
| 4 | Navigation cutover: switch router to new hub | 1 day | Medium |
| 5 | Decommission surfaces: disable old views | 1 day | Low |
| 6 | Cleanup & telemetry: remove dead code, verify metrics | 2 days | Low |

**Total Timeline:** ~12 days

### Risk Register (7 Items)

1. **Tab index drift:** Unified consolidation may break keyboard navigation if tab order not preserved
   - Mitigation: Test tab order parity snapshot at phase 2 completion
   
2. **Duplicate side effects:** Connector validation or persona save logic replicated in two places
   - Mitigation: Shared payload schema tests at phase 2 completion
   
3. **Connector validation drift:** Live connector selection in multiple sections may diverge
   - Mitigation: Single connector validator used by all sections; integration tests at phase 4
   
4. **Persona/runtime save rollback:** Settings save transaction fails mid-phase, leaving partial state
   - Mitigation: Explicit transaction semantics verified at phase 3; recovery guide in runbook
   
5. **Hidden polling coupling:** Settings surface polls for diagnostics; new hub may break polling logic
   - Mitigation: Identify all polling coupling at phase 1; integration tests at phase 4
   
6. **Quick action semantic mismatch:** Operator quick actions defined by launcher may not map cleanly to settings
   - Mitigation: Explicit mapping matrix created at phase 1
   
7. **Accessibility regression:** Consolidation may break screen reader labels or landmark regions
   - Mitigation: Accessibility audit at phase 3; WCAG checklist at phase 5

### Guardrail Checklist

- [ ] Single action → single execution assertion (no duplicate writes)
- [ ] Shared payload schema tests (Settings save contract validated across all sources)
- [ ] Settings save transaction behavior verified (rollback tested)
- [ ] Navigation entry point tests (all 5 old views route correctly to new hub)
- [ ] UI-state parity snapshots (tab order, field focus, visible elements match baseline)
- [ ] Integration checks with launcher orchestration (no launcher signal breakage)
- [ ] Manual operator checklist (connector state, persona changes, recovery actions exercised)

### Done Definition

✅ Functional consolidation: All settings accessible from one hub  
✅ Single-path ownership: settings_view.py owns all settings logic (no duplication)  
✅ Navigation consistency: All old entry points route to settings hub  
✅ Parity gates met: Tab order, focus behavior, validation, persistence all match baseline  
✅ Operational readiness: Operator can recover from failure, connector state visible  

---

## Plan 2: Models Hub Consolidation

**Owner:** models_view.py consolidates `local_llm_view.py`, `voices_view.py`, `models_runtime_library.py`

**Current State:** Models hub exists with runtime routing; 1622 lines (will expand to 1640 with consolidation)

### 6-Phase Migration

| Phase | Action | Duration | Risk Level |
|-------|--------|----------|------------|
| 0 | Contract freeze: verify provider registry, runtime settings, voice bindings stable | 1 day | Low |
| 1 | Hub shell (dark launch): new consolidated view with feature flag disabled | 2 days | Low |
| 2 | Local LLM migration: move local LLM health/runtime logic into hub | 2 days | Low |
| 3 | Voice migration: move voice selection/binding into hub | 2 days | Low |
| 4 | Navigation consolidation: route all model-related entry points to hub | 1 day | Medium |
| 5 | Deprecation & cleanup: disable old views, remove dead code | 1 day | Low |

**Total Timeline:** ~9 days

### Integrity Gates (6 Items)

1. **Provider registry validation:** All voice providers, LLM providers in `utils/personalization_config.py#L671` must be loaded cleanly
2. **Runtime settings preservation:** Voice bindings from `utils/personalization_config.py#L723` must survive consolidation
3. **Runtime-role mapping:** Route preview and role selection from `src/guppy/experience_config/services.py#L151` must work correctly
4. **Route preview behavior:** Local fallback preview must not break when migration occurs
5. **Voice binding resolution:** Voice device selection from active runtime must match old UI behavior
6. **Launcher signal wiring:** Navigation signals from launcher_window orchestration must trigger hub correctly

### Test Plan

| Test Category | Approach | Coverage |
|---------------|----------|----------|
| Existing smoke tests | Reuse/update for consolidated hub | Voice selection, LLM health, route preview |
| Route unit tests | Preserve full coverage of route logic | No degradation of route validation |
| Voice validation | Preserve voice device enumeration & binding tests | Device list enumeration, binding persistence |
| Hub-focused tests | Add new tests for consolidated scenarios | Multi-provider switching, voice + route interaction |
| Regression matrix | 4 scenarios: local LLM on/off, voice on/off, route dynamic, all combinations | Confirm no behavior regression |

### Done Definition

✅ One visible hub: Models hub is only entry point for model/voice/LLM configuration  
✅ Removed separate nav entries: local_llm_view, voices_view decommissioned  
✅ No schema changes: provider registry, runtime settings, voice bindings unchanged  
✅ All validation gates pass: Provider loading, route mapping, voice binding all green  
✅ Existing tests pass with updates: Smoke, unit, and new integration tests all green  
✅ No behavior regression: Voice selection, route preview, LLM health work exactly as before  
✅ Docs aligned: docs/API.md, docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md updated with hub references  

---

## Plan 3: Home Chat Cleanup

**Owner:** assistant_view.py removes operator UI fragments; keeps only conversation + lightweight context

**Current State:** Contains conversation logic PLUS model controls, route status, diagnostics, workspace details; 1507 lines (cap at 1520)

### 4-Phase Migration

| Phase | Action | Duration | Risk Level |
|-------|--------|----------|------------|
| 0 | Baseline & inventory: map all operator UI fragments in assistant_view + launcher_window quick actions | 1 day | Low |
| 1 | Decouple operator entry points: separate launcher controls from conversation context | 2 days | Low |
| 2 | Remove operator UI blocks: delete model controls, route status, diagnostics blocks | 1 day | Low |
| 3 | Consolidate hub ownership & navigation language: finalize Home Chat → Settings/Models routing | 1 day | Low |
| Stabilization | Debt cleanup: remove legacy context chips, update telemetry | 1 day | Low |

**Total Timeline:** ~6 days

### UX Acceptance Criteria

1. **Home Chat first-run clarity:** Only conversation, composer, minimal context chips, voice controls visible
2. **Model/route switching inaccessible from chat:** All model/route controls removed; user must visit Models Hub
3. **No status bar clutter:** Route status, diagnostics, workspace details removed from home view
4. **Quick actions demoted:** Operator quick-start actions now live in Settings/launcher, not in chat surface
5. **Voice input preserved:** Voice button remains visible and functional
6. **Context continuity:** Conversation history, persona, and runtime context all preserved
7. **Error handling:** If model unavailable, show graceful fallback (no inline recovery options)
8. **Navigation clarity:** Links to Settings/Models/Tools/Library obvious and adjacent

### Risk Register (7 Items)

1. **Index drift:** Removing UI blocks may break index references in launcher_window orchestration
   - Mitigation: Explicit index mapping created at phase 0; integration tests at phase 2
   
2. **Signal-wiring regression:** Navigation signals to old blocks may fail to route to new hubs
   - Mitigation: Trace all signal wiring at phase 0; functional tests at phase 2
   
3. **Hidden-but-required workflow:** Operator may depend on inline route/model switching for daily work
   - Mitigation: Operator interview at phase 0; fallback quick-links provided at phase 3
   
4. **Status visibility regression:** Operator loses real-time visibility of model state, route status
   - Mitigation: Status chips provided as lightweight context; status dashboard in Settings Hub
   
5. **Legacy destination compatibility:** Old URLs/deep links may reference removed inline controls
   - Mitigation: Redirect URLs to Settings/Models at phase 3
   
6. **Copy inconsistency:** Messages, tooltips, button labels may reference old inline controls
   - Mitigation: Copy audit at phase 1; update all references at phase 2
   
7. **Test coverage gap:** Existing tests may only cover inline operator paths, not new hub-based paths
   - Mitigation: Test plan below; regression matrix executed before phase 3 sign-off

### Regression Test Checklist

- [ ] Home Chat behavior: conversation history, context retention, composer state all work
- [ ] Navigation/hub routing: All Home → Settings/Models/Tools/Library routes functional
- [ ] State/context continuity: Persona, runtime, voice binding survive navigation
- [ ] Status/diagnostics: Lightweight status chips display correctly; full diagnostics accessible via Settings
- [ ] Compatibility/guardrails: No broken links; telemetry events still fire correctly
- [ ] Voice I/O: Voice input recognition, output synthesis both work from Home Chat
- [ ] Error handling: Graceful fallbacks work if model unavailable or voice device disconnected

### Done Definition

✅ Conversation-focused surface: Only chat history, composer, voice controls, minimal context chips visible  
✅ No inline operator controls: Model selection, route switching, diagnostics all moved to dedicated hubs  
✅ Navigation clarity: Links to Settings/Models/Tools/Library obvious and adjacent  
✅ UX acceptance criteria met: All 8 criteria verified in QA checklist  
✅ Regression tests pass: All 7 regression test categories green  
✅ No broken workflows: Operator can still access all previous functions via hubs  
✅ Telemetry intact: Event tracking, diagnostics logging all functional  

---

## Implementation Sequence Recommendation

### Why This Order?

**Settings Hub first** — Foundational operator surface consolidation; lower risk (consolidation of existing, stable views); unblocks Home Chat by providing destination for quick actions

**Models Hub second** — Self-contained consolidation with well-understood provider registry and voice binding contracts; low risk; parallelizable with Settings

**Home Chat cleanup third** — Highest user-visible impact; depends on Models/Settings hubs being ready to absorb operator features; simplest work (mostly removal)

### Timeline

- **Week 1:** Settings Hub + Models Hub (parallel, ~12 + 9 = 21 days if sequential, ~12 days if parallel)
- **Week 2:** Home Chat cleanup (6 days)
- **Week 3:** Navigation rail refactoring, integration testing, operator checklist

**Critical Path:** Settings Hub → Home Chat Cleanup → Navigation Refactoring (14 days)  
**Parallel Path:** Models Hub (9 days, no blocking dependencies)

---

## Guardrail Enforcement

All consolidations follow the existing guardrail stack:

1. **Module line cap:** Each consolidated hub will respect 700-line cap (with documented waiver if needed)
2. **Release debt guard:** No TODO/FIXME/HACK in added release-facing lines
3. **Architecture boundaries:** UI/utils import isolation maintained
4. **Test coverage:** Existing tests updated; new integration tests added per each plan

**Gate Verification:**
```bash
# Before each consolidation lands:
python tools/dev_workflow.py dev-check delta
python tools/dev_workflow.py test-default
python tools/dev_workflow.py release-check
```

---

## Success Criteria

### Global (All Hubs Complete)
- ✅ Five-hub surface navigation fully functional
- ✅ User never clutters Home Chat with operator controls
- ✅ Single canonical place for each category: Settings (config), Models (model/voice), Tools (integrations), Library (media/docs), Home (conversation)
- ✅ All guardrails passing
- ✅ All regression tests green
- ✅ Operator checklist sign-off

### Per-Hub (Each Consolidation Complete)
- ✅ Phased plan executed in order (baseline → implementation → cutover → cleanup)
- ✅ All risk items mitigated or monitored
- ✅ All guardrails in integrity gate list passing
- ✅ Old views disabled or removed
- ✅ Navigation routes correctly
- ✅ No behavior regression

---

## Next Steps

1. **User Approval:** Review this plan; request changes if needed
2. **Dependency Check:** Verify no blocking issues; run `dev-check delta` to confirm clean state
3. **Phase 0 Execution:** Begin Settings Hub Phase 0 (baseline freeze, ownership matrix documentation)
4. **Parallel Kickoff:** Spawn Models Hub Phase 0 concurrently
5. **Integration Planning:** After Phase 3 of each hub, schedule integration test execution

---

## Related Documents

- **Architectural Truth:** [PROJECT_BRIEF.md](PROJECT_BRIEF.md#5-hub-architecture)
- **Discoverability:** [ROADMAP.md](ROADMAP.md)
- **Execution Board:** [PROJECT_BRIEF.md](PROJECT_BRIEF.md#execution-board)
- **Guardrail Stack:** [tools/dev_workflow.py](../../tools/dev_workflow.py)
- **Waiver Rationale:** [tools/check_new_module_line_cap.py](../../tools/check_new_module_line_cap.py#L40-L70)

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| April 19, 2026 | AIAgentExpert (consolidated) | Initial master plan compiled from three specialist agent deliverables |

