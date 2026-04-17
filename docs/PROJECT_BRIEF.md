# Guppy Project Brief

Last updated: 2026-04-16

## Purpose

Guppy is a Windows-first, local-first personal assistant focused on:

1. Fast response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear persona/model/voice customization.

## Current State Snapshot

1. `M1` closed on April 13, 2026; `M2` is active as of April 15, 2026.
2. Current verified baseline on April 16, 2026: runtime smoke plus launcher/security regression suites are green, `R2.1` release-lane hardening is now in validation, and Workspace Framing is already in implementation alongside that closeout.
3. Next checkpoint: April 24, 2026 - keep release-lane hardening stable in validation with a reviewer bundle that carries a clear `Ref`, evidence timestamps, repeatable dry-run artifacts, and operator-readable handoff copy.
4. Next checkpoint: May 8, 2026 - finish the first Workspace Framing slice with onboarding examples, create-flow recipes, stronger recurring-context guidance, and cleaner workspace-ready handoff.
5. Next checkpoint: May 22, 2026 - continue Home/chat-first polish with calmer default copy, one obvious primary action, and optional starter guidance that does not crowd the chat surface.

## Primary Product Surface

1. Default entrypoint: guppy_launcher.py
2. Canonical launcher path: src/guppy/apps/launcher_app.py + ui/launcher/
3. Canonical launch helper: src/guppy/cli/launch.py
4. Default runtime instance layout: `guppy-primary` foreground with optional `builder-collab`
5. Teaching/code specialization now routes through `guppy-teach` and `guppy-code` instead of standalone Merlin/Council windows

## Runtime Services

1. API: `src/guppy/api/server.py` as the public module, composed by `src/guppy/api/server_runtime.py` plus imported routers/services, launched from the root shim `guppy_api.py`
2. Hub/tray: `src/guppy/apps/hub_app.py`, launched from the root shim `guppy_hub.py`
3. Daemon: `src/guppy/daemon/daemon.py`

Status contract for active docs:

1. `docs/PROJECT_BRIEF.md` is the canonical product-status snapshot.
2. `ROADMAP.md` is the canonical execution board and dated handoff log.
3. `docs/archive/planning-history/m2/` remains historical context only and does not define the active schedule.

## What Is Live

