# Legacy Quarantine Protocol

Last updated: 2026-04-20

## Purpose

Legacy code will be removed or quarantined deliberately, not opportunistically. The
goal is to preserve the migration path while making it obvious what is still active,
what is compatibility-only, and what is ready for removal.

## Current Legacy Surface Inventory

- `compat_shims/legacy_surfaces/guppy_ui_legacy.py`
- `compat_shims/legacy_surfaces/merlin_ui_legacy.py`
- `compat_shims/legacy_surfaces/council_ui_legacy.py`
- Active root launch shims:
  `guppy_launcher.py`, `guppy_hub.py`, `guppy_api.py`

## Active Compatibility Entry Points

- Supported launch paths:
  `src/guppy/cli/launch.py`,
  `guppy_launcher.py`,
  `guppy_hub.py`,
  `guppy_api.py`
- Historical specialist surface code remains quarantined under:
  `compat_shims/legacy_surfaces/`
- Thin wrappers that should stay thin until removal:
  root launch wrappers only
- Debug console ownership:
  `src/guppy/debug/` remains the canonical debug-console surface for supported desktop entrypoints.

## Initial Classification

- `compat_shims/legacy_surfaces/*`: compatibility-only historical surface code; no supported entrypoint should depend on it.
- root launch wrappers: keep thin and behavior-free.

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
- April 17, 2026: reference scan found no live code imports of the non-UI `compat_shims/*` aliases, so those shim files are now removable. Only `compat_shims/legacy_surfaces/` plus the root launch wrappers remain in the compatibility lane.
- April 20, 2026: wrapper-integrity checks now verify that supported root wrappers do not reference `compat_shims`, and the `compat_shims/legacy_surfaces/` package marker explicitly labels that area as quarantined.
