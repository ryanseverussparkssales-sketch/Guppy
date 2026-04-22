# AUTHORIZATION MEMO: 5-Hub Consolidations - APPROVED

**Date:** April 19, 2026  
**From:** Engineering  
**To:** All Developers  
**Subject:** Full Authorization: Start Phase 0 TODAY - All Hands on Deck

---

## ✅ YOU ARE APPROVED

You have explicit authorization from leadership to:

1. ✅ **Pursue all three hub consolidations in parallel**
   - Settings Hub → Consolidate 4 scattered surfaces
   - Models Hub → Consolidate LLM + Voice + Local routing
   - Home Chat → Strip operator UI, keep conversation only

2. ✅ **Use any development resources needed**
   - No time constraints
   - No risk constraints
   - Quality and thoroughness > speed

3. ✅ **Implement dark-launch pattern with feature flags**
   - Old and new surfaces run in parallel
   - Zero-downtime rollout (proven by Netflix, Uber, large platforms)
   - Instant rollback if anything breaks (no code revert needed)

---

## Deep Dive: Feature Flags (Why This Matters)

### The Problem Without Feature Flags

You consolidate Settings Hub. Ship to operators. One operator's connectors fail. You have three choices:

1. **Quick rollback commit** — Undo the entire Settings Hub work, delete new code, restore old code
   - Takes 2-4 hours
   - Operators lose access while you fix
   - Risky (what if the rollback fails?)

2. **Hotfix the new hub** — Debug the issue in production, ship a patch
   - Risky (unknown territory, untested)
   - Operators still broken during debug window
   - Might break something else

3. **Operator workaround** — Tell operators to manually edit config files or use old launcher
   - Not acceptable
   - Fragments user experience

### The Solution: Feature Flags

```
Feature Flag: settings_hub_enabled = False (default)
  ↓
OLD CODE RUNS: my_pc_view, advanced_view, connector_panel, advanced_terminal
NEW CODE WAITING: SettingsHubConsolidated (compiled but not used)

Feature Flag: settings_hub_enabled = True
  ↓
NEW CODE RUNS: SettingsHubConsolidated
OLD CODE STILL ALIVE: my_pc_view, advanced_view, etc. (still compiled, ready to fallback)

Operator reports: "Connectors failing in new Settings Hub"
  ↓
SET FLAG BACK TO FALSE
  ↓
OPERATORS INSTANTLY BACK ON OLD SURFACES
  ↓
NO ROLLBACK COMMIT NEEDED
  ↓
Old code never left the binary, just switched off by flag
```

**Time to recover:** 5 seconds (restart app with flag disabled)  
**Risk of rollback:** Zero (old code never deleted)  
**Operator downtime:** None (just restart app)

### How Feature Flags Work in Guppy

**Storage:** `~/.config/guppy/personalization.json`

```json
{
  "current_model": "guppy-main",
  "voice_enabled": true,
  "features": {
    "settings_hub_enabled": false,
    "models_hub_enabled": false,
    "home_chat_cleanup_enabled": false
  }
}
```

**Routing in Code:**

```python
# ui/launcher/launcher_window.py

if self.config.features.settings_hub_enabled:
    self.settings_view = SettingsHubConsolidated()  # NEW (dark launch)
else:
    self.settings_view = SettingsHubLegacy()        # OLD (default)
```

**How to Enable (Testing):**

1. Edit `~/.config/guppy/personalization.json`
2. Set `settings_hub_enabled: true`
3. Restart Guppy
4. New Settings Hub loads

**How to Disable (Emergency Rollback):**

1. Edit `~/.config/guppy/personalization.json`
2. Set `settings_hub_enabled: false`
3. Restart Guppy
4. Old surfaces load
5. No code changes needed

### Why This Is Not a "Hack"

This is the **standard pattern** for UI rewrites at scale:

- **Netflix:** Uses feature flags for all surface rewrites (proven over 500+ features)
- **Uber:** Rides & Eats both use flags for zero-downtime rollout
- **Google:** Gmail switches between new/old UI with flags
- **Facebook:** Dark-launches 80% of features to 5% of users first, then gradual rollout

This is **professional-grade risk mitigation**, not a workaround.

---

## The Three Consolidations (What You're Building)

### Consolidation 1: Settings Hub
**Unifies:** my_pc_view + advanced_view + connector_panel + advanced_terminal_panel → settings_view.py

**Why:**
- Operators waste time bouncing between 4 settings surfaces
- Connector validation logic lives in 2 places (bug risk)
- Dark-launch enables testing without touching old surfaces

**Feature Flag:** `settings_hub_enabled`

**Timeline:** 12 days (but no rush, all hands on deck)

### Consolidation 2: Models Hub
**Unifies:** local_llm_view + voices_view + runtime_routing → models_view.py

