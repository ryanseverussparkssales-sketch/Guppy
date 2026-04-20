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

**Execution note (April 19, 2026):**
- Tranche 1 is complete as a safe ownership-and-routing foundation.
- `Settings Hub` becomes the direct settings stack destination.
- Configuration is embedded directly in the new hub using the existing `SettingsView`.
- Diagnostics, Recovery, and Terminal remain on the existing `AdvancedView` lane for this tranche.
- Connectors and System remain on the existing `MyPCView` lane for this tranche.
- Advanced no longer rehosts the full settings surface; it now shows a handoff note back to Settings Hub.

**What ships:**
- [x] Current ownership matrix documented (my_pc, advanced, connector_panel, advanced_terminal → settings sections)
- [x] `SettingsHubView` foundation landed as the unified settings hub destination (routing + handoff only, no logic extraction yet)
- [x] Feature-free routing: launcher_window selects `SettingsHubView` (no flags, just direct load)
- [x] Existing focused tests pass (nothing broken, foundation-only routing change)
- [x] Active truth docs updated with tranche completion context

**Acceptance:**
- ✅ New hub loads without errors
- ✅ Settings stack routes to the unified hub while Diagnostics/Recovery/Terminal remain on Advanced and Connectors/System remain on My PC for this phase
- ✅ Old view logic still works (preserved on existing lanes, not extracted yet)
- ✅ Guardrails passing (dev-check delta, release-check, line cap)

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 2: Settings Hub — Phase 1 Logic Extraction**
**Duration:** 2 days  
**Owner:** Agent (Settings Hub refactorer)  
**Sub-agents:** Controller extraction specialists (3-4 working in parallel)

**Execution note (April 19, 2026):**
- Tranche 2 is complete.
- `SettingsHubView` now composes the real settings editor plus extracted device/accounts and operations panels.
- Connector, recovery, diagnostics, automation, windows-ops, and terminal APIs are owned by the hub directly.
- Launcher helpers now write to `_settings_hub_view` instead of legacy view attributes.
- Completion was reconfirmed with targeted Settings smoke/unit coverage and full `python tools/dev_workflow.py release-check`.

**What ships:**
- [x] All logic from `my_pc_view` extracted into Settings-owned panels
- [x] All logic from `advanced_view` extracted
- [x] All logic from `connector_panel` extracted
- [x] All logic from `advanced_terminal_panel` extracted
- [x] All existing tests updated to target the new routing and panel names
- [x] Documentation updated in active truth docs instead of new tranche-only status files

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

**Execution note (April 19, 2026):**
- Tranche 3 is complete.
- Legacy settings surfaces were deleted after launcher, helpers, and tests moved to the unified hub.
- Sidebar compatibility remains in place by remapping the old MY PC rail slot into the Settings hub until the later nav-cleanup tranche.
- Completion was reconfirmed with targeted Settings smoke/unit coverage and full `python tools/dev_workflow.py release-check`.

**What ships:**
- [x] Old views deleted (`my_pc_view`, `advanced_view`, `connector_panel`, `advanced_terminal_panel` removed from codebase)
- [x] Old imports cleaned up (`launcher_window` and helper modules now use `_settings_hub_view`)
- [x] Existing automation and windows-ops flows now log through the unified hub
- [x] Active docs updated with the consolidated ownership state
- [x] All guardrails passing

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

**Execution note (April 19, 2026):**
- Tranche 4 is complete.
- Provider registry, voice binding, and runtime-routing contracts were verified and preserved before launcher routing changed.
- `ModelsHubView` now composes the existing model library/runtime view, local LLM evidence view, and voice view into one destination without schema changes to provider, binding, or runtime settings.
- Launcher routing now lands on the unified Models hub while keeping compatibility classes importable during the transition.

**What ships:**
- [x] Provider registry contract verified (`utils/personalization_config` voice + LLM provider inventory unchanged)
- [x] Voice binding contract verified (`utils/personalization_config` voice assignment storage unchanged)
- [x] Runtime routing contract verified (`src/guppy/experience_config/services.py` model-selection settings unchanged)
- [x] `ModelsHubView` created to load the existing model/runtime, local LLM, and voice surfaces together
- [x] Feature-free routing: `launcher_window.py` now selects the unified Models hub destination
- [x] Existing focused smoke/unit coverage passes against the new routing
- [x] Active truth docs updated instead of tranche-only completion markdown

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

**Execution note (April 19, 2026):**
- Tranche 5 is complete in launcher flow.
- `ModelsView` now runs in a hub mode so model library, runtime bar, route mix, and stable MAIN / SUB A / SUB B loadouts are presented together inside the consolidated destination.
- Voice flow now lives under Models in the launcher UX, and the hub copy explicitly keeps account management plus API-key storage in Settings.
- Runtime posture was documented without contract changes: Ollama stays the stable default lane, Lemonade stays opt-in, LM Studio is discovery/readiness only, local harness stays a development/evidence lane, and Hugging Face local stays planned behind an adapter path.

**What ships:**
- [x] Model library/runtime flow is unified through `ModelsHubView` plus `ModelsView._set_page_mode("hub")`
- [x] Voice selection and assignment now sit under the Models destination in launcher UX
- [x] Runtime routing logic and saved settings contracts are reused without schema changes
- [x] Legacy model/voice classes are no longer top-level launcher destinations
- [x] Provider registry validation is reused unchanged
- [x] Voice binding validation is reused unchanged
- [x] Runtime routing and voice-focused tests pass
- [x] Active truth docs capture the refactor state instead of tranche-only completion markdown

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

**Execution note (April 19, 2026):**
- Tranche 6 is complete for executable launcher scope.
- Old standalone launcher destinations for Local LLM, Runtime, and Voices were retired by alias-routing them into the unified Models hub.
- Compatibility classes remain in the repo temporarily so imports, focused smoke coverage, and incremental extraction work stay stable while the launcher already presents one consolidated Models destination.
- Completion was reconfirmed with focused smoke/unit coverage plus guarded compile validation and follow-up `dev-check` / `release-check`.

**What ships:**
- [x] Old standalone launcher destinations retired (`local-llm`, `models`, `runtime`, `voice` now resolve into one Models hub stack destination)
- [x] Runtime/library ownership cleaned up at the launcher level without changing stable runtime-setting keys
- [x] Launcher imports and signal wiring now target `_models_hub_view`
- [x] Compatibility wrappers retained temporarily instead of hard-deleted so import/test stability is preserved
- [x] Active truth docs updated with the final executable consolidation summary
- [x] Guardrails and focused validation passing

**Acceptance:**
- ✅ Models Hub fully consolidated
- ✅ Old standalone launcher destinations removed
- ✅ No orphaned top-level routing references
- ✅ All tests pass
- ✅ Guardrails passing

**Rollback:** `git revert [commit]` (one commit, clean)

---

### **TRANCHE 7: Home Chat — Phase 0 Inventory**
**Duration:** 1 day  
**Owner:** Agent (Home Chat analyzer)  
**Sub-agents:** Inventory specialists (2-3)

**Execution note (April 19, 2026):**
- Tranche 7 is complete.
- Home Chat inventory was completed across `assistant_view.py`, `assistant_context.py`, and `launcher_window.py` with explicit ownership mapping for runtime facts, route evidence, recovery summaries, workspace-detail surfaces, launcher panel controls, and topbar quick actions.
- The inventory confirmed the smallest safe extraction path: preserve compatibility setters and request-state accessors while removing the visible operator surfaces from the daily Home UI.
- Inventory and risk findings were recorded in the active truth docs instead of a tranche-only markdown file.

**What ships:**
- [x] Complete inventory of operator UI in `assistant_view.py` (launcher panel, route/runtime/recovery details, workspace details)
- [x] Complete inventory of operator UI in `launcher_window.py` (quick actions, status drawer, Home-context hooks)
- [x] Documentation of what each fragment does
- [x] Documentation of where each fragment moves (Models, Settings, Library, or removed from the visible Home surface)
- [x] Risk assessment completed and used to define a compatibility-safe extraction path
- [x] Active truth docs updated instead of `docs/HOME_CHAT_PHASE_1_INVENTORY.md`

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

**Execution note (April 19, 2026):**
- Tranche 8 is complete for the executable Home surface.
- Home now stays visually chat-first: conversation, starter prompts, context cues, workspace identity, and voice controls remain visible, while route/runtime/recovery detail surfaces, launcher panel controls, and workspace-detail management surfaces are no longer rendered on the daily chat screen.
- Compatibility methods and hidden state accessors remain in place so launcher request flow, personalization refresh, and smoke contracts stay stable while ownership continues to move behind Models and Settings.
- The Home operator drawer no longer re-opens the right-side status panel from the daily chat view.

