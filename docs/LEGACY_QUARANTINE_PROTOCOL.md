# Legacy Quarantine Protocol

Last updated: 2026-04-14

## Purpose

Legacy code will be removed or quarantined deliberately, not opportunistically. The
goal is to preserve the migration path while making it obvious what is still active,
what is compatibility-only, and what is ready for removal.

## Current Legacy Surface Inventory

- `legacy_surfaces/guppy_ui_legacy.py`
- `legacy_surfaces/merlin_ui_legacy.py`
- `legacy_surfaces/council_ui_legacy.py`
- Root compatibility wrappers:
  `guppy_ui.py`, `merlin_ui.py`, `council_ui.py`, `guppy_launcher.py`,
  `guppy_hub.py`, `guppy_api.py`, `guppy_api_auth.py`, `guppy_agent.py`

## Active Compatibility Entry Points

- Canonical shim apps still importing legacy implementations:
  `src/guppy/apps/guppy_surface_app.py`,
  `src/guppy/apps/merlin_surface_app.py`,
  `src/guppy/apps/council_surface_app.py`
- Compatibility launch paths still exposed:
  `src/guppy/cli/launch.py`,
  `ui/launcher/views/advanced_view.py`,
  `src/guppy/hub/theme_config.py`,
  `src/guppy/hub/window.py`,
  `src/guppy/hub/agent_card.py`
- Thin wrappers that should stay thin until removal:
  `guppy_ui.py`, `merlin_ui.py`, `council_ui.py`

## Initial Classification

- `guppy_ui.py`: likely removable first once wrapper/reference sweep is complete.
- `merlin_ui.py`: compatibility-only, but still reachable through legacy launch paths.
- `council_ui.py`: compatibility-only, but still reachable through legacy launch paths.
- `legacy_surfaces/*`: not directly imported across the wider runtime; they are currently reached through the three canonical shim apps above.

## Quarantine Rules

- Active runtime logic must live under canonical `src/guppy/*` modules or `ui/launcher/*`.
- Root wrappers may remain only as thin import-and-launch compatibility shims.
- Any legacy module that still owns behavior must be either:
  moved into canonical modules, or
  explicitly quarantined with a dated removal note.
- Generated files, runtime reports, and experiment outputs must never be used as long-term architecture references.

## Removal Sequence

- 1. Inventory imports, launch paths, tests, and docs references.
- 2. Confirm wrapper responsibilities are thin and behavior-free.
- 3. Move any remaining behavior into canonical modules.
- 4. Quarantine unreferenced legacy modules.
- 5. Remove quarantined modules after reference scans and verification pass.

## Phase 1 Notes

- Runtime artifact cleanup happens before structural deletion so git noise does not mask real migration work.
- The next phase will use reference scans to classify each legacy entry as active, compatibility-only, or removable.