1. Launcher-first workflow with Home, Workspaces, Agent Tools, App Mgmt, Local LLM, Models, and Voices.
2. Embedded INIT path and launcher bootstrap auto-start the API and hub asynchronously when needed.
3. Startup guardrails and runtime telemetry markers.
4. Recovery operations now live under App Mgmt as the single operational surface.
5. Persona Builder v1 is now live end-to-end inside the App Mgmt settings section: saveable personas, scope/model assignment, prompt preview, and API prompt overlay are wired through the launcher flow.
6. Guided model routing visibility is live in Models: route strategy editing, fallback-chain controls, and a sample-query explainer now show why Guppy chose a route.
7. Voice assignment/import/preview is live in Voices: defaults, persona/model bindings, custom voice imports, and preview controls are wired through the launcher state.
8. Queue-driven local builder automation now supports launcher queueing, dry-run staging, approval, and report generation for low-risk tasks.
9. Backend instance capability enforcement now mirrors launcher tool restrictions for chat and inter-instance tool execution.
10. Instance logs now enforce raw-log retention and keep summary metadata for operator review.
11. Base install now excludes dev-only packages and the optional `openwakeword` / `chromadb` extras.
12. App Mgmt now exposes workflow-loop shortcuts for Morning Boot, acceptance snapshot, midday stability, evening close, and overnight low-compute runs through the embedded terminal.
13. Home now includes starter actions for morning brief, focused research, file triage, and builder review so first-run users have clear entry points without leaving the launcher.
14. Home is now chat-first: the messenger-style surface keeps workspace chat, starters, and the composer in front while runtime, routing, and recovery summaries moved out of the top of Home.
15. The right tray now holds compact workspace-tool shortcuts plus a reserved media dock area; App Mgmt now carries the heavier runtime, routing, recovery, and workflow context.
16. Route and voice choices now carry lightweight readiness evidence in the launcher, so Home, Models, and Voices all show a clearer "what Guppy chose and whether it looks ready" story.
17. The launcher shell now uses a premium light-gallery visual system with editorial typography, softer navigation chrome, a stronger empty-state composition, and art-directed color fields to make Home feel closer to leading consumer chat products than an operator console.
18. Home has now been pushed further toward a consumer messenger feel: the large top hero is gone, active chat context lives in the top bar, transcript bubbles are softer and more iOS-like, and the composer/right tray now match the same lower-density visual rhythm.
19. Models, Voices, and App Mgmt now hold the fuller readiness story: route evidence, default/runtime voice evidence, workflow evidence, and richer operational context are deeper in the product so Home can stay calm.
20. Agent Tools now mirrors workspace permission policy more explicitly in the UI, and restricted tools no longer prime Home indirectly when the active workspace should not be allowed to use them.
21. Workspaces now shows role mix and collaboration-fit cues directly in the manager, so users can see how many daily/builder/reference/ops contexts they have and what the active workspace is best suited for.
22. Cross-workspace query now follows the same policy framing server-side that the launcher explains client-side, so blocked source workspaces are denied before the bridge runs.
23. The launcher app icon now uses the Guppy fish mark, matching the shell branding instead of leaving the fish only as an internal sidebar motif.
24. Local LLM now has a dedicated launcher surface, so manifest state, benchmark artifacts, review packets, memory posture, and runtime-challenger recommendations no longer stay scattered across Home and Models.
25. Workspace governance is now productized on top of the capability system with an editable Workspaces UI for per-workspace auth modes, tool allow/block lists, endpoint filters, operator notes, and clearer policy reasons in Agent Tools.
26. Connector governance v1 is now live as workspace bindings over shared machine auth: Workspaces edits connector bindings and policy, App Mgmt owns machine-level connector verify/connect/reconnect/disconnect plus secret-management actions, and the API/runtime enforce both layers before connector tools run.
27. Blocked tool telemetry now distinguishes connector unbound/action/account/provider/auth failures plus endpoint scope and workspace-policy denials instead of collapsing everything into one coarse restriction reason, and Agent Tools surfaces the connector auth state directly.
28. App Mgmt now includes a Windows install/update/diagnostics surface with installed-runtime visibility, active local backend, data paths, repair-token posture, latest diagnostics artifact visibility, and one-click verify/update/package/supervised-API/restart/repair actions.
29. Windows servicing evidence is now persisted and operator-readable in App Mgmt: terminal-backed actions carry refs, step counts, "what changed" notes, and next-step guidance that point directly at packaging, supervision, or repair follow-ups.
30. App Mgmt now includes a guided `Automation Test` path, and the repo now ships a dedicated tester entrypoint at `bin/launch_automation_test.bat` for verify -> queue -> review -> approve -> validate flows.
31. Workspace Framing is already live as more than a rename pass: Workspaces and Home now carry role-aware creation defaults, recurring-context cues, saved mode/persona/voice framing, and role-specific starter behavior.
32. The default persona is now `main_guppy` with a curated profile summary plus persona-specific voice binding, and post-chat durable-memory promotion now lifts user-authored preferences, decisions, and scope cues into semantic memory.
33. Release-lane handoff now reads as a reviewer bundle instead of a loose status note: App Mgmt, the release summary, and the packaging/troubleshooting docs all point reviewers through the dry-run report, receipt, and summary in a consistent order, with a stable `Ref`, evidence timestamps, and a `Next Review Step` state when the gate is green.
34. Workspace creation now carries better first-run polish: role presets include example names and recipes, newly created workspaces open directly into onboarding, and Home now frames the composer as the main action with starters as optional head starts.

What is live in the M2 launcher shell right now:

1. Unified launcher entrypoint is `guppy_launcher.py` with canonical implementation in `src/guppy/apps/launcher_app.py` and `ui/launcher/`.
2. Current navigation model is Home, Workspaces, Agent Tools, App Mgmt, Local LLM, Models, and Voices, with settings folded into App Mgmt.
3. Home is now a chat-first daily surface with a consumer-messenger lean: workspace chat stays central, heavy context is off the canvas, and the active launcher context is controlled from the top bar instead of a large in-room panel.
4. App Mgmt now carries runtime facts, route preview, recovery summary, workflow loops, and settings, while the right tray owns softened quick tools, add-on spaces, and the media slot.
5. Workspace-first launcher framing is now live in the UI: the visible shell talks about workspaces, while backend instance contracts remain unchanged for safety.
6. The current visual direction is a warm, premium, chat-first shell rather than the older obsidian-terminal look.
7. The right way to deepen trust now is to keep live readiness evidence in Models, Voices, and App Mgmt rather than adding more status copy back onto Home.

## Current Gaps

