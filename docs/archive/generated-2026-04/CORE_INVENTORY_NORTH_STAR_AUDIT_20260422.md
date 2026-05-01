# Core Inventory And North-Star Audit

Date: April 22, 2026

## Scope

- Live core inventory after quarantine waves 01 and 02
- Fresh code-health check against the current five-hub product shell
- Comparison against:
  - `docs/GUPPY_PRODUCT_NORTH_STAR.md`
  - `docs/PRODUCT_FEATURE_FILTER.md`
  - `docs/PROJECT_BRIEF.md`
- Quarantine sweep to confirm whether sidelined files contain must-restore product work

## Fresh Validation

- `python tools/dev_workflow.py release-check`
  - passed on April 22, 2026
  - default suite: `626 passed, 2 skipped`
  - product smoke: `138 passed`
  - security gate: `Launch ready: YES`
- `python tools/validate_build_checks.py`
  - passed
  - packaging audit now accepts the quarantined packaged build under `.quarantine/2026-04-22_quarantine_wave_01/dist/Guppy/Guppy.exe`

## Live Core Inventory

- `src/`: `439` files
- `compat_shims/`: `163` files
- `ui/`: `14` files
- `tests/`: `453` files
- `tools/`: `60` files
- `docs/`: `67` files
- `config/`: `15` files
- `runtime/`: `377` files
- `web/`: `16` files
- `assets/`: `2` files
- `bin/`: `18` files

## North-Star Comparison

### 1. Chat / Home

- Status: strong
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/assistant_view.py`
  - `src/guppy/launcher_application/home_presenter.py`
- North-star fit:
  - chat remains the center of the product
  - workspace-aware starter flows and first-run guidance are present
  - launcher noise is demoted out of the visible daily path
- Finish:
  - transcript/composer polish
  - smoother context carry-through from Library into active chat
  - more confidence-building continuity cues when returning to a workspace
- Improve:
  - keep reducing anything that makes Home feel like a launcher instead of an assistant
  - keep compacting review-band Home helper modules without changing behavior

### 2. Workspaces

- Status: good, but still secondary in discoverability
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/instance_manager_view.py`
  - topbar workspace controls
  - `src/guppy/launcher_application/instance_manager_presenter.py`
- North-star fit:
  - workspace purpose, continuity, governance, and role-aware copy are real
  - workspaces are correctly subordinate to the daily chat path instead of a noisy sixth hub
- Finish:
  - cleaner re-entry and switching flow
  - stronger continuity summaries from saved context and recent activity
- Improve:
  - keep workspace management easier to find from Home without promoting it back into top-level navigation

### 3. Library

- Status: strong
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/library_view.py`
  - `compat_shims/launcher_ui/ui/launcher/views/library_media_panel.py`
  - `src/guppy/launcher_application/library_presenter.py`
- North-star fit:
  - approved roots, notes, artifacts, media playback, and use-in-chat handoff are all live
  - Library clearly supports the daily file workflow the north star calls for
- Finish:
  - richer previews
  - calmer metadata ergonomics
  - continued polish around artifact editing and saved-source reuse
- Improve:
  - keep Library fast and obvious for “find, attach, reuse, save”

### 4. Settings

- Status: strong
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/settings_hub_view.py`
  - `settings_device_accounts_panel.py`
  - `settings_operations_panel.py`
  - `src/guppy/launcher_application/storage_io.py`
- North-star fit:
  - credentials, key storage, diagnostics, recovery, daemon, connectors, and advanced controls are correctly centralized
  - operator detail remains demoted out of Home
- Finish:
  - credential lifecycle polish
  - panel-size reduction and further structure cleanup
  - continued simplification of diagnostics and recovery language
- Improve:
  - keep Settings powerful but quieter and easier to scan

### 5. Models

