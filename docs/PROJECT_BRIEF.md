# Guppy Project Brief

Last updated: 2026-04-28

## Purpose

Guppy is a Windows-first, local-first personal assistant focused on:

1. Fast response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear persona, model, and voice customization.

Product direction is constrained by `docs/GUPPY_PRODUCT_NORTH_STAR.md` and `docs/PRODUCT_FEATURE_FILTER.md`.

---

## Active Doc Contract

1. `docs/PROJECT_BRIEF.md` is the single active status, roadmap, and handoff source.
2. `README.md` is stable setup, operations, and repo-orientation reference only.
3. `documentation/` owns canonical technical architecture, security, and truth-audit material.
4. `docs/archive/` is historical only and does not define active priorities.
5. The archived pre-merge roadmap lives at `docs/archive/root-history/ROADMAP_2026-04-17.md`.

### Canonical Roadmap Rule (Cleanup)

1. `docs/PROJECT_BRIEF.md` is the only file allowed to hold active execution priorities, status, tranche checkpoints, and handoff sequencing.
2. `ROADMAP.md` must remain a pointer-only compatibility stub and must not duplicate active priorities.
3. If wording differs between files, `docs/PROJECT_BRIEF.md` wins and the pointer docs should be aligned in the same pass.

### North-Star Surface Mapping (Cleanup)

1. The north-star doc names four primary product surfaces: Chat, Workspaces, Library, Settings.
2. The current launcher executes a five-hub shell: Home, Models, Tools, Library, Settings.
3. Mapping rule for consistency:
   - `Home` maps to the north-star `Chat` daily path.
   - `Workspaces` remains first-class behavior and persistence but is intentionally surfaced through Home context/topbar controls instead of a separate primary nav destination.
   - `Models` and `Tools` are implementation hubs that support calm daily flow while remaining subordinate to the north-star daily path.

---

## 5-Hub Architecture — Single Truth Per Domain

Guppy's launcher is organized into exactly five destination hubs. Each hub owns one domain completely. No domain bleeds between hubs. Home Chat is the daily surface; all hubs are reachable from it but never clutter it.

### Hub 1 — Home Chat

**File:** `ui/launcher/views/assistant_view.py`
**Truth for:** The chat window. All active conversation, context, workspace state, and voice input.
**Does not own:** Settings, tools, models, or library internals. Those hubs are accessible via navigation, not embedded here.
**Goal:** One clean, excellent chat surface. No operator noise. No diagnostics panels. No model internals. Just the conversation and its live context.

### Hub 2 — Settings Hub

**File:** `ui/launcher/views/settings_hub_view.py` (composes `settings_view.py`, `settings_device_accounts_panel.py`, `settings_operations_panel.py`, `settings_connector_panel.py`, `settings_terminal_panel.py`)
**Truth for:** Every configuration, credential, and diagnostic in one place.

- API keys and account credentials (all providers)
- User preferences and runtime defaults
- System diagnostics and performance logs
- Recovery tools and system daemon controls
- Connector bindings and endpoint governance
**Does not own:** Model selection, tool management, or library content.

### Hub 3 — Tools Hub

**File:** `ui/launcher/views/tools_view.py`
**Truth for:** Everything about agent capabilities.

- All available tools and their current status
- Adding new tools and removing stale ones
- Tool permissions per workspace
- Tool commands and invocation patterns
- Tool debugging and execution traces
**Does not own:** Model routing, credentials, or library files.

### Hub 4 — Models Hub

**File:** `ui/launcher/views/models_hub_view.py` (composes `models_view.py`, `local_llm_view.py`, `voices_view.py`)
**Truth for:** Every model and persona decision in one place.

- Model loader, installer, uninstaller, and loadout control (stable main + spawnable sub models)
- Multi-provider model selector and route mixer (MAIN / SUB A / SUB B)
- Sub-agent selector
- Voice assignment, voice preview, and voice-backend readiness under the same model surface
- Model health, benchmark, and comparison evidence
- Local-runtime readiness for Ollama, Lemonade, LM Studio discovery, harness planning, and Hugging Face local planning
**Does not own:** Credentials or API-key storage (Settings Hub owns those), tool permissions, or library files.

### Hub 5 — Library Hub

**File:** `ui/launcher/views/library_view.py` (consolidates `library_view_components.py`)
**Truth for:** All files, notes, media, and artifacts.

- Workspace file browser with approved roots
- Pinned notes and saved artifacts
- Media management and media player
- Direct "use in chat" handoff to Home Chat
**Does not own:** Model routing, tool configuration, or system credentials.

---

## Surface Map

| Hub | Primary View | Consolidated Views | Navigation Label |
| --- | --- | --- | --- |
| Home Chat | `assistant_view.py` | — | HOME |
| Settings Hub | `settings_hub_view.py` | `settings_view.py`, `settings_device_accounts_panel.py`, `settings_operations_panel.py`, `settings_connector_panel.py`, `settings_terminal_panel.py` | SETTINGS |
| Tools Hub | `tools_view.py` | — | TOOLS |
| Models Hub | `models_hub_view.py` | `models_view.py`, `local_llm_view.py`, `voices_view.py` | MODELS |
| Library Hub | `library_view.py` | `library_view_components.py` | LIBRARY |

Views no longer on the top-level nav rail: `instance_manager_view.py` (Workspaces — accessible from Home context), `runtime_routing_view.py` (folded into Models Hub), `voices_view.py` (folded into Models Hub), `local_llm_view.py` (folded into Models Hub), `my_pc_view.py` (folded into Settings Hub), `advanced_view.py` (folded into Settings Hub).

---

## Primary Product Surface

1. Default entrypoint: `guppy_launcher.py`
2. Canonical launcher path: `src/guppy/apps/launcher_app.py` plus `ui/launcher/`
3. Canonical launch helper: `src/guppy/cli/launch.py`
4. Supported launch CLI surfaces: `guppy`, `launcher`, `guppyprime`, `hub`, and `api`
5. Default runtime instance layout: foreground `guppy-primary` with optional `builder-collab`

---

## Runtime Services

1. API: `src/guppy/api/server.py`, composed by `src/guppy/api/server_runtime.py`, launched from `guppy_api.py`
2. Hub and tray: `src/guppy/apps/hub_app.py`, launched from `guppy_hub.py`
3. Daemon: `src/guppy/daemon/daemon.py`

## Backend Boundary (Freeze)

Boundary intent: preserve the current five-hub product ownership while freezing what counts as backend-owned versus launcher-entry compatibility surfaces.

1. Backend-owned modules (authoritative runtime/business logic)
   - `src/guppy/api/` (routers, auth, runtime/status services, telemetry/query surfaces)
   - `src/guppy/runtime_application/`, `src/guppy/workspace_governance/`, `src/guppy/experience_config/`, `src/guppy/launcher_application/` seam contracts/services
   - `src/guppy/daemon/` and backend service helpers under `src/guppy/api/services_*`
2. Thin wrappers and entrypoints (launch-only, no domain ownership)
   - root shims: `guppy_api.py`, `guppy_hub.py`, `app.py`
   - API module shim: `src/guppy/api/server.py` forwarding to `src/guppy/api/server_runtime.py`
   - CLI/app composition roots: `src/guppy/apps/*`, `src/guppy/cli/launch.py`
3. Quarantined UI/legacy paths (compatibility only; no new feature ownership)
   - `compat_shims/legacy_surfaces/` and other `compat_shims/` legacy facades
   - historical specialist surfaces (Merlin/Council) and other legacy-only launch paths
   - removed/legacy launcher view surfaces already folded into the five canonical hubs

---

## Current State Snapshot

1. M1 closed April 13, 2026.
2. M2 became active April 15, 2026.
3. As of April 19, 2026: the 5-hub architecture is the canonical product structure. All planning and implementation must align to it.
4. Settings Hub Tranche 2 and 3 are complete as of April 19, 2026: `ui/launcher/views/settings_hub_view.py` owns the live settings stack, launcher helpers route through `_settings_hub_view`, and the legacy `my_pc_view.py`, `advanced_view.py`, `connector_panel.py`, and `advanced_terminal_panel.py` surfaces have been removed.
5. The launcher/runtime seam extraction is materially underway under `src/guppy/launcher_application/`, `src/guppy/runtime_application/`, `src/guppy/workspace_governance/`, and `src/guppy/experience_config/`.
6. Models Hub Tranche 4, 5, and 6 are complete in launcher flow as of April 19, 2026: `ui/launcher/views/models_hub_view.py` is now the single launcher destination for model library, runtime, local LLM evidence, and voice flows; stable MAIN / SUB A / SUB B loadouts remain in `models_view.py`; and provider accounts plus API-key storage remain unified in Settings.
7. Multi-provider model routing is implemented in Models Hub: Ollama local remains the stable default runtime, Lemonade remains the opt-in challenger lane, LM Studio stays discovery/readiness-visible, local harness stays a development/evidence lane, and Hugging Face local is explicitly tracked as a planned adapter path rather than a silent runtime swap.
8. Home Chat Tranche 7 and 8 are complete as of April 19, 2026: the daily Home surface now stays visually chat-first, visible operator detail surfaces no longer render there, and compatibility setters remain hidden behind the launcher so request-state and personalization seams stay stable.
9. Navigation Tranche 9 and final integration Tranche 10 are complete as of April 19, 2026: the visible launcher chrome now reads exactly `HOME`, `MODELS`, `TOOLS`, `LIBRARY`, `SETTINGS`, while `Workspaces` moved to the topbar workspace cluster instead of remaining a first-class hub.
10. Library Hub P4 is complete as of April 19, 2026: `ui/launcher/views/library_view.py` now supports multiline pinned-note editing, local audio/video playback through the Library-local media panel, and smoother Library-to-Home source reuse without adding new storage tables or credential surfaces.
11. Historical specialist surfaces (Merlin, Council) are quarantined under `compat_shims/legacy_surfaces/` and are not product surfaces.
12. `Guppy-pi` is not part of this repository. It was a separate project tracked by mistake as a gitlink and has been removed from git tracking.
13. **Web UI Parity Complete (2026-04-28):** Comprehensive parity testing between web UI (FastAPI + React) and desktop launcher is complete. The web UI is now the **primary & authoritative product surface**. The desktop launcher (`launcher_app.py`) is now a **wrapper** that spawns the FastAPI server locally and opens a browser window to the web UI. This eliminates dual codebase maintenance while preserving the "native desktop app" UX. All P0 features verified on web UI: chat, workspaces, model management, settings, tool execution. Single FastAPI + React codebase replaces the dual Qt/web architecture.

---

## Execution Board

| Priority | Track | Status | Goal | Acceptance | Target |
| --- | --- | --- | --- | --- | --- |
| P1 | Home Chat Cleanup | complete | Strip all operator noise from Home Chat; make it a clean chat window only | A first-run user sees only the conversation, context chips, and voice input on Home — no model internals, diagnostics, or settings panels | Completed April 19, 2026 |
| P2 | Models Hub Consolidation | complete | Merge `local_llm_view.py`, `voices_view.py`, `models_runtime_library.py` into one Models Hub destination while keeping credentials in Settings | Models Hub is the single place to load, select, install, and configure any model or persona | Completed April 19, 2026 |
| P3 | Settings Hub Consolidation | complete | Merge `my_pc_view.py`, `advanced_view.py`, `connector_panel.py`, `advanced_terminal_panel.py` into `settings_view.py` | Settings Hub owns all credentials, diagnostics, recovery, and daemon controls in one destination | Completed April 19, 2026 |
| P4 | Library Hub Completion | complete | Promote Library to a first-class hub with media player, richer note editing, and broader source reuse | Library Hub is the single destination for files, notes, media, and artifact reuse in chat | Completed April 19, 2026 |
| P5 | Tools Hub Hardening | complete | Tools Hub gains live tool debugging, execution traces, and per-command permission controls | Tools Hub is the complete operational view of every agent capability | Completed April 19, 2026 |
| P6 | Platform Hardening + Packaging Readiness | active | Reduce architectural hotspot risk while explicitly stabilizing local/cloud chat, model switching, stats fidelity, guarded PC-control flows, and dual web/desktop surface parity | Release remains repeatable; chat/runtime switching is stable; stats stop drifting from runtime truth; PC-control stays powerful but bounded; web and desktop remain parallel clients over shared contracts | April 20 - June 12, 2026 |

### P6 Goal Contract (April 22, 2026)

P6 is now judged against the following concrete product goals rather than generic hardening language:

1. Stable local and cloud chat.
   - Chat must stay reliable whether the active route is local-runtime or cloud-provider backed.
   - Route changes, provider availability changes, and auth refresh must not break the daily chat path.
2. Stable model switching.
   - Model/provider switching must update one shared runtime truth and must not leave launcher, web, and API surfaces showing different active models.
   - Switching must be safe across MAIN / SUB lanes and across local/cloud fallback behavior.
3. Accurate statistics.
   - User-visible counts, health labels, runtime readiness, and model/tool inventories must come from canonical runtime/state sources rather than placeholder or duplicated UI-only data.
   - If a metric is not trustworthy yet, it should be demoted or hidden instead of invented.
4. Total local PC control as a guarded advanced capability.
   - Local PC control remains a real capability goal, but it is not allowed to become a conflicting primary product surface.
   - The daily path stays calm; powerful machine-control flows remain bounded under Tools or Settings with clear policy and permission ownership.
5. North-star completion without surface conflict.
   - Chat, Workspaces behavior, Library, and Settings remain the primary product truths.
   - Models and Tools stay subordinate implementation hubs, not competing product centers.
6. Dual web UI and desktop launcher options that do not conflict.
   - Desktop launcher and root web UI must behave as parallel clients over shared inventories, shared workspace/config truth, and shared route contracts.
   - No surface may invent its own model list, tool list, connector registry, or workspace state contract.

---

## Roadmap Knife

Apply `docs/PRODUCT_FEATURE_FILTER.md` to every tranche before expanding scope.

| Track | Keep Now | Demote | Defer |
| --- | --- | --- | --- |
| P1 Home Chat | Conversation, context chips, voice, workspace switch | Model health panels, runtime telemetry, recovery buttons | Ambient assistant, multi-pane experiments |
| P2 Models Hub | Model install/uninstall, provider routing, persona, voice, sub-agent selector | Reviewer benchmark packets, deep comparison detail | Broad provider expansion beyond current 7 |
| P3 Settings Hub | API keys, credentials, diagnostics, recovery, daemon, connectors | Advanced power-user metadata | New top-level operator destinations |
| P4 Library Hub | Approved roots, recent files, pinned notes, media player, use-in-chat | Power-user file metadata | Whole-PC crawling, connector-heavy file surfaces |
| P5 Tools Hub | Tool list, permissions, add/remove, execution traces | Detailed per-invocation audit beyond recent history | Autonomous tool builder, tool marketplace |
| P6 Platform Hardening | Hotspot reduction, stable seams, stable local/cloud chat, stable model switching, stats truth, bounded PC-control, dual-surface parity | speculative downstream integration planning beyond interface-level, placeholder dashboard metrics, duplicate per-surface inventories | Large packaging or integration work before the hardening lane lands cleanly |

---

## Timeline and Checkpoints

1. April 19, 2026 - Completed: Home Chat is clean. No operator UI renders on the daily chat surface.
2. April 19, 2026 - Completed: Models Hub is one consolidated destination. Provider routing, local loadouts, runtime evidence, and voice flows live together while Settings still owns credentials.
3. April 19, 2026 - Completed: Settings Hub owns all credentials, diagnostics, recovery, and daemon controls.
4. April 19, 2026 - Completed: Library Hub has a local media player, multiline note workflows, and smoother source reuse into Home Chat.
5. April 19, 2026 - Completed: Tools Hub now has recent execution traces, per-command debug evidence, and a split Tools surface that keeps the Builder path and Settings boundary intact.
6. June 12, 2026 - Target: Platform hardening and packaging-readiness work are stable enough for downstream merge, real-machine runtime validation, and packaging work on the five-hub shell.
7. June 12, 2026 - Target: desktop launcher and root web UI both operate from the same runtime/config truth without route, inventory, or active-model drift.

---

## Health Check (April 20, 2026)

1. Release lane is green as of April 20, 2026. `python tools/dev_workflow.py release-check` passed with ref `release-check-20260420-154801`, `8/8` gates passed, `543 passed` in the default suite, and `138 passed` in product smoke.
2. The repository is healthy but still in active integration. The worktree remains intentionally active rather than clean, so this is green-for-continuation rather than clean-tag-ready.
3. `P1` through `P5` are complete, and the automatic `P6` hardening slices through Tranche 51 are now release-green. There are no blocking tranche errors left in the shell consolidation work; the remaining follow-up risk is concentrated in the largest coordinator modules plus real-machine runtime and voice validation.
4. The main technical pressure points are now the still-waived top-level coordinators: `server_runtime.py` (`741`), `server_runtime_snapshot.py` (`3098`), `launcher_window.py` (`3471`), `models_view.py` (`1529`), `assistant_view.py` (`1316`), and `settings_operations_panel.py` (`939`). Those hotspots are all guarded and have been shrinking tranche over tranche.
5. The packaging/readiness lane is materially healthier than the older checkpoint wording suggested: packaging/distribution contracts are now checked in `tools/validate_build_checks.py`, launcher-visible runtime data routes through bounded helpers, and the repo has explicit generated handoff matrices for runtime and voice validation instead of only broad gap notes.

---

## Guardrail Stack

Run `python tools/dev_workflow.py dev-check` before every merge. It enforces:

- Architecture boundary isolation (no direct UI imports of `utils.*`)
- Module line-cap enforcement (700 lines base, named transitional waivers)
- Release debt marker check (no debt markers in added release-facing lines)
- Wrapper and surface integrity

All three guardrail blockers from the April 18 audit have been resolved:

- Guppy-pi gitlink removed from tracking (`git rm --cached Guppy-pi`)
- Release debt guard patched to exclude its own source file from scan
- Transitional waiver caps updated to reflect actual module sizes with 5-hub rationale

---

## Current Gaps

1. Home Chat cleanup is complete in the visible launcher UX; remaining Home work is transcript/composer polish and source-flow refinement rather than operator-surface removal.
2. Models Hub consolidation is complete in launcher flow; remaining model work is deeper runtime execution parity beyond Anthropic/Ollama/Lemonade, broader real-device validation, and planned adapter work for Hugging Face local rather than destination ownership changes.
3. Settings Hub consolidation is complete; remaining Settings work is launcher-shell composition cleanup, panel-size reduction, and richer credential lifecycle polish rather than ownership migration.
4. Library Hub completion is now in place in launcher flow; remaining Library work is polish around richer previews and metadata ergonomics rather than missing core ownership or playback.
5. Tools Hub ownership is complete; remaining Tools work is polish rather than missing trace/debug foundations.
6. Voice lifecycle needs broader real-device validation across engines.
7. Builder and off-hours flows need output-cleanup polish and repeated stress validation.
8. Stable local/cloud chat is not yet called out as a first-class acceptance lane in the active brief; P6 now treats that as explicit release-facing scope.
9. Stable model switching still needs parity checks across launcher, web, runtime route state, and local/cloud provider transitions.
10. User-visible statistics are still uneven in fidelity across surfaces; placeholder or synthetic dashboard numbers must not outrun runtime truth.
11. Local PC control exists as tool capability, but its ownership and calm-surface boundaries must stay explicit so it does not regress the north-star into an automation dashboard.
12. Dual web and desktop support is now real, but route contracts and shared inventory ownership still need continued enforcement so the two clients do not drift again.

---

## Freeze-Readiness Debt Reduction Program (Post-Tranche 53)

Execution note (April 20, 2026):

- Tranche 53 closed the broad hardening/usability/security sweep, but the repo is not yet at a freezeable architecture state.
- The remaining debt is now concentrated in a finite hotspot set with explicit waiver caps and known framework seams.
- This program focuses on turning guarded transitional hotspots into smaller working components without changing five-hub ownership.
- Definition of “freezeable” for this program:
  1. no hotspot may grow during the program
  2. top coordinators must either drop below the cap or lose enough responsibility that the remaining waiver is narrow and justified
  3. launcher/runtime/provider/config seams must be explicit enough that release behavior is understandable without reading giant files
  4. release-check stays green throughout

Original hotspot inventory (all resolved — current sizes below cap as of 2026-04-22):

1. `src/guppy/api/server_runtime_snapshot.py` `2232` → **570** ✓
2. `ui/launcher/launcher_window.py` `3354` → **534** ✓
3. `ui/launcher/views/models_view.py` `1542` → **558** ✓
4. `ui/launcher/views/assistant_view.py` `1394` → **584** ✓
5. `ui/launcher/views/settings_operations_panel.py` `1032` → **593** ✓
6. `ui/launcher/views/settings_device_accounts_panel.py` `824` → **543** ✓
7. `ui/launcher/views/library_view.py` `961` → **531** ✓
8. `ui/launcher/views/voices_view.py` `866` → **457** ✓
9. `utils/connector_manager.py` `670` → below cap ✓
10. `utils/personalization_config.py` `1029` → below cap ✓
11. `src/guppy/api/server_runtime.py` `586` → **492** ✓
12. `src/guppy/api/services_realtime.py` `599` → below cap ✓

Program tranches:

1. `FR-C1 - API runtime snapshot decomposition`
   - Extract prompt/rich-context assembly, runtime bundle shaping, readiness assembly, and connector/governance payload builders out of `server_runtime_snapshot.py`.
   - Acceptance: `server_runtime_snapshot.py` becomes a bounded composition shell instead of the implementation home for unrelated helpers.

