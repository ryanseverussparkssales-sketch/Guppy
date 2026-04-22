# Tranche 54 Module Breakup And Stitch Execution Cards

Date: April 20, 2026

Status: in-progress

## Program intent

This tranche plans the complete breakup of remaining large modules into bounded seams while preserving launcher behavior, five-hub ownership, and current release guardrails.

This plan is execution-first:
1. Every major UI element has at least one tranche card.
2. Every tool/settings lane has explicit tranche cards.
3. Stitch choices are codified as implementation constraints, not optional style notes.
4. Desktop launcher hardening and account-connection/storage hardening are first-class workstreams.

## Baseline hotspots (observed in current worktree)

1. `ui/launcher/launcher_window.py` -> 1947
2. `src/guppy/api/server_runtime_snapshot.py` -> 972
3. `ui/launcher/views/settings_view.py` -> 643
4. `src/guppy/launcher_application/app_mgmt_presenter.py` -> 619
5. `ui/launcher/views/models_view.py` -> 603
6. `ui/launcher/views/voices_view.py` -> 600
7. `src/guppy/api/services_runtime.py` -> 595
8. `ui/launcher/views/models_sections.py` -> 594
9. `src/guppy/launcher_application/instance_manager_presenter.py` -> 577
10. `src/guppy/api/_server_fragment_bootstrap.py` -> 575

## Stitch implementation rules (locked)

1. Keep warm-sand neutral base + restrained blue/orange accents from launcher tokens.
2. Keep chat-first calmness; no novelty chrome competing with composer or runtime facts.
3. Keep typography hierarchy simple: expressive heading voice, plain readable body, compact mono for evidence labels.
4. Enforce responsive truth: no critical control depends on wide-screen-only layout.
5. Prefer progressive disclosure over always-open dense explanation panels.
6. Keep control copy literal and action-oriented; avoid ambiguous labels.

## Tranche map

1. `TR54-A` Architecture decomposition foundation and seam contracts.
2. `TR54-B` UI element decomposition cards.
3. `TR54-C` Tool and settings decomposition cards.
4. `TR54-D` Desktop launcher hardening cards.
5. `TR54-E` Account connection and secret-storage hardening cards.
6. `TR54-F` Integration gates, validation, and release closeout.

## TR54-A cards (foundation)

### `TR54-A1` Hotspot extraction contract
- Scope: define exact extraction seams for every current file above 550 lines.
- Targets: `launcher_window.py`, `server_runtime_snapshot.py`, `settings_view.py`, `models_view.py`, `models_sections.py`, `voices_view.py`.
- Acceptance:
1. Each target has a documented seam list and owner module destination.
2. No card executes with ambiguous destination ownership.

### `TR54-A2` Line-cap reset plan
- Scope: staged path to move all active UI and launcher orchestrators below 550 lines, then below 450 where practical.
- Acceptance:
1. Temporary waivers are explicit, dated, and linked to an active card.
2. No new large file is introduced as part of a split.

### `TR54-A3` Guardrail-first merge choreography
- Scope: define merge order so every extraction wave remains releasable.
- Acceptance:
1. Every wave has a required test subset.
2. `dev-check --guard-scope delta` is green at each merge checkpoint.

## TR54-B cards (UI element cards)

### `TR54-B1` Launcher shell orchestration split
- UI element: launcher root shell
- Files: `ui/launcher/launcher_window.py`
- Work: split refresh/polling, tab navigation, and command routing into dedicated launcher-application support modules.
- Acceptance:
1. Shell file loses mixed concern logic.
2. Startup, tab switching, and runtime-poll behavior are unchanged.

### `TR54-B2` Topbar chrome card
- UI element: top bar
- Files: `ui/launcher/components/topbar.py`
- Work: isolate compact-mode visibility rules, context summary composition, and quick-action signaling into small support helpers.
- Acceptance:
1. Topbar remains readable at compact widths.
2. Action and context labels remain Stitch-aligned and plain.

### `TR54-B3` Sidebar and status strip card
- UI elements: sidebar + status panel
- Files: `ui/launcher/components/sidebar.py`, `ui/launcher/components/status_panel.py`
- Work: separate presentation tokens from runtime evidence formatting.
- Acceptance:
1. No direct runtime-shaping logic in visual widgets.
2. Spacing and emphasis rhythm remains consistent with Stitch delta.

### `TR54-B4` Home shell decomposition card
- UI element: Home
- Files: `ui/launcher/views/assistant_view.py`, `assistant_shell_sections.py`, `assistant_behavior_support.py`
- Work: complete section-by-section split (composer, starters, first-run, context strip, transcript rail).
- Acceptance:
1. Home behavior remains chat-first.
2. Starter and first-run logic do not regress in compact mode.