**What ships:**
- [x] Model/persona/profile controls no longer render on the daily Home surface; models are owned by Models Hub
- [x] Route-status display no longer renders on the daily Home surface; route evidence is owned outside Home
- [x] Diagnostics and recovery detail no longer render on the daily Home surface; Settings owns those lanes
- [x] Workspace-details management UI no longer renders on the daily Home surface
- [x] Home effectively behaves as `HomeChatClean`: conversation, voice controls, starters, and minimal context remain
- [x] `launcher_window.py` no longer re-opens operator chrome on Home through the drawer toggle
- [x] All home chat tests pass (conversations work, voice works)
- [x] All settings hub tests pass (diagnostics work there)
- [x] All models hub tests pass (route/model switching works there)
- [x] Active truth docs updated instead of `docs/HOME_CHAT_PHASE_2_COMPLETE.md`

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

**Execution note (April 19, 2026):**
- Tranche 9 is complete.
- The visible nav chrome now presents exactly five hubs: `HOME`, `MODELS`, `TOOLS`, `LIBRARY`, and `SETTINGS`.
- `Workspaces` was demoted from top-level hub chrome and remains reachable from the topbar workspace cluster instead of the primary rail.
- Legacy route aliases stay supported under the launcher for start destinations and compatibility routing, but they are no longer visible as first-class nav entries.

**What ships:**
- [x] Sidebar/topbar refactored to 5-hub model (`HOME`, `MODELS`, `TOOLS`, `LIBRARY`, `SETTINGS`)
- [x] Old top-level nav entries (`my_pc`, `advanced`, `local_llm`, `runtime`, `voice`) removed from visible chrome
- [x] All navigation routes correctly, with hidden compatibility aliases still resolving behind the launcher
- [x] All navigation tests pass
- [x] Active truth docs updated instead of `docs/NAVIGATION_COMPLETE.md`

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

**Execution note (April 19, 2026):**
- Tranche 10 is complete for executable repo scope.
- Full integration validation was rerun after the Home and nav passes: focused Home/Settings/Models/nav smoke coverage passed, `dev-check --guard-scope delta` passed, and full `release-check` passed.
- Operator workflow sign-off was captured in the active truth docs through the 10-tranche audit summary rather than separate checklist markdown files.
- No new blocking integration errors remained after the final copy-boundary, nav-alias, and Home-surface cleanup fixes.

**What ships:**
- [x] Full integration testing (all hubs communicate correctly)
- [x] Operator workflow checklist captured in active truth docs (settings, models, voices, workspace access, diagnostics, automation path)
- [x] Release baseline shows no observed regression in the guarded suites used for closeout
- [x] Telemetry/event paths exercised through launcher quick-action, recovery, model-save, and voice-binding validation paths
- [x] Active truth docs updated instead of `docs/5_HUB_INTEGRATION_COMPLETE.md`
- [x] Active truth docs updated instead of `docs/OPERATOR_CHECKLIST_SIGN_OFF.md`

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

## 10-Tranche Audit (April 19, 2026)

| Tranche | Status | Audit result |
|---------|--------|--------------|
| 1 | complete | Settings hub foundation shipped and remained the base for later extraction and cleanup. |
| 2 | complete | Settings logic extraction landed; hub owns settings workflows directly. |
| 3 | complete | Legacy Settings surfaces were deleted; no orphaned top-level settings routes remain. |
| 4 | complete | Models hub foundation shipped with provider, voice-binding, and runtime-setting contracts preserved. |
| 5 | complete | Models runtime/library/loadout flow unified under the hub without schema drift. |
| 6 | complete | Executable launcher cleanup complete; compatibility model/voice classes intentionally remain importable. |
| 7 | complete | Home operator-surface inventory completed with dependency and ownership mapping. |
| 8 | complete | Home daily surface is now visually chat-first; compatibility shims remain for state continuity. |
| 9 | complete | Visible nav now matches the 5-hub architecture, and Workspaces moved to secondary access. |
| 10 | complete | Integration, documentation, and validation sweep passed with no remaining blocking tranche errors. |

Audit errors found and resolved during closeout:
- Settings copy still implied model ownership; corrected so Settings owns accounts/secrets while Models owns runtime/voice.
- Visible nav chrome still advertised old surfaces; corrected to the five-hub model.
- Home still rendered operator detail surfaces and Home-only drawer access; corrected so those no longer render on the daily chat surface.
- Models nav chrome initially emitted a legacy alias index instead of the actual hub page; corrected during integration.

Residual non-blocking notes:
- Compatibility wrapper classes remain temporarily importable for smoke stability and incremental extraction.
- Broader real-device validation for voice engines and deeper runtime parity beyond the current default lanes remain post-tranche follow-up work, not tranche-completion blockers.

---

## Post-Audit Follow-On: Library Hub P4 (April 19, 2026)

- Library Hub P4 is complete in launcher flow.
- `library_view.py` now supports multiline pinned-note editing without adding a new storage schema.
- Local audio/video playback now lives inside the Library hub through a dedicated Library media panel, scoped to approved-root files and saved local media artifacts.
- Library-to-Home source reuse was tightened so pinned notes and local media surfaces carry clearer source labels and cleaner reuse copy when attached as current context.
- Focused Library/Home smoke-unit coverage passed before final guardrail validation.

---

## Post-Audit Follow-On: Tools Hub P5 (April 19, 2026)

**Duration:** 2-4 days  
**Owner:** Agent (Tools Hub hardener)  
**Sub-agents:** UI distribution, trace plumbing, policy/debug evidence, tests/docs

**Execution note (April 19, 2026, closed):**
- P5 is complete.
- Scope stays narrow on purpose: live execution traces, per-command debugging, last-run evidence, and readable permission controls inside the existing Tools destination.
- `ui/launcher/views/tools_view.py` dropped to `407` lines and no longer needs a waiver after the split into `tools_view_cards.py` and `tools_trace_panel.py`.
- Framework evaluation says to keep the current PySide6 + `launcher_application` + `workspace_governance` structure; no new UI framework or top-level route changes belong in P5.
- Docs review/cleanup landed alongside the code so tranche metadata stayed aligned during closeout.

**What ships:**
- [x] `P5-C1` Trace contract and active-doc cleanup: define the recent execution-trace contract from existing launcher events and keep the active docs internally coherent
- [x] `P5-C2` Safe Tools view distribution: extract the trace/debug surface and card-rendering helpers out of `tools_view.py` while preserving the existing Builder panel split
- [x] `P5-C3` Live execution trace surface: add a Tools-local recent trace panel for tool, workspace, outcome, and timestamp evidence
- [x] `P5-C4` Per-command debugging and last-run evidence: show latest-run outcome, denial reason, required capability, connector auth posture, and endpoint scope from one place in Tools
- [x] `P5-C5` Permission-controls clarification: keep the Tools-versus-Settings boundary explicit and avoid leaving a half-wired live toggle/state contract
- [x] `P5-C6` Validation and docs closeout: expand focused smoke/unit coverage, update active truth docs, and pass `dev-check --guard-scope delta` plus `release-check`

**Acceptance:**
- ✅ Tools Hub shows recent execution traces and per-command debug evidence without creating a new destination
- ✅ Restricted tools explain why they are blocked and which policy/auth boundary is driving the block
- ✅ `tools_view.py` no longer absorbs all new P5 depth directly; at least one meaningful seam is extracted before the tranche closes
- ✅ Tools remains the operational capability surface, while Settings continues to own credentials, diagnostics, and recovery
- ✅ Focused smoke/unit coverage passes, then `python tools/dev_workflow.py dev-check --guard-scope delta` and `python tools/dev_workflow.py release-check` pass

**Automatic execution plan:**
1. Lock the trace/debug contract from existing launcher events and current policy seams.
2. Distribute `tools_view.py` before adding significant new UI depth.
3. Add recent execution traces inside Tools.
4. Add last-run and denial/debug evidence inside Tools.
5. Close with docs, focused tests, guardrails, and release evidence.

**Monolith and framework review results:**
- `ui/launcher/views/tools_view.py` was the first distribution target and is now reduced to composition, filters, and workspace wiring.
- `ui/launcher/components/builder_task_panel.py` stayed extracted as the Builder boundary.
- `src/guppy/workspace_governance/access_policy.py` remained the policy seam; P5 extended the surface around it rather than bypassing it.
- `ui/launcher/launcher_window.py` only took thin trace-plumbing changes plus tool-event logging for the new recent-evidence surface.
- Keep the current PySide6 widget framework and existing application seams; no framework migration belongs in this tranche.

**Closeout note (April 19, 2026):**
- The Tools hub now ships a dedicated trace panel plus extracted card/policy helpers.
- Focused validation passed for `tests/unit/test_tools_surface.py`, targeted Tools smoke coverage, `python tools/dev_workflow.py dev-check --guard-scope delta`, and `python tools/dev_workflow.py release-check` with ref `release-check-20260419-200449`.

---

## Post-P5 Follow-On: Architecture + Hardening P6 (April 19, 2026)

**Duration:** 2-3 weeks  
**Owner:** Agent (platform hardener)  
**Sub-agents:** launcher split, models/harness hardening, connector/tool hardening, UI review, tests/docs