2. `FR-C2 - Launcher shell coordinator reduction`
   - Continue reducing `launcher_window.py` by moving request routing, workspace/status synchronization, and launcher action orchestration into `src/guppy/launcher_application/` helpers.
   - Acceptance: launcher shell remains the composition root, but non-rendering orchestration lives outside the widget file.

3. `FR-C3 - Models hub panel split`
   - Split `models_view.py` into bounded panels/helpers for runtime status, model catalog operations, routing/loadout controls, and background worker coordination.
   - Acceptance: `ModelsView` becomes a smaller assembler over purpose-specific subcomponents.

4. `FR-C4 - Home chat coordinator split`
   - Reduce `assistant_view.py` by separating transcript/composer/starter/detail behavior into dedicated view helpers where the extraction is stable.
   - Acceptance: Home keeps its chat-first contract while shedding multi-purpose render/orchestration logic.

5. `FR-C5 - Settings operations and device/accounts split`
   - Separate diagnostics/recovery/runtime workflows from `settings_operations_panel.py`, and separate provider inventory/action sections from `settings_device_accounts_panel.py`.
   - Acceptance: Settings panels stay Settings-owned but stop bundling every operator flow into one class each.

6. `FR-C6 - Library and voice surface decomposition`
   - Reduce `library_view.py` and `voices_view.py` by moving stable row/card/editor/player logic into dedicated components/helpers.
   - Acceptance: the remaining parent views are smaller and easier to reason about without losing current behavior.

7. `FR-C7 - Connector manager extraction`
   - Move state/history/readiness/action orchestration out of `utils/connector_manager.py` into named `src/guppy/...` services, leaving only compatibility shims if still needed.
   - Acceptance: connector behavior no longer feels like hidden app logic inside `utils`.

8. `FR-C8 - Personalization config service split`
   - Split `utils/personalization_config.py` into dedicated services for provider registry, persona config, and voice bindings under `src/guppy/experience_config/` or equivalent bounded seams.
   - Acceptance: config persistence and normalization are service-shaped, not one giant utility file.

9. `FR-C9 - Runtime/request lane reduction`
   - Continue trimming `server_runtime.py` and `services_realtime.py` by isolating route groups, auth/request orchestration, and idempotency/request helper seams.
   - Acceptance: runtime service code stops mixing unrelated route and request concerns.

10. `FR-C10 - Freeze audit and waiver reset`
    - Re-audit every remaining waiver, remove stale waiver headroom, document what is truly still transitional, and run full guarded validation.
    - Acceptance: the worktree is freezeable for a stabilization branch, with current docs, current receipts, and no misleading hotspot metadata.

Recommended execution order:

1. `FR-C1`, `FR-C2`, and `FR-C3` first because they attack the largest runtime and launcher coordinators directly.
2. `FR-C5`, `FR-C7`, and `FR-C8` next because they reduce Settings/provider/config debt and prevent `utils/` from acting like an app layer.
3. `FR-C4`, `FR-C6`, and `FR-C9` after those contracts stabilize.
4. `FR-C10` last as the freeze-readiness closeout.

Recommended agent lane split:

1. Lane A: `FR-C1` API snapshot decomposition
2. Lane B: `FR-C2` launcher shell reduction
3. Lane C: `FR-C3` models hub split
4. Lane D: `FR-C5` Settings panels split
5. Lane E: `FR-C7` plus `FR-C8` connector/config extraction
6. Lead lane: tranche integration, guardrail updates, and freeze audit sequencing

Success metrics:

1. Every tranche must reduce at least one active hotspot measurably or document the exact blocking seam.
2. `release-check` remains green after each integrated tranche.
3. `utils/` shrinks as a behavior layer and becomes more clearly compatibility-focused.
4. The biggest UI coordinators become composition shells rather than implementation monoliths.
5. Freeze-readiness ends with current waiver caps, current docs, and no stale release/tranche truth drift.

Execution checkpoint (April 20, 2026 first freeze-reduction wave):

1. `FR-C1` landed an API snapshot split: `src/guppy/api/server_runtime_snapshot.py` now delegates instance/governance/connector/log payload assembly into `src/guppy/api/snapshot_instances_support.py`, with focused coverage in `tests/unit/test_snapshot_instances_support.py`.
2. `FR-C2` landed a launcher-shell split: `ui/launcher/launcher_window.py` now delegates assistant request submission/orchestration and topbar model summary shaping into `src/guppy/launcher_application/launcher_command_flow.py`, with focused coverage in `tests/unit/test_launcher_command_flow.py`.
3. `FR-C3` landed a Models-hub split: `ui/launcher/views/models_view.py` now delegates runtime/model worker threads to `ui/launcher/views/models_runtime_workers.py` and section construction to `ui/launcher/views/models_sections.py`, with focused coverage in `tests/unit/test_models_sections.py`.
4. Current observed hotspot reductions in this branch:
   - `server_runtime_snapshot.py`: `2232` -> `1990`
   - `launcher_window.py`: `3354` -> `3069`
   - `models_view.py`: `1542` -> `1298`
5. `FR-C9` also landed an API request-lane split: `src/guppy/api/services_realtime.py` now delegates the heavy realtime inference execution tree into `src/guppy/api/realtime_inference_support.py`, with focused coverage in `tests/unit/test_realtime_inference_support.py`.
6. The connector/config extraction wave is also live in this branch:
   - `utils/connector_manager.py` now delegates runtime/action behavior through `src/guppy/launcher_application/connector_state_service.py` and `connector_action_service.py`
   - `utils/personalization_config.py` now acts as a backward-compatible wrapper over `src/guppy/experience_config/personalization_defaults.py`, `personalization_storage.py`, and `personalization_resolution.py`
   - `ui/launcher/views/settings_device_accounts_panel.py` now routes panel shaping through a dedicated presenter seam and has dropped under the base cap
7. `services_realtime.py`, `server_runtime.py`, `settings_device_accounts_panel.py`, `connector_manager.py`, and `personalization_config.py` are now all below the base cap, so their transitional waivers were removed from `tools/check_new_module_line_cap.py`.
8. `server_runtime.py` also got a shell-support split into `src/guppy/api/server_runtime_shell_support.py`, moving FastAPI shell construction, `ServerContext` assembly, and voice-backend probing out of the module and dropping it to `403` lines.
9. The Home/Library/Voices reduction wave is also live in this branch:
   - `assistant_view.py` now delegates shell/chrome/composer/transcript assembly into `ui/launcher/views/assistant_shell_sections.py`
   - `library_view.py` now delegates root/browse/recent/saved card rendering into `ui/launcher/views/library_card_sections.py`
   - `voices_view.py` now delegates section construction into `ui/launcher/views/voices_sections.py`
10. `voices_view.py` is now below the base cap and its transitional waiver was removed.
11. `assistant_view.py` and `library_view.py` are materially smaller, but still slightly above the base cap after the integrated merge state, so their waiver caps were reset to the actual current branch sizes instead of the smaller worker-local estimates.
12. `settings_operations_panel.py` now routes compact-mode label/state shaping through `src/guppy/launcher_application/settings_operations_presenter.py`, and its waiver cap was reduced to the new observed size.
13. Transitional waiver caps were refreshed for the remaining touched hotspots so the freeze-readiness program cannot silently give back that ground.
14. Freeze-readiness validation is now green again after the integrated merge state:

- `ui/launcher/launcher_window.py` had a small follow-through regression fixed by restoring the local `re` import used by auth/repair error-code extraction
- the remaining library seam was revalidated against `src/guppy/launcher_application/library_context_support.py` and `library_workflow.py`, and the focused library workflow/context tests are green on the extracted boundary
- `tools/check_new_module_line_cap.py` was refreshed to the actual observed launcher size (`3070`) so the guardrails match the branch honestly instead of carrying stale headroom

1. Current release evidence for the freeze-reduction wave is `release-check-20260420-163159`, with `8/8` gates passing, `575 passed` in the default suite, and `138 passed` in product smoke.

---

## Freeze-Down Minimization Program (Post Freeze Wave)

Execution note (April 20, 2026):

- The repo is release-green again, but it is not yet at the "freezable branch" standard for a stabilization handoff.
- The tracked tree is `571` files, so the remaining debt is now mainly hotspot concentration, compatibility drag, stale legacy wording, and doc/archive noise rather than uncontrolled repo sprawl.
- This program follows `FR-C1` through `FR-C10` and focuses on three goals together:
  1. reduce the last oversized coordinators into bounded working components
  2. clean legacy and compatibility mentions down to explicit quarantine-only references
  3. pare the tracked tree down to files that are actually needed for product, validation, packaging, or explicit retained history

Top-level naming and product rule:

1. The platform is named `Guppy`.
2. The default assistant is also currently named `Guppy`, but that assistant name must become clearly user-editable.
3. Model surfaces should stop showing old assistant/loadout labels such as `guppy`, `merlin`, `fast`, and `vault` as if they were model identities.
4. Model selectors should show the actual model/runtime name, and customization should come from the attached persona rather than from legacy tab naming.

Current live sizes (all below 700-line cap, no active waivers — as of 2026-04-22):

1. `src/guppy/api/server_runtime_snapshot.py` **570**
2. `ui/launcher/launcher_window.py` **534**
3. `src/guppy/daemon/daemon.py` **63** (fully reduced)
4. `ui/launcher/views/models_view.py` **558**
5. `src/guppy/merlin/core.py` **401** (fully reduced)
6. `ui/launcher/views/settings_operations_panel.py` **593**
7. `src/guppy/memory/memory.py` **432** (fully reduced)
8. `ui/launcher/views/instance_manager_view.py` **370** (fully reduced)
9. `ui/launcher/views/assistant_view.py` **584**
10. `src/guppy/launcher_application/library_workflow.py` **502**
11. `ui/launcher/views/library_view.py` **531**
12. `ui/launcher/views/settings_view.py` **575**
13. `src/guppy/debug/console.py` **59** (fully reduced)
14. `src/guppy/voice/voice.py` **292** (fully reduced)

Current cleanup findings:

1. `compat_shims/legacy_surfaces/` is already a very small quarantine set and should stay compatibility-only until the last supported legacy launch hooks are gone.
2. Root wrappers such as `guppy_launcher.py`, `guppy_hub.py`, and `guppy_api.py` still belong in the tracked tree, but only as thin compatibility shims.
3. `docs/archive/` and `docs/generated/` are the main pare-down candidates, but only after active references, tests, and release flows stop depending on specific files there.
4. Several active docs still carry older hotspot counts or ambient transition wording; that language now needs its own cleanup tranche.
5. "Needed files only" must be defined by retention class, not by ad hoc deletion:
   - ship code and config
   - validation and release tooling
   - active truth docs
   - explicit compatibility shims
   - explicit retained history
   - current runtime and release evidence contracts

Program tranches:

1. `FR2-T1 - Naming, freeze contract, and retention baseline`
   - Lock the live hotspot inventory, stale waiver headroom, assistant/platform naming rules, compatibility rules, and file-retention classes from current branch state.
   - Include the model-label cleanup contract: show model names, not old persona/loadout labels, and make assistant naming explicitly user-editable.
   - Acceptance: one current source of truth exists for hotspot sizes, naming rules, legacy boundaries, and what counts as a required tracked file.

2. `FR2-T2 - API snapshot final decomposition`
   - Continue splitting `server_runtime_snapshot.py` into route groups and bounded support modules for prompt context, request orchestration, startup/readiness, ops routes, and instance/diagnostic shaping.
   - Acceptance: `server_runtime_snapshot.py` becomes a bounded shell instead of a catch-all coordinator.

3. `FR2-T3 - Launcher shell second-stage extraction`
   - Move hub routing, startup phase handling, status sync, view-to-workflow handoffs, and command/action dispatch out of `launcher_window.py` into `src/guppy/launcher_application/`.
   - Acceptance: the launcher shell is clearly the composition root, not the implementation home for workflow logic.

4. `FR2-T4 - Models surface normalization and panel dispersion`
   - Split `models_view.py` into bounded panels for runtime status, route preview, local model library, provider/loadout controls, and persona attachment.
   - Remove visible `guppy`, `merlin`, `fast`, and `vault` label treatment from model surfaces and replace it with actual model/runtime names plus persona context.
   - Acceptance: Models shows model identity cleanly, assistant naming is not conflated with model identity, and the main view drops materially in size.

5. `FR2-T5 - Settings surfaces split`
   - Split `settings_operations_panel.py` into diagnostics, recovery, terminal, and automation/workflow subpanels; split `settings_view.py` into smaller settings editors backed by presenters.
   - Acceptance: Settings panels stop bundling unrelated operator flows into one class each.

6. `FR2-T6 - Home and Library final UI cleanup`
   - Reduce `assistant_view.py` and `library_view.py` by moving remaining density/refresh/transcript/editor wiring into stable helpers and subviews.
   - Keep `library_workflow.py` as a controller shell and clean its stale waiver headroom.
   - Acceptance: Home and Library become smaller render/composition surfaces with clearer controller seams.

7. `FR2-T7 - Daemon service separation`
   - Split `daemon.py` into notifier, window watcher, scheduler, proactive loop, ambient watcher, and manager seams.
   - Acceptance: the daemon becomes a smaller orchestration shell with explicit service modules.

8. `FR2-T8 - Memory, Voice, and specialist runtime reduction`
   - Split `memory.py` into repository/service/extractor seams, `voice.py` into backend adapters plus recorder/playback orchestration, and decide whether `merlin/core.py` remains a quarantined specialist runtime or gets a deeper extraction.
   - Acceptance: these modules stop blocking freeze readiness through size and mixed concerns alone.

9. `FR2-T9 - Debug console and low-risk legacy wording cleanup`
   - Split `debug/console.py` tab bodies into dedicated widgets, remove stale "legacy" copy and broken-encoding headers in live modules, and clean references that no longer reflect the current product surface.
   - Acceptance: low-risk but high-noise debt is gone from the live code and docs.

10. `FR2-T10 - Wrapper slimming and compatibility quarantine hardening`
    - Audit `guppy_launcher.py`, `guppy_hub.py`, `guppy_api.py`, and `compat_shims/legacy_surfaces/` end to end.
    - Remove accidental behavior ownership from wrappers, verify quarantine boundaries, and tighten tests/guards around what still remains.
    - Acceptance: supported entrypoints are thin and compatibility surfaces are clearly bounded.

11. `FR2-T11 - Docs/archive/generated pare-down sweep`
    - Classify `docs/archive/`, `docs/generated/`, and stale planning/cleanup docs into active, historical keep, generated keep, and removable-after-reference-cleanup buckets.
    - Acceptance: the doc tree is lighter and less noisy without breaking release, smoke, or operator flows.

12. `FR2-T12 - Repo file retention and delete tranche`
    - Execute the first real removal pass for files proven unnecessary by the retention contract.
    - Include stale tracked artifacts, obsolete docs, and compatibility leftovers that no supported path still references.
    - Acceptance: tracked file count drops below the current `571` without losing build, test, packaging, or retained-history truth.

13. `FR2-T13 - Guardrail, waiver, and freeze closeout`
    - Remove stale waiver headroom, tighten architecture-boundary and wrapper-integrity rules, clean tests that still encode outdated transition assumptions, and close with full guarded validation.
    - Acceptance: the branch is small enough, clear enough, and validated enough to freeze for stabilization or release-candidate work.

Recommended execution order:

1. `FR2-T1` first to lock the naming rule, live baseline, and file-retention contract.
2. Run `FR2-T2`, `FR2-T3`, and `FR2-T5` as the first high-value parallel wave.
3. Start `FR2-T4` as soon as the launcher/model interfaces are stable enough to normalize model naming cleanly.
4. Follow with `FR2-T6`, `FR2-T7`, and `FR2-T8`.
5. Use `FR2-T9` and `FR2-T10` to strip stale wording and compatibility drag after the main seams have moved.
6. Finish with `FR2-T11`, `FR2-T12`, and `FR2-T13`.

Recommended agent lanes:

1. Lane A: runtime/backend debt (`FR2-T2`, `FR2-T7`)
2. Lane B: launcher/settings/workspace shells (`FR2-T3`, parts of `FR2-T5`)
3. Lane C: Models/Home/Library/Voice UI reduction and naming cleanup (`FR2-T4`, `FR2-T6`, parts of `FR2-T8`)
4. Lane D: memory/debug/specialist runtime and low-risk legacy cleanup (`FR2-T8`, `FR2-T9`)
5. Lane E: wrappers, compatibility quarantine, docs/generated/archive, and file-retention sweep (`FR2-T10`, `FR2-T11`, `FR2-T12`)
6. Lead lane: guardrails, waiver reset, integration, and freeze closeout (`FR2-T13`)

Success metrics:

1. At least half of the remaining waived hotspots either drop below the cap or lose enough responsibility that their waivers shrink materially.
2. `release-check` stays green after each integrated execution wave.
3. The tracked tree shrinks below the current `571` files without losing build, test, packaging, or retained-history truth.
4. Active docs stop describing the product through transition language unless the reference is intentionally compatibility-only.
5. Model surfaces show actual model/runtime names, while assistant naming becomes user-editable and persona-driven.
6. Root wrappers remain thin, `compat_shims/legacy_surfaces/` becomes an obvious compatibility island, and the repo ends the program with current docs, current waivers, and current release receipts.

Execution checkpoint (April 20, 2026 first freeze-down wave):

1. `FR2-T1` is now materially in place:
   - the active truth docs now distinguish the platform name (`Guppy`) from the default assistant name
   - the default assistant name is now treated as user-editable in Settings rather than as a fixed product label
   - `tools/check_architecture_boundaries.py` now also blocks direct live-code imports of the root `guppy_api` shim
2. `FR2-T2` landed an API snapshot reduction:
   - `src/guppy/api/server_runtime_snapshot.py` now delegates the remaining snapshot-only route behavior into `src/guppy/api/snapshot_route_support.py`
   - the snapshot shell is down to `1712` lines
3. `FR2-T3` landed another launcher shell extraction:
   - `ui/launcher/launcher_window.py` now delegates API/runtime control flow into `src/guppy/launcher_application/launcher_api_runtime_control.py`
   - the launcher shell is down to `2800` lines
4. `FR2-T4` materially advanced the Models surface:
   - `ui/launcher/views/models_view.py` is down to `1073` lines after more section/panel extraction
   - visible model/loadout surfaces now frame actual model/runtime identity, while persona remains separate customization state
   - old visible slot language no longer presents `guppy`, `merlin`, `fast`, or `vault` as model identities
5. `FR2-T5` materially advanced the Settings lane:
   - `ui/launcher/views/settings_view.py` now speaks in assistant-name terms instead of treating the default persona as a fixed `Main Guppy` label
   - shared personalization defaults now seed the default assistant as `Guppy`, and Settings exposes that as editable assistant/persona configuration
   - `ui/launcher/views/settings_view.py` is down to `700` lines
6. Transitional waiver metadata was tightened to the current observed sizes for:
   - `server_runtime_snapshot.py` -> `1712`
   - `launcher_window.py` -> `2800`
   - `models_view.py` -> `1073`
   - `settings_view.py` -> `700`
   - `library_workflow.py` -> `502`
7. Current integrated validation is green:
   - `python tools/dev_workflow.py dev-check --guard-scope delta` passed
   - `python tools/dev_workflow.py release-check` passed with ref `release-check-20260420-165643`
   - current release counts are `583 passed` in the default suite and `138 passed` in product smoke
8. The next natural freeze-down wave is `FR2-T6` through `FR2-T8`: Home/Library cleanup, daemon service separation, and Memory/Voice/specialist runtime reduction.

Execution checkpoint (April 20, 2026 follow-through wave):

1. Vercel Python discovery is now explicit through `api/index.py`, which exports the supported FastAPI app from `src.guppy.api.server_runtime`.
2. `FR2-T6` is materially complete:
   - `ui/launcher/views/assistant_view.py` is down to `614` lines after moving state/context/first-run density behavior into `ui/launcher/views/assistant_behavior_support.py`
   - `ui/launcher/views/library_view.py` is down to `619` lines after moving editor/root-path behavior into `ui/launcher/views/library_editor_support.py`
3. `FR2-T7` is materially complete in the live code:
   - `src/guppy/daemon/daemon.py` is now a thin compatibility shell over `ambient_watcher.py`, `manager.py`, `notifier.py`, `proactive_loop.py`, `scheduler.py`, `support.py`, and `window_watcher.py`
4. `FR2-T8` already has the memory/debug/voice split in place:
   - `src/guppy/memory/memory.py` is down to `316` lines with the store/support seams carrying the heavier persistence and extraction logic
   - `src/guppy/debug/console.py` is now a thin shell over `src/guppy/debug/_tabs.py` and `src/guppy/debug/_ui.py`
   - `src/guppy/voice/voice.py` is now a thin orchestration surface over `voice_runtime.py` and `voice_support.py`
5. `FR2-T9` live wording cleanup advanced:
   - the supported debug surface now presents `Guppy Debug & Emergency Console` instead of framing Merlin as a live peer desktop shell
6. `FR2-T11` and `FR2-T12` are materially advanced:
   - `docs/generated/` was reduced from `20` files to `10` live files by deleting stale April 14-17 one-off audit artifacts
   - the current tracked-existing file count is now `562`, down from the previous `571` baseline
7. `FR2-T13` guardrail tightening advanced:
   - stale waivers were removed for `daemon.py`, `memory.py`, `library_workflow.py`, `debug/console.py`, `voice.py`, `assistant_view.py`, `library_view.py`, and `settings_view.py`
   - the remaining waiver list now focuses on the real oversized hotspots still above the base cap
