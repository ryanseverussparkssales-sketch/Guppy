# Live Architecture Map

Last updated: 2026-04-17

## Live Domains

Guppy's active product path is organized around four live domains:

1. `launcher-application`
   Owns launcher orchestration, state loading, action dispatch, readiness polling, and cross-view coordination.
2. `runtime-application`
   Owns API startup/readiness, runtime snapshots, repair-token lifecycle, local-runtime warmup, and host state.
3. `workspace-governance`
   Owns workspace config, permissions, connector bindings, policy decisions, and denial reasons.
4. `experience-config`
   Owns persona, provider, voice, runtime profile, and other user-editable configuration.

## Current Seam Modules

The first clarity tranche added typed seam modules under `src/guppy/` so launcher and build work can move off dict-shaped payloads incrementally instead of through a big-bang rewrite.

1. `src/guppy/launcher_application/contracts.py`
   Defines `LauncherIntent` and `LauncherStateSnapshot`, the launcher-facing state contract for Home, App Mgmt, Models, Voices, and Workspaces.
2. `src/guppy/launcher_application/services.py`
   Provides connector-facing launcher helpers with explicit fallback behavior when the legacy connector backend is unavailable.
3. `src/guppy/launcher_application/workflows.py`
   Holds the shared workflow catalog used by launcher/App Mgmt and build-tool consumers so command recipes do not live inline in UI code.
4. `src/guppy/launcher_application/connector_dispatch.py` and `workspace_state.py`
   Keep connector action shaping and workspace selection rules in pure helper seams so the launcher shell can delegate record-building and active-workspace resolution without re-embedding those rules inline.
5. `src/guppy/launcher_application/workflow_panel.py`, `windows_ops_presenter.py`, `windows_ops_runtime.py`, `windows_ops_guidance.py`, `windows_ops_state.py`, and `terminal_recipes.py`
   Drive App Mgmt workflow-loop copy, Windows Ops render state, servicing guidance/receipt shaping, state persistence, multi-step chain summaries, and embedded-terminal recipe tracking from seam helpers instead of inline UI string assembly.
6. `src/guppy/launcher_application/instance_manager_presenter.py`
   Owns workspace-manager copy, role presets, governance editor state, connector binding editor state, and workspace snapshot translation so the Workspaces view can stay focused on rendering and emitting save intents.
7. `src/guppy/workspace_governance/contracts.py`, `connector_service.py`, `connector_metadata.py`, `machine_auth.py`, `provider_status.py`, and `connector_status.py`
   Normalize workspace summaries, connector inventory rows, governance snapshots, connector action requests/results, connector/provider metadata, machine-auth storage rules, connector guidance, and provider/readiness status builders that previously lived only inside the legacy connector manager.
8. `src/guppy/runtime_application/contracts.py` and `readiness.py`
   Normalize startup-readiness, runtime-health, local-runtime payloads, and launcher-facing readiness summaries/fallback fetch rules coming from the existing API/runtime layer.

These seams are additive for now. Existing launcher and runtime modules still own most live behavior, but new logic should prefer these contracts instead of introducing more cross-layer dict traffic.

## Allowed Dependency Flow

The intended live dependency shape is:

`entrypoint wrappers -> src/guppy/apps composition roots -> launcher/application services -> domain services -> persistence/adapters`

Current guardrail posture:

1. Root wrappers stay thin and forward into `src/guppy/`.
2. `src/guppy/apps/launcher_app.py` is the only live composition root currently allowed to import `ui.launcher`.
3. `ui/` should render state, emit intents, and display readiness/progress; direct imports from runtime/governance/config modules are transitional-only and tracked as file-local waivers in `tools/check_architecture_boundaries.py`.
4. `utils/` should not grow into a second UI or application layer.

Practical rule for the next tranche:

1. If a launcher surface needs connector, governance, or runtime state, add or reuse a seam contract first.
2. If a launcher control needs an operational workflow, define it in `launcher_application/workflows.py` first.
3. If behavior still has to reach into existing `utils/` or runtime modules, keep that import behind an application service instead of in a view.

## Active Live-Code Roots

The build guardrails treat these as the live-code roots:

1. `src/guppy/`
2. `ui/`
3. `utils/`

Line-cap and architecture-boundary checks apply across those roots, with explicit transitional waivers only for current hotspot files that still need to be split.

## What The Seams Protect

The seam layer is intended to keep the next integrations honest:

1. Views should consume `LauncherStateSnapshot` and emit `LauncherIntent` values.
2. Runtime and governance payload normalization should happen in seam contracts, not ad hoc in the launcher shell.
3. Workflow definitions should stay versioned and reviewable in one catalog.
4. App Mgmt should render presenter/state objects from `launcher_application` instead of rebuilding workflow, Windows Ops, or terminal status strings inline.
5. Legacy compatibility facades in `utils/` should delegate static metadata, machine-auth rules, connector guidance, and readiness/status builders to `workspace_governance` instead of duplicating them.
6. Fallback behavior for unavailable legacy backends should be explicit and testable instead of hidden in UI conditionals.

## Legacy Quarantine

`compat_shims/legacy_surfaces/` is compatibility-only. Live code should not import it, and no new feature ownership should move back into that area. See `docs/LEGACY_SURFACES.md` for the current quarantine rules.