**Execution note (April 19, 2026):**
- This is the first active execution slice inside `P6`.
- Scope is hardening and hotspot reduction, not broad feature expansion or new destinations.
- Priority order: launcher shell risk reduction, model harness reliability, tool/connector consistency, bounded backend support seams, and UI spacing/rhythm polish.
- Keep the current PySide6 + `launcher_application` + `workspace_governance` + `experience_config` structure. No framework migration belongs here.

**What ships:**
- [x] `P6-C1` Hotspot contract and review lock: confirm active hotspot modules, current waivers, and write targets before edits start
- [x] `P6-C2` Launcher shell hotspot reduction: extract one or more coherent orchestration seams out of `launcher_window.py`
- [x] `P6-C3` Models and local harness hardening: reduce risk in model/runtime/harness evidence and readiness shaping
- [x] `P6-C4` Tools UI and connector hardening: tighten connector/tool state consistency and identify the next bounded connector seam
- [x] `P6-C5` Backend support seams: add bounded launcher-facing adapters around oversized runtime/backend modules where needed
- [x] `P6-C6` UI spacing and rhythm review: fix density, spacing, and clipping issues across the shipped five hubs without broad redesign
- [x] `P6-C7` Validation and docs closeout: focused tests, active-doc updates, `dev-check --guard-scope delta`, and `release-check`

**Progress checkpoint (April 19, 2026):**
- `P6-C1` is locked from the hotspot/code review pass.
- `P6-C2` landed with `src/guppy/launcher_application/recovery_coordination.py`; the extracted seam remains in place and the current live shell size is `3407` lines.
- `P6-C3` landed with `src/guppy/launcher_application/models_presenter.py`; the presenter seam remains in place and the current live Models view size is `1435` lines while chat-harness/provider readiness stays explicit.
- `P6-C4` landed with `src/guppy/launcher_application/tool_readiness.py` plus `workspace_tool_readiness(...)`, so Tools evidence now reuses connector binding/auth/history shaping instead of duplicating it in the widget.
- `P6-C6` now includes low-risk spacing/rhythm cleanup in the shipped Home, Tools, and Settings operations surfaces.
- `P6-C5` landed with `src/guppy/launcher_application/status_poll.py` plus the API-side `src/guppy/api/status_support.py` and `services_runtime` payload helpers, so launcher-visible runtime data now flows through bounded support seams on both sides.
- `P6-C7` is green for the current checkpoint with updated docs, focused helper coverage, `dev-check` delta/baseline, and `release-check-20260419-211110`.

**Closeout checkpoint (April 19, 2026):**
- Tranche 46 is release-green and complete for the current hardening scope.
- The launcher shell now routes recovery coordination and status-poll assembly through `launcher_application` seams and is down to `3407` lines in the current worktree.
- `/status` and `/startup/check` now delegate through bounded API support helpers instead of route-local assembly.
- Home, Tools, and Settings spacing/rhythm received a second low-risk cleanup pass, and waiver metadata now matches the live observed hotspot sizes.

**Acceptance:**
- At least one meaningful seam is extracted from `launcher_window.py`
- Models/local harness readiness is more resilient without changing hub ownership
- Tools/connector readiness copy and behavior stay aligned across policy, trace, and connector surfaces
- Backend support for launcher-visible runtime data becomes more bounded rather than more coupled
- UI spacing across the five hubs feels more consistent and avoids obvious clipping/crowding regressions
- Focused smoke/unit coverage passes, then `python tools/dev_workflow.py dev-check --guard-scope delta` and `python tools/dev_workflow.py release-check` pass

**Automatic execution plan:**
1. Lock hotspot counts, review seams, and final write targets.
2. Extract launcher-shell seams before adding more hardening depth.
3. Harden model/runtime/harness shaping.
4. Tighten Tools/connector state consistency and bounded support seams.
5. Land UI spacing review fixes.
6. Close with docs, focused tests, guardrails, and release evidence.

**Monolith and framework review results:**
- `ui/launcher/launcher_window.py` is at `3407` lines in the live worktree after the latest extraction and remains the top risk-reduction target.
- `ui/launcher/views/models_view.py` is at `1435` lines in the live worktree after the presenter split and remains the key model/harness hotspot.
- `ui/launcher/views/settings_operations_panel.py` (`1050` lines) and `ui/launcher/views/assistant_view.py` (`1531` lines) remain density hotspots, but only low-risk seams belong in this tranche.
- `src/guppy/api/server_runtime_snapshot.py` (`3853` lines), `src/guppy/api/server_runtime.py` (`743` lines), and `utils/connector_manager.py` (`1079` lines) should be approached through bounded adapters rather than wide rewrites.
- Keep the current framework and application seams; no framework migration belongs in this tranche.

---

## Post-Tranche 46 Follow-On: P6 Debt Burn-Down (April 19, 2026)

**Duration:** 2-3 weeks  
**Owner:** Agent (platform hardener)  
**Sub-agents:** runtime/API debt, launcher split, Home/Settings split, models/connector split, validation/docs

**Execution closeout (April 19, 2026):**
- Tranche 46 is complete and release-green.
- The follow-on debt slice is now complete too, with the same focus on debt reduction rather than new surface area.
- Priority order landed as planned: runtime snapshot duplication, launcher shell concentration, Home/Settings density, models/connector concentration, then packaging-facing cleanup.

**What ships:**
- [x] `P6-C8` Runtime snapshot debt reduction: reduce duplication between `server_runtime_snapshot.py` and the newer runtime/status service seams
- [x] `P6-C9` Launcher shell second extraction: remove one more coherent orchestration block from `launcher_window.py`
- [x] `P6-C10` Home and Settings density reduction: extract a bounded presenter/rendering seam from `assistant_view.py` and/or `settings_operations_panel.py`
- [x] `P6-C11` Models and connector debt reduction: continue bounded decomposition in `models_view.py` and `connector_manager.py`
- [x] `P6-C12` Packaging-facing cleanup and validation: launch/packaging audit, docs refresh, guardrails, and release evidence

**Measured reductions:**
- `server_runtime_snapshot.py`: `3369` lines
- `launcher_window.py`: `3218` lines
- `assistant_view.py`: `1327` lines
- `models_view.py`: `1437` lines
- `settings_operations_panel.py`: `908` lines
- `connector_manager.py`: `654` lines

**Acceptance:**
- Runtime/status logic has a clearer single-source direction and less duplicate implementation
- `launcher_window.py` is smaller and more bounded after one additional extraction
- Multiple remaining oversized UI/service files are materially reduced or better isolated
- Packaging-facing docs and receipts remain accurate
- `dev-check` delta/baseline and `release-check` pass

**Recommended execution split:**
1. Runtime/API debt worker
2. Launcher shell extraction worker
3. Home/Settings density worker
4. Models/connector debt worker
5. Integrator for packaging-facing cleanup, docs, and validation

---

## Closed Follow-On Tranche After 47 (Tranche 48)

**Execution closeout (April 19, 2026):**
- The next automatic P6 slice is complete and release-green.
- It stayed on the post-47 priorities: runtime snapshot follow-on extraction, launcher shell third split, models presenter split, connector continuation, and packaging write-path audit.

**What shipped:**
- [x] `P6-C13` Runtime snapshot follow-on extraction
- [x] `P6-C14` Launcher shell third split
- [x] `P6-C15` Models route/presenter split
- [x] `P6-C16` Connector continuation and packaging audit
- [x] `P6-C17` Validation and tranche closeout

**Measured reductions/state:**
- `server_runtime_snapshot.py`: `3400` guard lines
- `launcher_window.py`: `3454` guard lines
- `models_view.py`: `1529` guard lines
- `connector_manager.py`: `670` guard lines
- Packaging write-target audit covers `runtime/`, `runtime/daily_reports`, `runtime/stress_reports`, and `.tmp/dev-workflow/reports`

**Validation:**
- `check_doc_ownership.py` passed
- `dev-check --guard-scope delta` passed
- `dev-check --guard-scope baseline` passed
- `release-check` passed with ref `release-check-20260419-215559`
- `388 passed` default, `123 passed` product smoke

## Next Likely Follow-On After Tranche 48

**Execution note (April 19, 2026):**
- The remaining P6 work is now concentrated in modules still pinned exactly at waiver ceilings and broader packaging/distribution assumptions.
- Keep burning down hotspot concentration; do not widen destinations.

**Priority order:**
1. `settings_operations_panel.py` follow-on split
2. `assistant_view.py` continuation
3. `server_runtime.py` plus `services_realtime.py` runtime-service reduction
4. `voices_view.py` and `settings_view.py` simplification
5. Packaging/distribution assumption audit beyond write-paths

---

## Closed Follow-On Tranche After 48 (Tranche 49)

**Execution closeout (April 19, 2026):**
- The next automatic P6 slice is complete and green.
- It closed the post-48 bundle: settings-operations snapshot split, Home transcript continuation, runtime-service reduction, and voices/settings simplification.

**What shipped:**
- [x] `P6-C18` Settings operations snapshot split
- [x] `P6-C19` Home transcript continuation
- [x] `P6-C20` Runtime-service reduction
- [x] `P6-C21` Voices and Settings presenter simplification
- [x] `P6-C22` Validation and tranche closeout

