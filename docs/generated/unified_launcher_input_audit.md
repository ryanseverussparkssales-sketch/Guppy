# Unified Launcher Input Audit

## Scope

Audit covers the unified PySide launcher surfaces under `ui/launcher/`.

## Live Controls

- Top bar navigation buttons, instance switcher, and search submit are wired.
- Sidebar tab rail is wired across all seven launcher tabs.
- Home chat input, send, cancel, mode, persona, and runtime-profile selectors are wired.
- Instance Manager create, refresh, switch, logs, and delete actions are wired.
- Agent Tools search/filter controls and builder queue panel are wired.
- App Management recovery actions and operator-log filter are wired.
- Models route selectors, fallback-chain input, refresh, and active-model selection are wired.
- Voices engine selection, default save, persona/model assignment, preview, and select actions are wired.
- Settings runtime defaults now share the tab with Persona Builder v1 and persist through the runtime/personalization helpers.

## Placeholder Or Gated Controls

- Top bar notification button is disabled and still placeholder-only.
- Top bar terminal button is disabled and still placeholder-only.
- Home mic/PTT button is disabled and still placeholder-only.
- Legacy Merlin and Council launch/deploy cards remain env-gated behind `GUPPY_ENABLE_LEGACY_SURFACES=1`.

## Consolidation Notes

- Active instance state is exposed in both Top Bar and Instance Manager and should continue using launcher window as the single source of truth.
- Mode and profile defaults exist in Home, Models routing, and Settings; launcher-window orchestration is already the correct sync point.
- Recovery outcomes are surfaced in Status Panel, Home, and App Management; follow-up work should keep those views driven from one event path.

## Immediate Follow-Up

- Either implement or hide the three placeholder controls before calling the launcher input surface complete.
- Keep future button/input additions listed here so the unified-app audit stays truthful against the code.
