# Legacy Surfaces Quarantine

Last updated: 2026-04-17

## Compatibility-Only Areas

These areas remain available for compatibility and migration support, not new product ownership:

1. `compat_shims/legacy_surfaces/`
2. legacy root launcher/hub aliases such as `guppy_launcher.py` and `guppy_hub.py` beyond their thin-wrapper role
3. older planning/history docs outside the active truth set

## Rules

1. No new feature work should originate in `compat_shims/legacy_surfaces/`.
2. Live code in `src/guppy/`, `ui/`, and `utils/` should not import `compat_shims.legacy_surfaces`.
3. Root wrappers stay thin and should only forward into the canonical `src/guppy/` implementation modules.
4. The active documentation truth set is `README.md`, `docs/PROJECT_BRIEF.md`, and `ROADMAP.md`.

## Related Guardrails

`tools/check_architecture_boundaries.py` blocks live imports of compatibility-only legacy surfaces and legacy root launcher/hub modules.