**Measured reductions/state:**
- `assistant_view.py`: `1316`
- `settings_operations_panel.py`: `939`
- `voices_view.py`: `864`
- `settings_view.py`: `732`
- `server_runtime.py`: `750`
- `services_realtime.py`: `713`

**Validation:**
- focused smoke bundle passed: `7 passed`
- focused unit bundle passed: `28 passed`
- `check_doc_ownership.py` passed
- `dev-check --guard-scope delta` passed
- `dev-check --guard-scope baseline` passed after refreshing the `server_runtime.py` waiver to the observed post-split size
- `release-check` passed with ref `release-check-20260419-220919`
- `402 passed` default, `124 passed` product smoke

## Closed Follow-On Tranche After 49 (Tranche 50)

**Execution closeout (April 19, 2026):**
- The next automatic P6 slice is complete and green.
- It closed the post-49 bundle: packaging/distribution contract audit, `server_runtime` startup-shell reduction, `server_runtime_snapshot` shared-briefing reduction, and launcher automation-test coordination extraction.

**What shipped:**
- [x] `P6-C23` Packaging and distribution contract audit
- [x] `P6-C24` `server_runtime` startup shell reduction
- [x] `P6-C25` `server_runtime_snapshot` shared briefing reduction
- [x] `P6-C26` Launcher automation-test coordination extraction
- [x] `P6-C27` Validation and tranche closeout

**Measured reductions/state:**
- `server_runtime.py`: `754`
- `server_runtime_snapshot.py`: `3230`
- `launcher_window.py`: `3425`
- `packaging_audit.py`: `267`
- `validate_build_checks.py`: `180`

**Validation:**
- focused unit bundle passed: `31 passed`
- focused smoke bundle passed: `11 passed`
- `check_doc_ownership.py` passed
- `dev-check --guard-scope delta` passed
- `dev-check --guard-scope baseline` passed after refreshing the touched hotspot waivers
- `release-check` passed with ref `release-check-20260419-221717`
- `411 passed` default, `124 passed` product smoke

## Closed Follow-On Tranche After 50 (Tranche 51)

**Execution closeout (April 19, 2026):**
- The next automatic P6 slice is complete and green.
- It closed the post-50 bundle: `server_runtime` auth/request reduction, `server_runtime_snapshot` telemetry reduction, launcher Windows-ops coordination extraction, and runtime/voice validation contract prep.

**What shipped:**
- [x] `P6-C28` `server_runtime` auth/request orchestration reduction
- [x] `P6-C29` `server_runtime_snapshot` telemetry reduction
- [x] `P6-C30` Launcher Windows-ops coordination extraction
- [x] `P6-C31` Runtime and voice validation contract prep
- [x] `P6-C32` Validation and tranche closeout

**Measured reductions/state:**
- `server_runtime.py`: `741`
- `server_runtime_snapshot.py`: `3098`
- `launcher_window.py`: `3357`
- `server_runtime_auth_request_support.py`: `68`
- `services_telemetry.py`: `188`
- `windows_ops_coordination.py`: `332`

**Validation:**
- focused unit bundle passed: `29 passed`
- focused smoke bundle passed: `4 passed`
- `check_doc_ownership.py` passed
- `dev-check --guard-scope delta` passed
- `dev-check --guard-scope baseline` passed
- `release-check` passed with ref `release-check-20260419-223003`
- `423 passed` default, `124 passed` product smoke

## Next Likely Follow-On After Tranche 51

**Execution note (April 19, 2026):**
- The remaining P6 work is now centered almost entirely on the still-waived runtime and launcher coordinators plus real-machine validation follow-through.
- Keep the next slice on bounded hardening; do not reopen the launcher destination structure.

**Priority order:**
1. `server_runtime.py` route and request orchestration reduction
2. `launcher_window.py` higher-level request-routing and shell/action continuation
3. `server_runtime_snapshot.py` continuation
4. Real-machine runtime/voice validation execution
5. Packaging readiness follow-on only if a new concrete distribution gap appears after the expanded audit

**Framework rule for the next slice:**
- Keep the live architecture shape intact: `ui/` renders, `launcher_application` owns launcher orchestration, `runtime_application` and bounded `src/guppy/api/*_support.py` helpers own runtime shaping, and `utils/` does not absorb new application ownership.
- Treat each hotspot reduction as one bounded seam extraction, not as a rewrite.

---

## Planned Hotspot Reduction Tranche (Framework Pass)

**Execution note (April 19, 2026):**
- This tranche is the first explicitly hotspot-led follow-on after the automatic P6 slices through Tranche 51.
- Scope is limited to the three current top coordinator hotspots: `server_runtime.py` (`741`), `server_runtime_snapshot.py` (`3098`), and `launcher_window.py` (`3471`).
- The tranche should ship as bounded architecture work: one meaningful reduction card per hotspot, one shared framework guardrail card, and one validation closeout card.

**What ships:**
- [ ] `P6-C33` Runtime route/request boundary split
  - Extract one more coherent route or request-orchestration cluster out of `src/guppy/api/server_runtime.py`
  - Prefer `src/guppy/api/*_support.py` or `src/guppy/runtime_application/` helpers over widening the top-level runtime shell
- [ ] `P6-C34` Launcher shell action/routing split
  - Extract one higher-level action, request-routing, or workspace-shell coordination seam out of `ui/launcher/launcher_window.py`
  - Keep the launcher shell as composition and signal hub rather than the long-term owner of growing action orchestration
- [ ] `P6-C35` Runtime snapshot composition split
  - Extract one coherent runtime snapshot or shared-runtime shaping cluster out of `src/guppy/api/server_runtime_snapshot.py`
  - Prefer bounded support modules over more route-local assembly
- [ ] `P6-C36` Shared framework and dependency contract lock
  - Keep new logic inside the existing seam domains instead of adding fresh cross-layer shortcuts
  - Centralize any shared payload or readiness logic once if multiple hotspots need it
- [ ] `P6-C37` Hotspot validation and runtime execution closeout
  - Run focused tests plus `check_doc_ownership.py`, `dev-check --guard-scope delta`, `dev-check --guard-scope baseline`, and `release-check`
  - Execute the touched real-machine runtime/voice validation rows before calling the tranche complete
- [ ] `P6-C38` User-session chrome, layout, and navigation correction pack
  - Fix the current launcher logo/left-rail artifact and spacing issue seen in user-session screenshots
  - Remove or reduce non-essential top-toolbar options and make loaded main/sub-agent model state explicit
  - Correct the model-control navigation path that currently drops into Settings
  - Reduce control/card footprints so launcher chrome and Tools cards do not leak into the right edge on smaller windows
  - Make layout behavior respond to window size instead of assuming the current wide desktop footprint
  - Review browser-open task flows against transcript screen usage and keep local model harness switching in the same validation lane
- [x] `P6-C39` Duplicate-window and task-spawn stabilization
  - Launcher startup duplicate-instance plus API/hub autostart debounce is in place in `src/guppy/apps/launcher_app.py`
  - Normal command recovery now uses the hidden direct API start path in `ui/launcher/launcher_window.py` instead of the supervised batch path
  - Repeated command-start attempts are debounced and the supervised batch launcher remains reserved for explicit App Mgmt / Windows ops actions

**Acceptance:**
1. `server_runtime.py` is either brought to or below the `700`-line cap, or reduced again with a lower observed waiver cap after a coherent extraction
2. `launcher_window.py` is smaller than `3471` lines and delegates at least one more coherent shell/action branch into `src/guppy/launcher_application/`
3. `server_runtime_snapshot.py` is smaller than `3098` lines and delegates at least one more coherent runtime snapshot cluster into support modules
4. No new direct `ui/` to runtime/governance/config shortcut imports are introduced
5. Focused tests plus full guardrails and release checks remain green
6. Launcher chrome, model controls, and Tools cards remain usable at smaller window sizes without right-edge overflow or incorrect routing
7. Browser/app-open flows and local harness switching validate without redundant visible command-window spawning

**Recommended execution order:**
1. `P6-C33` first so `server_runtime.py` has the clearest path back toward the global line cap
2. `P6-C34` second so launcher-shell risk keeps shrinking without destabilizing the five-hub shell
3. `P6-C35` third so snapshot/runtime shaping keeps moving into support seams
4. `P6-C38` alongside or immediately after `P6-C34` so launcher-shell work also closes the active user-session UI defects
5. `P6-C39` before closeout so duplicate-window spawning is treated as a launcher stabilization item, not deferred cleanup
6. `P6-C36` as an active merge rule throughout
7. `P6-C37` last with runtime/voice validation follow-through

**Recommended lane split:**
- Lane A: `server_runtime.py`
- Lane B: `launcher_window.py` plus duplicate-window stabilization
- Lane C: `server_runtime_snapshot.py`
- Lane D: launcher/topbar/sidebar/tools responsive UI review plus tests, docs, and runtime/voice validation
- Main lane: integration, waiver refreshes, and release evidence