- Status: useful and aligned as a secondary hub
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/models_hub_view.py`
  - `models_view.py`
  - `voices_view.py`
  - `src/guppy/launcher_application/provider_registry.py`
- North-star fit:
  - acceptable as a secondary hub because it supports the daily path without dominating it
  - Ollama local is real, Lemonade is present, LM Studio is part of the sourcing lane, voice routing is integrated
- Finish:
  - broader real-device validation
  - deeper runtime execution parity across providers
  - actual adapter completion for AnythingLLM and Hugging Face local, which are still planned lanes
- Improve:
  - keep model routing understandable in one session
  - avoid exposing internal route complexity on Home

### 6. Tools

- Status: solid foundation, still needs product-tightening
- Live surface:
  - `compat_shims/launcher_ui/ui/launcher/views/tools_view.py`
  - `src/guppy/launcher_application/tool_action_registry.py`
  - `src/guppy/launcher_application/launcher_tools_coordination.py`
- North-star fit:
  - tool states, permission controls, and recent traces exist
  - this is acceptable as a secondary implementation hub under the current five-hub shell
- Finish:
  - clearer tool onboarding
  - stronger plugin/tool registry story
  - better explanation of what is available now versus planned
- Improve:
  - keep traces and governance available without turning Tools into a product-internal dashboard

### 7. Tray / Background Runtime

- Status: real and important
- Live surface:
  - `src/guppy/hub/app.py`
  - `src/guppy/apps/hub_app.py`
  - `guppy_hub.py`
  - `src/guppy/daemon/daemon.py`
- North-star fit:
  - system tray, background runtime, and daemon posture are real
  - this supports the “always available local assistant” goal without demanding user attention
- Finish:
  - more real-machine validation
  - cleaner operator handoff when tray/runtime/API disagree
- Improve:
  - keep tray behavior invisible unless needed

### 8. Memory / Persistence

- Status: implemented, needs more visible product payoff
- Live surface:
  - `src/guppy/memory/memory.py`
  - `src/guppy/memory/memory_store.py`
  - `src/guppy/memory/semantic.py`
- North-star fit:
  - conversation history, semantic memory, and workspace-scoped recall are real
  - this supports the product promise of persistence and continuity
- Finish:
  - stronger end-user continuity proof in the UI
  - more explicit recall quality validation
- Improve:
  - make persistence feel obvious to users, not just present in backend code

### 9. Web Backup UI

- Status: usable sidecar, not primary product
- Live surface:
  - `web/src/hooks/useAPI.ts`
  - `web/src/hooks/useAppState.ts`
  - `web/src/pages/Assistant.tsx`
  - `web/src/pages/Workspace.tsx`
  - `web/src/pages/Models.tsx`
- North-star fit:
  - backup web UI is connected to the live backend contract at `127.0.0.1:8081`
  - it remains secondary and should stay secondary
- Finish:
  - browser/type-check pass on a machine with installed frontend dependencies
  - parity decisions for missing model/library/settings depth
- Improve:
  - keep it as fallback or companion UI, not a competing product surface

## Overall North-Star Read

- Personal: mostly yes
- Persistent: backend yes, front-end payoff still needs more polish
- Calm: improved materially, but review-band UI modules still need cleanup
- Useful with files: yes, especially through Library
- Smooth in chat: mostly yes, but continuity polish is still one of the highest-value remaining product tasks

## Highest-Value Finish Work

1. Home continuity polish
   - make return-to-workspace state feel smarter and calmer
2. Workspace switching and re-entry polish
   - reduce friction between remembered purpose and active chat flow
3. Memory payoff
   - show persistent context value more clearly in normal use
4. Tool/plugin clarity
   - tighten what is real now versus planned
5. Real-machine runtime and voice validation
   - confirm local model, STT/TTS, tray, and daemon behavior under real operator conditions

## Quarantine Audit

### Wave 01

- `.quarantine/2026-04-22_quarantine_wave_01/build`: `17` files
- `.quarantine/2026-04-22_quarantine_wave_01/dist`: `16762` files
- `.quarantine/2026-04-22_quarantine_wave_01/splits`: `3409` files

Findings:

- `build/`
  - generated packaging output only
  - not a restore candidate
- `dist/`
  - packaged artifacts and runtime distribution output
  - useful as packaging evidence only
  - not source to restore into the live tree
- `splits/`
  - contains duplicate branch-like trees such as `archive-clutter`, `backend-working`, `Guppy_splits`, `lane_split_v1`, and `qt-creator-ui`
  - extension mix confirms it is a large split/archive bundle, not a focused live source lane
  - Python filename comparison found `0` unique Python filenames relative to the live repo
  - conclusion: no must-restore code was found

Practical note:

- `splits/` does include optional UI experiments and older operator surfaces such as command palettes, startup checklists, timeline/status strips, and extra settings subpanels
- those are not missing core product work; they are mostly duplicate, older, or more dashboard-like than the current north star allows
- recommendation: keep quarantined

### Wave 02

- `.quarantine/2026-04-22_quarantine_wave_02/stitch_azure_reef_assistant (1)`: `10` files

Findings:

- this is the saved Builder/Stitch export bundle
- it contains design comps and HTML exports, not backend or launcher logic
- it is still useful as visual reference
- it is not a restore candidate for the live runtime path

## Quarantine Verdict

- No quarantined tree currently contains must-restore source needed to keep the core product working
- The only quarantined material that is still actively useful is the Builder/Stitch export bundle as design reference
- The `splits/` tree does not currently justify reintroduction into the live repo

## Recommended Next Move

1. Treat this audit as the new baseline for live-core work
2. Keep quarantine intact
3. Focus next on continuity polish:
   - Home
   - Workspaces
   - memory payoff
4. Only reopen quarantined material if a specific visual reference or historical diff is needed