8. `FR2-T6` through `FR2-T13` are now effectively complete for this freeze-down wave:
   - the remaining baseline waiver set is narrowed to `server_runtime_snapshot.py`, `merlin/core.py`, `launcher_window.py`, `instance_manager_view.py`, `models_view.py`, and `settings_operations_panel.py`
   - release validation is green with the slimmer docs/generated tree, the explicit Vercel API entrypoint, and the post-split daemon/memory/voice/debug wrapper surfaces

## Remaining Hotspot Reduction Tranches (April 20, 2026)

Execution note:

- The next freeze-readiness wave is now narrowed to the six baseline-waived files still above the base cap.
- Current observed sizes are:
  - `src/guppy/api/server_runtime_snapshot.py` -> `1712`
  - `src/guppy/merlin/core.py` -> `1115`
  - `ui/launcher/launcher_window.py` -> `2800`
  - `ui/launcher/views/instance_manager_view.py` -> `869`
  - `ui/launcher/views/models_view.py` -> `1073`
  - `ui/launcher/views/settings_operations_panel.py` -> `1008`
- The goal of this tranche set is freezeability, not feature expansion: each card must materially reduce ownership concentration or prove the remaining surface is an intentional bounded shell.

What ships:

1. `FR3-T1 - Snapshot route and telemetry final split`
   - Reduce `server_runtime_snapshot.py` by pushing the remaining chat/request assembly, telemetry shaping, and report composition into named support modules.
   - Preserve the supported import surface and route behavior while making snapshot assembly legible by concern.
   - Acceptance: `server_runtime_snapshot.py` becomes a smaller composition shell and loses at least one major responsibility cluster.
2. `FR3-T2 - Launcher shell fourth extraction`
   - Reduce `launcher_window.py` by moving another bounded action family into `src/guppy/launcher_application/`.
   - Preferred targets are top-level request routing, tab/hub orchestration helpers, and any remaining shell-local coordination that is not pure view composition.
   - Acceptance: `launcher_window.py` drops again and launcher-side orchestration moves through named support seams rather than direct inline shell methods.
3. `FR3-T3 - Models hub final panel split`
   - Reduce `models_view.py` by extracting the remaining mixed loadout/runtime operations and any dense panel builders into dedicated view/support modules.
   - Keep model identity separate from persona/customization and do not reintroduce legacy labels as runtime names.
   - Acceptance: `models_view.py` becomes a smaller hub shell with panel/state wiring delegated cleanly.
4. `FR3-T4 - Settings Operations split`
   - Reduce `settings_operations_panel.py` by separating diagnostics, recovery, automation, and machine-operation sections into dedicated subviews or presenters.
   - Preserve the current Settings ownership model while lowering density and improving testable seams.
   - Acceptance: the operations panel becomes a composition surface rather than the single owner of all operational section assembly.
5. `FR3-T5 - Workspace manager reduction`
   - Reduce `instance_manager_view.py` by moving governance summary shaping, filtering, and repeated card/section composition into support modules.
   - Keep workspace governance ownership intact, but remove unnecessary render-plus-policy coupling from the widget.
   - Acceptance: workspace management remains behavior-compatible while the main view drops under less pressure and gains clearer seams.
6. `FR3-T6 - Merlin specialist runtime disposition`
   - Decide whether `src/guppy/merlin/core.py` remains a bounded quarantined specialist runtime or gets one more extraction pass.
   - If it stays, tighten quarantine/ownership docs and guards; if it moves, extract the largest mixed concern into a support seam.
   - Acceptance: `merlin/core.py` stops being ambiguous debt and becomes either an explicitly bounded retained specialist surface or a materially smaller module.
7. `FR3-T7 - Guardrail reset and freeze candidate closeout`
   - Refresh the waiver file to match the new observed sizes, remove any waiver that is no longer justified, and run the full guarded validation lane.
   - Update the active truth docs with the final remaining hotspot picture and whether the worktree is ready for freeze candidate status.
   - Acceptance: the waiver list is smaller or tighter, `release-check` is green, and the branch can be described honestly as freeze-candidate or not.

Lane checkpoint (April 20, 2026, FR3-T4 / FR3-T6):

- `settings_operations_panel.py` now composes the desktop runtime, connected services, and automation sections through `settings_operations_sections.py` instead of building those clusters inline.
- Merlin is now treated as a bounded retained specialist runtime: dispatch remains in `merlin/core.py`, while extracted helper support lives in `src/guppy/merlin/specialist_support.py`.

Recommended execution order:

1. Start with `FR3-T1` and `FR3-T2` because the API snapshot and launcher shell are the highest centrality hotspots.
2. Run `FR3-T3`, `FR3-T4`, and `FR3-T5` as the parallel UI-shell wave once the integration lane is stable.
3. Use `FR3-T6` as a bounded decision tranche after the main live hubs are reduced.
4. Finish with `FR3-T7` as the freeze-candidate guardrail pass.

Recommended agent lanes:

1. Lane A: API/runtime hotspot (`FR3-T1`)
2. Lane B: launcher shell hotspot (`FR3-T2`)
3. Lane C: Models and workspace UI shells (`FR3-T3`, `FR3-T5`)
4. Lane D: Settings Operations hotspot (`FR3-T4`)
5. Lane E: specialist runtime disposition and guardrail/doc cleanup (`FR3-T6`, `FR3-T7`)
6. Lead lane: integration, waiver tightening, validation, and freeze-candidate call

Success metrics:

1. At least three of the six remaining waived modules either lose their waiver entirely or drop by a meaningful bounded amount.
2. The remaining waived modules, if any, read as intentional shells rather than mixed-concern monoliths.
3. `release-check` stays green after the integrated wave.
4. The repo can be described with a short remaining-hotspots list and a credible freeze-candidate statement.

Integrated closeout (April 20, 2026, FR3-T1 through FR3-T7):

- `FR3-T1` is complete: `server_runtime_snapshot.py` now delegates realtime request/route assembly through `src/guppy/api/snapshot_realtime_support.py`.
- `FR3-T2` is complete: `launcher_window.py` now delegates workspace snapshot/bootstrap coordination through `src/guppy/launcher_application/workspace_snapshot_support.py`.
- `FR3-T3` is complete: `models_view.py` now delegates the library/search/loadout panel cluster through `ui/launcher/views/models_library_panel.py`, with shared route parsing in `src/guppy/launcher_application/models_route_support.py`.
- `FR3-T4` is complete: `settings_operations_panel.py` is now a composition shell over `ui/launcher/views/settings_operations_sections.py`.
- `FR3-T5` is complete: `instance_manager_view.py` now delegates dense card and section assembly through `ui/launcher/views/instance_manager_sections.py` and is no longer waived.
- `FR3-T6` is complete: `src/guppy/merlin/core.py` is now explicitly a bounded retained specialist runtime over `src/guppy/merlin/specialist_support.py`, not an ambiguous live hub surface.
- `FR3-T7` is complete: waivers were tightened to the measured post-split sizes and the remaining hotspot list is now down to five files.

Measured post-wave sizes:

- `src/guppy/api/server_runtime_snapshot.py` -> `1419`
- `src/guppy/merlin/core.py` -> `1071`
- `ui/launcher/launcher_window.py` -> `2648`
- `ui/launcher/views/models_view.py` -> `969`
- `ui/launcher/views/settings_operations_panel.py` -> `738`
- `ui/launcher/views/instance_manager_view.py` -> `370`

Freeze-readiness call:

- This wave materially lowered the remaining hotspot pressure and removed `instance_manager_view.py` from the waiver set.
- The branch is now a credible freeze-candidate worktree for this tranche set, with the remaining debt narrowed to five explicit bounded shells rather than a broader mixed-concern cluster.

## Remaining Hotspot Reduction Follow-On (April 20, 2026, FR4)

Execution note:

- With `FR3` complete, the remaining waived hotspot set started at five files: `server_runtime_snapshot.py`, `merlin/core.py`, `launcher_window.py`, `models_view.py`, and `settings_operations_panel.py`.
- The first automatic `FR4` slice focuses on the two smallest live UI shells first so the waiver list can shrink again before touching the heavier launcher/API pair.

What ships:

1. `FR4-T1 - Settings workflow/terminal detail extraction`
   - Move the remaining workflow loop, operator-log, and embedded-terminal construction out of `settings_operations_panel.py`.
   - Acceptance: Settings Operations drops fully below the base cap and remains a composition shell.
2. `FR4-T2 - Models route/loadout coordination extraction`
   - Move route-strategy and mixed/loadout coordination out of `models_view.py` into a dedicated support seam.
   - Acceptance: `models_view.py` drops fully below the base cap while keeping model identity distinct from persona.
3. `FR4-T3 - Launcher shell fifth extraction`
   - Target another bounded family inside `launcher_window.py`, preferably API control or automation/request routing.
4. `FR4-T4 - Snapshot compatibility shell final reduction`
   - Push one more bounded response/composition family out of `server_runtime_snapshot.py`.
5. `FR4-T5 - Merlin retained-runtime hardening`
   - Either reduce `merlin/core.py` again or tighten its retained-runtime quarantine with one more extraction.
6. `FR4-T6 - Guardrail reset and freeze-candidate refresh`
   - Refresh waivers, rerun guarded validation, and restate the remaining debt truthfully.

Integrated checkpoint (April 20, 2026, FR4-T1 / FR4-T2):

- `settings_operations_panel.py` now delegates the remaining workflow, operator-log, and embedded-terminal construction through `ui/launcher/views/settings_workflow_terminal_sections.py`.
- `models_view.py` now delegates mixed-route, loadout, and route-strategy coordination through `ui/launcher/views/models_management_support.py`.
- Measured post-slice sizes:
  - `ui/launcher/views/settings_operations_panel.py` -> `593`
  - `ui/launcher/views/models_view.py` -> `694`
- Result: both files are now below the base cap and can be removed from the waiver list.

Remaining waived hotspot set after the FR4 checkpoint:

- `src/guppy/api/server_runtime_snapshot.py` -> `1419`
- `src/guppy/merlin/core.py` -> `1071`
- `ui/launcher/launcher_window.py` -> `2648`

Integrated checkpoint (April 20, 2026, FR4-T3 / FR4-T5):

- `FR4-T3` is complete: `launcher_window.py` now delegates the direct runtime warmup/audit/health helpers through the existing `src/guppy/launcher_application/launcher_api_runtime_control.py` seam.
- `FR4-T4` is complete: `server_runtime_snapshot.py` now delegates Claude/Ollama tool-call execution through the existing `src/guppy/api/realtime_inference_support.py` seam instead of owning those assembled loops inline.
- `FR4-T5` is complete: `merlin/core.py` now delegates spell dispatch and startup-system assembly through the bounded retained-runtime seam in `src/guppy/merlin/specialist_support.py`.
- Measured post-wave sizes:
  - `ui/launcher/launcher_window.py` -> `2590`
  - `src/guppy/api/server_runtime_snapshot.py` -> `1325`
  - `src/guppy/merlin/core.py` -> `1003`

Remaining waived hotspot set after the full FR4 wave:

- `src/guppy/api/server_runtime_snapshot.py` -> `1325`
- `src/guppy/merlin/core.py` -> `1003`
- `ui/launcher/launcher_window.py` -> `2590`

Freeze-readiness note:

- FR4 removed two more waivers entirely and materially lowered the final three bounded shells.
- The repo remains release-green and is now down to a three-file final hotspot set for the next freeze-down pass.

## Final Hotspot Freeze-Down (April 20, 2026, FR5)

Execution note:

- `FR5` is the closing freeze-down tranche for the last three baseline waivers: `server_runtime_snapshot.py`, `merlin/core.py`, and `launcher_window.py`.
- The goal is not feature expansion. Each card must either push one bounded responsibility family out of the hotspot or prove the remaining shell is intentional and small enough to freeze honestly.
- This tranche also closes with a legacy wording/tree audit so the branch exits slimmer, clearer, and easier to hold.

What ships:

1. `FR5-T1 - Snapshot composition and receipt split`
   - Move one more bounded family out of `server_runtime_snapshot.py`, preferably summary/receipt assembly or workspace readiness composition.
   - Acceptance: `server_runtime_snapshot.py` drops materially again and retains only compatibility-shell orchestration that still genuinely belongs there.
2. `FR5-T2 - Launcher shell sixth extraction`
   - Move another launcher-only responsibility cluster out of `launcher_window.py`, preferably route handoff, status/banner wiring, or shell action coordination.
   - Acceptance: `launcher_window.py` shrinks again without changing visible hub behavior.
3. `FR5-T3 - Merlin catalog and startup reduction`
   - Pull one more bounded concern out of `merlin/core.py`, preferably spell catalog wiring, startup prompt assembly, or helper dispatch normalization.
   - Acceptance: `merlin/core.py` becomes a tighter retained-runtime shell with a shorter direct surface.
4. `FR5-T4 - Legacy wording and repo pare-down pass`
   - Remove stale mentions, dead compatibility wording, and obviously unnecessary tracked remnants discovered during the final hotspot pass.
   - Acceptance: docs and live UI no longer imply obsolete ownership or legacy names, and the tracked tree is smaller or cleaner than it was at FR5 start.
5. `FR5-T5 - Freeze audit and waiver closeout`
   - Re-measure the final three shells, tighten waivers again, rerun full validation, and state plainly whether the branch is freezeable at the end of the pass.
   - Acceptance: `release-check` is green, waiver metadata matches the repo exactly, and the branch exits with an honest freeze-readiness statement.

Execution order:

1. Run `FR5-T1`, `FR5-T2`, and `FR5-T3` in parallel or near-parallel because their write scopes are disjoint.
2. Fold the resulting cleanup opportunities into `FR5-T4` once the major extractions settle.
3. Finish with `FR5-T5` for line-cap truth, release evidence, and the final freeze statement.

Expected exit:

- The branch remains release-green.
- The three remaining hotspots are materially smaller again.
- The repo exits with a short, explicit final debt list suitable for freeze or stabilization-branch handling.

Integrated checkpoint (April 20, 2026, FR5-T1 / FR5-T5):

- `FR5-T1` is complete: `server_runtime_snapshot.py` now delegates status-context and metrics shaping through `src/guppy/api/snapshot_status_context_support.py`, and its realtime helper wrappers have been reduced to direct bound aliases where the compatibility shell does not need to own bespoke bodies.
- `FR5-T2` is complete: `launcher_window.py` now delegates the API/runtime-control method family through `ui/launcher/launcher_runtime_control_mixin.py`, while keeping module-level compatibility symbols intact for smoke and security tests that still patch the launcher shell directly.
- `FR5-T3` is complete: `merlin/core.py` now imports its retained system prompt, spell map, and tool catalog from `src/guppy/merlin/catalog.py`, leaving the core module focused on runtime dispatch and startup assembly.
- `FR5-T4` is complete: stale launcher chrome wording was trimmed from `Guppy AI // WORKSPACE_ASSISTANT` to `Guppy // WORKSPACE_ASSISTANT`, and the final hotspot pass removed one more oversized waiver entirely instead of just shrinking it.
- Measured post-wave sizes:
  - `src/guppy/api/server_runtime_snapshot.py` -> `1242`
  - `ui/launcher/launcher_window.py` -> `2436`
  - `src/guppy/merlin/core.py` -> `402`
- Remaining waived hotspot set after FR5:
  - `src/guppy/api/server_runtime_snapshot.py` -> `1242`
  - `ui/launcher/launcher_window.py` -> `2436`
- Result: Merlin is now fully below the base cap, the waiver list is down to two bounded shells, and the branch is materially closer to a true freeze-ready hold state than it was at the end of FR4.

Follow-on checkpoint (April 20, 2026, FR5 continuation):

- `launcher_window.py` now delegates the Windows Ops/reporting/artifact family through `ui/launcher/launcher_windows_ops_mixin.py`, keeping the launcher shell focused on top-level hub orchestration while preserving the existing smoke-facing behavior.
- `server_runtime_snapshot.py` now delegates one more runtime/helper family through `src/guppy/api/snapshot_runtime_support.py`, and several compatibility wrappers have been tightened into direct bound aliases instead of bespoke shell bodies.
- Measured post-follow-on sizes:
  - `src/guppy/api/server_runtime_snapshot.py` -> `1141`
  - `ui/launcher/launcher_window.py` -> `2141`
- Remaining waived hotspot set after the FR5 continuation:
  - `src/guppy/api/server_runtime_snapshot.py` -> `1141`
  - `ui/launcher/launcher_window.py` -> `2141`
- Result: the repo is down to two materially smaller bounded shells, both with honest pinned waivers and a much narrower freeze-readiness debt surface than the original FR5 starting state.

TR54-B1 Wave 9 checkpoint (current session, TR54 launcher decomposition):

- `launcher_window.py` reduced further via Wave 9 extraction of six more method families:
  - `_refresh_first_run_banner` + `_on_first_run_action_requested` → new `src/guppy/launcher_application/launcher_first_run.py`
  - `_sync_topbar_model_context` → `src/guppy/launcher_application/launcher_poll_orchestration.py`
  - `_on_settings_saved` + `_on_voice_bindings_changed` → `src/guppy/launcher_application/launcher_tools_coordination.py`
  - `_on_home_starter_requested` → `src/guppy/launcher_application/launcher_shell_support.py`
- `server_runtime_snapshot.py` reduced via voice-backend probe extraction → new `src/guppy/api/snapshot_voice_support.py`
- Waivers tightened:
  - `launcher_window.py`: 2141 → 1492
  - `server_runtime_snapshot.py`: 1141 → 1108
  - `launcher_command_flow.py`: new waiver added at 728 (above base cap, pending `launcher_chat_session.py` split)
- All 8 dev-check guards green after wave.
- Measured post-wave sizes:
  - `ui/launcher/launcher_window.py` → `1492`
  - `src/guppy/api/server_runtime_snapshot.py` → `1108`
  - `src/guppy/launcher_application/launcher_command_flow.py` → `728`

## Pre-Launch Work Roadmap Additions (April 19, 2026)

1. `PL-1 - Tool entry and starter-command unification` `proposed`
   - Repo review: tool discovery and prompting are split today across `ui/launcher/views/tools_view_cards.py` (tool catalog), `ui/launcher/launcher_window.py` (`_tool_prompt_for_home`), and Home starter templates in `src/guppy/launcher_application/home_presenter.py`.
   - Response: yes, this should ship. Add one shared action registry so each tool owns a visible label, a button path, a dropdown/starter path, and a short voice-friendly command line a user can say naturally.
   - Suggestion: treat this as a pre-launch usability priority because it simplifies both voice guidance and “what do I type?” onboarding.
2. `PL-2 - Light Guppy branding pass` `proposed`
   - Repo review: the launcher is structurally cleaner now, but the visual language is still restrained and mostly functional; the current shell has room for more identity without changing the information architecture.
   - Google Stitch review: the downloaded `stitch_azure_reef_assistant.zip` bundle proposes an Atoll Editorial / Tropical Editorial direction with warm sand surfaces (`#FBF9F4` / `#F5F3EE`), Noto Serif plus Manrope/Inter typography, a no-hard-divider rule, subtle Caribbean gradient accents, glassmorphic floating surfaces, and a premium stylized “Guppy G” logo mark with turquoise plus sunset-orange glow.
   - Response: yes, with restraint. Add a standard-mode visual theme built from existing blue/orange cues, a subtle sunset gradient, light bubble/reef atmosphere, and the Stitch “editorial horizon” spacing guidance rather than novelty tropical theming.
   - Suggestion: keep branding token-driven in launcher theme/style modules so it can be tuned globally and turned down easily if it starts fighting readability; treat the Stitch logo exploration as a refinement lane for the existing Guppy identity, not a disconnected rebrand.
3. `PL-3 - Senior-friendly clarity, spacing, and hover-help pass` `proposed`
   - Repo review: tooltips and plain-language copy already exist in places like Home starters, tool cards, and Settings panels, but the clarity level is inconsistent across hubs and some controls still rely on learned context.
   - Response: yes, this is a launch requirement rather than polish. Every screen should answer “what is this page for?”, “what happens if I press this?”, and “what should I do next?” in obvious language.
   - Suggestion: add a cross-hub UX pass for hit-target sizing, spacing rhythm, hover-help consistency, and one-line page-purpose copy before launch.
4. `PL-4 - Unified vendor, account, and API-key onboarding` `proposed`
   - Repo review: Settings already owns credentials and device accounts, connector workflows exist, and `/connectors/.../verify` plus machine-secret handling are live; however `docs/CREDENTIALS_AUDIT.md` still shows multiple vendor lanes as stubbed or lifecycle-incomplete, and broader provider onboarding is not yet “5-minute install” simple.
   - Response: yes, this needs to become a first-run system, not just a settings surface. Vendors like TTS providers, image/doc viewers, Docker/Desktop-linked helpers, Lemonade-style challengers, and future plugins should all follow one registry-backed onboarding model with save, verify, reconnect, and clear guidance.
   - Suggestion: add a provider/plugin registry with typed secret fields, account selectors, verify actions, and “next step” guidance so grandma can connect a service without reading setup docs.
5. `PL-5 - Install package versus local base-model fast path` `proposed`
   - Repo review: packaging contracts and audits are now strong (`docs/PACKAGING.md`, `tools/validate_build_checks.py`, `src/guppy/launcher_application/packaging_audit.py`), but the repo still reports no built `dist/` artifact in the current release lane; local Ollama/runtime verification is present, but “fresh install to first working local model” is not yet closed as a guided end-to-end flow.
   - Response: this needs to split into two pre-launch promises: “basic desktop install works cleanly” and “local base model is guided to first success.” They are related, but they are not the same milestone.
   - Suggestion: keep one install checklist lane and one local-model onboarding lane with separate acceptance evidence.