### `TR54-B5` Models hub decomposition card
- UI element: Models hub
- Files: `ui/launcher/views/models_hub_view.py`, `models_view.py`, `models_sections.py`, `models_runtime_support.py`
- Work: separate model library UI, runtime source UI, route evidence UI, and operation/health UI into independently testable sections.
- Acceptance:
1. Runtime source switching, install/uninstall, and route evidence still work.
2. Models core files stay under tranche line targets.

### `TR54-B6` Voice surface decomposition card
- UI element: Voice in Models
- Files: `ui/launcher/views/voices_view.py`
- Work: split assignment controls, backend evidence rendering, and diagnostics copy.
- Acceptance:
1. Voice assignment persistence remains stable.
2. TTS/STT evidence text remains accurate.

### `TR54-B7` Tools surface decomposition card
- UI element: Tools
- Files: `ui/launcher/views/tools_view.py`, `tools_view_cards.py`
- Work: split card rendering, policy/status reasoning, and action dispatch text lanes.
- Acceptance:
1. Blocked/remediation messaging remains consistent with settings ownership.
2. Tool cards remain compact and readable at narrow widths.

### `TR54-B8` Library surface decomposition card
- UI element: Library
- Files: `ui/launcher/views/library_view.py`, `src/guppy/launcher_application/library_workflow.py`
- Work: isolate root/path state, editor state, and use-in-chat assembly.
- Acceptance:
1. Root switching and note editing remain stable.
2. Source-origin evidence is preserved.

### `TR54-B9` Settings shell decomposition card
- UI element: Settings hub + settings editor
- Files: `ui/launcher/views/settings_hub_view.py`, `settings_view.py`
- Work: split tabs, section routing, and edit/save behavior into dedicated helpers.
- Acceptance:
1. Section focus methods remain deterministic.
2. Embedded-mode behavior is preserved.

### `TR54-B10` Settings accounts and operations decomposition card
- UI elements: Device & Accounts, Operations
- Files: `ui/launcher/views/settings_device_accounts_panel.py`, `settings_operations_panel.py`
- Work: split connectors/accounts list rendering, verify/reconnect actions, and backend operation cards.
- Acceptance:
1. Account actions remain functional and discoverable.
2. Recovery/diagnostic operations remain deterministic.

### `TR54-B11` Instance manager decomposition card
- UI element: workspace/instance management
- Files: `ui/launcher/views/instance_manager_sections.py`, related presenter seams
- Work: split list/filter shell from action/detail shell.
- Acceptance:
1. Instance state changes and routing remain stable.
2. Section-level smoke tests cover compact mode and action behavior.

### `TR54-B12` Shared design tokens and stylesheet card
- UI element: shared visual language
- Files: `ui/launcher/tokens.py`, `ui/launcher/stylesheet.py`
- Work: codify Stitch choices as explicit token groups with no ad-hoc per-widget color drift.
- Acceptance:
1. All touched UI cards consume tokenized values.
2. No new hardcoded color/style islands are introduced.

## TR54-C cards (tool and setting cards)

### `TR54-C1` Tool action registry hardening card
- Scope: canonical action language
- Files: tool action registry + tool cards + starter sources
- Acceptance:
1. One canonical phrase per tool action across typed, spoken, and card surfaces.
2. No duplicate drift copy remains in view-local constants.

### `TR54-C2` Tool permissions and policy split card
- Scope: explicit allow/block rationale and destination owner
- Files: `src/guppy/launcher_application/tool_readiness.py`, relevant config + views
- Acceptance:
1. Every blocked action maps to one reason and one destination owner.
2. Policy text stays concise and non-contradictory.

### `TR54-C3` Connector workflow settings card
- Scope: Settings-owned remediation path
- Files: `src/guppy/launcher_application/connector_workflow.py`, Tools + Settings surfaces
- Acceptance:
1. Connector remediation never routes outside Settings ownership.
2. Source/surface request channels remain explicit and bounded.

### `TR54-C4` Runtime settings schema card
- Scope: normalized runtime settings contract
- Files: `src/guppy/experience_config/services.py`, related views/presenters
- Acceptance:
1. Runtime backend and endpoint keys are consistent across read/write paths.
2. Missing keys degrade gracefully with explicit defaults.

### `TR54-C5` Tool evidence and trace copy card
- Scope: concise, truthful trace/evidence text
- Files: tool card evidence and status presenters
- Acceptance:
1. Evidence labels never overclaim readiness.
2. Tooltip/detail copy is progressive-disclosure aligned.

## TR54-D cards (desktop launcher hardening)

### `TR54-D1` Startup sequence reliability card
- Scope: startup ordering and retries
- Files: launcher shell + runtime control seams
- Acceptance:
1. Startup transitions are explicit and test-covered.
2. No ambiguous state label during bootstrap.

### `TR54-D2` Duplicate window and process guard card
- Scope: single-instance and re-entry safety
- Acceptance:
1. No normal-user duplicate launcher path remains.
2. Recovery path remains plain-language.

