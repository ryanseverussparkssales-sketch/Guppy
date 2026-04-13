# Guppy Project Brief

Last updated: 2026-04-13

## Purpose

Guppy is a Windows-first, local-first personal assistant focused on:

1. Fast response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear persona/model/voice customization.

## Primary Product Surface

1. Default entrypoint: guppy_launcher.py
2. Main implementation: src/guppy/apps/launcher_app.py + ui/launcher/
3. Hub split migration path: src/guppy/apps/hub_app.py + src/guppy/hub/
4. Legacy specialist surfaces (compatibility only): guppy_ui.py, merlin_ui.py, council_ui.py

## Runtime Services

1. API: guppy_api.py
2. Hub/tray: guppy_hub.py (wrapper), src/guppy/apps/hub_app.py (implementation)
3. Daemon: guppy_daemon.py

## What Is Live

1. Launcher-first workflow with Assistant, Tools, Settings, Advanced, Models, Voices.
2. Embedded INIT path default behavior; legacy launches compatibility-gated.
3. Startup guardrails and runtime telemetry markers.
4. Recovery operations in launcher settings.
5. Guided persona and guided provider routing builder are live in launcher settings.

## Current Gaps

1. Final guided builder polish for provider routing edge cases and voice lifecycle parity.
2. Complete voice assignment/import/preview lifecycle parity.
3. Full legacy retirement from recommended daily path.
4. In-app daily workflow loop (Morning/Workday/Close).

## Developer Rules

1. Keep entrypoint wrappers thin; move logic under src/guppy/.
2. Prefer launcher modules over adding features to legacy surfaces.
3. Keep changed `src/guppy` modules below line cap guard limits (CI).
4. Record milestone changes in ROADMAP handoff log.

## CI Guardrails

1. `tools/check_new_module_line_cap.py` enforces a line cap on changed Python modules under `src/guppy/`.
2. `tools/check_wrapper_integrity.py` enforces thin wrapper shape for `guppy_launcher.py` and `guppy_hub.py`.
3. `tools/check_architecture_boundaries.py` blocks legacy/root and cross-domain imports on changed `src/guppy` files.
4. All checks run in `.github/workflows/quality-gates.yml`.

## Where To Look

1. Roadmap and handoff: ROADMAP.md
2. Setup and architecture details: README.md
3. Measurable targets: GOALS.md
4. Daily operator runbook: DAILY_WORKFLOW.md
