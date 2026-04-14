# Guppy Project Brief

Last updated: 2026-04-14

## Purpose

Guppy is a Windows-first, local-first personal assistant focused on:

1. Fast response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear persona/model/voice customization.

## Primary Product Surface

1. Default entrypoint: guppy_launcher.py
2. Canonical launcher path: src/guppy/apps/launcher_app.py + ui/launcher/
3. Canonical launch helper: src/guppy/cli/launch.py
4. Legacy specialist surfaces (compatibility only): guppy_ui.py, merlin_ui.py, council_ui.py
5. Canonical CLI blocks legacy `merlin` and `council` launches unless `GUPPY_ENABLE_LEGACY_SURFACES=1` is set.

## Runtime Services

1. API: src/guppy/api/server.py (wrapper: guppy_api.py)
2. Hub/tray: guppy_hub.py (wrapper), src/guppy/apps/hub_app.py (implementation)
3. Daemon: src/guppy/daemon/daemon.py (wrapper: guppy_daemon.py)

## What Is Live

1. Launcher-first workflow with Assistant, Tools, Settings, Advanced, Models, Voices.
2. Embedded INIT path default behavior; legacy launches compatibility-gated.
3. Startup guardrails and runtime telemetry markers.
4. Recovery operations in launcher settings.
5. Guided persona and guided provider routing controls are live in launcher settings, with edge-case polish still in progress.
6. Backend instance capability enforcement now mirrors launcher tool restrictions for chat and inter-instance tool execution.
7. Instance logs now enforce raw-log retention and keep summary metadata for operator review.
8. Base install now excludes dev-only packages and the optional `openwakeword` / `chromadb` extras.

What is live in the M2 launcher shell right now:

1. Unified launcher entrypoint is `guppy_launcher.py` with canonical implementation in `src/guppy/apps/launcher_app.py` and `ui/launcher/`.
2. Current navigation model is Home, Instance Manager, Agent Tools, App Mgmt, Settings, Models, and Voices.
3. Home now carries active-instance identity, background activity, runtime facts, and recovery summary so the right rail stays ops-focused.
4. Instance Manager foundation is live with persisted config/runtime state, create or update, activate, delete, and per-instance log viewing.

## Current Gaps

1. Agent Tools vs App Mgmt content is still transitional: labels and stack order are aligned, but view content is not fully split by responsibility.
2. Final guided builder polish for provider routing edge cases and voice lifecycle parity.
3. Complete voice assignment/import/preview lifecycle parity.
4. Full legacy retirement from recommended daily path; specialist surfaces remain compatibility bridges for fallback and debug.
5. In-app daily workflow loop (Morning/Workday/Close).
6. Dependency and packaging surface is still broader than the long-term product target because local, cloud, provider, and voice stacks still share one base runtime bundle.

## Developer Rules

1. Keep entrypoint wrappers thin; move logic under src/guppy/.
2. Prefer launcher modules over adding features to legacy surfaces.
3. Keep changed `src/guppy` modules below line cap guard limits (CI).
4. Record milestone changes in ROADMAP handoff log.

## CI Guardrails

1. `tools/check_new_module_line_cap.py` enforces a line cap on changed Python modules under `src/guppy/`.
2. `tools/check_wrapper_integrity.py` enforces thin wrapper and shim shape for launcher/hub plus migrated root compatibility files.
3. `tools/check_architecture_boundaries.py` blocks legacy/root and cross-domain imports on changed `src/guppy` files.
4. All checks run in `.github/workflows/quality-gates.yml`.

## Test Layout

1. `tests/unit/` is the default fast regression suite.
2. `tests/integration/` holds runtime or hardware-adjacent tests; interactive PTT smoke is explicitly kept out of default pytest.
3. `tests/smoke/` holds smoke and stress scripts kept out of the default pytest run.

## Where To Look

1. Roadmap and handoff: ROADMAP.md
2. Setup and architecture details: README.md
3. Measurable targets: GOALS.md
4. Daily operator runbook: DAILY_WORKFLOW.md