### `TR54-D3` Desktop packaging boot card
- Scope: packaged launcher path verification
- Acceptance:
1. Desktop link and packaged entry target current build output.
2. Packaging readiness never reports GO without valid artifact evidence.

### `TR54-D4` Polling and health signal hardening card
- Scope: status polling stability and route/runtime sync
- Acceptance:
1. Poll failures degrade visibly but safely.
2. Topbar and tray context stay synchronized with current runtime facts.

### `TR54-D5` Launcher diagnostics and support card
- Scope: diagnostics generation + support copy
- Acceptance:
1. Diagnostics actions are easy to discover.
2. Output path and next step are always explicit.

## TR54-E cards (account connection and storage best practices)

### `TR54-E1` Account lifecycle UX card
- Scope: connect, verify, reconnect, disable, remove
- Files: `settings_device_accounts_panel.py`, provider status/presenter seams
- Acceptance:
1. Every provider follows the same lifecycle states.
2. Next-step guidance is plain-language and consistent.

### `TR54-E2` Secret storage enforcement card
- Scope: keyring-first enforcement and fallback truthfulness
- Files: `utils/secret_store.py`, auth/provider status seams
- Acceptance:
1. Plaintext/degraded fallbacks never appear as secure-ready.
2. Storage posture is visible where users make account decisions.

### `TR54-E3` Provider schema and field ownership card
- Scope: typed secret fields, account slots, verification shape
- Acceptance:
1. Provider additions use registry-first schema, not bespoke panel logic.
2. Verify/reconnect copy remains standardized.

### `TR54-E4` Storage boundary and data-minimization card
- Scope: keep secrets out of logs, snapshots, and broad telemetry payloads
- Acceptance:
1. Secrets never leak into readiness snapshots or trace text.
2. Audit checks explicitly scan for redaction compliance.

### `TR54-E5` Account troubleshooting path card
- Scope: practical recovery from broken auth states
- Acceptance:
1. Broken account states provide deterministic remediation steps.
2. Tool surfaces that depend on accounts link back to exact settings destination.

## TR54-F cards (integration and closeout)

### `TR54-F1` Wave-by-wave validation matrix
- Required checks per wave:
1. targeted unit tests for touched seams
2. targeted smoke tests for affected hub surfaces
3. `python tools/dev_workflow.py dev-check --guard-scope delta`

### `TR54-F2` Release lane closeout
- Required closeout:
1. `python tools/dev_workflow.py release-check`
2. updated tranche closeout notes in master planning docs
3. waiver diff reduced or justified with dated follow-on cards

### `TR54-F3` Done definition
- Tranche done when:
1. every TR54-B UI element card has acceptance evidence
2. every TR54-C tool/settings card has acceptance evidence
3. every TR54-D launcher hardening card has acceptance evidence
4. every TR54-E account/storage card has acceptance evidence
5. default and product smoke suites remain green in release lane

## Execution order recommendation

1. Run `TR54-A1` through `TR54-A3` first.
2. Run `TR54-B1`, `TR54-B5`, `TR54-B9`, and `TR54-B10` as first execution wave.
3. Run `TR54-C1` through `TR54-C4` in parallel with wave one after seam contracts are locked.
4. Run `TR54-D1` through `TR54-D4` once shell/runtime splits are merged.
5. Run `TR54-E1` through `TR54-E4` with Settings ownership as the source of truth.
6. Run `TR54-F1` through `TR54-F3` as integrated closeout.

## Lane split recommendation

1. Lane A: launcher shell + startup hardening (`TR54-B1`, `TR54-D1`, `TR54-D4`)
2. Lane B: models/voice decomposition (`TR54-B5`, `TR54-B6`)
3. Lane C: tools/tool-settings decomposition (`TR54-B7`, `TR54-C1`, `TR54-C2`, `TR54-C5`)
4. Lane D: settings/accounts/operations decomposition (`TR54-B9`, `TR54-B10`, `TR54-E1`, `TR54-E5`)
5. Lane E: library/home/topbar/sidebar polish and token enforcement (`TR54-B2`, `TR54-B3`, `TR54-B4`, `TR54-B8`, `TR54-B12`)
6. Lane F: backend and schema support seams (`TR54-A2`, `TR54-C3`, `TR54-C4`, `TR54-E2`, `TR54-E3`, `TR54-E4`)
7. Integration lane: wave validation, waiver reduction, release closeout (`TR54-F1`, `TR54-F2`, `TR54-F3`)

## Success metrics

1. No active launcher/UI hotspot remains above 550 lines at tranche close.
2. Launcher startup and status transitions are deterministic and smoke-covered.
3. Tool action wording is canonical and stable across all user entry points.
4. Account connection and secret-storage posture is plain-language and security-truthful.
5. Stitch-aligned visual rhythm remains intact while module complexity is reduced.