6. `PL-6 - Security hardening for launch, not just development` `proposed`
   - Repo review: the repo has a serious security regression suite (`tests/test_security_hardening.py`), token/repair/auth hardening, permission checks, and connector validation, but it is not yet reasonable to assume the current build is launch-hardened by default.
   - Response: agreed. The current state is much better than “wide open,” but it still needs a launch-grade security pass covering secret storage defaults, network exposure assumptions, connector least privilege, packaged-build posture, dependency hygiene, and a written threat model.
   - Suggestion: create a dedicated pre-launch security gate with explicit default-deny checks, secret-handling review, localhost/external boundary review, and dependency/CVE scanning evidence.

Overall suggestion:

1. Put `PL-1`, `PL-3`, and `PL-4` first because they most directly determine whether a normal user can succeed quickly.
2. Run `PL-5` in parallel once those interaction contracts are stable, because packaging and first local-model success need their own evidence path.
3. Treat `PL-6` as a launch blocker, not a backlog item.
4. Keep `PL-2` intentionally bounded so the UI gets more personality without sacrificing the clarity work in `PL-3`.

---

## Consultant Review Integration (April 19, 2026)

**Source:** Paid engineering + design consultant audit against goals, north star, credentials audit, packaging docs, and voice status.

**Five critical findings and their fixes:**

1. **North star vs complexity gap** - The product thesis is calm, personal, persistent. The current build still leaks too much operator complexity into the first-run surface. Fix: enforce the 3-click rule for anything outside the first 10 minutes; add progressive disclosure in Settings and Tools; reduce first-run to three tasks only (install check, model runtime, first request).

2. **Provider and dependency sprawl** - Four AI SDKs, three TTS options, five integration stubs, and no clear signal about which ones work today. Fix: introduce a formal provider tier system: Core (works with no credentials), Supported Optional (works with a key), Experimental (hidden by default). The registry shows tier and health inline. No bespoke onboarding UX per provider.

3. **Engineering hotspot concentration** - The six tracked coordinator modules are being reduced in P6, but each waiver still needs an explicit weekly reduction target, not just a size cap. Fix: each hotspot waiver is a debt token. Every tranche touching a waived module must reduce its observed size or document why not.

4. **Security posture not launch-simple** - keyring is installed and the hardening suite exists, but there is no explicit launch gate enforcing keychain-first storage, connector least-privilege, or clean dependency posture. Fix: make PL-C6 a release-check step that fails the gate if any of these are unresolved. This is a hard blocker.

5. **First-run path still operationally heavy** - Track 1 vs Track 2 split in PACKAGING.md is the right framing. What is missing is a stateful wizard that guides users through it and a measurable completion rate. Fix: add a three-checkpoint first-run wizard and log first_run_checkpoint_N_completed per checkpoint.

**Design direction adopted from consultant review:**

- Quiet hierarchy: one primary accent color, fewer competing badge stacks, no permanent status blocks in Home Chat.
- Large hit targets (primary buttons >= 36px, secondary >= 28px) are non-negotiable.
- PL-C3 (clarity) must land before PL-C2 (branding). Branding over unresolved layout makes it worse.
- Reference product for first-run: ChatGPT Desktop (immediate comprehension without explanation).

**Competitive positioning notes:**

- Claude Desktop: best-in-class calm interaction model. Guppy Home Chat should feel this quiet.
- Cursor: contextual actions scoped to immediate relevance. Guppy Tools should surface only what is actionable right now.
- LM Studio: local runtime status stays demoted from daily chat. Guppy Models Hub should follow this.
- Open WebUI: excellent operator power, poor first-run experience. Guppy must not inherit that cost.

**Revised success metrics for Tranche 52 exit:**

- Time to first successful request on a clean machine: target under 5 minutes.
- Hub purpose comprehension: first-time user can name each hub purpose in under 3 seconds.
- First-run wizard completion rate: target >= 80% from checkpoint 1 to checkpoint 3.
- Security gate: release-check passes the security gate step on every release candidate.
- Provider setup: Core providers require zero credentials; Supported Optional require under 2 minutes to verify.

---

## Executable Pre-Launch Tranche (Tranche 52: Pre-Launch Usability, Onboarding, and Trust)

Execution note (April 20, 2026 closeout):

- This tranche is now closed with release-green evidence and a generated readiness report.
- The five-hub ownership model remained intact: Home, Models, Tools, Library, and Settings did not change domain ownership.
- Stitch guidance remained bounded visual direction while clarity and trust foundations landed first; the dedicated branding lane (`PL-C2`) has now been executed as part of tranche closeout follow-through.

What ships:

1. `PL-C1 - Tool action registry and starter-command unification` `complete`
   - Build one shared tool action registry that pairs each tool with:
     - a launcher-visible label
     - a short command line a user can type or speak
     - a starter/dropdown entry for Home
     - a button action path from Tools or other hubs
   - Remove the current split between tool prompts in `ui/launcher/launcher_window.py`, starter copy in `src/guppy/launcher_application/home_presenter.py`, and catalog-only data in `ui/launcher/views/tools_view_cards.py`.
   - Acceptance: a user can discover the same action from button, starter, dropdown, and plain-language prompt without the wording changing across surfaces.
2. `PL-C2 - Stitch-guided visual system and logo refinement` `complete`
   - Add a bounded standard-mode visual pass using the reviewed Stitch guidance:
     - warm sand surface hierarchy
     - turquoise/sunset-orange accent system
     - serif headline plus clean sans UI pairing
     - no-heavy-divider layout separation
     - light glass/gradient treatment for select surfaces only
   - Review and integrate the downloaded premium “Guppy G” logo direction as a refinement path for launcher/taskbar/sidebar branding.
   - Acceptance: launcher chrome feels more branded and cohesive without reducing legibility, information density, or interaction clarity.
3. `PL-C3 - Senior-friendly clarity, spacing, and hover-help pass` `complete`
   - Audit every hub for:
     - button hit-target clarity
     - spacing rhythm at common desktop sizes
     - page-purpose text
     - hover-help or tooltip support where labels are not self-explanatory
   - Use the “80-year-old user” bar as the product test for wording, visual grouping, and button confidence.
   - Acceptance: each primary screen explains itself plainly, and key controls no longer depend on hidden product knowledge.
4. `PL-C4 - Unified provider, account, and API-key onboarding` `complete`
   - Normalize vendor onboarding behind one provider/plugin registry with typed secret fields, account slots, verify/reconnect flows, and guided next steps.
   - Cover current and planned external lanes such as TTS vendors, image/doc viewing helpers, Docker/Desktop-linked services, Lemonade/runtime challengers, and future provider plugins.
   - Acceptance: Settings can save, verify, reconnect, and explain provider status consistently, and new providers can be added without bespoke one-off UX each time.
5. `PL-C5 - Install package and local base-model first-success split` `complete`
   - Separate “basic desktop install” from “first local base model works” into two explicit readiness contracts.
   - Define acceptance evidence for:
     - package/install success
     - first-run onboarding
     - local runtime detection
     - first local model success path
   - Acceptance: the roadmap and validation evidence no longer blur installer readiness with local-model readiness.
6. `PL-C6 - Launch-grade security gate` `complete`
   - Convert the current strong development hardening posture into a launch gate with explicit checks for:
     - secret storage defaults
     - localhost versus external boundary assumptions
     - connector least privilege
     - packaged-build posture
     - dependency and vulnerability review
     - written threat model / truth summary
   - Acceptance: launch security is evaluated by a dedicated gate, not inferred only from existing regression tests.
7. `PL-C7 - Validation, docs, and pre-launch handoff evidence` `complete`
   - Update active truth docs with progress, tradeoffs, and final acceptance for the tranche.
   - Add focused tests for the new tool action registry, onboarding flows, and any touched launcher UI behavior.
   - Run `check_doc_ownership.py`, `dev-check --guard-scope delta`, and `release-check`.

Acceptance (closeout status):

1. Tool actions are discoverable through shared registry paths and consistent wording.
2. Cross-hub spacing, hover-help, and plain-language guidance landed and are smoke-covered.
3. Provider/account/API-key onboarding now carries provider-tier metadata and consistent selector badges.
4. Installer readiness and local-model readiness are represented as separate, testable tracks.
5. Security is enforced through an explicit release-check launch gate with documented evidence.
6. Validation is green for the tranche closeout, with receipts and summary written under `.tmp/dev-workflow/reports/`.
7. Dedicated Stitch-guided branding (`PL-C2`) is complete with bounded launcher token/style updates and topbar chrome alignment.

Next tranche focus from current gaps:

1. Validate and tune the shipped `PL-C2` branding tokens against readability and contrast checks on real machines.
2. Deepen Agent Tools vs App Mgmt execution enforcement (behavior and permission routing, not labels only).
3. Expand Library workflow depth (root selection ergonomics, note editing flow, richer source reuse).
4. Run broader real-device voice preview validation and document matrix results.
5. Improve live route/status signaling depth while preserving current hub boundaries.
6. Continue builder/off-hours polish with repeated stress validation.
7. Close collaboration-cue and local-model decision evidence gaps for the May 22 checkpoint.

Execution checkpoint (April 20, 2026 - tranche follow-through wave 1):

1. `PL-C2` completion evidence: bounded quiet-hierarchy branding updates landed in `ui/launcher/tokens.py`, `ui/launcher/stylesheet.py`, `ui/launcher/components/topbar.py`, `ui/launcher/components/sidebar.py`, and `ui/launcher/components/status_panel.py` (warm-sand surface aliases, softer border tokens, and aligned launcher chrome treatment).
2. Dedicated launcher-chrome smoke validations are green after the branding pass: `tests/smoke/test_launcher_interactions_smoke.py` and `tests/smoke/test_launcher_nav_chrome_smoke.py`.
3. Live route/status signaling depth improved in launcher polling: `ui/launcher/launcher_window.py` now refreshes daily runtime + route context and re-syncs topbar model context every poll tick after runtime facts update.
4. Off-hours stress validation was rerun with a bounded profile and wrote a fresh evidence artifact at `runtime/stress_reports/stress_report_20260420_024522.json` (`failure_count: 0` across auth, endpoint, reminder, and logging lanes).
5. Validation snapshot for this wave: `python tools/check_doc_ownership.py` passed, `python tools/dev_workflow.py dev-check --guard-scope delta` passed, and focused regression suite passed (`21 passed`) for launcher/status/route/provider-runtime coverage.

Execution checkpoint (April 20, 2026 - tranche follow-through wave 2 / N1-N5):

1. `N1` branding/readability tuning is now live and test-covered: deeper contrast-safe accent text tokens plus quieter launcher chrome landed in `ui/launcher/tokens.py`, `ui/launcher/components/topbar.py`, `ui/launcher/components/sidebar.py`, and `ui/launcher/components/status_panel.py`, with focused validation in `tests/unit/test_launcher_branding_tokens.py`.
2. `N2` Agent Tools versus App Mgmt execution enforcement is now behaviorally routed instead of copy-only: blocked connector-tool remediation requests now move through `ui/launcher/views/tools_view.py`, `ui/launcher/views/tools_view_cards.py`, `src/guppy/launcher_application/tool_readiness.py`, `src/guppy/launcher_application/connector_workflow.py`, and `ui/launcher/launcher_window.py` so Settings owns connector/account fixes while workspace-policy-only issues stay out of Settings.
3. `N3` Library follow-through is live: `ui/launcher/views/library_view.py`, `src/guppy/launcher_application/library_workflow.py`, and `src/guppy/launcher_application/library_presenter.py` now support inline approved-root switching, clearer multiline note edit guidance, and richer `USE IN CHAT` detail/origin reuse for saved reply notes, saved reply artifacts, and approved-root files.
4. `N4` voice/runtime evidence was refreshed structurally on the current machine: `python tools/verify_provider_runtime.py` wrote `runtime/provider_runtime_snapshot.json`, and `python tools/generate_voice_runtime_prefill.py` wrote `docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md` with current machine/audio metadata plus pending-matrix counts (`VOICE: 11`, `RUNTIME: 6`). Manual real-device sign-off is still required for those remaining matrix rows.
5. `N5` live route/status signaling depth is now explicitly locked by tests: `tests/unit/test_shell_status.py` covers route-preview mirroring into Settings, daily-activity sync, and right-tray context sync for the `src/guppy/launcher_application/shell_status.py` seam.
6. Focused N1-N5 regression validation is green: launcher branding, tool routing, library workflow, voice/runtime prefill, provider-runtime scope, shell-status sync, Settings hub smoke, Library hub smoke, and launcher interaction smoke all passed (`72 passed` across the focused bundle).

Recommended lane split:

1. Lane A: tool action registry plus starter/dropdown/prompt unification
2. Lane B: UI clarity, spacing, hover-help, and senior-friendly copy audit
3. Lane C: Stitch-guided theme tokens, gradient treatment, and logo refinement
4. Lane D: provider/account/API-key onboarding registry and verification flows
5. Lane E: installer versus local-model readiness contracts plus security gate planning
6. Lead integrator: merge sequencing, docs, guardrails, and release evidence

---

## Mega-Tranche 53 Closeout (Massive Hardening, Usability, UI Quality, And Tool-System Sweep)

Execution note (April 20, 2026 closeout):

- Tranche 53 is complete.
- It was intentionally split into 10 high-impact execution packs so the work could be parallelized without dissolving into unbounded polish.
- The tranche explicitly combined desktop launcher/startup hardening, large usability sweeps, a UI review against Guppy goals plus Stitch and inspiration sources, a full tool-system audit, packaging/install/local-runtime readiness, and trust/security hardening.
- Framework rule held throughout: keep the existing PySide6 + `launcher_application` + `runtime_application` shape; do not introduce new top-level destinations or a framework rewrite.
- Packaging/install evidence is now part of the live release truth instead of a planned future lane.

What ships:

1. `PL-C8 - Product goals, UI goals, and first-run contract audit` `complete`
   - Lock a written pass/fail audit against Guppy’s actual goals: calm chat-first, 5-minute useful success, grandma-readable screens, and progressive disclosure for operator features.
   - Produce one matrix per hub: Home, Models, Tools, Library, Settings.
   - Acceptance: every major hub has a written pass/fail assessment and every failing item maps to one of the cards below.
2. `PL-C9 - Stitch and inspiration-source UI review with implementation deltas` `complete`
   - Review the shipped UI against Google Stitch guidance, Guppy’s blue/orange island-flavor constraints, and reference products such as Claude Desktop, ChatGPT Desktop, Cursor, and LM Studio.
   - Convert that review into a keep/change/remove delta table for chrome, hierarchy, spacing, typography, and token use.
   - Acceptance: one explicit implementation delta table exists and later UI work references it directly.
3. `PL-C10 - Desktop launcher hardening and startup hardening` `complete`
   - Audit and tighten launcher startup, hidden/direct API start, supervised launch, duplicate-window risk, browser-open behavior, startup timing, retries, and failure messaging.
   - Acceptance: no known normal-use duplicate window path remains, startup/recovery messaging is plain-language, and startup-state transitions are test-covered.
4. `PL-C11 - Cross-hub usability sweep and responsive layout pass` `complete`
   - Run a full cross-hub sweep for spacing rhythm, hit-target sizing, control grouping, tooltip coverage, and responsive behavior at smaller launcher widths.
   - Acceptance: no obvious right-edge overflow remains, all hubs stay usable at smaller widths, and new smoke coverage locks the most fragile layouts.
5. `PL-C12 - Home and launcher chrome calmness pass` `complete`
   - Re-evaluate topbar/sidebar/Home against the calm chat-first north star.
   - Demote or remove remaining chrome that competes with daily chat and review secondary window use of screen space.
   - Acceptance: Home remains visually first, model/sub-agent state is visible without clutter, and operator-heavy surfaces do not leak back into Home.
6. `PL-C13 - Full tool-system audit and tool-entry hardening` `complete`
   - Audit tools end to end: tool registry/starter consistency, typed and spoken command discoverability, card clarity, traces/debug evidence, blocked/remediation routing, and permission posture display.
   - Acceptance: every visible tool has one canonical user-facing action line, blocked tools explain why they are blocked and where to fix them, and stale/duplicate wording is removed.
7. `PL-C14 - Provider, account, connector, and plugin lifecycle hardening` `complete`
   - Continue unified onboarding with stronger lifecycle coverage: install, verify, reconnect, disable, and remove states, plus registry-first addition for future providers/plugins.
   - Acceptance: provider lifecycle is consistent across save/verify/reconnect/remove, new providers do not require bespoke UI ownership decisions, and account/key state remains explainable from one Settings-owned surface.
8. `PL-C15 - Packaging, installer, local-model, and real-time execution readiness` `complete`
   - Treat current release-truth gaps as active work: build a real `dist/` artifact path, validate installer/build assumptions against actual output, tighten first-success local-model flow, and verify Ollama, LM Studio, local harness, and declared runtime options honestly.
   - Acceptance: packaging no longer claims GO without a real built artifact, installer readiness and local runtime readiness each have current evidence, and the release-check packaging lane is green for the right reason.
9. `PL-C16 - Massive trust and security hardening sweep` `complete`
   - Expand the launch-grade security gate into a broader trust sweep: secret storage and keychain-first enforcement, network exposure review, connector least privilege, dependency/CVE scanning, packaged-build posture, and honest trust/readiness labels.
   - Acceptance: no misleading `READY`, `GO`, or `healthy` labels remain in launch-critical flows, and trust copy aligns with actual enforcement.
10. `PL-C17 - Integrated code audit, docs audit, UI audit, tool audit, and release closeout` `complete`

- Close the tranche with one top-to-bottom pass across code, docs, UI, tools/connectors, and guarded validation.
- Acceptance: docs, code, tests, and release evidence agree, and remaining blockers are specific and ranked.

April 20, 2026 execution checkpoint:

- `PL-C8` is complete with a repo-grounded baseline in `docs/generated/TRANCHE_53_GOALS_UI_AUDIT_20260420.md`.
- `PL-C9` is complete with a keep/change/remove implementation delta in `docs/generated/TRANCHE_53_STITCH_DELTA_20260420.md`.
- `PL-C10` is now complete and its first live shell fixes remain in code:
  - the topbar now shows a visible runtime/startup status chip
  - the topbar `CHAT` control now routes to chat-context drawer behavior instead of Workspaces
  - Home drawer toggling now actually opens and closes on Home
- Focused validation for the first wave is expected to cover `launcher_shell_support`, `TopBar`, and launcher interaction smoke before broader tranche work continues.

April 20, 2026 second execution checkpoint:

- `PL-C10` and `PL-C11` now have a second live follow-through in Home:
  - Home surfaces a first-run banner with install/model/first-ask status chips
  - the banner gives direct Settings and Models navigation plus a fast path back to the composer
  - Home now applies a tighter density mode at smaller widths so starter and detail controls stop competing with the main chat lane
- The first-run banner is driven from the existing `FirstRunWizard` state file and refreshed when workspace views refresh, so the launcher now exposes setup state without introducing a new route or modal dependency.

April 20, 2026 third execution checkpoint:

- `PL-C11` now has its first broader cross-hub responsive sweep beyond Home:
  - Settings overview cards now collapse from two columns to one at tighter widths, and section shortcut buttons shorten to `OPEN` instead of forcing overflow
  - Device & Accounts connector cards now reflow to 1, 2, or 3 columns based on width, and the desktop/action rows compress without changing workflow meaning
  - Library manager controls now shorten labels on smaller widths and suppress lower-priority hint copy so file, note, and artifact controls stop crowding the main content lane
  - Tools now hide the type-tab strip at narrow widths, shorten the details affordance, and tighten the search/control stack for smaller launcher windows
- Focused clarity smoke now covers these compact-mode behaviors directly, so the responsive pass is validated instead of being visual-only.

April 20, 2026 fourth execution checkpoint:

- `PL-C11` and `PL-C12` now have a closeout pass across launcher chrome, dense secondary panels, and tooltip/plain-language coverage:
  - the topbar now demotes workspace chrome earlier at smaller widths so the visible model/session summary stays present while search and workspace controls stop crowding the header
  - Settings Operations now carries broader hover-help on recovery/runtime/connector/workflow/terminal actions and compresses long secondary button labels when the surface is narrower
  - tool cards now mirror their evidence, policy, and guard text into tooltips so the longer explanations remain available without forcing every card open
- The result is a calmer chat-first shell and a more explainable secondary operations surface without removing the visible model/runtime state that earlier tranche work established.

April 20, 2026 fifth execution checkpoint:

- `PL-C13` now closes around the shared tool action registry instead of one-off card wording:
  - tool cards now surface one canonical typed/spoken action line directly from `tool_action_registry.py`
  - the same registry-backed phrasing still feeds Home starters, launcher prompt priming, and tool-card hint affordances, so visible tool-entry wording no longer drifts by surface
  - blocked tool remediation keeps the same Settings-owned route, but the manage tooltip now carries the destination plus the current note instead of a generic handoff
- `PL-C14` now closes around provider-registry-backed lifecycle guidance in Settings:
  - provider entries now carry both pre-connect guidance and post-connect example prompts
  - Device & Accounts now uses that registry-backed lifecycle copy for next steps, connected hints, and action tooltips
  - the result is a more registry-first provider extension path, with fewer connector-specific copy branches living only in the panel

April 20, 2026 sixth execution checkpoint:

- `PL-C15` is now complete with real packaging and readiness evidence instead of structural placeholders:
  - `src/guppy/launcher_application/install_readiness.py` now treats release handoff evidence and a real `dist/` build as part of Track 1, and the root-path bug in the install/model/first-run helpers was fixed so the checks read the repo and runtime directories correctly
  - `src/guppy/launcher_application/local_model_readiness.py` now passes on any honest declared local route (`ollama`, `lmstudio`, or `local_harness`) instead of treating Ollama as the only valid success path, while still reporting optional challengers such as Lemonade honestly
  - `src/guppy/launcher_application/packaging_audit.py` now rejects stale non-packaging release receipts and tiny fake `dist` outputs, so packaging cannot claim `GO` from an old verify receipt or a stub executable

April 20, 2026 seventh execution checkpoint:

- `PL-C16` is now materially advanced with trust/readiness enforcement tightening in code instead of doc-only intent:
  - degraded keyring backends now count as unavailable in `utils/secret_store.py`, so insecure/plaintext keyring fallbacks no longer masquerade as real OS-backed secret storage
  - `src/guppy/launcher_application/security_gate.py` now checks both Settings-owned connector action enforcement and auth-state/secret-read gating when evaluating connector scope
  - provider secret readiness now surfaces environment-backed storage posture through `src/guppy/workspace_governance/machine_auth.py` and `provider_status.py`, so “ready” states that still rely on env fallback carry an explicit hardening warning
  - `src/guppy/launcher_application/connector_workflow.py` now only accepts the known Settings request sources instead of any `settings*` prefix
  - `src/guppy/launcher_application/status_poll.py` no longer defaults missing API status to `healthy`, and background launcher copy now reports `ONLINE` instead of overclaiming `READY`
- Focused trust/security validation is green: targeted unit tests passed, `tools/run_security_gate.py` reported `Launch ready: YES`, and `dev-check --guard-scope delta` passed.

April 20, 2026 eighth execution checkpoint:

- `PL-C17` is now complete as the integrated audit and doc closeout lane:
  - active truth docs were refreshed to the current tranche state and current release-lane contract instead of older April 19 packaging-era snapshots
  - `docs/generated/PRE_LAUNCH_READINESS_20260420.md` was replaced with an honest tranche-53 checkpoint that no longer overclaims launch `GO` from an older tranche/receipt
  - `docs/generated/TRANCHE_53_INTEGRATED_AUDIT_20260420.md` now records the bounded code/docs/UI/tool audit findings fixed in this pass plus the ranked remaining blockers
  - packaging/install wording drift was cleaned up so Track 1 / Track 2 language, default Windows build output, and release-closeout evidence read consistently across code and docs

April 20, 2026 ninth execution checkpoint:

- `PL-C16` is now complete as a release-backed trust/security lane instead of an advisory-only sweep:
  - `tools/dev_workflow.py release-check` now runs `tools/run_dependency_audit.py`, and the dependency audit writes machine-readable `pip-audit` evidence to `.tmp/dev-workflow/reports/pip-audit-report.json`
  - the current dependency audit is green with no known vulnerabilities found in `requirements.txt`, so the tranche now has real dependency/CVE evidence instead of a manual reminder
  - desktop launcher support was re-verified on this machine by refreshing `tools/ensure_desktop_launcher.ps1`, and the supported desktop shortcut now targets `dist/Guppy/Guppy.exe` directly when the packaged build exists
  - `docs/generated/TRANCHE_53_SECURITY_AUDIT_20260420.md` now records the trust/security closeout evidence, remaining non-launch blockers, and the supported launcher-link posture
- With `PL-C16` and `PL-C17` both closed, Tranche 53 is now complete as an integrated hardening/usability/security sweep.

Acceptance:

1. Launcher and startup behavior are materially more stable and easier to understand.
2. The UI has a written review against Guppy goals, Stitch direction, and inspiration sources.
3. All five hubs receive a real usability sweep, not isolated button polish.
4. Tool discovery, tool wording, tool blocking, and remediation are audited end to end.
5. Provider/account/plugin lifecycle remains unified in Settings and is cheaper to extend.
6. Packaging/install/local-runtime evidence is honest and current, including a real `dist/` path.
7. Security/trust language and actual enforcement align.
8. The tranche closes with one integrated audit and a ranked blocker list.

Recommended execution order:

1. `PL-C8` to lock the goals/usability contract.
2. `PL-C9` so the Stitch/inspo review becomes implementation guidance.
3. `PL-C10`, `PL-C11`, and `PL-C12` as the first main execution wave for launcher, Home, and responsive usability hardening.
4. `PL-C13` and `PL-C14` in parallel once UI wording/routing contracts are stable.
5. `PL-C15` as an active execution lane because packaging truth is currently the main release blocker.
6. `PL-C16` throughout the tranche, then explicitly closed before release evidence.
7. `PL-C17` last as the integrated audit and closeout.

Recommended lane split:

1. Lane A: `PL-C8` + `PL-C9` goals/UI/Stitch/inspo contract baseline
2. Lane B: `PL-C10` launcher/startup hardening
3. Lane C: `PL-C11` + `PL-C12` cross-hub usability and chrome calmness
4. Lane D: `PL-C13` tool-system audit and tool-entry hardening
5. Lane E: `PL-C14` provider/account/plugin lifecycle hardening
6. Lane F: `PL-C15` packaging/install/local-runtime readiness
7. Lane G: `PL-C16` trust/security sweep
8. Main integration lane: `PL-C17` docs/code/UI/tool audit, evidence, and final validation

High-impact success metrics:

1. Time to first useful result on a clean machine stays under 5 minutes.
2. Every primary hub purpose is understandable in under 3 seconds by a first-time user.
3. No right-edge overflow or obvious spacing break remains at smaller launcher widths.
4. Tool invocation wording is canonical and consistent across button, starter, typed, and spoken paths.
5. Packaging/install readiness is backed by a real built artifact, not assumptions.
6. Launch-critical trust/readiness labels remain honest.

Code and repo evaluation summary:

1. The current repo already has the right ownership boundaries for this tranche: Tools owns operational discovery, Settings owns credentials, Models owns runtime/model selection, and Home already has starter plumbing that can be reused.
2. The biggest structural win available is to replace duplicated prompt/copy definitions with a shared action registry rather than adding more per-view button logic.
3. The Stitch bundle is a good fit for the launcher because it reinforces desktop-first information density and calmer editorial spacing rather than pushing a mobile or novelty aesthetic.
4. Provider/account onboarding is functionally present in pieces today, but it still reads like a power-user system rather than a “5 minutes to helpful assistant” launch path.
5. Packaging and local-model readiness are both real priorities, but they need separate evidence and should stop being treated as one blended milestone.
6. Security has meaningful real work behind it already, but it is still missing the explicit launch-grade framing and closure criteria that would make it a trustworthy ship gate.

---

## Handoff Log Archive Reference

The full entry-by-entry handoff history through April 18, 2026 is preserved verbatim at `docs/archive/root-history/ROADMAP_2026-04-17.md` and in the tranche notes embedded in the git log. This file does not repeat those entries — see the archive for full historical context.

Release-lane closeout uses `python tools/dev_workflow.py release-check`, which writes the receipt and summary with a stable `Ref`, complete gate state, and an explicit `Next Review Step`.

## Weekly Status Report (April 19 - April 25, 2026)

1. Week objective
   Keep the automatic `P6` slices moving until the remaining runtime and launcher coordinators are smaller, cleaner, and ready for real-machine validation and downstream packaging work.

2. Track status
   `P1`, `P2`, `P3`, `P4`, and `P5` are complete as of April 19, 2026; `P6` remains active as the platform-hardening and packaging-readiness lane, with Tranches 46 through 51 now closed and green.

3. Gate snapshot
   Release lane is green today: `release-check-20260420-154801` passed at `8/8`, with `543 passed` in the default suite and `138 passed` in product smoke.

4. Active risks
   The remaining risk is no longer destination ownership. It is concentrated in the still-waived runtime and launcher coordinators plus broader real-machine validation for voice playback, local runtime behavior, and packaged-environment spot checks.

5. This-week decisions
   Keep `P6` focused on bounded coordinator reductions and validation-contract clarity, not new hub work; treat the new runtime and voice validation matrices as the handoff for real-machine follow-through; and hold packaging expansion behind those hardening seams.

## Completed Tranche (Tranche 46: April 20 - May 9)

Execution note (April 19, 2026):

- Tranche 46 is the first active execution slice inside `P6`.
- Scope is intentionally about hardening and distribution, not new destinations or broad feature expansion.
- The priority is to reduce change risk in the largest active hotspots while keeping stable main/sub-agent loadability, model harness reliability, connector readiness, backend support, and release repeatability intact.
- Framework evaluation says keep the existing PySide6 + `launcher_application` + `workspace_governance` + `experience_config` structure. Do not introduce a new UI framework or route layer.
- Code review says the first tranche targets should be the active shell and harness hotspots rather than more product-surface expansion.

What ships:

1. `P6-C1 — Architecture hotspot contract and review lock`
   - Complete a code/docs review pass for active hotspot modules, current waivers, and launcher-facing runtime seams.
   - Freeze the tranche write targets and extract-only strategy before implementation starts.
   - Keep the active truth docs aligned so the tranche tracks measured hotspot reduction rather than vague cleanup.
2. `P6-C2 — Launcher shell hotspot reduction`
   - Reduce pressure in `ui/launcher/launcher_window.py` by extracting one or more coherent orchestration seams into `src/guppy/launcher_application/`.
   - Prefer workspace refresh, tool/debug refresh, automation/recovery coordination, or view-payload wiring seams over cosmetic reformatting.
   - Preserve the five-hub shell and existing launcher behavior.
3. `P6-C3 — Models and local harness hardening`
   - Harden model-harness readiness, provider status shaping, and local-runtime evidence paths that currently concentrate in the Models surface.
   - Reduce risk around Ollama, LM Studio, and local harness readiness without changing ownership boundaries between Models and Settings.
   - Favor seam extraction or presenter/service shaping over more widget-local branching.
4. `P6-C4 — Tools UI and connector hardening`
   - Tighten Tools/connector state consistency across card copy, readiness evidence, and connector policy hints.
   - Review `utils/connector_manager.py` and connected launcher surfaces for the next safe extraction or hardening seam.
   - Keep Tools operational and recent-evidence focused rather than broadening into a marketplace or audit browser.
5. `P6-C5 — Backend support seams`
   - Add or improve thin backend-facing support seams for launcher-visible runtime/snapshot data instead of deepening direct shell dependence on oversized backend modules.
   - Focus on support for shell/model/tool hardening needs, not broad API redesign.
   - Prefer bounded adapters around `server_runtime*` style hotspots where needed.
6. `P6-C6 — UI spacing and rhythm review`
   - Review spacing, padding, scroll density, and section rhythm across the five shipped hubs.
   - Land targeted layout fixes that improve consistency and reduce crowding/clipping without triggering a broad visual redesign.
   - Reuse existing tokens/components where possible.
7. `P6-C7 — Validation, docs, and release evidence`
   - Expand focused tests for new hardening seams and any visible UI spacing or connector/model behavior changes.
   - Update active truth docs with tranche progress and closeout evidence.
   - Keep `dev-check --guard-scope delta` and `release-check` green.

Progress checkpoint (April 19, 2026):

- `P6-C1` is locked from the hotspot/code review pass.
- `P6-C2` is in with `src/guppy/launcher_application/recovery_coordination.py`; the extracted seam remains in place and the current live shell size is `3407` lines.
- `P6-C3` is in with `src/guppy/launcher_application/models_presenter.py`; the presenter seam remains in place and the current live Models view size is `1435` lines while chat-harness/provider readiness stays explicit.
- `P6-C4` is in with `src/guppy/launcher_application/tool_readiness.py` plus `workspace_tool_readiness(...)` in `utils/connector_manager.py`.
- `P6-C6` now includes low-risk spacing/rhythm cleanup in the shipped Home, Tools, and Settings operations surfaces.
- `P6-C5` is now in with `src/guppy/launcher_application/status_poll.py` plus the API-side `src/guppy/api/status_support.py` and `services_runtime` payload helpers, so launcher-visible runtime data now flows through bounded support seams on both sides.
- `P6-C7` is green for the current checkpoint with updated docs, focused helper coverage, `dev-check` delta/baseline, and `release-check-20260419-211110`.

Closeout checkpoint (April 19, 2026):

- Tranche 46 is release-green and complete for the current hardening scope.
- The launcher shell now routes recovery coordination and status-poll assembly through `launcher_application` seams and is down to `3407` lines in the current worktree.
- `/status` and `/startup/check` now delegate through bounded API support helpers instead of route-local assembly.
- Home, Tools, and Settings spacing/rhythm received a second low-risk cleanup pass, and waiver metadata now matches the live observed hotspot sizes.

Acceptance:

- At least one meaningful seam is extracted from `launcher_window.py`, and launcher-shell hotspot risk is measurably lower after the tranche.
- Models/local harness behavior is more resilient and easier to verify without adding new destination ownership or credential surfaces.
- Tools/connector readiness copy and behavior stay aligned across policy, trace, and connector surfaces.
- Backend support for launcher-visible runtime data becomes more bounded rather than more coupled.
- UI spacing across the five hubs feels more consistent and avoids obvious crowding, clipping, or density regressions.
- Focused smoke/unit coverage passes, then `python tools/dev_workflow.py dev-check --guard-scope delta` and `python tools/dev_workflow.py release-check` pass.

### Code And Docs Review

1. `ui/launcher/launcher_window.py` is the largest active launcher hotspot at `3407` lines and remains the first risk-reduction target.
2. `ui/launcher/views/models_view.py` stays large at `1435` lines and still carries model routing, harness evidence, and runtime-readiness pressure.
3. `ui/launcher/views/settings_operations_panel.py` (`1140` lines) and `ui/launcher/views/assistant_view.py` (`1531` lines) remain major UI density hotspots, though only the lowest-risk seams should be touched in this tranche.
4. `src/guppy/api/server_runtime_snapshot.py` (`3853` lines), `src/guppy/api/server_runtime.py` (`743` lines), and `utils/connector_manager.py` (`1079` lines) remain backend/support hotspots that should be approached through bounded adapters rather than wide edits.
5. The active brief should now describe a hardening tranche rather than leaving the closed P5 tranche as the visible next action.
6. Current measured checkpoint in the live worktree: `launcher_window.py` `3407`, `models_view.py` `1435`, `settings_operations_panel.py` `1050`, `assistant_view.py` `1531`, and `server_runtime_snapshot.py` `3853`.

### Framework And Monolith Evaluation

1. Keep the current PySide6 widget framework and the existing `launcher_application` / `workspace_governance` / `experience_config` seams.
2. Do not introduce a new UI framework, route architecture, or broad API refactor for Tranche 46.
3. Preferred distribution targets for this tranche:
   - launcher-shell orchestration helpers out of `launcher_window.py`
   - model/runtime/harness shaping seams out of `models_view.py`
   - connector-status or connector-policy support seams that reduce UI coupling
   - bounded backend adapters in `src/guppy/launcher_application/` rather than direct UI-to-backend expansion
   - spacing/layout cleanup through existing tokenized UI components instead of new styling systems
4. Current hotspot watchlist:
   - `ui/launcher/launcher_window.py` at `3407` lines
   - `ui/launcher/views/models_view.py` at `1435` lines
   - `ui/launcher/views/settings_operations_panel.py` at `1050` lines
   - `ui/launcher/views/assistant_view.py` at `1531` lines
   - `utils/connector_manager.py` at `1079` lines
   - `src/guppy/api/server_runtime_snapshot.py` at `3853` lines

### Agent Execution Split (Tranche 46)

1. Agent A: launcher-shell hotspot reduction and bounded seam extraction.
2. Agent B: models/runtime/harness hardening and evidence shaping.
3. Agent C: connector/tool hardening plus any bounded support-module extraction.
4. Agent D: UI spacing review, focused test support, and docs review.
5. Lead integrator: merge sequence, hotspot tracking, guardrails, and final release evidence.

### Tranche 46 Merge Checkpoints

1. After `P6-C2`: compile plus focused launcher/model smoke.
2. After `P6-C3` through `P6-C5`: focused unit/smoke coverage for harness, connector, and support seams.
3. After `P6-C6`: targeted UI/smoke pass to confirm no density or clipping regressions in shipped hubs.
4. Every merge gate: `python tools/dev_workflow.py dev-check --guard-scope delta`.
5. Tranche close: `python tools/dev_workflow.py release-check` with updated receipt/summary references.

## Closed Tranche (Tranche 47: April 20 - May 16)

Execution closeout (April 19, 2026):

- Tranche 47 is complete and release-green inside `P6`.
- Scope stayed on technical-debt reduction and packaging-facing cleanup rather than new launcher destinations or broad feature expansion.
- The tranche retired another duplicate runtime-status path, extracted one more launcher shell seam, reduced Home/Settings density, split connector workspace readiness logic into its own module, and refreshed the guardrails/docs to the new observed hotspot sizes.

Tech-debt review:

1. `src/guppy/api/server_runtime_snapshot.py` is still the largest backend hotspot, but it is down to `3369` lines and now reuses the shared status/startup support path for one more legacy branch.
2. `ui/launcher/launcher_window.py` is down to `3218` lines after the automation-test support extraction, though top-level workspace and orchestration pressure still remains.
3. `ui/launcher/views/assistant_view.py` is down to `1327` lines, with active-context rendering moved behind a dedicated helper view module.
4. `ui/launcher/views/models_view.py` remains oversized at `1437` lines, but route/loadout copy shaping now flows through the models presenter seam instead of staying fully inline.
5. `ui/launcher/views/settings_operations_panel.py` is down to `908` lines, and `utils/connector_manager.py` is down to `654` lines after the connector workspace/readiness split.
6. Active docs and guardrails are now aligned to the latest observed sizes, receipts, and tranche state instead of the earlier post-audit estimates.

What ships:

1. `P6-C8 - Runtime snapshot debt reduction` `complete`
   - Reduce duplication between `server_runtime_snapshot.py`, `services_runtime.py`, and the new runtime/status helpers.
   - Prefer extracting or deleting duplicated legacy runtime-status helpers over adding more wrappers.
   - Keep `/status`, `/startup/check`, and local-runtime behavior stable.
2. `P6-C9 - Launcher shell second extraction` `complete`
   - Extract another coherent seam out of `launcher_window.py`.
   - Preferred targets are workspace refresh/state application, automation snapshot wiring, or status-panel composition helpers.
   - Avoid route or product-surface changes.
3. `P6-C10 - Home and Settings density reduction` `complete`
   - Split one or more presenter/rendering seams out of `assistant_view.py` and `settings_operations_panel.py`.
   - Focus on read-only or copy/payload shaping first, not behavior rewrites.
   - Keep the visible Home chat-first contract unchanged.
4. `P6-C11 - Models and connector debt reduction` `complete`
   - Continue bounded decomposition in `models_view.py` and `connector_manager.py`.
   - Preferred direction is presenter/service extraction, not broader provider-surface expansion.
   - Keep current model/provider/connector behavior stable.
5. `P6-C12 - Packaging-facing cleanup and validation` `complete`
   - Audit launch/packaging prerequisites, runtime write locations, and release evidence paths for distribution readiness.
   - Update docs and guardrail metadata to match the live codebase after the debt cuts land.
   - Close with focused tests, `dev-check --guard-scope delta`, `dev-check --guard-scope baseline`, and `release-check`.

Acceptance:

- Runtime/status logic has fewer duplicated implementations and a clearer single-source direction.
- `launcher_window.py` is materially smaller after one additional extraction.
- `assistant_view.py`, `settings_operations_panel.py`, and `connector_manager.py` are all materially reduced, and `models_view.py` gained another presenter seam.
- Packaging-facing docs, guardrails, and release evidence are refreshed to the latest observed state.
- Guardrails and `release-check` stay green.

Recommended execution split:

1. Agent A: runtime snapshot and API/runtime duplication reduction.
2. Agent B: launcher shell second extraction.
3. Agent C: Home/Settings density reduction.
4. Agent D: Models/connector debt reduction.
5. Lead integrator: packaging-facing cleanup, docs, guardrails, and final validation.

## Closed Tranche (Tranche 48: April 19, 2026)

Execution closeout (April 19, 2026):

- Tranche 48 is complete and release-green inside `P6`.
- Scope stayed on the packaging-facing and at-cap hotspot priorities identified after Tranche 47.
- The tranche closed another full automatic slice: runtime snapshot follow-on extraction, launcher shell third split, models presenter split, connector continuation, and packaging write-path audit.

What shipped:

1. `P6-C13 - Runtime snapshot follow-on extraction` `complete`
   - `server_runtime_snapshot.py` now reuses more of the shared runtime/status services for startup readiness and local-runtime helper paths.
   - The snapshot hotspot is now at `3400` guard lines instead of the earlier `3834`.
2. `P6-C14 - Launcher shell third split` `complete`
   - Quick-action planning and notification badge state moved into `src/guppy/launcher_application/launcher_shell_support.py`.
   - `launcher_window.py` is now at `3454` guard lines.
3. `P6-C15 - Models route/presenter split` `complete`
   - Route preview wording, target formatting, and route decision narration moved behind `src/guppy/launcher_application/models_presenter.py`.
   - `models_view.py` is now at `1529` guard lines.
4. `P6-C16 - Connector continuation and packaging audit` `complete`
   - Connector action-history/finalization moved behind `utils/connector_action_history.py`, reducing `connector_manager.py` to `670` guard lines.
   - Packaging/report write-path checks now run through `src/guppy/launcher_application/packaging_audit.py` and `tools/validate_build_checks.py`.
