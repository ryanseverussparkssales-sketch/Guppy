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
   Defines `LauncherIntent` and `LauncherStateSnapshot`, the typed launcher-facing contract that the launcher shell already uses and the individual views are incrementally adopting.
2. `src/guppy/launcher_application/services.py`
   Provides connector-facing launcher helpers with explicit fallback behavior when the legacy connector backend is unavailable.
3. `src/guppy/launcher_application/workflows.py`
   Holds the shared workflow catalog used by launcher/App Mgmt and build-tool consumers so command recipes do not live inline in UI code.
4. `src/guppy/launcher_application/connector_dispatch.py` and `workspace_state.py`
   Keep connector action shaping and workspace selection rules in pure helper seams so the launcher shell can delegate record-building and active-workspace resolution without re-embedding those rules inline.
5. `src/guppy/launcher_application/workflow_panel.py`, `windows_ops_presenter.py`, `windows_ops_runtime.py`, `windows_ops_guidance.py`, `windows_ops_state.py`, `terminal_recipes.py`, and `embedded_terminal.py`
   Drive App Mgmt workflow-loop copy, Windows Ops render state, servicing guidance/receipt shaping, state persistence, multi-step chain summaries, and embedded-terminal session orchestration from seam helpers instead of inline UI string assembly.
6. `src/guppy/launcher_application/instance_manager_presenter.py`
   Owns workspace-manager copy, role presets, create/save request shaping, section-toggle state, governance editor state, connector binding editor state, and workspace snapshot translation so the Workspaces view can stay focused on rendering and emitting save intents.
7. `src/guppy/launcher_application/home_presenter.py`
   Owns Home workspace framing, role-aware starter copy, welcome messaging inputs, and calm chat-summary text so the Home view can render from one shared copy seam instead of rebuilding workspace guidance inline.
8. `src/guppy/experience_config/services.py`
   Owns launcher-facing runtime settings plus personalization/voice persistence helpers so Settings, Models, Voices, and the launcher shell no longer import `utils.runtime_profile` or `utils.personalization_config` directly.
9. `src/guppy/workspace_governance/access_policy.py`
   Owns the launcher-facing wrappers for workspace tool-permission checks and auth-mode labeling so Agent Tools and the launcher shell no longer import `utils.instance_capabilities` directly.
10. `src/guppy/workspace_governance/contracts.py`, `connector_service.py`, `connector_metadata.py`, `machine_auth.py`, `provider_status.py`, and `connector_status.py`
   Normalize workspace summaries, connector inventory rows, governance snapshots, connector action requests/results, connector/provider metadata, machine-auth storage rules, connector guidance, and provider/readiness status builders that previously lived only inside the legacy connector manager.
11. `src/guppy/runtime_application/contracts.py`, `readiness.py`, and `auth.py`
   Normalize startup-readiness, runtime-health, local-runtime payloads, launcher-facing readiness summaries/fallback fetch rules, and the launcher-local bearer-token helper that keeps `ui/launcher/launcher_window.py` from importing `src.guppy.api` directly.

These seams are additive for now. Existing launcher and runtime modules still own most live behavior, but new logic should prefer these contracts instead of introducing more cross-layer dict traffic.

## Documentation Contract

1. `docs/PROJECT_BRIEF.md` is the single active status, roadmap, and handoff source.
2. `README.md` is stable setup and operations context.
3. `documentation/ARCHITECTURE.md` and related `documentation/` references own canonical technical architecture and security truth.
4. `docs/archive/` is historical only and should not be treated as an active architecture source.

## Allowed Dependency Flow

The intended live dependency shape is:

`entrypoint wrappers -> src/guppy/apps composition roots -> launcher/application services -> domain services -> persistence/adapters`

Current guardrail posture:

1. Root wrappers stay thin and forward into `src/guppy/`.
2. `src/guppy/apps/launcher_app.py` is the only live composition root currently allowed to import `ui.launcher`.
3. `ui/` should render state, emit intents, and display readiness/progress; direct imports from runtime/governance/config modules are transitional-only and should move behind seam helpers before they land in views or the launcher shell.
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

Line-cap and architecture-boundary checks apply across those roots. The current transition pressure is concentrated in line-cap hotspot files that still need to be split; the launcher's direct UI-to-runtime API import waiver is now closed.

## What The Seams Protect

The seam layer is intended to keep the next integrations honest:

1. Views are transitioning toward `LauncherStateSnapshot` and `LauncherIntent`; today the launcher shell already builds the typed snapshot, while several views still emit raw Qt signals and dict payloads during the migration.
2. Runtime and governance payload normalization should happen in seam contracts, not ad hoc in the launcher shell.
3. Workflow definitions should stay versioned and reviewable in one catalog.
4. App Mgmt should render presenter/state objects from `launcher_application` instead of rebuilding workflow, Windows Ops, or terminal status strings inline.
5. Home and Workspaces should consume shared launcher presenter copy instead of rebuilding role-aware onboarding or starter language inside the view layer; `assistant_view.py` and `instance_manager_view.py` now do this for the main calm-start and workspace-framing paths.
6. Legacy compatibility facades in `utils/` should delegate static metadata, machine-auth rules, connector guidance, and readiness/status builders to `workspace_governance` instead of duplicating them.
7. Fallback behavior for unavailable legacy backends should be explicit and testable instead of hidden in UI conditionals.
8. Oversized launcher views can still be transitional, but new orchestration should land in presenters/services first and only leave rendering/signals in the Qt layer.

## Legacy Quarantine

`compat_shims/legacy_surfaces/` is compatibility-only. Live code should not import it, and no new feature ownership should move back into that area. See `docs/LEGACY_SURFACES.md` for the current quarantine rules.
