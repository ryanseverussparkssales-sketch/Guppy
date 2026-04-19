# Guppy Project Brief

Last updated: 2026-04-18

## Purpose

Guppy is a Windows-first, local-first personal assistant focused on:

1. Fast response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear persona, model, and voice customization.

Product direction is further constrained by `docs/GUPPY_PRODUCT_NORTH_STAR.md` and `docs/PRODUCT_FEATURE_FILTER.md`, which define what Guppy is, what it is not, and how to decide what stays on the roadmap.

## Active Doc Contract

1. `docs/PROJECT_BRIEF.md` is the single active status, roadmap, and handoff source.
2. `README.md` is stable setup, operations, and repo-orientation reference only.
3. `documentation/` owns canonical technical architecture, security, and truth-audit material.
4. `docs/archive/` is historical only and does not define active priorities.
5. The archived pre-merge roadmap log lives at `docs/archive/root-history/ROADMAP_2026-04-17.md`.

## Current State Snapshot

1. `M1` closed on April 13, 2026.
2. `M2` became active on April 15, 2026.
3. As of April 17, 2026, release-lane hardening and connector governance remain in validation while Workspace Framing is the active implementation lane.
4. The launcher/runtime seam extraction is materially underway under `src/guppy/launcher_application/`, `src/guppy/runtime_application/`, `src/guppy/workspace_governance/`, and `src/guppy/experience_config/`, including a landed launcher-local bearer-token helper in `src/guppy/runtime_application/auth.py`.
5. Historical specialist launcher surfaces are no longer part of any supported CLI or batch launch path; compatibility material is quarantined under `compat_shims/legacy_surfaces/`.
6. First-run startup reliability, workspace warmup fallback, and launcher navigation discoverability are now stable enough to treat the next tranche as bugfix and UI-polish work rather than launch-correctness recovery.

## Primary Product Surface

1. Default entrypoint: `guppy_launcher.py`
2. Canonical launcher path: `src/guppy/apps/launcher_app.py` plus `ui/launcher/`
3. Canonical launch helper: `src/guppy/cli/launch.py`
4. Supported launch CLI surfaces: `guppy`, `launcher`, `guppyprime`, `hub`, and `api`
5. Default runtime instance layout: foreground `guppy-primary` with optional `builder-collab`

## Runtime Services

1. API: `src/guppy/api/server.py`, composed by `src/guppy/api/server_runtime.py` plus imported routers and services, launched from `guppy_api.py`
2. Hub and tray: `src/guppy/apps/hub_app.py`, launched from `guppy_hub.py`
3. Daemon: `src/guppy/daemon/daemon.py`

## What Is Live

1. Launcher-first workflow with Home, Workspaces, Agent Tools, App Mgmt, Local LLM, Models, and Voices.
2. Embedded INIT plus async launcher bootstrap of the API and hub when needed.
3. Startup guardrails, runtime telemetry markers, and launcher-owned readiness summaries.
4. Recovery operations, workflow loops, Windows servicing, and automation-test flows in App Mgmt.
5. Persona Builder v1, route explainability, voice assignment/import/preview, and role-aware workspace creation defaults.
6. Workspace governance with per-workspace auth modes, tool allow/block lists, connector bindings, endpoint filters, and clearer denial reasons.
7. Connector governance v1 with machine-level auth inventory/actions and workspace binding policy enforced in the runtime.
8. Chat-first Home shell with calmer canvas, top-bar context, softened right tray, and deeper readiness evidence moved into Models, Voices, and App Mgmt.
9. Local LLM surface with manifest state, benchmark artifacts, review packets, memory posture, and challenger recommendations.
10. Release-lane reviewer bundle flows with persisted `Ref`, evidence timestamps, receipt, summary, and launcher-visible next-step guidance.
11. Mixed-role workspace framing acceptance coverage now spans unit presenter tests plus launcher smoke checks for role summaries, empty-state onboarding, workspace-ready handoff copy, and cross-workspace switching.

## Execution Board