5. `P6-C17 - Validation and tranche closeout` `complete`
   - Active docs, line-cap waivers, and release evidence were refreshed after the integrated pass.
   - Guardrails, smoke, default tests, and release-check all stayed green.

Measured hotspot state:

1. `src/guppy/api/server_runtime_snapshot.py`: `3400`
2. `ui/launcher/launcher_window.py`: `3454`
3. `ui/launcher/views/models_view.py`: `1529`
4. `utils/connector_manager.py`: `670`
5. Packaging write-path audit now covers `runtime/`, `runtime/daily_reports`, `runtime/stress_reports`, and `.tmp/dev-workflow/reports`.

Validation:

- `python tools/check_doc_ownership.py` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py release-check` passed with ref `release-check-20260419-215559`.
- Current suite counts: `388 passed` default, `123 passed` product smoke.

## Closed Tranche (Tranche 49: April 19, 2026)

Execution closeout (April 19, 2026):

- Tranche 49 is complete and release-green inside the active `P6` lane.
- This slice closed the full post-48 automatic bundle: Settings operations split, Home transcript continuation, runtime-service reduction, and voices/settings simplification.

What shipped:

1. `P6-C18 - Settings operations snapshot split` `complete`
   - Recovery, automation, and windows-ops snapshot/render application moved into `ui/launcher/views/settings_snapshot_panel.py`.
   - `settings_operations_panel.py` now delegates the snapshot application paths instead of owning them inline.
2. `P6-C19 - Home transcript continuation` `complete`
   - Transcript row construction, assistant reply action rows, and transcript clearing moved into `ui/launcher/views/assistant_transcript.py`.
   - `assistant_view.py` now stays focused on chat orchestration and visible Home behavior.
3. `P6-C20 - Runtime-service reduction` `complete`
   - Morning-brief detection, report discovery, markdown preview parsing, and response assembly moved into `src/guppy/api/services_briefing.py`.
   - `server_runtime.py` now binds directly to the extracted briefing seam instead of depending on the block living inside `services_realtime.py`.
4. `P6-C21 - Voices and Settings presenter simplification` `complete`
   - Voice engine readiness, engine summary, binding summary, and voice evidence now route through `src/guppy/launcher_application/voice_catalog_support.py`.
   - Persona assignment-summary and preview copy now route through `src/guppy/launcher_application/settings_persona_presenter.py`.
5. `P6-C22 - Validation and tranche closeout` `complete`
   - Focused unit and smoke coverage landed for the new seams.
   - The `server_runtime.py` waiver was refreshed to the new observed size after the briefing extraction.

Measured hotspot state:

1. `ui/launcher/views/assistant_view.py`: `1316`
2. `ui/launcher/views/settings_operations_panel.py`: `939`
3. `ui/launcher/views/voices_view.py`: `864`
4. `ui/launcher/views/settings_view.py`: `732`
5. `src/guppy/api/server_runtime.py`: `750`
6. `src/guppy/api/services_realtime.py`: `713`

Validation:

- `python tools/check_doc_ownership.py` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline` passed after refreshing the `server_runtime.py` waiver to the observed post-split size.
- Focused smoke bundle passed: `7 passed`.
- Focused unit bundle passed: `28 passed`.
- `.venv\Scripts\python.exe tools/dev_workflow.py release-check` passed with ref `release-check-20260419-220919`.
- Current suite counts: `402 passed` default, `124 passed` product smoke.

## Closed Tranche (Tranche 50: April 19, 2026)

Execution closeout (April 19, 2026):

- Tranche 50 is complete and release-green inside the active `P6` lane.
- This slice closed the next bounded automatic bundle: packaging/distribution contract audit, `server_runtime` startup-shell reduction, `server_runtime_snapshot` shared-briefing reduction, and launcher automation-test coordination extraction.

What shipped:

1. `P6-C23 - Packaging and distribution contract audit` `complete`
   - `src/guppy/launcher_application/packaging_audit.py` now validates canonical launcher/build entrypoints, packaging-doc coverage, release handoff artifacts when present, and expected `dist/` layout assumptions without requiring a real installer build.
   - `tools/validate_build_checks.py` now includes a dedicated packaging/distribution assumption check alongside the writable-target checks.
2. `P6-C24 - server_runtime startup shell reduction` `complete`
   - Startup/repair-token/readiness shell wiring moved into `src/guppy/api/server_runtime_startup_support.py`.
   - `server_runtime.py` now binds startup support and lifespan behavior through the extracted seam.
3. `P6-C25 - server_runtime_snapshot shared briefing reduction` `complete`
   - Morning-brief detection and report-preview logic now route through the shared `services_briefing.py` helper instead of duplicating that behavior inside `server_runtime_snapshot.py`.
   - The shared briefing helper now supports both live-server and snapshot owner shapes.
4. `P6-C26 - Launcher automation-test coordination extraction` `complete`
   - Launcher-side automation-test evidence/snapshot/report coordination moved into `src/guppy/launcher_application/automation_test_coordination.py`.
   - `launcher_window.py` now delegates that builder-evidence flow through the extracted helper instead of owning the orchestration inline.
5. `P6-C27 - Validation and tranche closeout` `complete`
   - Focused packaging, runtime, snapshot, and launcher-shell tests landed.
   - Touched hotspot waivers were refreshed to the new observed sizes after the integrated pass.

Measured hotspot state:

1. `src/guppy/api/server_runtime.py`: `754`
2. `src/guppy/api/server_runtime_snapshot.py`: `3230`
3. `ui/launcher/launcher_window.py`: `3425`
4. `src/guppy/launcher_application/packaging_audit.py`: `267`
5. `tools/validate_build_checks.py`: `180`

Validation:

- Focused unit bundle passed: `31 passed`.
- Focused smoke bundle passed: `11 passed`.
- `python tools/check_doc_ownership.py` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline` passed after refreshing the touched hotspot waivers to the new observed sizes.
- `.venv\Scripts\python.exe tools/dev_workflow.py release-check` passed with ref `release-check-20260419-221717`.
- Current suite counts: `411 passed` default, `124 passed` product smoke.

## Closed Tranche (Tranche 51: April 19, 2026)

Execution closeout (April 19, 2026):

- Tranche 51 is complete and release-green inside the active `P6` lane.
- This slice closed the next bounded automatic bundle: `server_runtime` auth/request reduction, `server_runtime_snapshot` telemetry reduction, launcher Windows-ops coordination extraction, and runtime/voice validation contract prep.

What shipped:

1. `P6-C28 - server_runtime auth/request orchestration reduction` `complete`
   - Auth/request binding and timing-middleware orchestration moved into `src/guppy/api/server_runtime_auth_request_support.py`.
   - `server_runtime.py` now binds its request/auth contract through the extracted helper instead of owning that cluster inline.
2. `P6-C29 - server_runtime_snapshot telemetry reduction` `complete`
   - Telemetry timestamp parsing, SQLite/JSONL query helpers, and telemetry report shaping moved into `src/guppy/api/services_telemetry.py`.
   - `server_runtime_snapshot.py` now delegates `/telemetry/query` and `/telemetry/report` behavior through the extracted telemetry seam.
3. `P6-C30 - Launcher Windows-ops coordination extraction` `complete`
   - Windows-ops state persistence, chain completion, and terminal-recipe completion normalization moved into `src/guppy/launcher_application/windows_ops_coordination.py`.
   - `launcher_window.py` now delegates the Windows-ops completion/state path through that extracted coordinator.
4. `P6-C31 - Runtime and voice validation contract prep` `complete`
   - `tools/verify_provider_runtime.py` now records and prints its structural-versus-real-device validation scope explicitly.
   - `docs/generated/RUNTIME_VALIDATION_MATRIX.md` now defines the concrete real-machine follow-up matrix for local runtime, provider connectivity, voice/device behavior, and post-package checks.
5. `P6-C32 - Validation and tranche closeout` `complete`
   - Focused runtime, launcher, telemetry, and validation-contract tests landed.
   - Touched hotspot waivers were refreshed to the new observed sizes after the integrated pass.

Measured hotspot state:

1. `src/guppy/api/server_runtime.py`: `741`
2. `src/guppy/api/server_runtime_snapshot.py`: `3098`
3. `ui/launcher/launcher_window.py`: `3357`
4. `src/guppy/api/server_runtime_auth_request_support.py`: `68`
5. `src/guppy/api/services_telemetry.py`: `188`
6. `src/guppy/launcher_application/windows_ops_coordination.py`: `332`

Validation:

- Focused unit bundle passed: `29 passed`.
- Focused smoke bundle passed: `4 passed`.
- `python tools/check_doc_ownership.py` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline` passed.
- `.venv\Scripts\python.exe tools/dev_workflow.py release-check` passed with ref `release-check-20260419-223003`.
- Current suite counts: `423 passed` default, `124 passed` product smoke.

## Next Likely Tranche (Post-51 Follow-On)

Execution note (April 19, 2026):

- `P6` remains active after Tranche 51, and the remaining work is now concentrated almost entirely in the still-waived top-level coordinators plus real-machine validation follow-through.
- The next slice should keep burning down orchestration concentration, not reopen product-surface ownership.

Priority order:

1. `src/guppy/api/server_runtime.py` follow-on reduction around route and request orchestration.
2. `ui/launcher/launcher_window.py` continuation on higher-level request-routing and remaining shell-heavy action branches.
3. `src/guppy/api/server_runtime_snapshot.py` continuation on the remaining large shared-runtime hotspot.
4. Real-machine runtime/voice validation execution using `docs/generated/RUNTIME_VALIDATION_MATRIX.md` and `docs/generated/VOICE_VALIDATION_MATRIX.md`.
5. Packaging readiness follow-on only if a new concrete distribution or handoff contract gap appears.

What the next hotspot tranche should optimize for:

1. Reduce the three still-waived top-level coordinators without changing the shipped five-hub product structure.
2. Preserve the current live framework shape: `PySide6` in `ui/`, launcher-facing logic in `src/guppy/launcher_application/`, runtime/API shaping in `src/guppy/runtime_application/` or bounded `src/guppy/api/*_support.py` helpers, and governance/config logic in their existing seam domains.
3. Avoid pushing new orchestration back into `utils/`; if a hotspot still needs legacy utilities, keep that import behind an application or runtime seam.
4. Pair each reduction card with focused runtime or launcher validation so the tranche stays executable rather than speculative.

## Hotspot Reduction Tranche (Framework Pass)

Execution note (April 19, 2026):

- This follow-on tranche is the first explicitly hotspot-led architecture pass after the automatic P6 slices through Tranche 51.
- Scope is limited to the three live coordinator hotspots: `server_runtime.py` (`741`), `server_runtime_snapshot.py` (`3098`), and `launcher_window.py` (`3471`).
- The tranche should prefer coherent seam extraction over broad rewrites: each hotspot gets one bounded ownership reduction, shared framework rules stay intact, and validation closes the tranche.

What ships:

1. `P6-C33 - Runtime route/request boundary split` `complete`
   - Reduce `src/guppy/api/server_runtime.py` by extracting one more coherent route and request-orchestration seam.
   - Preferred targets: request middleware binding, route registration clusters, provider/runtime request prep, or shared failure shaping that still lives inline.
   - New logic should prefer `src/guppy/api/*_support.py` or `src/guppy/runtime_application/` helpers instead of expanding the top-level runtime shell.
2. `P6-C34 - Launcher shell action/routing split` `complete`
   - Reduce `ui/launcher/launcher_window.py` by extracting one higher-level shell/action seam into `src/guppy/launcher_application/`.
   - Preferred targets: top-level request routing, launcher action dispatch, workspace-driven shell transitions, or other large coordination branches that are still shell-owned.
   - The launcher shell should stay the composition and signal hub, not the long-term home for growing action orchestration.
3. `P6-C35 - Runtime snapshot composition split` `complete`
   - Reduce `src/guppy/api/server_runtime_snapshot.py` through one more support-module extraction around a coherent behavior cluster.
   - Preferred targets: runtime snapshot assembly, provider/runtime summaries, machine-status payload shaping, or other shared-runtime helper clusters that still duplicate service-level shaping.
   - Extracted logic should land in bounded support modules instead of widening route-local logic.
4. `P6-C36 - Shared framework and dependency contract lock` `complete`
   - Keep the tranche inside the live architecture map: `ui/` renders and emits intents, `launcher_application` owns launcher-facing orchestration, `runtime_application` and bounded API support helpers own runtime shaping, and `utils/` does not gain new application-layer ownership.
   - Where the three hotspots share payload shaping or readiness rules, centralize that behavior once rather than splitting the same logic in parallel.
   - Do not introduce a new UI framework, route framework, or cross-layer shortcut imports as part of this tranche.
5. `P6-C37 - Hotspot validation and runtime execution closeout` `complete`
   - Add or extend focused coverage around the extracted seams and run real executable validation against the touched launcher/runtime paths.
   - Minimum closeout remains `python tools/check_doc_ownership.py`, `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta`, `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline`, and `.venv\Scripts\python.exe tools/dev_workflow.py release-check`.
   - If the hotspot work changes runtime or voice flow assumptions, follow through on the corresponding rows in `docs/generated/RUNTIME_VALIDATION_MATRIX.md` and `docs/generated/VOICE_VALIDATION_MATRIX.md` before calling the tranche complete.
6. `P6-C38 - User-session chrome, layout, and navigation correction pack` `complete`
   - Fold the current user-session findings into the launcher hotspot pass instead of treating them as detached polish.
   - Correct the left-rail/logo artifact and spacing issue in the launcher chrome, including the stale or ghosted logo placement seen in the current user screenshots.
   - Remove or reduce non-essential top-toolbar options, make the loaded main-agent model and spawned/sub-agent model state clearly visible, and keep model selectors explicit instead of visually leaking into the search and utility area.
   - Fix the current incorrect navigation path where the left model control routes to Settings instead of the intended model surface.
   - Reduce card and control footprints so Tools and launcher chrome fit narrower windows without leaking into the right edge; make sizing responsive to the active window width rather than relying on fixed roomy layouts.
   - Review browser-open and external-window usage during task execution so the transcript keeps useful screen real estate, and explicitly validate the local model harness switch path as part of the same user-flow pass.
7. `P6-C39 - Duplicate-window and task-spawn stabilization` `complete`
   - Duplicate launcher startup is guarded by process-lock plus API/hub autostart debounce in `src/guppy/apps/launcher_app.py`.
   - Launcher command recovery no longer routes normal task execution through the supervised batch launcher; it now uses the hidden direct API start path in `ui/launcher/launcher_window.py`.
   - Repeated supervised/direct command-start attempts are debounced, and the explicit supervised batch path remains reserved for the App Mgmt / Windows ops lane instead of everyday chat-task recovery.

Acceptance:

1. `server_runtime.py` is either brought to or below the `700`-line cap, or reduced again with one clearly bounded extracted seam and a lower observed waiver cap.
2. `launcher_window.py` is smaller than the current `3471`-line waiver and delegates at least one more coherent shell/action branch into `src/guppy/launcher_application/`.
3. `server_runtime_snapshot.py` is smaller than the current `3098`-line waiver and delegates at least one more coherent runtime snapshot cluster into support modules.
4. No new direct `ui/` to runtime/governance/config shortcut imports are introduced while doing the reductions.
5. Focused tests plus `dev-check` delta/baseline and `release-check` all pass before the tranche is considered closed.
6. The launcher header, left rail, model controls, and Tools cards remain usable and contained at smaller window sizes without right-edge overflow or misrouted navigation.
7. Browser/app launches and local-harness switching are validated against the real user-flow path without spawning redundant visible command windows.

### Code And Framework Review

1. `server_runtime.py` is now the smallest of the three hotspots and should be treated as the most likely file to get back under the global `700`-line cap first.
2. `launcher_window.py` remains the main launcher-shell concentration point; the right move is continued extraction of orchestration seams into `src/guppy/launcher_application/`, not a shell rewrite or new routing layer.
3. `server_runtime_snapshot.py` remains the largest active hotspot and still overlaps conceptually with newer runtime/status/telemetry service helpers, so support-module extraction is the right next move.
4. `docs/LIVE_ARCHITECTURE.md` and `documentation/ARCHITECTURE.md` both reinforce the same framework rule: the seam domains are already the intended architecture, so this tranche should deepen them rather than inventing another abstraction layer.
5. Current session evidence in `runtime/launcher_events.jsonl` shows repeated `launcher_duplicate_instance` startup phases, plus startup over-budget events for `build_ui`, `bootstrap_services`, and `first_status_poll`; those make the launcher shell and startup path the right home for the duplicate-window and chrome-density fixes.
6. Current user-session commands in `runtime/launcher_events.jsonl` include browser and desktop-app open flows, so transcript width, external-window sizing, and launcher chrome density need to be reviewed against real interaction patterns rather than only static smoke coverage.

### Recommended Execution Order

1. Land `P6-C33` first so `server_runtime.py` gets the most realistic shot at leaving the waiver list.
2. Land `P6-C34` second so launcher-shell orchestration continues to move out of `launcher_window.py` while the current five-hub shell remains stable.
3. Land `P6-C35` third so `server_runtime_snapshot.py` keeps shrinking through support extraction instead of collecting more route-local logic.
4. Land `P6-C38` alongside or immediately after `P6-C34` so the launcher-shell work also closes the active user-session chrome, routing, and responsive-layout defects.
5. Land `P6-C39` before closeout so duplicate-window spawning is treated as part of launcher stability, not deferred cleanup.
6. Treat `P6-C36` as a merge rule throughout the tranche, not as a separate cleanup pass at the end.
7. Close with `P6-C37` validation and the real-machine runtime/voice rows touched by the extracted seams.

### Recommended Agent Split

1. Lane A: `server_runtime.py` route/request reduction
2. Lane B: `launcher_window.py` shell/action reduction plus duplicate-window stabilization
3. Lane C: `server_runtime_snapshot.py` support extraction
4. Lane D: responsive launcher/topbar/sidebar/tools layout review plus focused tests and runtime/voice validation follow-through
5. Lead integrator: merge sequencing, guardrail passes, waiver refreshes, and final closeout evidence

### Next Automatable Queue (Spawned-Agent Execution)

Execution note (April 19, 2026):

- The following queue was built from spawned-agent lane analysis and is scoped to bounded seams that can be completed automatically with low-to-medium risk.
- Tandem lanes are designed to avoid overlap by file ownership.

Tandem batch A (parallel):

1. `P6-C33A - Runtime path/binding seam split` `complete`
    - Extract path-config mutation and owner-binding alias wiring from `src/guppy/api/server_runtime.py` into:
       - `src/guppy/api/server_runtime_path_support.py`
       - `src/guppy/api/server_runtime_bindings.py`
    - Validation target: `tests/unit/test_chat_routing_routes.py`, `tests/unit/test_server_runtime_auth_request_support.py`, `tests/smoke/test_runtime_smoke.py`, `dev-check --guard-scope delta`.

2. `P6-C34A - Launcher windows-ops request-flow split` `complete`
    - Extract windows-ops request dispatch and chain-update orchestration from `ui/launcher/launcher_window.py` into:
       - `src/guppy/launcher_application/windows_ops_request_flow.py`
    - Validation target: `tests/unit/test_windows_ops_coordination.py`, launcher interaction smoke, `dev-check --guard-scope delta`.

Tandem batch B (parallel):

1. `P6-C35A - Snapshot instance scaffold lifecycle split` `complete`
    - Extract scaffold/config/state load-save + normalized bundle lifecycle from `src/guppy/api/server_runtime_snapshot.py` into:
       - `src/guppy/api/services_instances.py`
    - Validation target: `tests/unit/test_chat_routing_routes.py`, snapshot-focused smoke, `dev-check --guard-scope delta`.

2. `P6-C35B - Snapshot ops telemetry/repair split` `complete`
    - Extract jsonl-tail, diagnostics bundle shaping, and repair action helpers from `src/guppy/api/server_runtime_snapshot.py` into:
       - `src/guppy/api/services_ops.py`
    - Validation target: `tests/unit/test_services_telemetry.py`, `tests/unit/test_security_hardening.py`, `dev-check --guard-scope delta`.

Succession batch C (merge last):

1. `P6-C35C - Snapshot realtime prompt/inference utility split` `complete`
    - Extract prompt-context, cacheability, voice upload temp-file, and inference utility helpers from `src/guppy/api/server_runtime_snapshot.py` into:
       - `src/guppy/api/services_realtime.py`
    - Validation target: `tests/unit/test_chat_routing_routes.py`, `tests/unit/test_chat_routing_module_contract.py`, voice-upload route coverage, `dev-check --guard-scope delta`.

2. `P6-C37A - Integrated closeout` `complete`
    - Run merge-sequenced validation for the completed cards:
       - `python tools/check_doc_ownership.py`
       - `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta`
       - `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope baseline`
       - `.venv\Scripts\python.exe tools/dev_workflow.py release-check`
    - Record receipt and summary refs in this brief.

Spawned-agent assignment (operational):

1. Spawned agent A: `P6-C33A`
2. Spawned agent B: `P6-C34A`
3. Spawned agent C: `P6-C35A`
4. Spawned agent D: `P6-C35B`
5. Lead integrator lane: merge order, conflict resolution, and `P6-C37A` closeout.

### Execution Checkpoint

April 20, 2026 closeout pass:

1. `P6-C38` is fully closed in live code.
2. Launcher chrome now uses a denser responsive topbar and tighter sidebar chrome, the stale left-rail badge artifact path is removed from the sidebar badge, and visible model summary text is now surfaced in the topbar instead of staying tooltip-only.
3. The launcher shell no longer collides the Settings alias with the Models hub index, and model-loadout summary sync now refreshes when the Models hub is active.
4. Tools cards now reflow by available width so smaller windows do not leave the same dead-space/right-edge pressure pattern.
5. `P6-C39` is fully closed in live code: launcher startup debounce for API/hub autostart is reconfirmed, repeated supervised/direct API command-start attempts are debounced, and normal task recovery now stays on the hidden direct-start path instead of re-entering the supervised batch launcher.
6. The supervised batch path remains available only in the explicit App Mgmt / Windows ops lane, so duplicate-window stabilization now closes inside the launcher shell rather than depending on deferred real-machine follow-through.
7. `P6-C35` is fully closed in live code: chat idempotency ownership and replay-state logic was extracted from `src/guppy/api/server_runtime_snapshot.py` into the new bounded seam `src/guppy/api/chat_idempotency.py`, reducing snapshot inline coordinator pressure while preserving `/chat` behavior.
8. Focused validation for the extraction is green: `tests/unit/test_chat_routing_routes.py` passed and `python tools/dev_workflow.py dev-check --guard-scope delta` passed.
9. `P6-C35` advanced again with a second bounded support extraction: instance config/state normalization and limits shaping moved from `src/guppy/api/server_runtime_snapshot.py` into `src/guppy/api/instance_state_support.py`, and snapshot now aliases those helpers through the seam.
10. Focused validation for the second extraction is green: `tests/unit/test_runtime_challengers.py` + `tests/unit/test_chat_routing_routes.py` passed, and `python tools/dev_workflow.py dev-check --guard-scope delta` passed.
11. Spawned queue closeout cards are complete in sequence: `P6-C33A`, `P6-C34A`, `P6-C35A`, `P6-C35B`, `P6-C35C`, then integrator closeout `P6-C37A`.
12. Integrator gate run is fully green for this queue closeout: `python tools/check_doc_ownership.py` passed, `python tools/dev_workflow.py dev-check --guard-scope delta` passed, `python tools/dev_workflow.py dev-check --guard-scope baseline` passed, and `python tools/dev_workflow.py release-check` passed.
13. Current release handoff ref is `release-check-20260420-154801` with gate state `8/8 passed`; summary and receipt are recorded at `.tmp/dev-workflow/reports/release-check-summary.txt` and `.tmp/dev-workflow/reports/release-check-receipt.json`.
14. Post-closeout verification rerun is still green on the current worktree: `python tools/check_doc_ownership.py`, `python tools/dev_workflow.py dev-check --guard-scope delta`, `python tools/dev_workflow.py dev-check --guard-scope baseline`, and `python tools/dev_workflow.py release-check` all pass with the same handoff ref and gate state.

## Closed Prior Tranche (Tranche 45: April 20 - May 20)

Execution note (April 19, 2026, closed):

- P5 is complete.
- Scope stays intentionally narrow: live execution traces, per-command debugging, last-run evidence, and readable permission controls inside the existing Tools destination.
- P5 did not expand into a marketplace, autonomous tool builder, or a new top-level operator destination.
- `ui/launcher/views/tools_view.py` dropped to `407` lines and is no longer waived after the split into `tools_view_cards.py` (`451` lines) and `tools_trace_panel.py` (`211` lines).
- Framework evaluation says keep the existing PySide6 + `launcher_application` + `workspace_governance` structure. Do not introduce a new UI framework or route layer.
- Docs and ownership checks stayed aligned while the tranche landed.

What ships:

1. `P5-C1 — Tools trace contract and doc cleanup` `complete`
   - Define the P5 execution-trace contract from existing launcher events and current tool-policy seams.
   - Add a thin launcher-application adapter for recent tool events instead of parsing event history ad hoc in the widget layer.
   - Keep the active truth docs internally consistent while the tranche is in flight.
2. `P5-C2 — Safe Tools view distribution before depth` `complete`
   - Split the trace/debug surface out of `ui/launcher/views/tools_view.py`.
   - Split card policy-rendering helpers out of `tools_view.py` so one file no longer owns catalog, card rendering, filter orchestration, and future trace UI together.
   - Preserve the already-extracted `builder_task_panel.py` boundary.
3. `P5-C3 — Live execution trace surface` `complete`
   - Add a Tools-local trace panel showing recent tool events, workspace, event type, outcome, and timestamp.
   - Keep the trace lane recent and operational rather than turning it into a deep audit browser.
4. `P5-C4 — Per-command debugging and last-run evidence` `complete`
   - Surface the latest run outcome, denial reason, required capability, connector auth posture, and endpoint scope from one place in Tools.
   - Make restricted-tool reasoning and latest execution evidence readable without leaving the hub.
5. `P5-C5 — Permission controls clarification` `complete`
   - Tighten the Tools-versus-Settings ownership line: Tools owns operational permissions and debug evidence, while Settings continues to own credentials, diagnostics, and recovery.
   - Either complete the live tool-state/toggle contract end to end or explicitly keep it out of P5; do not leave a half-wired state path.
6. `P5-C6 — Validation, docs, and release evidence` `complete`
   - Expand focused smoke/unit coverage for traces, last-run evidence, restricted-tool reasoning, and any shipped state/toggle workflow.
   - Update active truth docs with P5 closeout and the next-lane handoff.
   - Keep `dev-check --guard-scope delta` and `release-check` green throughout.

Acceptance:

- `Tools Hub` shows recent execution traces and per-command debug evidence without adding a new destination.
- Restricted tools explain why they are blocked and what boundary or auth posture is driving the block.
- `tools_view.py` no longer absorbs all new P5 depth directly; distribution work lands before or alongside trace/debug depth.
- Tools remains the operational view of capabilities, while Settings continues to own credentials and recovery.
- Focused smoke/unit coverage passes, then `python tools/dev_workflow.py dev-check --guard-scope delta` and `python tools/dev_workflow.py release-check` pass.

### Code And Docs Review (P5)

1. `ui/launcher/views/tools_view.py` was the primary P5 monolith hotspot and is now reduced to composition, filters, and workspace wiring.
2. `ui/launcher/components/builder_task_panel.py` stayed extracted and untouched as the Builder boundary.
3. `src/guppy/workspace_governance/access_policy.py` remained the policy seam; P5 extended the surface around it rather than bypassing it.
4. `ui/launcher/launcher_window.py` only took thin trace-plumbing changes plus tool-event logging for the new recent-evidence surface.
5. The active brief previously had stale `Tranche 44` labels inside the `Tranche 45` block; P5 closeout keeps the tranche metadata coherent and current.

### Framework And Monolith Evaluation (P5)

1. Keep the current PySide6 widget framework and the existing `launcher_application` / `workspace_governance` seams.
2. Do not introduce a new UI framework, route architecture, or broad API refactor for P5.
3. Preferred distribution targets now landed as:
   - `tools_view.py` for composition and filters
   - `tools_view_cards.py` for card catalog and policy rendering
   - `tools_trace_panel.py` for recent trace/debug evidence
   - `src/guppy/launcher_application/tools_trace_adapter.py` for launcher-event parsing
4. Current hotspot watchlist:
   - `ui/launcher/launcher_window.py` at `3820` lines
   - `src/guppy/api/server_runtime_snapshot.py` at `3853` lines
   - `ui/launcher/views/settings_operations_panel.py` remains a larger transitional panel

### Agent Execution Split (Tranche 45)

1. Agent A owned the `tools_view.py` breakup and the new card helper seam.
2. Agent B owned the recent-trace adapter and launcher wiring seam.
3. Agent C owned focused test support for the Tools surface and adjacent evidence copy.
4. Lead integrator sequenced the merges, added the dedicated trace panel, tightened event logging, ran guardrails, and published the tranche closeout summary.

### Tranche 45 Merge Checkpoints

1. After `P5-C2`: compile plus focused Tools smoke.
2. After `P5-C3` and `P5-C4`: focused Tools smoke/unit coverage plus launcher interaction smoke.
3. Every merge gate: `python tools/dev_workflow.py dev-check --guard-scope delta`.
4. Tranche close: `python tools/dev_workflow.py release-check` with updated receipt/summary references.

P5 closeout summary (April 19, 2026):

- `src/guppy/launcher_application/tools_trace_adapter.py` now owns the thin read-only launcher/tool trace contract.
- `ui/launcher/views/tools_view.py` now focuses on composition, filters, and workspace wiring.
- `ui/launcher/views/tools_view_cards.py` owns the tool catalog and policy-rendering surface.
- `ui/launcher/views/tools_trace_panel.py` owns recent execution traces and per-command debug evidence.
- Focused validation passed for `tests/unit/test_tools_surface.py`, targeted Tools smoke coverage, `python tools/dev_workflow.py dev-check --guard-scope delta`, and `python tools/dev_workflow.py release-check` with ref `release-check-20260419-200449`.

## Current Tranche Handoff

1. April 17, 2026
   The active doc-truth contract was simplified so `docs/PROJECT_BRIEF.md` is now the only active status, roadmap, and handoff source.

2. April 17, 2026
   The previous root roadmap log was archived verbatim to `docs/archive/root-history/ROADMAP_2026-04-17.md`, and root `ROADMAP.md` is now a compatibility pointer only.

3. April 17, 2026
   Supported launcher paths no longer include Merlin or Council surfaces; compatibility material remains quarantined for migration reference rather than product ownership.

4. April 17, 2026
   App Mgmt `RELEASE DRY RUN` now runs the canonical `tools/dev_workflow.py release-check` preflight before emitting the beta reviewer bundle, keeping the launcher recipe, packaging doc, and release guidance on one path.

5. April 17, 2026
   Home workspace framing now flows through `src/guppy/launcher_application/home_presenter.py`, and Workspaces role presets now use shared presenter copy instead of rebuilding role text inside the view layer.

6. April 17, 2026
   App Mgmt embedded-terminal session ownership now lives in `src/guppy/launcher_application/embedded_terminal.py`, and Workspaces save/toggle shaping now lives in typed `launcher_application` helpers instead of view-local payload assembly.

7. April 17, 2026
   App Mgmt no longer imports `utils.runtime_profile` directly; the runtime-profile read moved behind `src/guppy/experience_config/services.py`, which removes one active UI architecture-boundary waiver.

8. April 17, 2026
   `tools/dev_workflow.py release-check` now writes a human-readable summary with a stable `Ref`, gate-state line, and an explicit review/fix-next section so the brief, CLI output, and App Mgmt release guidance describe the same handoff contract.

9. April 17, 2026
   Settings, Models, Voices, and the launcher shell now reach runtime-profile, persona, provider, and voice persistence through `src/guppy/experience_config/services.py` instead of importing `utils.runtime_profile` or `utils.personalization_config` directly.

10. April 17, 2026
   Agent Tools, My PC, and the launcher shell now reach workspace capability policy and connector field metadata through `src/guppy/workspace_governance/` seams instead of importing `utils.instance_capabilities` or `utils.connector_manager` directly.

11. April 17, 2026
   `ui/launcher/launcher_window.py` now gets its launcher-local bearer token from `src/guppy/runtime_application/build_local_bearer_token`, removing the last direct UI import of `src/guppy.api` and closing the corresponding architecture-boundary waiver.

12. April 17, 2026
   `AssistantView` and `InstanceManagerView` now consume shared `launcher_application` presenters for Home calm-start copy, mixed-role starter guidance, workspace create/save shaping, and workspace-ready messaging, while both views remain oversized transitional shells tracked by the line-cap guard.

13. April 17, 2026
   Mixed-role Workspace Framing coverage now includes presenter-level role-copy assertions plus launcher smoke coverage for mixed workspace summaries, empty workspace onboarding guidance, and workspace-ready handoff messaging.

14. April 17, 2026
   Home now updates the visible mode/persona controls when workspaces switch, so Home controls and launcher routing state stay aligned during first-run and mixed-role workspace changes.

15. April 17, 2026
   Workspace create/delete now use launcher-local file fallback during API warmup, so the first-run workspace flow remains usable before the API fully settles.

16. April 17, 2026
   `TOOLS` / `APP MGMT` are now visible in the top navigation, `CONNECTED SERVICES` is visible on first render in App Mgmt, and `bin/Guppy.bat` now routes through `src/guppy/cli/launch.py launcher` to match the supported desktop path.

17. April 17, 2026
   Guppy no longer depends on vendored Lemonade or MemPalace source trees, the deprecated repo-local web UI, or checked-in `tests/runtime` stress reports; runtime challengers, local memory, and any future external integrations now anchor on explicit external integration contracts and `runtime/` evidence paths instead.

18. April 17, 2026
   P1 UI simplification is underway: the sidebar now hides advanced destinations behind an explicit toggle, and the top bar groups notifications plus terminal access inside a lower-emphasis `DETAILS` capsule so the daily Chat / Workspaces / Library / Settings path reads first.

19. April 17, 2026
   The right tray now reads as a quieter workspace-context drawer: primary file and context actions stay visible, while write/code/shell actions and optional spaces live behind a `DETAILS` reveal instead of competing with the daily path by default.

20. April 17, 2026
   Agent Tools copy now follows the same framing, referring to the side panel as the workspace drawer rather than quick actions so the daily-path language stays consistent across navigation and tool discovery.

21. April 17, 2026
   Home now splits primary workspace context from on-demand system details, and the hero subtitle stays role-aware instead of doubling as an activity ticker, which reduces visible status noise on the default chat surface.

22. April 18, 2026
   The top bar and Home defaults now use calmer daily-path wording: `DETAILS` instead of `SYSTEM`, `daily workspace assistant` instead of `local workspace assistant`, and role-aware header copy that stays stable while live activity remains in the workspace context area.

23. April 18, 2026
   `P2` is now active in code: Library shows explicit approved roots plus recent saved or approved-root files, and each recent item can prime Chat directly with a bounded “use in chat” handoff instead of acting like a passive reference page.

24. April 18, 2026
   `P3` has started through the same slice: Home now keeps active Library context chips on the chat surface, so selected files or study/coding items read as live assistant context rather than a separate launcher destination.

25. April 18, 2026
   Library is now a real control surface instead of a read-only summary page: approved roots can be added from the UI, pinned notes and artifact entries can be saved per workspace, and Chat now exposes attached Library context with per-item removal plus clear-all controls.

26. April 18, 2026
   Attached Library sources now support a lightweight focus path on Home: users can promote one attached source to the front of the active context without clearing and rebuilding it, and composer/starter guidance now tracks that focused source as the current emphasis.

27. April 18, 2026
   Repo/doc alignment pass closed the current subtitle contract gap: smoke assertions now validate activity text in the context bar while keeping the hero subtitle role-aware, local Gmail credential JSON files were moved out of repo root to the user-home credential path, root-only local artifacts were quarantined under `C:\Users\Ryan\Guppy_Quarantine\2026-04-18_root_sweep`, and `dev-check --guard-scope baseline` plus the targeted launcher smoke subset were re-run.

28. April 18, 2026
   Home, Library, and shell wording moved through a visible UX tranche: Library now spells out approved-root boundaries, active root state, and why `USE IN CHAT` matters; Home now presents attached Library sources as clearer current-source context with calmer composer guidance; and the shell now emphasizes the daily path with `HOME`, `WORKSPACES`, `LIBRARY`, `SETTINGS`, `MY PC`, and `LOCAL LLM` language while baseline and targeted smoke stayed green after a small helper extraction pulled `library_view.py` back under its transitional cap.

29. April 18, 2026
   `daemon.py` no longer imports `utils.runtime_profile` directly; `get_runtime_envelope_config` is now exposed from `src/guppy/experience_config/services.py` and `daemon.py` uses the seam. The inline 10-line try/except fallback block was removed, shrinking the waived line count from 1483 to 1473.

30. April 18, 2026
   `src/guppy/hub/app.py` no longer imports `utils.runtime_profile` directly; `apply_runtime_profile`, `load_runtime_settings` (aliased as `load_app_settings`), and `recommend_runtime_profile` are all consumed from the `experience_config.services` seam. The `apply_runtime_profile` convenience function was added to the seam as the composition of `load_runtime_settings` + `apply_runtime_settings_to_env`.

31. April 18, 2026
   `src/guppy/launcher_application/builder_workflow.py` was created as a thin seam wrapper around `utils.offhours_builder`. All four inline lazy `from utils.offhours_builder import ...` calls in `launcher_window.py` now go through the seam. The wrapper includes full no-op fallbacks so the launcher remains functional when the offhours backend is absent.

32. April 18, 2026
   Architecture boundary guard and all 309 unit + integration tests stayed green across all three closures above. `settings_view.py` cap risk flagged in the original triage was a false alarm — the file already had a waiver at 743 lines with 48 lines of actual headroom.

33. April 18, 2026
   Builder task templates now route through the `launcher_application` seam too: `ui/launcher/components/builder_task_panel.py` no longer imports `utils.offhours_builder` directly and now consumes `load_builder_templates` from `src/guppy/launcher_application/builder_workflow.py`. In the same tranche, the daemon line-cap waiver in `tools/check_new_module_line_cap.py` was tightened from 1483 to 1473 to match current observed size, and baseline `dev-check` plus full unit/integration tests (`309 passed`) stayed green.

34. April 18, 2026
   Launcher shell safe I/O and instance-log access now route through `src/guppy/launcher_application/storage_io.py` instead of importing `utils.safe_io` or `utils.instance_logger` directly in `ui/launcher/launcher_window.py`. This closes two more direct UI-to-utils imports while preserving explicit fallback behavior, and baseline `dev-check` plus full unit/integration tests (`309 passed`, `EXIT:0`) remained green after the seam extraction.

35. April 18, 2026
   The remaining launcher-shell secret-store dependency now routes through the same storage seam: `ui/launcher/launcher_window.py` no longer imports `utils.secret_store` directly, and `src/guppy/launcher_application/storage_io.py` now owns secret-store availability, lookup, and compatibility-client access with explicit fallback behavior. Launcher compatibility hooks for `_SECRET_STORE_AVAILABLE` and `_secret_store` were preserved so existing security and smoke test patch points remain stable, and baseline `dev-check` plus full unit/integration tests (`309 passed`, `EXIT:0`) stayed green.

36. April 18, 2026
   Pre-preflight UX polish tightened the first-run daily path without changing feature scope: Home no longer implies Library sources are attached when none exist, attached-source empty-state guidance now tells users they can ask directly from those sources, and Library cards plus empty states now explain more explicitly that `USE IN CHAT` sends files, notes, and artifacts back to Home as source context. Baseline `dev-check` and full unit/integration tests (`309 passed`, `EXIT:0`) stayed green after the copy pass.

37. April 18, 2026
   Full preflight smoke debugging closed the remaining launcher blockers: Home now skips expensive Library browse-card discovery when it only needs lightweight context summaries, Library root-file discovery is scan-bounded so repo-sized approved roots do not stall the UI, launcher/workspace mutation/refresh restored several smoke-facing compatibility wrappers, and status/onboarding copy was brought back in line with the current smoke contract. The runtime smoke, launcher smoke, and security smoke bundle reached `[100%]`, and the launcher-window transitional line-cap waiver was updated to reflect the current shell size pending a later composition-cut tranche.

38. April 18, 2026
   The launcher shell now aligns more closely with the chat-first structure from the UX review: Home uses a compact identity row instead of a dashboard hero, optional workspace details and starters stay collapsed by default, the right workspace drawer is hidden by default on Home and exposed through a top-bar toggle, the left rail is now collapsible, and the stack order was corrected so `SETTINGS` opens the dedicated settings view while diagnostics/automation remain in the separate advanced surface. The Settings page also gained subsection navigation so runtime defaults, persona configuration, and advanced-surface handoff live in a dedicated configuration area rather than leaking into the daily path, and full launcher smoke stayed green after the shell pass.

39. April 18, 2026
   Library root saves now have end-to-end validation and user-visible guidance: the workflow rejects missing/unreadable/non-directory paths before persistence, the Library UI shows inline save feedback instead of relying only on syslog cues, and focused unit coverage now verifies valid/invalid root handling contracts.

40. April 18, 2026
   Home/Library source continuity now includes per-workspace default source pinning: users can pin the current primary source as the workspace default, the pinned default is persisted under `runtime/library_workspace_defaults.json`, attached context prioritization respects that default when present, and deletion/removal clears stale defaults to avoid dangling source pointers.

41. April 18, 2026
   `bin/launch_automation_test.bat` now has hardened launch diagnostics and interpreter fallback order (`.venv\pythonw` -> `.venv\python` -> system `pythonw` -> system `python`) with clear error output when launch prerequisites are missing.

42. April 18, 2026
   Repo-wide hardening/bug-hunt pass landed targeted safety fixes with focused regression coverage: `guppy_core/tool_runner.py` now defers connector runtime side effects (for example Gmail account switching) until after instance capability permission approval, `ui/launcher/launcher_window.py` now uses instance dispatch (`self`) for mode-readiness and timeout helper calls to reduce brittle class-bound behavior in command flow, and `src/guppy/api/routes_instances.py` now validates connector binding payloads (known connector/provider, action allow/block conflicts, supported action ids, non-empty endpoint filters) before persistence. New unit coverage in `tests/unit/test_tool_runner_metrics.py` and `tests/unit/test_instance_connector_binding_validation.py` keeps these guardrails pinned.

43. April 18, 2026
   Follow-on hardening closed three additional risk seams: API runtime degraded-permission fallbacks now fail closed (`src/guppy/api/server_runtime.py`, `src/guppy/api/server_runtime_snapshot.py`, and `src/guppy/api/_server_fragment_bootstrap.py` no longer default to allow when capability policy backends are unavailable), connector endpoint allow/block filters now share wildcard-aware matching semantics in `utils/connector_manager.py` with focused regression coverage in `tests/unit/test_connector_manager.py`, and contributor-facing ownership boundaries now explicitly keep Guppy and `Guppy-pi` on separate development tracks in `CONTRIBUTING.md`.

