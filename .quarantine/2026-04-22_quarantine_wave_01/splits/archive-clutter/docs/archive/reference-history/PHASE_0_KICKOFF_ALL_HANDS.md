# Phase 0 Kickoff: All Hands 5-Hub Consolidations

**Authorization:** ✅ Full go-ahead, all developers on deck  
**Start Date:** April 19, 2026 (TODAY)  
**Phase 0 Duration:** 1 day (just documentation + planning, no code shipping yet)  
**Phase 1 Start:** April 20, 2026

---

## The Mission (TL;DR)

Transform Guppy from a cluttered, operator-heavy surface into a **clean 5-hub architecture**:

| Hub | Purpose | Owner | Status |
|-----|---------|-------|--------|
| 🏠 **Home** | Pure conversation | Home Chat Team | Ready to clean |
| ⚙️ **Settings** | Config, creds, connectors | Settings Hub Team | Ready to consolidate |
| 🧠 **Models** | LLM selection, voice, local agents | Models Hub Team | Ready to consolidate |
| 🔧 **Tools** | Integrations, custom tools | Tools Team | Deferred (week 2) |
| 📚 **Library** | Media player, docs | Library Team | Deferred (week 2) |

**Your job:** Build Phase 0 (documentation + planning), launch Phase 1-5 (implementation) in parallel.

**Why today matters:** Phase 0 is the foundation. Get it right, everything else flows.

---

## Your Assignment (Pick One Team)

### 🎯 Team 1: Settings Hub Consolidation

**What you're consolidating:**
- `ui/launcher/views/my_pc_view.py` — My PC info and configuration
- `ui/launcher/views/advanced_view.py` — Advanced system settings
- `ui/launcher/views/connector_panel.py` — Connector management
- `ui/launcher/views/advanced_terminal_panel.py` — Terminal for diagnostics

→ Into one unified hub: `ui/launcher/views/settings_view.py` (expand it)