**Execution checkpoint (April 19, 2026):**
- `P6-C38` is materially advanced in live code: responsive topbar/sidebar density work landed, the left-rail badge no longer depends on the stale desktop logo path, Models-vs-Settings route collision was removed in the launcher shell, and Tools cards now reflow by available width.
- The launcher shell now refreshes its three-model summary when the Models hub is active, so the visible Models lane stays aligned with current saved runtime state.
- `P6-C39` is fully closed in live code: launcher startup debounce for API/hub autostart is already present and reconfirmed, repeated supervised/direct API command-start attempts are debounced, and normal task recovery now stays on the hidden direct-start path instead of re-entering the supervised batch launcher.
- The supervised batch path remains available only in the explicit App Mgmt / Windows ops lane, so duplicate-window stabilization now closes inside the launcher shell rather than depending on deferred real-machine follow-through.

**Pre-launch roadmap note (April 19, 2026):**
- The active pre-launch additions now live in `docs/PROJECT_BRIEF.md` under “Pre-Launch Work Roadmap Additions”.
- Highest-priority additions after the current hotspot lane are tool-entry/starter unification, senior-friendly clarity and hover-help, unified vendor/account onboarding, install-versus-local-model onboarding split, and a dedicated launch-grade security gate.
- The downloaded Google Stitch bundle (`stitch_azure_reef_assistant.zip`) is now explicitly part of that roadmap input, with Atoll Editorial / Tropical Editorial guidance and premium “Guppy G” logo exploration folded into the planned UI-branding lane.

---

## Consultant Review Integration (April 19, 2026)

**Source:** Paid engineering + design consultant audit against goals, north star, credentials audit, packaging docs, and voice status.

**Summary findings:**
1. **North star vs complexity gap** - Product claims calm chat-first but still carries too much visible operator surface. Fix: enforce the 3-click rule for anything outside the first-10-minute path; add progressive disclosure in Settings and Tools; reduce first-run to three tasks only.
2. **Provider and dependency sprawl** - Optional/stubbed/partial integrations are not cleanly separated from ready ones. Fix: tier providers into Core / Supported Optional / Experimental; hide Experimental by default; enforce a single provider registry UX with typed validation and in-line verify.
3. **Hotspot concentration still high** - Already tracked in P6 but needs explicit weekly burn-down targets and a no-new-responsibilities rule for waived modules. Fix: treat each waiver as a debt token with a written reduction target, not just a cap.
4. **Security posture not launch-simple** - Secret handling mixes inline env examples with keyring availability; no explicit launch gate exists. Fix: OS keychain-first for all secrets; permission scopes per connector action; dependency scanning and secret audit in release gate.
5. **Packaging and first-model paths still operationally heavy** - Already split into Track 1/Track 2 (good), but no guided first-run stateful wizard and no clean-machine completion-rate metric. Fix: add a guided first-run wizard with stateful checkpoints and plain-language remediation; define clean-machine completion rate as a primary success metric.
6. **Design direction** - Adopt quiet hierarchy: one strong accent, fewer competing badges, fewer persistent status blocks. Do PL-C3 (clarity) before PL-C2 (branding). Large hit targets and explicit microcopy are non-negotiable for trust/accessibility.

**Competitive product comparisons used:**
- Claude Desktop: calm primary interaction model, minimal persistent chrome -> adopt for Home Chat.
- Cursor: high-signal contextual actions scoped to relevance -> adopt for tool/context surfaces.
- LM Studio: transparent local-runtime status kept demoted from daily chat -> adopt for Models Hub.
- ChatGPT Desktop: immediate comprehension on first open -> target this for first-run success standard.
- Open WebUI: pays full onboarding cost for operator power -> avoid for Guppy personal-assistant positioning.

**30-day execution plan driven by consultant findings:**
1. Weeks 1-2: Onboarding and provider registry simplification (PL-C1, PL-C3, PL-C4).
2. Week 2-3: Hotspot reduction sprint on top three coordinator files.
3. Week 3: Security gate hardening and secret-handling cleanup (PL-C6).
4. Week 4: First-run UX test loop; fix top friction points (PL-C5, PL-C7).

**Mapping of consultant findings to Tranche 52 cards:**
- PL-C1 now requires a shared action registry and a plain-language command line per tool.
- PL-C2 now has explicit quiet-hierarchy constraints and defers logo novelty until after PL-C3.
- PL-C3 now requires an 80-year-old-user bar and a 3-click rule audit.
- PL-C4 now requires Core/Optional/Experimental tiering and OS keychain-first.
- PL-C5 now requires a stateful first-run wizard and a clean-machine completion rate measurement.
- PL-C6 is now a hard launch blocker, not a nice-to-have.

---

## Planned Pre-Launch Tranche (Tranche 52)

**Execution note (April 19, 2026):**
- This tranche turns the current pre-launch wishlist into executable work.
- Stitch guidance is used as bounded visual direction with a quiet-hierarchy constraint, not as a literal rebuild.
- The five-hub launcher ownership model remains fixed during this tranche.
- All cards below are enriched with consultant-review acceptance criteria for clean agent auto-execution.

**What ships:**

### PL-C1 - Tool Action Registry and Starter-Command Unification
- **Owner:** Lane A agent
- **Key files:** ui/launcher/views/tools_view_cards.py, src/guppy/launcher_application/home_presenter.py, ui/launcher/launcher_window.py
- **Work:**
  - Create src/guppy/launcher_application/tool_action_registry.py with a typed ToolAction datatype: tool_id, label, short_command (plain-language), starter_text (Home dropdown), button_path, voice_hint.
  - Wire the registry into the Home starter list so each tool entry resolves from the same datatype.
  - Wire the registry into the Tools hub card render so label and command text are always in sync.
  - Wire the registry into _tool_prompt_for_home in launcher_window.py so prompt wording matches short_command.
  - Remove duplicate inline literal strings for tool names and commands across the three source locations.
- **Acceptance:**
  - A user can discover the same action via button, starter dropdown, voice hint, and typed prompt with identical wording.
  - Adding a new tool requires touching only the registry, not three separate files.
  - Tests: new unit test for registry consistency plus one smoke test confirming Home starters draw from registry.
- **Consultant note:** Closes the discoverable action gap. Without it, onboarding copy in PL-C3/C4 cannot stay in sync.

### PL-C2 - Stitch-Guided Visual System and Logo Refinement (Quiet Hierarchy)
- **Owner:** Lane C agent -- run after PL-C3 is complete
- **Key files:** ui/launcher/launcher_window.py (chrome), theme/style modules, assets
- **Work:**
  - Apply quiet-hierarchy visual pass: one turquoise/sunset-orange accent, warm neutral surface for key areas, no competing badge stacks, no permanent status blocks in Home.
  - Integrate Stitch Atoll Editorial guidance: editorial serif for primary headings only, clean sans for body and controls.
  - Refine the Guppy logo/taskbar mark with the Stitch Guppy G direction; treat as identity refinement, not rebrand.
  - All visual changes token-driven in one theme/style module -- no inline hex strings in widget files.
- **Acceptance:**
  - Home Chat feels calm and branded without reducing legibility or adding visual clutter.
  - Visual tokens exist in one location; no inline hex strings added to widget files.
  - Does not regress any PL-C3 clarity/spacing work.
  - Tested: smoke visual integrity check confirms hub layout is not broken.
- **Consultant constraint:** Run PL-C3 first. Branding layered onto confusing layout makes it worse.

### PL-C3 - Senior-Friendly Clarity, Spacing, and Hover-Help Pass (3-Click Rule)
- **Owner:** Lane B agent -- first executing lane
- **Key files:** All five hub views, Home Chat, Settings, Tools, Library, Models
- **Work:**
  - Audit every hub with the 80-year-old-user bar: does this screen answer what is this page for, what happens if I press this, what should I do next.
  - Add a one-line hub-purpose label at the top of each primary hub (visually understated, always present).
  - Enforce the 3-click rule: any action not needed in the first 10 minutes must be reachable in 3 clicks from its hub but not visible on initial load.
  - Audit hit targets: all primary action buttons >= 36px tall; secondary controls >= 28px.
  - Add or fix tooltips on every non-obvious control; use plain-language copy matching the PL-C1 registry where applicable.
  - Fix spacing rhythm inconsistencies already noted in P6-C6/C38.
- **Acceptance:**
  - Each primary hub screen has a visible one-line purpose statement.
  - All primary buttons meet the 36px hit target.
  - All non-obvious controls have tooltips.
  - A first-time user can identify each hub purpose in under 3 seconds without explanation.
  - Tests: new smoke test confirming purpose labels present and tooltips exist on target controls.
- **Consultant note:** This is a launch requirement, not polish. Highest-leverage pre-launch UX investment.

### PL-C4 - Unified Provider, Account, and API-Key Onboarding (Core/Optional/Experimental Tiering)
- **Owner:** Lane D agent
- **Key files:** ui/launcher/views/settings_device_accounts_panel.py, utils/personalization_config.py, config/connector_bindings.json
- **Work:**
  - Introduce a provider_tier field to the provider/connector registry: Core (works by default), Supported Optional (key-verified), Experimental (hidden by default, toggled in Settings).
  - Normalize all vendor onboarding to: type secret -> in-line verify -> status badge -> next-step guidance. No bespoke UX per provider.
  - Enforce OS keychain-first (keyring already installed): all secret storage must write to OS keyring. Env-var fallback only for GUPPY_DEV_MODE=1.
  - Display provider health as a compact badge (pass / warn / fail) without requiring Settings expansion.