| Priority | Track | Status | Current Tranche | Acceptance Criteria | Target Window |
| --- | --- | --- | --- | --- | --- |
| P1 | UI Bugfix + Navigation Simplification | active | Reduce daily-path clutter, fix navigation confusion, and tighten visible hierarchy before deeper polish | A first-run user can tell where Chat, Workspaces, Library, and Settings live without learning the operator surfaces first | April 17 - April 24, 2026 |
| P2 | Library / Files Completion | active | Turn Library into a real workspace file surface with approved roots, recent files, pinned notes, and artifact links | Workspace files feel first-class and can be reused in chat without hunting through secondary surfaces | April 21 - May 8, 2026 |
| P3 | Chat-First Workflow Completion | active | Make transcript, composer, study context, and coding context feel native instead of bolted on | Chat, Workspaces, and Library read as one daily workflow rather than separate tools | April 24 - May 12, 2026 |
| P4 | Operator Surface Demotion | queued | Keep Settings and App Mgmt powerful while moving them farther out of the daily path | Daily work no longer feels like it starts inside an operations console | May 1 - May 16, 2026 |
| P5 | Trust + Local Runtime Promotion | queued | Finish route clarity, voice/device trust, and the default local runtime decision with reviewer evidence | Users can understand runtime choices and the local default is measurable and auditable | May 12 - June 6, 2026 |
| P6 | Packaging + Bob Merge Readiness | watch | Keep packaging stable while aligning Guppy with external runtime, memory, and library contracts for future Bob linking | Release remains repeatable and future merge work can happen on stable interfaces instead of copied repo baggage | June 1 - June 20, 2026 |

## Roadmap Knife

Apply `docs/PRODUCT_FEATURE_FILTER.md` to every tranche before expanding scope. The board below is the current keep / demote / defer cut.

| Track | Decision | Keep Now | Demote Or Narrow | Defer / Explicitly Not Now |
| --- | --- | --- | --- | --- |
| P1 | keep | Navigation clarity, calmer hierarchy, fewer visible controls, cleaner first-run path, obvious `Chat / Workspaces / Library / Settings` flow | Operator shortcuts, status noise, duplicate navigation affordances | Cosmetic redesign work that does not improve comprehension |
| P2 | keep | Approved roots, recent files, pinned notes, saved artifacts, direct file reuse in chat, simpler Library browsing | Power-user file metadata and secondary management flows | Broad filesystem intelligence, whole-PC crawling by default, connector-heavy file surfaces |
| P3 | keep | Transcript/composer rhythm, attached context review, clearer source reuse, stronger continuity between Library and Chat | Route, model, and runtime internals on the daily chat surface | Bigger agent orchestration, ambient assistant behavior, flashy multi-pane chat experiments |
| P4 | demote | Settings remains the home for recovery, runtime setup, diagnostics, and release/admin flows | App Mgmt prominence, operator logs, connector internals, servicing detail, release evidence visibility | New operator-facing top-level destinations |
| P5 | narrow and gate | Trust only where it improves user confidence now: clear tool availability, route clarity, dependable local runtime choice, device/voice trust | Reviewer-only evidence, benchmark packets, deeper runtime comparison detail | Broad automation expansion, more visible route controls, future-flexibility provider complexity, "Jarvis" scope |
| P6 | defer behind product finish | Stable packaging, external integration contracts, no repo-baggage regression | Bob merge planning should stay interface-level and backgrounded | Large merge effort, copied sidecar repos, preemptive compatibility work before P1-P4 feel finished |

### Keep Through May 2026

1. Chat smoothness.
2. Workspace continuity.
3. Library usefulness.
4. File attach and reuse.
5. Startup reliability.
6. Navigation clarity.
7. Calm UI cleanup.

### Demote Through May 2026

1. App Mgmt prominence on the daily path.
2. Runtime telemetry visibility in Chat.
3. Route, model, and recovery internals outside `Settings`.
4. Connector and governance detail outside task-relevant moments.