**Phase 0 Today (1 day):**
1. Read [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#plan-1-settings-hub-consolidation)
2. Create a table showing current ownership:
   - What UI sections exist?
   - What does each control/display?
   - Where does data come from?
   - Where does it persist?
3. Document the 6 sections you'll create in unified hub:
   - Configuration
   - Diagnostics
   - Recovery
   - Connectors
   - System
   - Terminal

**Deliverable:** `docs/SETTINGS_HUB_PHASE_0_OWNERSHIP_MATRIX.md`

**Guardrail checkpoints:** See [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#guardrail-checklist)

---

### 🧠 Team 2: Models Hub Consolidation

**What you're consolidating:**
- `ui/launcher/views/local_llm_view.py` — Local LLM health, model selection
- `ui/launcher/views/voices_view.py` — Voice device selection, voice profiles
- `models_runtime_library.py` (runtime provider routing)

→ Into one unified hub: `ui/launcher/views/models_view.py` (expand it)

**Phase 0 Today (1 day):**
1. Read [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#plan-2-models-hub-consolidation)
2. Verify three "integrity gates" are stable (these can't change during consolidation):
   - Provider registry in `utils/personalization_config.py#L671` — List all voice/LLM providers
   - Voice bindings in `utils/personalization_config.py#L723` — Document how voices are stored
   - Runtime routing in `src/guppy/experience_config/services.py#L151` — How models are selected
3. Document the 4 sections you'll create in unified hub:
   - Library (all available models)
   - Runtime/Routing (active model selection)
   - Local LLM Health (local agent status)
   - Voices (voice device + profile selection)

**Deliverable:** `docs/MODELS_HUB_PHASE_0_CONTRACT_VERIFICATION.md`

**Guardrail checkpoints:** See [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#integrity-gates-6-items)

---

### 💬 Team 3: Home Chat Cleanup

**What you're removing:**
- Model selection controls (inline in chat)
- Route status display (inline in chat)
- Diagnostics/workspace details (cluttering chat)
- Quick action shortcuts to operator features

→ Leave only: conversation, minimal context chips, voice input

**Phase 0 Today (1 day):**
1. Read [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#plan-3-home-chat-cleanup)
2. Create an inventory of all operator UI currently in chat:
   - `ui/launcher/views/assistant_view.py` — Lines with model controls, route status, diagnostics
   - `ui/launcher/launcher_window.py` — Quick action shortcuts that route to operator features
3. For each fragment, document:
   - What is it? (What does operator see?)
   - Where will it move to? (Settings? Models?)
   - Are there any hidden dependencies? (Does chat logic depend on this?)

**Deliverable:** `docs/HOME_CHAT_PHASE_0_OPERATOR_UI_INVENTORY.md`

**Guardrail checkpoints:** See [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md#regression-test-checklist)

---

## TODAY'S CHECKLIST (For All Teams)

### Step 1: Understand the Architecture (30 min)
- [ ] Read [docs/PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) — Understand 5-hub model
- [ ] Read [docs/HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md) — Full plan with 7/6/4 phases
- [ ] Read [docs/FEATURE_FLAG_STRATEGY.md](FEATURE_FLAG_STRATEGY.md) — Dark-launch approach

### Step 2: Pick Your Team (5 min)
- [ ] Settings Team signals (put your name in the doc)
- [ ] Models Team signals (put your name in the doc)
- [ ] Home Chat Team signals (put your name in the doc)

### Step 3: Execute Phase 0 (1 hour per team)

**Settings Hub Team:**
- [ ] Document current ownership matrix (my_pc, advanced, connector_panel, advanced_terminal)
- [ ] List fields/sections for unified hub
- [ ] Create `docs/SETTINGS_HUB_PHASE_0_OWNERSHIP_MATRIX.md`

**Models Hub Team:**
- [ ] Verify provider registry, voice bindings, runtime routing are stable
- [ ] Document contracts that can't change
- [ ] Create `docs/MODELS_HUB_PHASE_0_CONTRACT_VERIFICATION.md`

**Home Chat Team:**
- [ ] Inventory operator UI fragments in assistant_view + launcher_window
- [ ] Document where each fragment will move
- [ ] Create `docs/HOME_CHAT_PHASE_0_OPERATOR_UI_INVENTORY.md`

### Step 4: Verify Feature Flags (30 min - ALL TEAMS TOGETHER)
- [ ] One person implements Step 1-3 from [FEATURE_FLAG_STRATEGY.md](FEATURE_FLAG_STRATEGY.md#concrete-implementation-for-phase-0)
- [ ] Add FeatureFlags to `utils/personalization_config.py`
- [ ] Update `ui/launcher/launcher_window.py` to route on flags
- [ ] Create test fixtures for toggling flags
- [ ] Verify: `python tools/dev_workflow.py dev-check delta` passes

### Step 5: Git & PR (30 min - ALL TEAMS)
- [ ] Each team creates branch: `git checkout -b feat/settings-hub-phase-0` (or models, home-chat)
- [ ] Commit your Phase 0 deliverable
- [ ] Commit feature flag implementation (one shared commit across all teams)
- [ ] Open PR with description: "Phase 0: [Team] planning and feature flag setup"

### Step 6: Daily Standup (4 PM)
- [ ] All three teams report: What did Phase 0 reveal?
- [ ] Any blockers or surprises?
- [ ] Approve Phase 1 kickoff for each team

---

## Phase 0 Success Criteria

✅ **Settings Hub Team:**
- Ownership matrix shows all 4 source views mapped to unified hub sections
- No hidden dependencies found
- Feature flag routing coded for settings_hub_enabled

✅ **Models Hub Team:**
- Contract verification complete (provider registry, voice bindings, runtime routing all stable)
- 4 hub sections defined (Library, Runtime/Routing, Local LLM Health, Voices)
- Feature flag routing coded for models_hub_enabled

✅ **Home Chat Team:**
- Complete inventory of operator UI (model controls, route status, diagnostics, quick actions)
- Location mapped for each fragment (Settings? Models? Deprecated?)
- Feature flag routing coded for home_chat_cleanup_enabled

✅ **Feature Flags:**
- FeatureFlags added to PersonalizationConfig
- launcher_window routes on flag state
- All flags default to False (old surfaces live)
- Test fixtures created for headless flag toggling
- `dev-check delta` passes

✅ **Git:**
- Three PRs open, one per team (Phase 0 deliverables)
- One shared commit for feature flag infrastructure
- All linked to [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md)

---

## Phase 1 Preview (Starting Tomorrow)

Tomorrow morning at 9 AM, each team starts their first real phase:

**Settings Hub Team:**
- Phase 1: IA definition (define sections, ownership boundaries)
- Build consensus on unified hub structure before coding

**Models Hub Team:**
- Phase 1: Hub shell (dark launch) — Create new consolidated view with feature flag disabled
- Smoke test: Feature flag off → old surfaces, on → new hub

**Home Chat Team:**
- Phase 1: Decouple operator entry points — Separate launcher controls from conversation logic
- Preserve all conversations while you're working

---

## Communication

### Daily Standup (4 PM)
All teams report status, blockers, asks

### Weekly Sync (Monday 10 AM)
Cross-team dependencies, risk review, timeline adjustment

### Emergency Channel
If you hit a blocker today: ping @Ryan in Slack (don't wait for standup)

---

## Resources

| Document | Purpose | Read Time |
|-----------|---------|-----------|
| [PROJECT_BRIEF.md](../../PROJECT_BRIEF.md) | 5-hub architecture definition | 15 min |
| [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md) | All three consolidation plans with phases/risks | 45 min |
| [FEATURE_FLAG_STRATEGY.md](FEATURE_FLAG_STRATEGY.md) | How to implement dark-launch flags | 30 min |
| Your Phase 0 Deliverable | Team-specific documentation | Create today |

---

## Questions Before You Start?

1. **Why Phase 0?** To document current state before changing anything. Prevents surprises in Phase 1.
2. **Why today?** Kick off all teams in parallel. Finish Phase 0 by end of day, start Phase 1 tomorrow.
3. **Why feature flags?** Enable instant rollback if something breaks (flip flag off, no code revert needed).
4. **What if I find a blocker?** Document it in your Phase 0 deliverable, we'll resolve tomorrow morning.
5. **Can Settings + Models run in parallel?** Yes, they have zero dependencies. Home Chat depends on both being ready to absorb operator features.

---

## You Got This 🚀

This is a straightforward consolidation with proven patterns (Netflix, Uber, large platforms all do this).

**Phase 0 is just documentation — no risky code changes yet.**

Phase 1 onward is where the real work happens, but you'll have a solid foundation to build on.

**Let's go build the cleanest, most operator-friendly Guppy ever.**

---

**Next action:** Form your team, grab a Phase 0 deliverable template from your team's section above, and document what you have TODAY.

Standup at 4 PM. Report findings, unblock, approve Phase 1.