1. Agent Tools vs App Mgmt framing is now clearer in the UI, but execution flow and deeper enforcement still need to catch up with the split.
2. Builder polish remains: stronger guardrails and more visual explanation for edge-case provider/voice configurations.
3. Voice lifecycle still needs broader real-device validation across all engines, especially preview behavior on more machines.
4. Route visibility is now explainable in-app with readiness context and light latency evidence, but fuller live status signaling is still pending.
5. Builder/off-hours flow needs output-cleanup polish, broader template coverage, and repeated stress validation before wider rollout.
6. Finish pruning remaining legacy aliases, historical docs, and compatibility wording that still imply Merlin/Council are active surfaces.
7. Workflow loop productization is underway: App Mgmt now has launcher-first workflow shortcuts, next-step guidance, and short outcome summaries, but richer execution evidence and tighter UX still need work.
8. Workspace framing is active and materially stronger, but it still needs deeper collaboration cues and broader acceptance validation across more real workspace mixes.
9. Dependency and packaging surface is still broader than the long-term product target because local, cloud, provider, and voice stacks still share one base runtime bundle.
10. Local LLM evidence is now centralized in its own launcher surface, but promotion decisions still need more reviewer scores, broader challenger comparison, and a clearer default-runtime decision between Ollama and the new Lemonade lane.
11. Governance and Windows ops now have stronger productized surfaces, but richer provider/account UX, deeper workspace credential lifecycle polish, broader release automation, and fuller installer lifecycle polish still need deeper productization.
12. Home calm-start work has started, but transcript/composer rhythm, starter priority, and first-run persistence still need one more polish pass before the May 22 checkpoint feels closed.
13. The new `main_guppy` persona and durable-memory path need calmer operator-facing explanation and review controls so persistent identity feels deliberate instead of implicit.

## Developer Rules

1. Keep entrypoint wrappers thin; move logic under src/guppy/.
2. Prefer launcher modules over adding features to legacy surfaces.
3. Treat `src/guppy/`, `ui/`, and `utils/` as active live-code roots for build guardrails; new drift should land through typed seams, not deeper direct cross-layer imports.
4. Record milestone changes in ROADMAP handoff log.
5. Prefer `src/guppy/launcher_application/`, `src/guppy/workspace_governance/`, and `src/guppy/runtime_application/` when introducing new launcher-facing contracts, normalization helpers, or shared workflow definitions.

## CI Guardrails

1. `tools/dev_workflow.py` is the canonical command entrypoint for local and CI workflows: `dev-check`, `test-fast`, `test-default`, `test-smoke`, and `release-check`.
2. `tools/check_new_module_line_cap.py` enforces the live-code line cap across `src/guppy/`, `ui/`, and `utils/`, with explicit transitional waivers pinned to current hotspot sizes.
3. `tools/check_architecture_boundaries.py` blocks legacy-surface imports and new UI/runtime-governance coupling outside the narrow launcher transition waivers.
4. `.github/workflows/quality-gates.yml` now maps CI into three lanes: `guardrails`, `default-tests`, and `product-smoke`, all through `tools/dev_workflow.py`.
5. `release-check` writes a machine-readable receipt and short text summary under `.tmp/dev-workflow/reports/`.
6. Pytest cache now defaults to `.tmp/pytest-cache`, and the canonical workflow entrypoint also pins temp/cache scratch directories inside `.tmp/dev-workflow/`.
7. Shared launcher/App Mgmt workflow recipes now belong in `src/guppy/launcher_application/workflows.py`; build docs and future runtime-facing consumers should reuse that catalog instead of duplicating commands.

## Live Architecture and Docs

1. `docs/LIVE_ARCHITECTURE.md` is the concise map for live domains, allowed dependency flow, and transitional launcher guardrails.
2. `docs/BUILD_TRUTH_PATH.md` is the concise build/CI workflow reference.
3. `docs/LEGACY_SURFACES.md` records what is compatibility-only and should not regain product ownership.
4. The seam contracts in `src/guppy/launcher_application/`, `src/guppy/workspace_governance/`, and `src/guppy/runtime_application/` are now the preferred source for launcher-facing typed state and normalization behavior.
5. `README.md`, `docs/PROJECT_BRIEF.md`, and `ROADMAP.md` remain the active truth set; older planning/history docs are background context only.

## Test Layout

1. `test-fast` runs the unit-focused fast path.
2. `test-default` runs the default `tests/unit` + `tests/integration` suite, with interactive PTT still excluded from default pytest.
3. `test-smoke` runs launcher/runtime/security smoke coverage through the canonical workflow entrypoint.
4. `tests/smoke/` still contains both pytest-collected smoke coverage and standalone/manual smoke-stress scripts, so it should not be described as entirely outside the default pytest story.

## Where To Look

1. Roadmap and handoff: ROADMAP.md
2. Setup and operator reference: README.md
3. Live architecture map: docs/LIVE_ARCHITECTURE.md
4. Build and CI truth path: docs/BUILD_TRUTH_PATH.md
5. Legacy compatibility quarantine: docs/LEGACY_SURFACES.md
6. Measurable targets: docs/GOALS.md
7. Daily operator runbook: docs/DAILY_WORKFLOW.md
8. Local LLM plan: docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md
9. Local LLM benchmark spec: docs/LOCAL_LLM_BENCHMARK_SPEC.md
