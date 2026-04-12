# Interface Improvement Plan

Date: 2026-04-12

## Goals

1. Improve clarity of system state in all UIs.
2. Reduce perceived latency with better feedback loops.
3. Increase trust through stronger diagnostics and recovery guidance.
4. Keep runtime overhead low while adding richer telemetry.

## Phase 1 (Immediate: 1-2 days)

1. Standardize status strips across Guppy, Merlin, Council, and Hub.
2. Add a single latency vocabulary across apps: p50, p95, p99, queue depth.
3. Add user-facing incident badges: degraded, reconnecting, fallback active.
4. Add one-click copy diagnostics bundle in each UI.

Deliverables:
1. Shared status component in guppy_theme-backed widget helpers.
2. Shared telemetry formatter utility for consistent labels.
3. Shared error badge style and severity mapping.

## Phase 2 (Short-term: 3-7 days)

1. Add command palette for top actions in each interface.
2. Add timeline view for recent agent actions and route decisions.
3. Add startup checklist panel with pass/fail + fix hints.
4. Add queue trend sparkline and latency trend sparkline in Hub.

Deliverables:
1. Action registry module for reusable commands.
2. Timeline event model from session_events and agent_performance.
3. Lightweight chart renderer (PySide6 custom paint, no heavy dependency).

## Phase 3 (Medium-term: 1-3 weeks)

1. Build an interface design system package for all PySide surfaces.
2. Add accessibility profiles (compact, high contrast, larger text).
3. Add role-based layouts (operator mode vs focus mode).
4. Add guided onboarding and contextual tooltips.

Deliverables:
1. Component library module with card, badge, ribbon, meter primitives.
2. Theme token expansion for spacing, typography, motion timings.
3. Profile presets persisted per-user.

## Assets To Add

1. Icon pack with consistent glyphs for queue, route, fallback, and auth states.
2. Sound pack for non-intrusive status cues (ready, warning, error).
3. UI motion preset JSON for coherent transition timing across apps.
4. Empty-state illustrations for no-data, disconnected, and recovering states.
5. Screenshot baseline set for regression checks.

## Programs / Libraries To Add

1. pyqtgraph for efficient tiny sparklines and trend charts.
2. qasync for cleaner async integration in UI event loops.
3. structlog for richer structured logs with context binding.
4. rich (optional for CLI tooling) to improve diagnostics readability.
5. pytest-qt for interaction and widget-level UI tests.

## Code Modules To Add

1. utils/telemetry_window.py
Purpose: rolling window math (p50/p95/p99), queue depth, trend direction.

2. utils/diagnostics_bundle.py
Purpose: collect logs, env summary, runtime checks, and package versions.

3. ui/components/status_strip.py
Purpose: shared status ribbon with badges and quick actions.

4. ui/components/timeline_panel.py
Purpose: render recent actions from structured events.

5. ui/components/sparkline.py
Purpose: minimal trend renderer for latency and queue.

6. ui/accessibility_profiles.py
Purpose: load/apply high-contrast and large-text settings.

## Success Metrics

1. Time to identify active failure cause under 10 seconds.
2. First response feedback shown under 200 ms for all UI paths.
3. Queue depth and p95 visible in all main views.
4. Startup readiness failures become self-resolving via guided actions.
5. Reduction in repeated support/debug questions over 2 weeks.

## Execution Order Recommendation

1. Shared telemetry and status component extraction.
2. Diagnostics bundle and incident badge unification.
3. Hub sparklines and route timeline.
4. Accessibility profiles and role-based layouts.
5. Onboarding and contextual guidance.