**Why:**
- Model selection, voice device, and route preview are logically one flow
- Voice provider registry is stable (can't change during consolidation)
- Dark-launch enables testing with real provider registry without affecting operators

**Feature Flag:** `models_hub_enabled`

**Timeline:** 9 days (lower risk, can run in parallel with Settings Hub)

### Consolidation 3: Home Chat Cleanup
**Removes:** Model controls, route status, diagnostics from chat surface

**Why:**
- Operator UI clutters conversation experience
- Operators already have Settings + Models hubs for these functions
- Dark-launch enables testing operator UI removal without affecting old surface

**Feature Flag:** `home_chat_cleanup_enabled`

**Timeline:** 6 days (mostly removal work)

---

## Risk Profile (Now vs. With Feature Flags)

### Without Feature Flags (High Risk)
```
Day 1:  Ship Settings Hub consolidation
Day 2:  Operator reports: "Can't find advanced diagnostics"
Day 3:  Spend 4 hours debugging, shipping hotfix (risky, untested)
Day 4:  Hotfix breaks something else
Day 5:  Rollback entire Settings Hub (all work wasted)
```

### With Feature Flags (Low Risk)
```
Day 1:  Ship Settings Hub consolidation (disabled by default, old surfaces live)
Day 2:  Operator tests new hub manually (flag enabled in config)
Day 3:  Operator finds issue: "Can't find advanced diagnostics"
Day 4:  Engineer fixes in new hub code, operators flip flag to False (back to old surfaces instantly)
Day 5:  Ship fixed Settings Hub (new code validated, ready for real rollout)
```

---

## Implementation Checklist (Today)

✅ **Feature Flags Infrastructure**
- Add `FeatureFlags` dataclass to `utils/personalization_config.py`
- Update `ui/launcher/launcher_window.py` to route on flag state
- Create test fixtures for headless testing with flags enabled
- Verify: `dev-check delta` passes

✅ **Phase 0 Documentation (Team-Specific)**
- **Settings Hub:** Document current ownership matrix (4 surfaces → 6 unified sections)
- **Models Hub:** Verify provider registry & voice bindings stable (3 integrity gates)
- **Home Chat:** Inventory operator UI fragments (where do they move to?)

✅ **Git Workflow**
- Three teams, three branches, three PRs
- One shared commit for feature flag infrastructure
- All PRs linked to [HUB_CONSOLIDATION_MASTER_PLAN.md](HUB_CONSOLIDATION_MASTER_PLAN.md)

---

## Questions & Answers

### Q: What if I need to rollback during Phase 1-2?
**A:** Flip feature flag to False in config, restart app. Old surfaces load instantly. No code revert needed.

### Q: What if multiple developers work on the same hub?
**A:** Feature flags route at runtime, so both old and new code coexist. Developers can work in parallel without conflicts.

### Q: What if an operator finds a bug in the new hub?
**A:** Operator disables flag in config, restarts app, back to old surfaces. Meanwhile, engineering fixes new hub code. Ship fixed version, operator re-enables flag.

### Q: Do we need to delete old surfaces immediately?
**A:** No. Deletion happens in Phase 5 (weeks 3+) after new hub is proven stable. Phases 1-4 keep old code alive for safety.

### Q: Can we test with feature flags in CI/CD?
**A:** Yes. `pytest` fixtures toggle flags, so test suite can verify both old and new code paths.

### Q: What if the new hub needs a database schema change?
**A:** You can't make schema changes during dark-launch (violates zero-downtime). All three plans explicitly avoid schema changes. If you need a schema change, it happens before the dark-launch (Phase 0).

---

## Success Criteria

### Day 1 (Phase 0 - TODAY)
- ✅ Feature flags infrastructure merged
- ✅ All three teams complete Phase 0 deliverables
- ✅ `dev-check delta` passing
- ✅ All three PRs approved

### Week 1 (Phases 1-2)
- ✅ Settings Hub dark-launched (disabled by default)
- ✅ Models Hub dark-launched (disabled by default)
- ✅ Home Chat cleanup dark-launched (disabled by default)
- ✅ Operators can manually enable flags to test

### Week 2 (Phases 3-4)
- ✅ All three hubs tested with flags enabled
- ✅ Operators can toggle between old/new surfaces
- ✅ No regressions found; all guardrails passing

### Week 3 (Phase 5)
- ✅ Cutover: New hubs go live (flags set to True by default)
- ✅ Old surfaces disabled or deleted
- ✅ Navigation rail refactored to 5-hub model
- ✅ Operator checklist sign-off

---

## What You're Building (The Big Picture)

**Today:** Guppy has operator controls scattered everywhere (chat, settings, models, workspace details, quick actions). Operators get confused. Chat surface is cluttered.

**In 3 weeks:** Guppy has one clean Home Chat for conversation + one place for each category (Settings, Models, Tools, Library). Operators know exactly where to go. Chat stays clean.

**This is the move from** "scattered, operator-heavy, confusing" **to** "unified, conversation-focused, crystal clear."

---

## Authorization Summary

🚀 **You are fully authorized to:**

✅ Use all development capacity  
✅ Pursue all three consolidations in parallel  
✅ Implement feature flags as risk mitigation  
✅ Take until Phase 5 complete (3 weeks)  
✅ Prioritize quality and thorough testing over speed  
✅ Roll back any hub to old surfaces via flag if needed  

**Your success criteria:** All guardrails passing, all regression tests green, operator checklist signed off.

**Your risk mitigation:** Dark-launch with feature flags. If anything breaks, flip flag and operators are back to old surfaces in 5 seconds.

**Your support:** Daily standup, weekly sync, emergency channel if you hit blockers.

---

**GO BUILD THIS. YOU GOT THIS.** 🚀

Phase 0 starts now. Phase 1 tomorrow. Phase 5 complete by end of month.

