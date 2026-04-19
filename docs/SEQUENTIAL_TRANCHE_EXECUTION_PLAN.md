# Sequential Execution Plan: Bottom-Up, One Tranche at a Time

**Date:** April 19, 2026  
**Approach:** Siloed execution, no feature flags, complete one consolidation → ship → next  
**Execution Model:** Each tranche is a complete, shippable card for agent + sub-agents

---

## Core Principle

**Ship → Validate → Move On**

Each tranche contains the maximum amount of safe, documented, testable work that can be completed and shipped as a single unit. No feature flags, no partial rollouts. Old code is replaced by new code, validated, shipped.

---

## Tranche Structure

Each tranche contains:
1. **Code changes** — Complete, compilable, shippable
2. **Tests** — All new tests passing, all existing tests passing
3. **Documentation** — Inline code docs + user-facing docs updated
4. **Validation** — Guardrails passing, manual operator checklist complete
5. **Rollback plan** — If needed (git revert one commit)

**Duration:** Each tranche: 1-3 days (agent + sub-agents working in parallel on subtasks)

---

## Tranche Sequence

### **TRANCHE 1: Settings Hub — Phase 0 Foundation**
**Duration:** 1 day  
**Owner:** Agent (Settings Hub consolidator)  
**Sub-agents:** Code gen specialists (4-5 working in parallel)

**What ships:**
- [ ] Current ownership matrix documented (my_pc, advanced, connector_panel, advanced_terminal → settings sections)
- [ ] SettingsHubConsolidated stub created (loads all 4 old surfaces into one view, no logic changes yet)
- [ ] Feature-free routing: launcher_window selects SettingsHubConsolidated (no flags, just direct load)
- [ ] All old tests pass (nothing broken, just new view created)
- [ ] docs/SETTINGS_HUB_PHASE_1_COMPLETE.md explains what's shipped

**Acceptance:**
- ✅ New hub loads without errors
- ✅ All 6 sections visible (Configuration, Diagnostics, Recovery, Connectors, System, Terminal)
- ✅ Old view logic still works (copied into new view, not refactored yet)
- ✅ Guardrails passing (dev-check delta, release-check, line cap)

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 2: Settings Hub — Phase 1 Logic Extraction**
**Duration:** 2 days  
**Owner:** Agent (Settings Hub refactorer)  
**Sub-agents:** Controller extraction specialists (3-4 working in parallel)

**What ships:**
- [ ] All logic from my_pc_view extracted into SettingsHubConsolidated (ownership consolidation)
- [ ] All logic from advanced_view extracted
- [ ] All logic from connector_panel extracted
- [ ] All logic from advanced_terminal_panel extracted
- [ ] Old files deprecated (comments added: "Deprecated, replaced by SettingsHubConsolidated")
- [ ] All existing tests pass with new routing
- [ ] docs/SETTINGS_HUB_PHASE_2_COMPLETE.md explains refactoring

**Acceptance:**
- ✅ All settings functionality works from unified hub
- ✅ No logic duplication
- ✅ All tests pass
- ✅ Operators see no change (UX identical)
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 3: Settings Hub — Phase 2 Cleanup**
**Duration:** 1 day  
**Owner:** Agent (Settings Hub finisher)  
**Sub-agents:** Deprecation + telemetry specialists (2-3)

**What ships:**
- [ ] Old views deleted (my_pc_view, advanced_view, connector_panel, advanced_terminal_panel removed from codebase)
- [ ] Old imports cleaned up (launcher_window no longer imports 4 old views)
- [ ] Telemetry updated (new hub events, old hub events removed)
- [ ] docs/SETTINGS_HUB_COMPLETE.md final summary
- [ ] All guardrails passing

**Acceptance:**
- ✅ Settings Hub fully consolidated
- ✅ Old code completely removed
- ✅ No orphaned references
- ✅ All tests pass
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 4: Models Hub — Phase 0 Foundation**
**Duration:** 1 day  
**Owner:** Agent (Models Hub consolidator)  
**Sub-agents:** Code gen specialists (4-5)

