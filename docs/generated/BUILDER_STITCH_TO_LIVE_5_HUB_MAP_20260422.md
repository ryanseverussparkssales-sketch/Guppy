# Builder/Stitch To Live 5-Hub Map

Date: April 22, 2026

Scope:
- Builder exports found on disk:
  - `.quarantine/2026-04-22_quarantine_wave_02/stitch_azure_reef_assistant (1)/stitch_azure_reef_assistant/home_guppy_ai_desktop/code.html`
  - `.quarantine/2026-04-22_quarantine_wave_02/stitch_azure_reef_assistant (1)/stitch_azure_reef_assistant/models_hub_desktop/code.html`
  - `.quarantine/2026-04-22_quarantine_wave_02/stitch_azure_reef_assistant (1)/stitch_azure_reef_assistant/knowledge_library_desktop/code.html`
- Live desktop contract:
  - `docs/PROJECT_BRIEF.md` defines the canonical five-hub shell: `HOME`, `MODELS`, `TOOLS`, `LIBRARY`, `SETTINGS`

## Mapping

| Builder source | Corresponding live pane | Adopt literally | Keep live/backend-owned |
| --- | --- | --- | --- |
| Shared chrome across all three exports | Global shell chrome across all five hubs | Warm sand palette, editorial serif-for-headings treatment, roomy left rail, soft card borders, quieter top bar rhythm | Real nav labels, workspace selector state, readiness chips, notifications, route/status text, and all live counts/metrics |
| `home_guppy_ai_desktop` main canvas | `HOME` | Chat-first transcript + composer hierarchy, generous spacing, message-island treatment, calmer empty-state/editorial tone | Transcript data, starters, first-run state, voice state, workspace context, route facts, citations, and any recovery/runtime hints |
| `home_guppy_ai_desktop` right utility panel | Home-adjacent workspace drawer / right tray tone only | Secondary-column proportions, grouped utility cards, lower-emphasis action styling | Actual workspace context, runtime health, tray slots, syslog/recovery evidence, and launcher-to-tray synchronization |
| `models_hub_desktop` | `MODELS` | Search/header rhythm, spacious status hero, large model-card layout, lighter telemetry framing | Provider inventory, readiness truth, install/uninstall state, route/loadout decisions, MAIN/SUB mappings, local-runtime evidence, and voice assignment/readiness |
| `knowledge_library_desktop` | `LIBRARY` | Search-first header, asymmetrical hero blocks, editorial card/table hierarchy, calmer metadata styling | Approved roots, file/note/media data, sync timestamps, playback state, and `use in chat` handoff behavior |

## Missing Builder Coverage

- `TOOLS` has no Builder export. Design should follow the live Tools ownership model, not inferred mock content.
- `SETTINGS` has no Builder export. Credentials, diagnostics, recovery, connectors, and admin controls remain Settings-owned and need live-first design.
- The tray/background companion is not exported. The Home right column is useful as visual tone only, not as a literal tray contract.
- Workspaces/instance management are not exported as a primary screen; live Guppy keeps them subordinate to Home/top-bar context instead of a sixth hub.
- Voice-in-Models detail, local runtime evidence lanes, and narrow/compact responsive states are only partially implied by Builder and should stay implementation-driven.

## Practical Rule

- Copy Builder literally for visual language, spacing, and shell composition.
- Do not copy Builder literally for product copy, fake metrics, placeholder identities, or ownership boundaries.
- Treat live backend and launcher seams as authoritative for anything that changes with runtime, workspace, permissions, models, files, or credentials.
