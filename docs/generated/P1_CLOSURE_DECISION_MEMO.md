# P1 Closure Decision Memo

**Last updated: April 18, 2026**
**Track:** P1 — UI Bugfix + Navigation Simplification
**Target window:** April 17 – April 24, 2026
**Decision date:** April 18, 2026

---

## P1 Acceptance Criteria

> *"A first-run user can tell where Chat, Workspaces, Library, and Settings live without learning the operator surfaces first."*
>
> — `docs/PROJECT_BRIEF.md`, Execution Board

Secondary bar (Roadmap Knife, P1 Keep column): navigation clarity, calmer hierarchy, fewer visible controls, cleaner first-run path, obvious Chat / Workspaces / Library / Settings flow, operator shortcuts demoted, status noise reduced, duplicate navigation affordances removed.

---

## Current State Assessment

### P1 Keep Items

| Keep Item | Status | Evidence (Handoff Entry) |
|---|---|---|
| Navigation clarity | ✅ Done | Entry 18: sidebar hides advanced destinations behind explicit toggle; daily path reads first. Entry 28: shell now emphasizes `HOME`, `WORKSPACES`, `LIBRARY`, `SETTINGS`, `MY PC`, `LOCAL LLM`. |
| Calmer hierarchy | ✅ Done | Entry 19: right tray reads as quieter workspace-context drawer; primary actions visible, write/code/shell behind `DETAILS` reveal. Entry 22: calmer daily-path wording throughout. |
| Fewer visible controls | ✅ Done | Entry 18: top bar groups notifications + terminal access in a lower-emphasis `DETAILS` capsule. Entry 38: workspace details and starters collapsed by default; right drawer hidden by default. |
| Cleaner first-run path | ✅ Done | Entry 36: Home no longer implies Library sources are attached when none exist; empty-state guidance is explicit. Entry 39: Library root saves have inline validation and user-visible guidance. |
| Obvious Chat / Workspaces / Library / Settings flow | ✅ Done | Entry 38: `SETTINGS` now opens the dedicated settings view; diagnostics/automation moved to separate advanced surface. Settings gained subsection navigation so runtime defaults, persona config, and advanced-surface handoff live in a dedicated area. |
| Operator shortcuts demoted | ✅ Done | Entry 18: sidebar hides advanced operator destinations behind explicit toggle. Entry 38: left rail is collapsible; advanced surface separated from Settings. |
| Status noise reduced | ✅ Done | Entry 21: Home splits primary workspace context from on-demand system details; hero subtitle stays role-aware instead of doubling as activity ticker. Entry 22: `DETAILS` replaces `SYSTEM`; `daily workspace assistant` replaces `local workspace assistant`. |
| Duplicate navigation affordances removed | ✅ Done | Entry 38: stack order corrected so `SETTINGS` does not compete with diagnostics/automation for the same conceptual slot. |

### P1 Demote Items (confirmed demoted)

| Item | Status |
|---|---|
| Operator shortcuts on primary surface | ✅ Demoted — behind toggle |
| Status noise on default chat surface | ✅ Reduced — moved to `DETAILS` capsule |
| Duplicate navigation affordances | ✅ Removed — single Settings destination, single advanced surface |

### P1 Defer Items (confirmed deferred)

| Item | Status |
|---|---|
| Cosmetic redesign work that does not improve comprehension | ✅ Deferred — not pursued in P1 tranches |

---

## Remaining Risks and Gaps

The following items from `docs/PROJECT_BRIEF.md` Current Gaps are relevant to P1:

| Gap ID | Description | P1 Impact |
|---|---|---|
| Gap 1 | Agent Tools vs App Mgmt framing is clearer in the UI, but deeper execution flow and enforcement still need to catch up with the split. | Low-medium. The navigation distinction is now visible (Handoff entry 38), but if a first-run user clicks into Agent Tools expecting Settings-level config, the framing gap could still cause confusion. Does not block the acceptance criterion but is adjacent to it. |
| Gap 8 | Transcript/composer rhythm, starter priority, and broader persistence polish still need one more pass before the May 22 checkpoint. | Low. This is primarily a P3 concern. Does not affect whether a first-run user can locate the four primary destinations. |

No Current Gaps directly block the P1 acceptance criterion as stated.

---

## Recommendation

**CONDITIONAL CLOSE**

**Rationale:**
All eight P1 keep items are demonstrably addressed through Handoff entries 18–38 as of April 18, 2026. The primary acceptance criterion — a first-run user can identify Chat, Workspaces, Library, and Settings without learning operator surfaces — is met structurally: the shell now leads with those four destinations, operator surfaces are demoted behind toggles, and status noise is confined to the `DETAILS` capsule.

The conditional flag applies because:
1. The acceptance criterion has not yet been validated with a real first-run user session (no recorded user testing on the new shell as of this memo).
2. Gap 1 (Agent Tools vs App Mgmt execution flow) could confuse a first-run user navigating from Settings into the advanced surface, particularly before the deeper execution-flow catch-up lands.

**Close condition:** P1 can be declared fully closed when a single real-device smoke walkthrough by a tester unfamiliar with the current shell confirms the four destinations are self-evident on first launch, and Gap 1 does not surface as a blocker during that walkthrough.

---

## Next Action Items (if Conditional or Keep Open)

1. **Run a first-run walkthrough** — have one tester unfamiliar with the current shell launch Guppy cold and locate Chat, Workspaces, Library, and Settings using only the UI. Record result in the sign-off table below.
2. **Verify Agent Tools vs Settings boundary** — confirm that navigating from Settings into the advanced surface does not leave a first-run user stranded in an operator-facing surface without a clear "back to daily path" affordance. File a P4 item if needed (demote is the P4 target, not P1).
3. **Close Gap 1 ticket for P1 scope** — explicitly note in the P4 triage that the execution-flow catch-up for Agent Tools vs App Mgmt is a P4 item, not a P1 re-opener.

---

## Sign-Off

| Decision | Decided By | Date |
|---|---|---|
| *(CONDITIONAL CLOSE / CLOSE / KEEP OPEN)* | — | — |

---

## Appendix: Relevant Handoff Entries

| Entry | Date | Summary |
|---|---|---|
| 18 | April 17, 2026 | Sidebar hides advanced destinations; top bar groups noise into `DETAILS` capsule. |
| 19 | April 17, 2026 | Right tray reads as quieter workspace-context drawer; write/code/shell actions behind `DETAILS` reveal. |
| 21 | April 17, 2026 | Home splits primary context from on-demand system details; hero subtitle stays role-aware. |
| 22 | April 18, 2026 | Calmer daily-path wording: `DETAILS`, `daily workspace assistant`, role-aware header copy. |
| 28 | April 18, 2026 | Shell emphasizes `HOME`, `WORKSPACES`, `LIBRARY`, `SETTINGS`, `MY PC`, `LOCAL LLM`; smoke stayed green. |
| 36 | April 18, 2026 | First-run daily path tightened; empty-state guidance explicit; no implied context when none exists. |
| 38 | April 18, 2026 | Compact identity row replaces dashboard hero; optional details collapsed by default; `SETTINGS` corrected to dedicated settings view; Settings gained subsection navigation; full launcher smoke green. |