**What ships:**
- [ ] Provider registry contract verified (utils/personalization_config#L671 — voice & LLM providers, no changes made)
- [ ] Voice binding contract verified (utils/personalization_config#L723 — voice storage, no changes made)
- [ ] Runtime routing contract verified (src/guppy/experience_config/services#L151 — model selection logic, no changes made)
- [ ] ModelsHubConsolidated stub created (loads all 3 old surfaces: local_llm, voices, models_runtime)
- [ ] Feature-free routing: launcher_window selects ModelsHubConsolidated
- [ ] All old tests pass
- [ ] docs/MODELS_HUB_PHASE_1_COMPLETE.md explains what's shipped

**Acceptance:**
- ✅ New hub loads without errors
- ✅ All 4 sections visible (Library, Runtime, Local LLM, Voices)
- ✅ All provider registry tests pass
- ✅ Voice binding tests pass
- ✅ Runtime routing tests pass
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 5: Models Hub — Phase 1 Logic Extraction**
**Duration:** 2 days  
**Owner:** Agent (Models Hub refactorer)  
**Sub-agents:** Controller + provider specialists (3-4)

**What ships:**
- [ ] Local LLM logic extracted from local_llm_view into ModelsHubConsolidated
- [ ] Voice selection logic extracted from voices_view
- [ ] Runtime routing logic extracted from models_runtime_library
- [ ] Old files deprecated
- [ ] Provider registry validation reused (no schema changes)
- [ ] Voice binding validation reused (no schema changes)
- [ ] Runtime routing tests all pass
- [ ] docs/MODELS_HUB_PHASE_2_COMPLETE.md explains refactoring

**Acceptance:**
- ✅ All model/voice/routing functionality works from unified hub
- ✅ Provider registry contracts unchanged
- ✅ Voice bindings unchanged
- ✅ Runtime routing logic unchanged
- ✅ All tests pass
- ✅ Operators see no change (UX identical)
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 6: Models Hub — Phase 2 Cleanup**
**Duration:** 1 day  
**Owner:** Agent (Models Hub finisher)  
**Sub-agents:** Deprecation specialists (2-3)

**What ships:**
- [ ] Old views deleted (local_llm_view, voices_view removed)
- [ ] models_runtime_library cleaned up (deprecated or integrated)
- [ ] Old imports cleaned up
- [ ] Telemetry updated
- [ ] docs/MODELS_HUB_COMPLETE.md final summary
- [ ] All guardrails passing

**Acceptance:**
- ✅ Models Hub fully consolidated
- ✅ Old code completely removed
- ✅ No orphaned references
- ✅ All tests pass
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 7: Home Chat — Phase 0 Inventory**
**Duration:** 1 day  
**Owner:** Agent (Home Chat analyzer)  
**Sub-agents:** Inventory specialists (2-3)

**What ships:**
- [ ] Complete inventory of operator UI in assistant_view.py (model controls, route status, diagnostics, workspace details)
- [ ] Complete inventory of operator UI in launcher_window.py (quick actions)
- [ ] Documentation of what each fragment does
- [ ] Documentation of where each fragment will move (Settings? Models? Removed?)
- [ ] Risk assessment: what breaks if we remove this?
- [ ] docs/HOME_CHAT_PHASE_1_INVENTORY.md

**Acceptance:**
- ✅ Complete inventory
- ✅ All dependencies mapped
- ✅ No surprises about what needs to move where
- ✅ Ready for Phase 1 extraction

**Rollback:** Documentation change, zero code risk

---

### **TRANCHE 8: Home Chat — Phase 1 Extraction**
**Duration:** 2 days  
**Owner:** Agent (Home Chat refactorer)  
**Sub-agents:** UI extraction specialists (3-4)

**What ships:**
- [ ] Model selection controls removed from assistant_view, users now go to Models Hub
- [ ] Route status display removed from assistant_view, users now go to Models Hub
- [ ] Diagnostics panel removed from assistant_view, users now go to Settings Hub
- [ ] Workspace details removed from assistant_view
- [ ] HomeChatClean view created (conversation only, voice controls, minimal context)
- [ ] launcher_window routes to HomeChatClean (no more inline operator UI)
- [ ] All home chat tests pass (conversations work, voice works)
- [ ] All settings hub tests pass (diagnostics work there)
- [ ] All models hub tests pass (route/model switching works there)
- [ ] docs/HOME_CHAT_PHASE_2_COMPLETE.md explains extraction

**Acceptance:**
- ✅ Home Chat is conversation-only surface
- ✅ All operator UI moved to appropriate hubs (Settings/Models)
- ✅ No functionality lost (it just moved)
- ✅ Operators know where to find everything
- ✅ All tests pass
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 9: Navigation Rail Refactor**
**Duration:** 1-2 days  
**Owner:** Agent (Navigation architect)  
**Sub-agents:** UI routing specialists (2-3)

**What ships:**
- [ ] Sidebar/topbar refactored to 5-hub model (HOME, MODELS, TOOLS, LIBRARY, SETTINGS)
- [ ] Old navigation entries (my_pc, advanced, local_llm, voices, etc.) removed
- [ ] All navigation routes correctly
- [ ] All navigation tests pass
- [ ] docs/NAVIGATION_COMPLETE.md explains new structure

**Acceptance:**
- ✅ Navigation rail shows 5 hubs clearly
- ✅ All routing works
- ✅ All tests pass
- ✅ Operators immediately understand structure
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 10: Final Integration & Operator Checklist**
**Duration:** 1 day  
**Owner:** Agent (Integration validator)  
**Sub-agents:** QA + documentation specialists (2-3)

**What ships:**
- [ ] Full integration testing (all hubs communicate correctly)
- [ ] Operator workflow checklist (connector changes work, model switching works, voice works, diagnostics accessible, etc.)
- [ ] Performance baseline (no regressions)
- [ ] Telemetry validation (all events fire correctly)
- [ ] docs/5_HUB_INTEGRATION_COMPLETE.md final summary
- [ ] docs/OPERATOR_CHECKLIST_SIGN_OFF.md signed off

**Acceptance:**
- ✅ All integration tests pass
- ✅ Operator checklist complete
- ✅ No performance regressions
- ✅ Telemetry events all fire
- ✅ All guardrails passing
- ✅ Ready for operator hand-off

---

## Summary: 10 Tranches, ~10-12 Days

| Tranche | Consolidation | Phase | Duration | Deliverable | Rollback |
|---------|---------------|-------|----------|------------|----------|
| 1 | Settings | 0 | 1 day | Consolidated stub | git revert |
| 2 | Settings | 1 | 2 days | Logic extracted | git revert |
| 3 | Settings | 2 | 1 day | Cleanup complete | git revert |
| 4 | Models | 0 | 1 day | Consolidated stub | git revert |
| 5 | Models | 1 | 2 days | Logic extracted | git revert |
| 6 | Models | 2 | 1 day | Cleanup complete | git revert |
| 7 | Home Chat | 0 | 1 day | Inventory complete | docs only |
| 8 | Home Chat | 1 | 2 days | Extraction complete | git revert |
| 9 | Navigation | - | 1-2 days | Refactor complete | git revert |
| 10 | Integration | - | 1 day | All systems go | git revert |

**Critical Path:** Tranches 1-2-3 (Settings) → 4-5-6 (Models) → 7-8 (Home Chat) → 9-10 (Nav + Integration)  
**Total:** ~12 days sequential, **but each tranche is parallelizable within itself** (agent + 3-5 sub-agents per tranche)

---

## Tranche Execution Model

### Each Tranche Flow

**Day 1 (Morning):** Agent & sub-agents gather, plan the tranche
- [ ] What exactly ships in this tranche?
- [ ] What are the sub-tasks?
- [ ] Which sub-agent owns which piece?
- [ ] What tests must pass?

**Day 1-2 (Work):** Sub-agents execute in parallel
- Sub-agent 1: Handles component A
- Sub-agent 2: Handles component B
- Sub-agent 3: Handles testing
- Sub-agent 4: Handles documentation
- Main agent: Orchestrates, validates, integrates

**Day 2-3 (Validation):** All together
- [ ] All code merged into one tranche commit
- [ ] All tests pass
- [ ] All guardrails pass
- [ ] PR opens, review happens
- [ ] Merge to main branch

**What ships:** One commit per tranche, one PR per tranche, clean history

---

## Why This Approach Works

1. **No feature flags** — Simpler code, faster execution, less orchestration
2. **Clear boundaries** — Each tranche is obvious, shippable unit
3. **Parallelizable** — Sub-agents work in parallel within tranche
4. **Sequential safety** — One tranche complete, validated, shipped before next starts
5. **Easy rollback** — One commit per tranche, `git revert [tranche]` if needed
6. **Clear ownership** — One agent per tranche, fully responsible
7. **Documentation built-in** — Each tranche has completion docs

---

## Key Differences from Feature Flag Approach

| Aspect | Feature Flags | Tranche Approach |
|--------|---------------|------------------|
| **Execution** | Parallel (Settings + Models + Home Chat) | Sequential (Settings → Models → Home Chat) |
| **Complexity** | High (4-5 feature flags, conditional routing) | Low (direct routing, no flags) |
| **Rollback** | Flip flag (5 seconds) | git revert (1 commit) |
| **Testing** | Must test both flag on/off | Test one state (shipped state) |
| **Code retention** | Old code stays (until later cleanup) | Old code deleted in same tranche |
| **Operator experience** | Gradual (opt-in to new hubs) | Immediate (shipped = active) |
| **Agent workload** | Complex coordination | Clear, siloed units |

---

## Success Criteria Per Tranche

**Every tranche must exit with:**
- ✅ Code complete, compilable, shippable
- ✅ All new tests passing
- ✅ All existing tests passing
- ✅ Guardrails passing (dev-check delta, release-check, line cap)
- ✅ Documentation complete (inline + user-facing)
- ✅ One clean commit
- ✅ One approved PR
- ✅ Merged to master branch

---

## Communication Plan

| When | What |
|------|------|
| **Tranche start (morning)** | Agent + sub-agents plan (30 min) |
| **During (daily)** | Slack async updates on progress |
| **Tranche end (EOD)** | Code ready for review |
| **Next day (morning)** | PR review, merge decision |
| **Merge day (afternoon)** | Validation on main branch |
| **Next tranche (morning)** | Next agent kicks off |

---

## Tranche 1 Ready to Start TODAY

**Tomorrow morning (April 20):**

1. **Agent assigned** to Settings Hub Tranche 1
2. **Sub-agents assigned** (3-4 specialists)
3. **Deliverable:** SettingsHubConsolidated stub + ownership matrix doc
4. **Acceptance:** All old tests pass, new hub loads, no logic changes yet
5. **Rollback:** One git revert

**By EOD April 20:** PR ready, all tests passing, ready to merge

**April 21 morning:** Tranche 2 begins (Agent + sub-agents extract Settings logic)

---

## Documentation Built Into Each Tranche

Each tranche produces:

| Document | Purpose |
|----------|---------|
| `docs/[CONSOLIDATION]_PHASE_[N]_COMPLETE.md` | What shipped, how to use it, breaking changes (none expected) |
| Inline code docs | // explanations in new code |
| Commit message | Clear, detailed, linked to [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md) |
| PR description | Links to plan, explains tranche scope, lists tests passing |

---

## Next Action

1. **Assign Agent to Tranche 1** (Settings Hub consolidation stub + ownership matrix)
2. **Assign 3-4 sub-agents** to parallel work:
   - Sub-agent 1: Create SettingsHubConsolidated view (stub)
   - Sub-agent 2: Document ownership matrix
   - Sub-agent 3: Update launcher_window routing (no flags, just load new view)
   - Sub-agent 4: Run all tests, verify pass
3. **Tranche 1 target:** EOD April 20 (ready to merge)
4. **Daily standup:** 4 PM (quick updates on tranche progress)

---

## Why This Is Better

✅ Simpler code (no feature flag orchestration)  
✅ Faster decisions (ship it, done, move on)  
✅ Cleaner history (one commit per tranche)  
✅ Easier rollback (git revert, done)  
✅ Clear ownership (one agent per tranche)  
✅ Safe execution (each tranche validated before next starts)  
✅ Agent-friendly (clear, bounded tasks)  

**You're building the cleanest Guppy ever. Let's do it.** 🚀