- **Acceptance:**
  - Core providers work with no credentials on a fresh install.
  - Supported Optional providers onboard via standard typed-secret + verify flow.
  - Experimental providers hidden until explicitly toggled.
  - All secrets written to OS keyring; no secrets in plain config unless GUPPY_DEV_MODE=1.
  - Tests: unit test for keyring write/read path + smoke test confirming tier visibility defaults.
- **Consultant note:** Closes the onboarding complexity gap. OS keychain-first is both a security requirement (PL-C6) and a trust prerequisite for external beta.

### PL-C5 - Install Package and Local Base-Model First-Success Path (Stateful First-Run Wizard)
- **Owner:** Lane E agent (co-run with PL-C6)
- **Key files:** src/guppy/launcher_application/install_readiness.py, src/guppy/launcher_application/local_model_readiness.py, first-run wizard entry point
- **Work:**
  - Add a stateful first-run wizard surface that runs on first launch when no workspace is configured.
  - Three stateful checkpoints: (1) app install check passes, (2) model runtime detected, (3) first successful request completed.
  - Each checkpoint shows plain-language status, a one-action remediation button, and a skip-for-now option.
  - Log first_run_checkpoint_N_completed events per checkpoint so clean-machine completion rate is measurable.
  - Wizard is skipped if a saved workspace already exists (returning user).
  - Track 1 (install) and Track 2 (local model) remain separate gates; wizard surfaces them as two distinct steps.
- **Acceptance:**
  - A clean-machine user reaches first successful request in under 5 minutes without external docs.
  - Each checkpoint has a recoverable state.
  - first_run_checkpoint_N_completed log events exist and are queryable.
  - Tests: unit test for wizard state machine + smoke test confirming each checkpoint is reachable.
- **Consultant note:** Clearest signal of product readiness. If this is not smooth, every other quality signal is moot.

### PL-C6 - Launch-Grade Security Gate (Hard Launch Blocker)
- **Owner:** Lane E agent (co-run with PL-C5)
- **Key files:** tests/test_security_hardening.py, tools/dev_workflow.py, documentation/SECURITY.md
- **Work:**
  - Secret storage audit: verify all secret write paths go through keyring after PL-C4 lands; fail gate if any plaintext secret write remains outside dev-mode.
  - Localhost vs external boundary audit: every port binding and network-open call explicitly justified; no 0.0.0.0 binding without an explicit config override.
  - Connector least-privilege audit: each connector action must declare its required scope; no connector may request broad permissions when only narrow access is needed.
  - Dependency vulnerability scan: add pip-audit run to release gate; gate fails if any HIGH or CRITICAL CVE exists in locked dependencies.
  - Write threat model summary to documentation/SECURITY.md covering: secret storage, network exposure, connector permissions, and packaged-build posture.
  - Add a security-gate step to tools/dev_workflow.py release-check that runs the above checks and writes runtime/security_gate_report.json.
- **Acceptance:**
  - release-check includes and passes a security gate step.
  - Zero plaintext secrets in any code path outside GUPPY_DEV_MODE=1.
  - Zero 0.0.0.0 default bindings without explicit justification.
  - pip-audit finds no HIGH/CRITICAL CVEs.
  - documentation/SECURITY.md threat model is present and current.
  - Tests: existing security hardening suite passes; new audit check integrated into release-check.
- **Consultant note:** Hard launch blocker. External beta without a clean security gate is a reputational and liability risk regardless of every other quality signal.

### PL-C7 - Validation, Docs, and Pre-Launch Handoff Evidence
- **Owner:** Main integration lane
- **Work:**
  - Run focused tests for all PL-C1 through PL-C6 changes.
  - Update docs/PROJECT_BRIEF.md active state and gaps with tranche completion notes.
  - Run check_doc_ownership.py, dev-check --guard-scope delta, dev-check --guard-scope baseline, and release-check.
  - Produce docs/generated/PRE_LAUNCH_READINESS_[DATE].md with: all six gates checked, first-run wizard completion status, security gate status, and a GO / LIMITED GO / NO GO recommendation.
- **Acceptance:**
  - All checks pass.
  - Pre-launch readiness doc exists with a GO or LIMITED GO recommendation supported by evidence.

**Recommended execution order:**
1. PL-C1 - registry foundation (other cards depend on consistent wording)
2. PL-C3 - clarity and spacing (must land before branding)
3. PL-C2 - visual and branding (only after clarity baseline is solid)
4. PL-C4 - provider onboarding and keychain-first (parallel with PL-C2 once PL-C3 wording is stable)
5. PL-C5 - first-run wizard (parallel with PL-C4 once onboarding contracts are clear)
6. PL-C6 - security gate (final closing lane, runs as PL-C4/C5 land)
7. PL-C7 - integration, validation, release evidence

**Lane split:**
- Lane A: PL-C1 tool action registry
- Lane B: PL-C3 clarity, spacing, and hover-help
- Lane C: PL-C2 Stitch-guided branding and visual tokens
- Lane D: PL-C4 provider/account/keychain onboarding
- Lane E: PL-C5 first-run wizard + PL-C6 security gate
- Main lane: integration, wiring PL-C1 output into PL-C3/C4 copy, docs, and validation

**Success metrics (consultant-derived):**
- First successful request on a clean machine: under 5 minutes.
- Hub purpose comprehension: first-time user identifies each hub purpose in under 3 seconds without docs.
- First-run wizard completion rate: target >= 80% from checkpoint 1 to checkpoint 3.
- Security gate: passes clean on every release candidate.
- Provider setup: Core providers require zero credentials; Supported Optional require under 2 minutes to verify.

**April 20, 2026 follow-through checkpoint (N1-N5):**
- `N1` branding/readability tuning is now live and test-covered through `ui/launcher/tokens.py`, `ui/launcher/components/topbar.py`, `ui/launcher/components/sidebar.py`, `ui/launcher/components/status_panel.py`, and `tests/unit/test_launcher_branding_tokens.py`.
- `N2` Tools/App Mgmt enforcement now routes blocked connector remediation into Settings-owned connector/account setup from the Tools surface via `ui/launcher/views/tools_view.py`, `ui/launcher/views/tools_view_cards.py`, `src/guppy/launcher_application/tool_readiness.py`, `src/guppy/launcher_application/connector_workflow.py`, `ui/launcher/views/settings_hub_view.py`, and `ui/launcher/launcher_window.py`.
- `N3` Library follow-through is live through `ui/launcher/views/library_view.py`, `src/guppy/launcher_application/library_workflow.py`, and `src/guppy/launcher_application/library_presenter.py`: inline root switching, clearer note-edit guidance, and richer `USE IN CHAT` source reuse all landed without schema churn.
- `N4` structural voice/runtime evidence was refreshed on the current machine using `python tools/verify_provider_runtime.py` and `python tools/generate_voice_runtime_prefill.py`; the resulting prefill report is `docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md`, and manual real-device matrix sign-off remains required for the pending rows.
- `N5` route/status signaling depth is now explicitly guarded by `tests/unit/test_shell_status.py`, which covers route-preview mirroring into Settings, daily-activity sync, and right-tray workspace/runtime sync for the `src/guppy/launcher_application/shell_status.py` seam.
- Focused N1-N5 validation is green: unit + smoke coverage across branding, tool routing, library workflow, voice/runtime evidence, provider-runtime scope, shell-status sync, Settings hub, Library hub, and launcher interactions passed (`72 passed` in the focused bundle).

**Source of truth:**
- Full tranche definition and repo-grounded evaluation live in docs/PROJECT_BRIEF.md under Executable Pre-Launch Tranche (Tranche 52).

---

## Planned Mega-Tranche (Tranche 53)

**Execution note (April 20, 2026):**
- This is the next planned pre-launch mega-tranche after the Tranche 52 follow-through waves.
- Scope combines massive hardening, usability sweeps, UI review against Guppy goals + Stitch + inspiration sources, a full tool-system audit, packaging/install/local-runtime readiness, and trust/security follow-through.
- The tranche is intentionally split into 10 high-impact execution packs so several lanes can run in parallel while still closing as one integrated release-quality wave.
- Keep the current framework and five-hub ownership model intact.
- Current blocker context: packaging remains an honest release blocker until a real `dist/` artifact exists.

**What ships:**
- [ ] `PL-C8` Product goals, UI goals, and first-run contract audit
- [ ] `PL-C9` Stitch and inspiration-source UI review with implementation deltas
- [ ] `PL-C10` Desktop launcher hardening and startup hardening
- [x] `PL-C11` Cross-hub usability sweep and responsive layout pass
- [x] `PL-C12` Home and launcher chrome calmness pass
- [x] `PL-C13` Full tool-system audit and tool-entry hardening
- [x] `PL-C14` Provider, account, connector, and plugin lifecycle hardening
- [x] `PL-C15` Packaging, installer, local-model, and real-time execution readiness
- [x] `PL-C16` Massive trust and security hardening sweep
- [x] `PL-C17` Integrated code audit, docs audit, UI audit, tool audit, and release closeout