### Defer Through May 2026

1. Bigger "Jarvis" ambitions.
2. Broad automation expansion.
3. New top-level product surfaces.
4. Heavy Bob merge work beyond stable contracts and packaging readiness.
5. Fancy multi-agent or multi-provider ideas that make the product feel larger before it feels smoother.

## Timeline And Checkpoints

1. April 24, 2026
   The daily path is visibly simpler, with navigation clutter reduced and the primary Chat / Workspaces / Library / Settings flow easier to read on first launch.
2. May 8, 2026
   Library becomes a real workspace file surface with approved roots, recent files, and pinned study or coding context that can be reused in chat.
3. May 22, 2026
   Chat-first workflow and operator-surface demotion land together, so Guppy feels like a local AI workspace first and a systems console second.

## Current Acceptance Gates

1. `python tools/dev_workflow.py dev-check --guard-scope baseline`
   All build guardrails pass, including architecture boundaries, line-cap policy, wrapper integrity, runtime artifact hygiene, and doc ownership.
2. `python tools/dev_workflow.py test-default`
   Default unit and integration suites pass.
3. `python tools/dev_workflow.py test-smoke`
   Launcher interaction, runtime, and security smoke suites pass.
4. `python tools/dev_workflow.py release-check`
   Release receipt and summary are written with a stable `Ref`, complete gate state, and an explicit `Next Review Step`.

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
   Guppy no longer depends on vendored Lemonade or MemPalace source trees, the deprecated repo-local web UI, or checked-in `tests/runtime` stress reports; runtime challengers, local memory, and future Bob-linking work now anchor on explicit external integration contracts and `runtime/` evidence paths instead.
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

## Current Gaps

1. Agent Tools versus App Mgmt framing is clearer in the UI, but deeper execution flow and enforcement still need to catch up with the split.
   Library roots are now browsable from the UI, pinned notes and artifacts can be edited or removed in place, and attached Library context now shapes outbound chat requests; the next Library gap is deeper file workflows like broader root selection, better note editing ergonomics, and richer source reuse.
2. Voice lifecycle still needs broader real-device validation across engines, especially preview behavior on more machines.
3. Route visibility now includes readiness context and light latency evidence, but fuller live status signaling is still pending.
4. Builder and off-hours flow still need output-cleanup polish, broader template coverage, and repeated stress validation.
5. Workspace framing is materially stronger, and mixed-role acceptance coverage is now in place, but it still needs deeper collaboration cues and broader validation across real user workspace mixes.
6. Local LLM evidence is centralized, but promotion decisions still need more reviewer scores, broader challenger comparison, and a clearer default runtime decision between Ollama and Lemonade.
7. Governance and Windows ops have stronger productized surfaces, but richer provider/account UX, deeper credential lifecycle polish, broader release automation, and fuller installer lifecycle polish still remain.
8. Home calm-start work is now routed through shared presenter copy and mixed-role starter states, and the first Library-to-Chat context chips are live, but transcript/composer rhythm, starter priority, and broader persistence polish still need one more pass before the May 22 checkpoint feels closed.

## Developer Rules

1. Keep entrypoint wrappers thin and move product logic under `src/guppy/`.
2. Prefer launcher seams over adding new behavior to legacy compatibility surfaces.
3. Treat `src/guppy/`, `ui/`, and `utils/` as the live-code roots for build guardrails.
4. Prefer `src/guppy/launcher_application/`, `src/guppy/runtime_application/`, `src/guppy/workspace_governance/`, and `src/guppy/experience_config/` for launcher-facing contracts and normalization behavior.
5. Record short active tranche notes in this brief instead of creating parallel status markdown files.

## CI Guardrails

1. `tools/dev_workflow.py` is the canonical command entrypoint for local and CI workflows: `dev-check`, `test-fast`, `test-default`, `test-smoke`, and `release-check`.
2. `tools/check_new_module_line_cap.py` enforces the live-code line cap across `src/guppy/`, `ui/`, and `utils/`.
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