44. April 18, 2026
   A new multi-agent execution tranche was planned and staged for April 19 - May 2 with 12 concrete execution items spanning code hardening, governance validation, runtime resilience, and repo maintenance. The plan includes explicit agent/workstream split, merge checkpoints (`dev-check delta`, `test-default`, `test-smoke`, `release-check`), and a refreshed weekly status plus timeline checkpoint additions for May 2 and May 16.

45. April 18, 2026
   Tranche 44 execution items were landed in tandem through multi-agent workstreams and integrated validation: waiver metadata drift reporting is now emitted by `tools/check_new_module_line_cap.py`; release comment-debt guard (`tools/check_release_comment_debt.py`) is wired into `tools/dev_workflow.py release-check`; connector binding request validation now lives in shared `src/guppy/workspace_governance/connector_binding_validation.py` and is consumed by API routes; runtime/snapshot/bootstrap permission fallback behavior is fail-closed and aligned through workspace-governance policy seams; connector endpoint filters now use wildcard-aware parity semantics in `utils/connector_manager.py`; architecture-boundary and wrapper-integrity guards were strengthened with focused test expansion; API route registration parity and deterministic readiness/rate-limit time-control tests were added; and safe JSON/JSONL loader behavior was consolidated via `src/guppy/runtime_application/json_io.py` and adopted in `src/guppy/api/services_ops.py`. Focused tranche test bundle and baseline `dev-check` passed (with documented temporary `GUPPY_ALLOW_CROSS_PROJECT_DIRTY=1` due local `Guppy-pi` dirty state).

46. April 19, 2026
   Executable Tranche 2 and Tranche 3 of the Settings Hub plan were confirmed complete from live repo state and validation. `ui/launcher/views/settings_hub_view.py` now composes `settings_view.py` with the extracted device/accounts and operations panels, launcher workflows route through `_settings_hub_view`, legacy settings surfaces (`my_pc_view.py`, `advanced_view.py`, `connector_panel.py`, `advanced_terminal_panel.py`) are deleted, and validation passed via targeted Settings smoke/unit coverage plus full `python tools/dev_workflow.py release-check` (`360 passed` default suite, `121 passed` smoke/security suite, release receipt written under `.tmp/dev-workflow/reports/`).

47. April 19, 2026
   Executable Tranche 4, Tranche 5, and Tranche 6 of the Models Hub plan were completed in launcher flow and reconfirmed from live repo state plus focused validation. `ui/launcher/views/models_hub_view.py` is now the single launcher destination for model library, runtime routing, local LLM evidence, and voice flows; `ui/launcher/views/models_view.py` now runs in hub mode so stable MAIN / SUB A / SUB B loadouts stay visible beside runtime state; voice ownership now sits under Models with live Edge, Kokoro, Windows SAPI, ElevenLabs, and local Whisper coverage plus explicit Deepgram planning; and provider account management plus API-key storage remain unified in Settings. Compatibility model/voice classes remain temporarily importable for smoke stability, but the launcher no longer exposes them as separate destinations.

48. April 19, 2026
   Executable Tranche 7 completed through a Home Chat inventory and ownership audit. The inventory confirmed that route/runtime/recovery detail, workspace-detail management, launcher panel controls, and the Home-only operator drawer were the remaining visible blockers to a chat-first Home surface, and it defined the compatibility-safe extraction path used for Tranche 8.

49. April 19, 2026
   Executable Tranche 8 completed in the live Home surface. `ui/launcher/views/assistant_view.py` now keeps the daily Home UI visually chat-first by hiding operator detail surfaces, workspace-management panes, and launcher panel controls while preserving compatibility setters and hidden state accessors for request flow, personalization refresh, and smoke stability. `ui/launcher/launcher_window.py` no longer re-opens the right-side status panel from Home.

50. April 19, 2026
   Executable Tranche 9 completed through the launcher chrome pass. `ui/launcher/components/sidebar.py` and `ui/launcher/components/topbar.py` now present exactly five visible hubs (`HOME`, `MODELS`, `TOOLS`, `LIBRARY`, `SETTINGS`), while `Workspaces` moved to the topbar workspace cluster instead of remaining a first-class hub entry. Hidden compatibility aliases still resolve through the launcher for start-destination and legacy routing stability.

51. April 19, 2026
   Executable Tranche 10 completed with full closeout validation and a 10-tranche audit. Focused nav/Home/Settings/Models smoke coverage passed, `.venv\Scripts\python.exe tools/dev_workflow.py dev-check --guard-scope delta` passed, and `.venv\Scripts\python.exe tools/dev_workflow.py release-check` passed. Audit issues found during closeout were copy-boundary drift between Settings and Models, stale visible nav chrome, Home operator-surface leakage, and one remaining visible MODELS alias-route mismatch; all four were corrected before final validation.

## 10-Tranche Audit

1. Tranches 1-3: complete. Settings ownership, extraction, and cleanup all landed and stayed green.
2. Tranches 4-6: complete for executable launcher scope. Models ownership is unified in launcher flow; compatibility model/voice classes remain intentionally importable.
3. Tranche 7: complete. Home operator-surface inventory and risk mapping were finished and used directly for extraction.
4. Tranche 8: complete. Home now renders as a chat-first surface with voice controls and minimal context only.
5. Tranche 9: complete. Visible nav chrome now matches the five-hub architecture, and Workspaces is secondary access instead of top-level chrome.
6. Tranche 10: complete for executable repo scope. Integration, docs, and validation passed with no blocking tranche errors left open.

Audit errors found and resolved:

1. Settings copy still implied model ownership; corrected so Settings owns account management and API-key storage while Models owns runtime and voice.
2. Visible nav chrome still exposed old surfaces and labels; corrected to the five-hub model.
3. Home still rendered operator details and allowed a Home-only operator drawer path; corrected so those no longer render on the daily chat screen.
4. The visible MODELS nav button initially emitted a legacy alias route instead of the actual hub page; corrected during integration.

---

## Planned Tranche 54 (Complete Module Breakup And Stitch-Driven Streamlining)

Execution note (April 20, 2026):

- This is the full execution planning tranche for complete breakup of remaining large modules while keeping the current product architecture intact.
- The tranche includes explicit execution cards for every major UI element and every tool/settings lane.
- Desktop launcher hardening and account connection/storage best practices are first-class card groups.
- Stitch UI choices are treated as locked implementation constraints for hierarchy, spacing rhythm, copy clarity, and progressive disclosure.

Program artifacts:

1. Detailed tranche card deck: `docs/generated/TRANCHE_54_MODULE_BREAKUP_AND_STITCH_EXECUTION_CARDS_20260420.md`
2. Tranche group map:
   - `TR54-A` foundation contracts and merge choreography
   - `TR54-B` UI element decomposition cards
   - `TR54-C` tool/settings decomposition cards
   - `TR54-D` desktop launcher hardening cards
   - `TR54-E` account connection and secret-storage best-practice cards
   - `TR54-F` integration gates and release closeout

Primary acceptance direction:

1. Remaining large UI/runtime modules are split into bounded seams with no behavior regressions.
2. Launcher startup and runtime status signaling remain deterministic and release-green.
3. Tool-setting language and policy routing are canonical across typed/spoken/card surfaces.
4. Account lifecycle and storage posture are explicit, secure, and user-comprehensible.

Residual non-blocking follow-up:

1. Compatibility wrapper classes remain temporarily importable for smoke stability and incremental extraction.
2. Broader real-device validation for voice engines and deeper runtime parity beyond the current default lanes remain follow-up work, not tranche-completion blockers.

## Current Gaps (Tranche 54)

1. Agent Tools versus App Mgmt framing is clearer in the UI, but deeper execution flow and enforcement still need to catch up with the split.
   Library roots now have inline validation feedback and per-workspace default source pinning is live, but the next Library gap remains deeper file workflows like broader root selection, better note editing ergonomics, and richer source reuse.

2. Voice lifecycle still needs broader real-device validation across engines, especially preview behavior on more machines.
3. Route visibility now includes readiness context and light latency evidence, but fuller live status signaling is still pending.
4. Builder and off-hours flow still need output-cleanup polish, broader template coverage, and repeated stress validation.
5. Workspace framing is materially stronger, and mixed-role acceptance coverage is now in place, but it still needs deeper collaboration cues and broader validation across real user workspace mixes.
6. Local LLM evidence is centralized, but promotion decisions still need more reviewer scores, broader challenger comparison, and a clearer default runtime decision between Ollama and Lemonade.
7. Governance and Windows ops have stronger productized surfaces, but richer provider/account UX, deeper credential lifecycle polish, broader release automation, and fuller installer lifecycle polish still remain.
8. Home calm-start work is now routed through shared presenter copy and mixed-role starter states, and the first Library-to-Chat context chips are live, but transcript/composer rhythm, starter priority, and broader persistence polish still need one more pass before the May 22 checkpoint feels closed.

## Planned Tranche 55 (Desktop Assistant End-State Execution Deck)

Execution note (April 21, 2026):

- This tranche translates the current `P6` hardening lane into an end-state execution checklist for the actual Guppy product contract: five-hub desktop launcher, tray/background companion, local-first model execution, persistent memory/library continuity, extensible tools/plugins, and backup web parity against the same backend.
- The deck stays bound to the north-star and feature filter: chat-first daily flow remains primary, while diagnostics/admin/power surfaces stay demoted to the correct hubs.
- Planned adapter lanes such as AnythingLLM or Hugging Face local are treated as explicit registry/onboarding contracts, not fake-ready runtime claims.

Program artifact:

1. `docs/generated/TRANCHE_55_DESKTOP_ASSISTANT_EXECUTION_CARDS_20260421.md`

Primary acceptance direction:

1. Launcher, tray, and fallback web surfaces all agree on one backend/runtime/workspace truth.
2. Local-runtime, voice, memory, library, and tool/plugin flows are honest, bounded, and validated on real machines.
3. Guppy feels like one calm desktop assistant rather than a shell plus disconnected side surfaces.

## Move-Everything-To-Strong Roadmap (April 22, 2026)

Execution note:

- The April 22 quarantine plus core audit pass confirmed that the live repo is healthy, quarantined trees do not contain must-restore product code, and the remaining work is mostly finish-quality rather than architecture rescue.
- The new roadmap focuses on upgrading all non-strong surfaces to `strong` without reopening scope drift.

Program artifact:

1. `docs/generated/ROADMAP_MOVE_ALL_SURFACES_TO_STRONG_20260422.md`
2. `docs/generated/CORE_INVENTORY_NORTH_STAR_AUDIT_20260422.md`

Primary execution order:

1. Continuity spine: Home, Workspaces, memory payoff
2. Tool clarity and plugin truth
3. Model, voice, and local runtime confidence
4. Tray/runtime/web alignment
5. Library polish and freeze-quality calmness cleanup

## Developer Rules

1. Keep entrypoint wrappers thin and move product logic under `src/guppy/`.
2. Prefer launcher seams over adding new behavior to legacy compatibility surfaces.
3. Treat `src/guppy/`, `ui/`, and `utils/` as the live-code roots for build guardrails.
4. Prefer `src/guppy/launcher_application/`, `src/guppy/runtime_application/`, `src/guppy/workspace_governance/`, and `src/guppy/experience_config/` for launcher-facing contracts and normalization behavior.
5. Record short active tranche notes in this brief instead of creating parallel status markdown files.
6. Keep Guppy and `Guppy-pi` fully isolated: no Guppy/Guppy Prime agent workflow should modify files under `Guppy-pi/` while working this repo.

Execution checkpoint (April 20, 2026, tandem execution tranche):

1. `launcher_command_flow.py` policy/topbar helper family was decomposed into `src/guppy/launcher_application/launcher_command_policy.py`.
2. `launcher_command_flow.py` dropped to `590` lines and no longer needs a line-cap waiver.
3. A doc-retention execution artifact was added at `docs/generated/DOC_RETENTION_CLASSIFICATION_20260420.md` to drive quarantine/purge sequencing.
4. Low-risk legacy wording cleanup executed in inference/router and UI/tool docstrings/messages without behavior changes.
5. Launcher shell voice/system-strip family was extracted into `src/guppy/launcher_application/launcher_voice_strip.py`, and `launcher_window.py` now delegates those methods.
6. Regression compatibility fix retained `FirstRunWizard` monkeypatch behavior for launcher smoke tests after first-run extraction.
7. Validation evidence after this wave: focused launcher smoke suite green and `python tools/dev_workflow.py dev-check --guard-scope delta` green.
8. Assistant queue draining and request-state transitions were split into `src/guppy/launcher_application/launcher_assistant_event_flow.py`, with `launcher_command_flow.py` delegating to that seam.
9. `server_runtime_snapshot.py` APIRouter/lifespan wave started by extracting app bootstrap logic into `src/guppy/api/snapshot_app_bootstrap.py`.
10. Measured post-wave sizes: `src/guppy/api/server_runtime_snapshot.py` -> `938`; `src/guppy/launcher_application/launcher_command_flow.py` -> `426`.
11. Launcher signal wiring and personalization refresh/worker flows were extracted into `src/guppy/launcher_application/launcher_signal_personalization.py`, with `launcher_window.py` delegating those seams.
12. Snapshot status/auth/metrics route registration was extracted into `src/guppy/api/snapshot_status_routes.py` and wired from `server_runtime_snapshot.py`.
13. Measured post-wave sizes: `ui/launcher/launcher_window.py` -> `1263`; `src/guppy/api/server_runtime_snapshot.py` -> `859`; `src/guppy/launcher_application/launcher_command_flow.py` -> `426`.

Execution checkpoint (TR54 integrated closeout, tandem subagent execution):

**Lane A — `launcher_window.py` decomposition:**
1. Connector action handlers extracted → `launcher_connector_handlers.py` (62 lines).
2. Library context handlers extracted → `launcher_library_handlers.py` (141 lines).
3. Instance/workspace handlers extracted → `launcher_instance_handlers.py` (98 lines).
4. Nav/tab/panel/notification handlers + view-index constants extracted → `launcher_nav_handlers.py` (156 lines).
5. Dead import debt purged across each extraction pass.
6. Final size: `ui/launcher/launcher_window.py` → `993` lines (target <1,000 ✅). Waiver retained at-cap.

**Lane B — `server_runtime_snapshot.py` reduction:**
1. Auth try/except stubs + response cache helpers extracted → `snapshot_auth_cache_support.py` (73 lines).
2. Persona/prompt builder functions (`build_chat_system_prompt`) extracted → `snapshot_prompt_support.py` (87 lines).
3. Final size: `src/guppy/api/server_runtime_snapshot.py` → `789` lines. Waiver retained at-cap.

**Lane C — `launcher_command_flow.py` follow-through:**
1. `rotate_chat_session`, `apply_chat_context`, `on_chat_context_changed` re-exported to new `launcher_chat_session.py` (19 lines). Backward-compat re-exports kept.
2. Final size: `src/guppy/launcher_application/launcher_command_flow.py` → `401` lines (no waiver needed).

**TR54-B UI element decomposition:**
- `settings_view.py`: 723 → 512 lines (sections → `settings_view_sections.py`, 162 lines). Waiver removed entirely (now below 700 cap).
- `voices_view.py`: 667 → 495 lines (sections → `voices_sections.py`, 300 lines).
- `models_sections.py`: 643 → 470 lines (support → `models_panel_support.py`, 154 lines).
- `settings_device_accounts_panel.py`: 609 → 548 lines (sections → `settings_accounts_sections.py`, 35 lines).
- `tools_view_cards.py`: 542 → 512 lines (registry consolidation).
- All 5 view files now below 700-line cap. All 8 guards green.

**TR54-C tool/settings decomposition:**
- C1: Tool registry consolidated in `tools_view_cards.py`.
- C2: Policy split — `connector_workflow.py` module docstring added documenting Settings-ownership contract (302 lines).
- C3: `lmstudio_base_url` + `local_harness_base_url` added to `DEFAULT_SETTINGS` and `apply_settings_to_env` in `runtime_profile.py` to close silent key-drop on save/load.
- C4: `tool_readiness.py` policy destination text updated to canonical "Fix in Settings > Device & Accounts: ..." (108 lines).

**TR54-D desktop launcher hardening:**
- D1: `tests/unit/test_launcher_startup.py` created — 31 tests covering startup phase transitions.
- D2: `launcher_app.py` — plain-English "already running" message added (+4 lines).
- D3: Packaging paths verified correct (no change needed).
- D4: `launcher_poll_orchestration.py` — poll failure hardening with try/except + topbar/syslog degradation (+38 lines).
- D5: `launcher_api_runtime_control.py` — diagnostics message now shows full path + "share this file with support" (+2 lines net).

**TR54-E account/secret-storage lifecycle:**
- E1: `settings_device_accounts_presenter.py` — "RECONNECT" label for partial auth; standardized "VERIFY" labels (was "CHECK"/"TEST KEY"). 342 lines.
- E2: `settings_device_accounts_panel.py` — storage posture label, disable placeholder button, updated reconnect UX. 572 lines.
- E3: `snapshot_route_support.py` — nosec annotation on repair_token endpoint.
- E4: `tools/check_secret_redaction.py` created — 113 lines scanning snapshot/readiness files for credential patterns.
- E5: Troubleshooting path updated to canonical Settings > Device & Accounts location string.

**TR54-F integration gates and release closeout:**
- F1: `dev-check` — all 8 guards (delta + baseline) PASSED.
- F2: `release-check` — all guards PASSED; full default test suite PASSED (0 failures after fixing 11 tests whose assertions referenced moved symbols or pre-TR54 copy strings).
   - Fixed 3 `MalformedRuntimeFileTests`: `launcher_window.read_json_dict` → `storage_io.read_json_dict` (function moved to `launcher_application/storage_io.py`).
   - Fixed 4 urllib patch targets: `ui.launcher.launcher_window.urllib` → `src.guppy.launcher_application.launcher_api_runtime_control.urllib` (import purged from shell during dead-import cleanup).
   - Fixed 4 copy-text assertions to match canonical TR54-C/E policy strings ("Fix in Settings > Device & Accounts", "VERIFY", "VERIFY SETUP", "Pick a CRM provider first").
   - Removed stale `settings_view.py` waiver from `check_new_module_line_cap.py` (file now 512 lines, below 700 cap).
- F3: Done definition satisfied — all TR54-B through TR54-E acceptance evidence confirmed; smoke suite green; release-check clean.

Post-TR54 hotspot inventory:
- `ui/launcher/launcher_window.py` → `993` (at-cap waiver, continued seam splits tracked)
- `src/guppy/api/server_runtime_snapshot.py` → `789` (at-cap waiver, route-family splits tracked)
- `src/guppy/launcher_application/launcher_command_flow.py` → `401` (no waiver)
- All TR54-B view files below 700 lines.

## CI Guardrails

1. `tools/dev_workflow.py` is the canonical command entrypoint for local and CI workflows: `dev-check`, `test-fast`, `test-default`, `test-smoke`, and `release-check`.
2. `tools/check_new_module_line_cap.py` enforces the live-code line cap across `src/guppy/`, `ui/`, `compat_shims/launcher_ui/ui/launcher/`, and `utils/`, with baseline hardening tiers of ideal `<=250`, healthy `<=400`, review `<=600`, urgent `<=700`, and waiver-only above the cap.
3. `tools/check_architecture_boundaries.py` blocks legacy-surface imports and new UI/runtime-governance coupling outside the narrow launcher transition waivers.
   The runtime-auth/UI waiver is now closed; remaining launcher transition pressure is tracked primarily through line-cap hotspot waivers.

4. `.github/workflows/quality-gates.yml` maps CI into `guardrails`, `default-tests`, and `product-smoke`, all through `tools/dev_workflow.py`.
5. `release-check` writes a machine-readable receipt and short text summary under `.tmp/dev-workflow/reports/`.

## Live Architecture And Docs

1. `docs/LIVE_ARCHITECTURE.md` is the concise map for live domains, allowed dependency flow, and transitional launcher guardrails.
2. `docs/BUILD_TRUTH_PATH.md` is the concise build and CI workflow reference.
3. `docs/LEGACY_SURFACES.md` records what is compatibility-only and should not regain product ownership.
4. `documentation/ARCHITECTURE.md` is the canonical technical architecture reference.
5. `documentation/TRUTH_AUDIT.md` records where historical docs diverge from live code and active references.

## Where To Look

1. Current product status, roadmap, and handoff: `docs/PROJECT_BRIEF.md`
2. Product north star and scope boundary: `docs/GUPPY_PRODUCT_NORTH_STAR.md`
3. Feature keep / cut / demote / defer filter: `docs/PRODUCT_FEATURE_FILTER.md`
4. Setup and operator reference: `README.md`
5. Technical architecture and security truth: `documentation/README.md`
6. Live architecture map: `docs/LIVE_ARCHITECTURE.md`
7. Build and CI truth path: `docs/BUILD_TRUTH_PATH.md`
8. Legacy compatibility quarantine: `docs/LEGACY_SURFACES.md`
9. Daily operator runbook: `docs/DAILY_WORKFLOW.md`
10. Local LLM plan: `docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`
11. Historical roadmap log: `docs/archive/root-history/ROADMAP_2026-04-17.md`
12. Move-everything-to-strong execution roadmap: `docs/generated/ROADMAP_MOVE_ALL_SURFACES_TO_STRONG_20260422.md`