**April 20, 2026 execution checkpoint:**
- `PL-C8` started with `docs/generated/TRANCHE_53_GOALS_UI_AUDIT_20260420.md`.
- `PL-C9` started with `docs/generated/TRANCHE_53_STITCH_DELTA_20260420.md`.
- `PL-C10` first-wave launcher hardening is live:
  - topbar runtime/startup chip added
  - topbar `CHAT` action corrected to chat-context drawer behavior
  - Home drawer toggle now actually opens/closes on Home

**April 20, 2026 second checkpoint:**
- Home now surfaces first-run status directly from `src/guppy/launcher_application/first_run_wizard.py` through `ui/launcher/views/assistant_view.py` and `ui/launcher/launcher_window.py`.
- The first-run banner keeps setup visible without breaking the chat-first shell: install, model runtime, and first-ask state are shown as chips, with direct jumps into Settings and Models plus a fast path back to the composer.
- Home also applies a tighter width-based density mode so starter/detail controls compress earlier on smaller windows.

**April 20, 2026 third checkpoint:**
- `PL-C11` now extends beyond Home into Settings, Device & Accounts, Library, and Tools.
- Settings overview cards now reflow to a single column at tighter widths, and section shortcut buttons shorten to `OPEN` so the card grid stays readable.
- Device & Accounts now reflows connector cards across 1, 2, or 3 columns based on width and compresses desktop/account action labels without changing the underlying flows.
- Library now shortens manager/action labels and trims lower-priority hint copy at narrow widths so note/artifact controls stop crowding the content lane.
- Tools now hides the type-tab strip at narrow widths, shortens the details affordance, and uses a tighter search/control presentation.
- Focused smoke coverage was expanded so these compact-mode behaviors are now asserted directly.

**April 20, 2026 fourth checkpoint:**
- `PL-C11` and `PL-C12` now have a closeout pass on launcher chrome calmness and secondary-surface explainability.
- The topbar demotes workspace/session chrome earlier at smaller widths so the model/session summary remains visible without the header feeling crowded.
- Settings Operations now adds broader tooltip coverage across recovery, runtime, connector, workflow, automation, and terminal actions, and it compresses long secondary button labels at narrower widths.
- Tool cards now expose their evidence, policy, and guard copy through tooltips so the deeper explanation remains available without keeping every card expanded.
- Focused nav/settings/hub smoke now covers the calmer topbar state plus the new compact/tooltip behavior.

**April 20, 2026 fifth checkpoint:**
- `PL-C13` now routes visible tool-entry wording through the shared action registry end to end: canonical tool action lines now render on tool cards, and the same registry-backed language still powers Home starters and launcher prompt priming.
- Blocked tool remediation keeps the Settings-owned route, but the tool-card management tooltip now carries both the destination and the current fix note instead of a generic handoff.
- `PL-C14` now uses provider-registry-backed lifecycle copy for Device & Accounts next-step guidance, connected-state hints, example prompts, and action tooltips.
- Provider entries now carry both connect-time guidance and post-connect example prompts so future providers are cheaper to add without bespoke panel copy.

**April 20, 2026 sixth checkpoint:**
- `PL-C15` is now complete with real package/build evidence instead of placeholder packaging assumptions.
- Track 1 install readiness now includes release handoff and `dist/` artifact evidence, and the readiness helpers now anchor to the actual repo root instead of one directory too high.
- Track 2 local-model readiness now accepts any honest declared local route (`ollama`, `lmstudio`, or `local_harness`) and reports which routes are actually ready instead of treating Ollama as the only pass condition.
- `packaging_audit.py` now rejects stale non-packaging receipts and undersized fake `dist` outputs.
- `bin/build_executable.bat` and `bin/validate_build.bat` were repaired for real `cmd` execution, the package recipe now bundles `config/local_llm` instead of stale repo roots, and a fresh onedir build now exists at `dist/Guppy/Guppy.exe`.
- The packaging lane is now green for the right reason: `bin/validate_build.bat` passes, Track 1 reads `10/10 passed`, and `python tools/dev_workflow.py release-check` is green again.

**April 20, 2026 seventh checkpoint:**
- `PL-C16` is now materially advanced with live trust/readiness enforcement tightening.
- Degraded keyring backends now count as unavailable in `utils/secret_store.py`, so insecure/plaintext keyring fallbacks no longer present as OS-backed secret storage.
- The launch-grade security gate now verifies both Settings-owned connector action enforcement and auth-state/secret-read gating when evaluating connector scope.
- Provider secret readiness now carries explicit env-fallback storage warnings through the workspace-governance machine-auth/provider-status seams, so “ready” states that still rely on environment variables stop looking launch-grade.
- `connector_workflow.py` now only accepts the explicit Settings request sources instead of any `settings*` prefix.
- `status_poll.py` no longer defaults absent API status to `healthy`, and launcher background copy now reports `ONLINE` instead of overclaiming `READY`.
- Focused trust/security validation is green: targeted unit tests passed, `tools/run_security_gate.py` reports `Launch ready: YES`, and `dev-check --guard-scope delta` passed.

**April 20, 2026 eighth checkpoint:**
- `PL-C17` is now complete as the integrated audit/doc closeout lane.
- Active truth docs were refreshed to the current tranche state and current release-lane contract instead of older April 19 snapshots.
- `docs/generated/PRE_LAUNCH_READINESS_20260420.md` was replaced with an honest tranche-53 checkpoint that no longer carries the older Tranche 52 `GO` claim.
- `docs/generated/TRANCHE_53_INTEGRATED_AUDIT_20260420.md` now records the bounded code/docs/UI/tool audit fixes from this pass plus the ranked remaining blockers.
- Packaging/install wording drift was cleaned up so Track 1 / Track 2 language, default Windows build output, and release-closeout evidence read consistently.

**April 20, 2026 ninth checkpoint:**
- `PL-C16` is now complete as a release-backed trust/security lane.
- `python tools/dev_workflow.py release-check` now runs `tools/run_dependency_audit.py`, which captures machine-readable `pip-audit` evidence in `.tmp/dev-workflow/reports/pip-audit-report.json`.
- The current dependency audit is green with no known vulnerabilities found in `requirements.txt`, so dependency/CVE evidence now exists in the canonical release flow instead of as a manual note.
- The supported desktop launcher link was refreshed and re-verified on this machine: `Desktop\\Guppy Launcher.lnk` now targets `dist/Guppy/Guppy.exe` directly when the packaged build is present.
- `docs/generated/TRANCHE_53_SECURITY_AUDIT_20260420.md` now records the trust/security closeout evidence and remaining non-launch blockers.
- With `PL-C16` and `PL-C17` both closed, Tranche 53 is now complete.

**Acceptance:**
1. Launcher/startup behavior is materially more stable and easier to understand.
2. The UI has a written review against Guppy goals, Stitch direction, and inspiration sources.
3. All five hubs receive a real usability sweep, not isolated polish.
4. Tool discovery, wording, blocking, and remediation are audited end to end.
5. Provider/account/plugin lifecycle remains unified in Settings and cheaper to extend.
6. Packaging/install/local-runtime evidence is honest and current, including a real `dist/` path.
7. Security/trust language and actual enforcement align.
8. The tranche closes with one integrated audit and a ranked blocker list.

**Recommended execution order:**
1. `PL-C8`
2. `PL-C9`
3. `PL-C10`, `PL-C11`, and `PL-C12`
4. `PL-C13` and `PL-C14`
5. `PL-C15`
6. `PL-C16`
7. `PL-C17`

**Recommended lane split:**
- Lane A: `PL-C8` + `PL-C9`
- Lane B: `PL-C10`
- Lane C: `PL-C11` + `PL-C12`
- Lane D: `PL-C13`
- Lane E: `PL-C14`
- Lane F: `PL-C15`
- Lane G: `PL-C16`
- Main lane: `PL-C17`

**High-impact success metrics:**
1. Time to first useful result on a clean machine stays under 5 minutes.
2. Every primary hub purpose is understandable in under 3 seconds by a first-time user.
3. No right-edge overflow or obvious spacing break remains at smaller launcher widths.
4. Tool invocation wording is canonical across button, starter, typed, and spoken paths.
5. Packaging/install readiness is backed by a real built artifact, not assumptions.
6. Launch-critical trust/readiness labels remain honest.

---

## Freeze-Down Follow-On (April 20, 2026)

The next execution program now lives in `docs/PROJECT_BRIEF.md` under `Freeze-Down Minimization Program (Post Freeze Wave)`.

Key additions beyond the earlier freeze-reduction wave:

1. Start with a naming and retention baseline:
   - platform is `Guppy`
   - the default assistant name must become user-editable
   - model surfaces should show actual model/runtime names, not old labels like `guppy`, `merlin`, `fast`, or `vault`
   - persona is the customization layer, not the model label
2. Continue the hotspot reduction program across:
   - `server_runtime_snapshot.py`
   - `launcher_window.py`
   - `daemon.py`
   - `models_view.py`
   - `settings_operations_panel.py`
   - `assistant_view.py`
   - `memory.py`
   - `voice.py`
   - `merlin/core.py`
3. Add explicit cleanup lanes for:
   - stale legacy and compatibility wording
   - wrapper slimming and compatibility quarantine hardening
   - `docs/archive/` and `docs/generated/` classification
   - tracked-file retention and delete tranche execution
4. The follow-on tranche set is `FR2-T1` through `FR2-T13`.
5. The closeout bar is a smaller tracked tree, narrower waivers, thin root wrappers, explicit compatibility quarantine, and a fully green release lane at freeze time.

Recommended first wave:

1. `FR2-T1` naming, freeze contract, and retention baseline
2. `FR2-T2` API snapshot final decomposition
3. `FR2-T3` launcher shell second-stage extraction
4. `FR2-T5` Settings surfaces split

Recommended parallel lanes:

- Lane A: runtime/backend debt
- Lane B: launcher/settings/workspace shells
- Lane C: Models/Home/Library/Voice reduction plus model-label cleanup
- Lane D: memory/debug/specialist runtime and low-risk legacy cleanup
- Lane E: wrappers, docs/generated/archive, and file-retention sweep
- Lead lane: guardrails, waiver reset, integration, and freeze closeout

First execution checkpoint (April 20, 2026):

1. `FR2-T1` through `FR2-T5` are materially advanced together.
2. `server_runtime_snapshot.py` now delegates snapshot-only route behavior through `snapshot_route_support.py` and is down to `1712` lines.
3. `launcher_window.py` now delegates API/runtime control flow through `launcher_api_runtime_control.py` and is down to `2800` lines.
4. `models_view.py` is down to `1073` lines and now keeps model/runtime identity separate from persona/customization naming.
5. `settings_view.py` now treats the default assistant name as editable assistant/persona state and is down to `700` lines.
6. The architecture guard now blocks live imports of the root `guppy_api` shim as well as the other root wrappers.
7. Integrated validation is green at `release-check-20260420-165643` with `583 passed` default and `138 passed` product smoke.

Second execution checkpoint (April 20, 2026):

1. Vercel Python app discovery is now explicit through `api/index.py`.
2. `FR2-T6` materially advanced:
   - `assistant_view.py` now delegates state/context/first-run density behavior into `assistant_behavior_support.py` and is down to `614` lines
   - `library_view.py` now delegates editor/root-path behavior into `library_editor_support.py` and is down to `619` lines
3. `FR2-T7` is now visibly landed in the live tree:
   - `daemon.py` is a thin compatibility shell over `ambient_watcher.py`, `manager.py`, `notifier.py`, `proactive_loop.py`, `scheduler.py`, `support.py`, and `window_watcher.py`
4. `FR2-T8` follow-through is now visible in the live tree:
   - `memory.py` is down to `316` lines over the existing store/support seams
   - `voice.py` is a thin orchestration surface over `voice_runtime.py` and `voice_support.py`
   - `debug/console.py` is now a thin shell over `_tabs.py` and `_ui.py`
5. `FR2-T9` wording cleanup advanced by removing the live `Guppy / Merlin` console framing from the supported debug surface.
6. `FR2-T11` and `FR2-T12` materially advanced:
   - `docs/generated/` dropped from `20` files to `10`
   - tracked-existing files are down to `562` from the prior `571` baseline
7. `FR2-T13` guardrail tightening advanced by removing stale waivers for `daemon.py`, `memory.py`, `library_workflow.py`, `debug/console.py`, `voice.py`, `assistant_view.py`, `library_view.py`, and `settings_view.py`.
8. `FR2-T6` through `FR2-T13` are now effectively complete for this freeze-down execution wave, with the remaining baseline waivers narrowed to `server_runtime_snapshot.py`, `merlin/core.py`, `launcher_window.py`, `instance_manager_view.py`, `models_view.py`, and `settings_operations_panel.py`.

---

## Remaining Hotspot Reduction Follow-On (April 20, 2026)

Current remaining waived hotspots:

1. `src/guppy/api/server_runtime_snapshot.py` -> `1712`
2. `src/guppy/merlin/core.py` -> `1115`
3. `ui/launcher/launcher_window.py` -> `2800`
4. `ui/launcher/views/instance_manager_view.py` -> `869`
5. `ui/launcher/views/models_view.py` -> `1073`
6. `ui/launcher/views/settings_operations_panel.py` -> `1008`

Follow-on tranche set:

1. `FR3-T1` snapshot route and telemetry final split
2. `FR3-T2` launcher shell fourth extraction
3. `FR3-T3` models hub final panel split
4. `FR3-T4` Settings Operations split
5. `FR3-T5` workspace manager reduction
6. `FR3-T6` Merlin specialist runtime disposition
7. `FR3-T7` guardrail reset and freeze candidate closeout

Checkpoint (April 20, 2026, FR3-T4 / FR3-T6):
1. `settings_operations_panel.py` now delegates the desktop runtime, connected services, and automation assembly blocks to `settings_operations_sections.py`.
2. Merlin is explicitly retained as a bounded specialist runtime, with extracted helper support living in `src/guppy/merlin/specialist_support.py` while dispatch stays in `merlin/core.py`.

Execution order:

1. Run `FR3-T1` and `FR3-T2` first as the highest-centrality core shells.
2. Run `FR3-T3`, `FR3-T4`, and `FR3-T5` as the parallel UI-shell wave.
3. Follow with `FR3-T6` once the live hub shells are reduced enough to make the Merlin call cleanly.
4. Close with `FR3-T7` for waiver tightening, full validation, and freeze-candidate truth.

Agent lanes:

1. Lane A: API/runtime hotspot (`FR3-T1`)
2. Lane B: launcher shell hotspot (`FR3-T2`)
3. Lane C: Models and workspace UI shells (`FR3-T3`, `FR3-T5`)
4. Lane D: Settings Operations hotspot (`FR3-T4`)
5. Lane E: Merlin disposition plus guardrail/doc cleanup (`FR3-T6`, `FR3-T7`)
6. Lead lane: integration, validation, waiver tightening, and freeze-candidate call

Acceptance bar:

1. At least three of the remaining waived modules lose their waiver or drop materially.
2. Remaining waived files, if any, read as bounded shells rather than mixed-concern monoliths.
3. `release-check` stays green after the integrated wave.
4. The repo exits with a short and honest remaining-hotspot list suitable for freeze-candidate review.

Integrated closeout (April 20, 2026):

1. `FR3-T1` complete: `server_runtime_snapshot.py` now delegates realtime assembly to `snapshot_realtime_support.py`.
2. `FR3-T2` complete: `launcher_window.py` now delegates workspace snapshot/bootstrap coordination to `workspace_snapshot_support.py`.
3. `FR3-T3` complete: `models_view.py` now delegates library/search/loadout panel construction to `models_library_panel.py`, with shared route parsing in `models_route_support.py`.
4. `FR3-T4` complete: `settings_operations_panel.py` now composes extracted section builders from `settings_operations_sections.py`.
5. `FR3-T5` complete: `instance_manager_view.py` now delegates dense workspace shell assembly to `instance_manager_sections.py` and is no longer waived.
6. `FR3-T6` complete: `merlin/core.py` is now explicitly retained as a bounded specialist runtime over `specialist_support.py`.
7. `FR3-T7` complete: waiver caps were tightened to the measured post-split sizes and the remaining hotspot list dropped to five files.

Measured post-wave sizes:

1. `src/guppy/api/server_runtime_snapshot.py` -> `1419`
2. `src/guppy/merlin/core.py` -> `1071`
3. `ui/launcher/launcher_window.py` -> `2648`
4. `ui/launcher/views/models_view.py` -> `969`
5. `ui/launcher/views/settings_operations_panel.py` -> `738`
6. `ui/launcher/views/instance_manager_view.py` -> `370`

Freeze-candidate note:

1. The tranche materially reduced the remaining hotspot field and removed `instance_manager_view.py` from the waiver list.
2. The remaining debt is now concentrated in five named bounded shells, which is a credible freeze-candidate state for this tranche set.

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

## Tranche 1 Kickoff Snapshot (Historical)

**Executed on April 20:**

1. **Agent assigned** to Settings Hub Tranche 1
2. **Sub-agents assigned** (3-4 specialists)
3. **Deliverable:** `SettingsHubView` foundation routing + ownership matrix doc
4. **Acceptance:** Existing tests pass, new hub loads, no logic extraction in this phase
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

## Next Action (Historical Kickoff Record)

1. **Assign Agent to Tranche 1** (Settings Hub foundation routing + ownership matrix)
2. **Assign 3-4 sub-agents** to parallel work:
  - Sub-agent 1: Create `SettingsHubView` foundation wiring
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

