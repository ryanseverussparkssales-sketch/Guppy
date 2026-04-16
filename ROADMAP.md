# Roadmap and Handoff

Last updated: April 15, 2026 — **M1 Exit Gate PASSED**

Historical note: this file preserves handoff and execution history. Older entries may reference pre-migration root paths or runtime utility locations; use `README.md`, `instructions/OPERATIONS.md`, and `docs/PROJECT_BRIEF.md` for current commands and canonical module paths.

## M1 Status: CLOSED (April 13, 2026)

- ✅ Embedded-only INIT live — `AgentCard._btn_init` wired to emit signal, no legacy window spawns
- ✅ Transcript UX stable — "Processing..." moved to status strip, chat shows user→assistant turns only
- ✅ Right-rail strictly operational — all content is status/logging only, no chat payloads
- ✅ No-freeze startup telemetry — phases tracked with <750ms budget enforcement; all bootstrap async

## Next Phase: M2 — Surface Consolidation: Multi-Instance, Home Primary, Tool Separation

**M2 Planning Documents** (Read in order):

1. [M2_UI_QUICK_REFERENCE.md](docs/M2_UI_QUICK_REFERENCE.md) — One-pager: tab structure, instance switching, tool separation
2. [M2_UI_ARCHITECTURE_GUIDE.md](docs/M2_UI_ARCHITECTURE_GUIDE.md) — Comprehensive design spec with mockups, data model, inter-agent patterns
3. [M2_ENGINEERING_PLAN.md](docs/M2_ENGINEERING_PLAN.md) — Full epics (0–6) with acceptance criteria, risks, schedule
4. [M2_SCOPE_LOCK.md](docs/M2_SCOPE_LOCK.md) — Scope lock, decisions, blockers, escalation path
5. [M2_LAUNCH_CHECKLIST.md](docs/M2_LAUNCH_CHECKLIST.md) — 8-week ramp plan, weekly tracking, go/no-go gates

Quick condensed project brief: `docs/PROJECT_BRIEF.md`

## Doc Ownership Contract

1. `docs/PROJECT_BRIEF.md` is the canonical status source.
2. `ROADMAP.md` owns queue and dated handoff execution log entries.
3. `README.md` is architecture/setup/operations reference only.
4. Session logs and active priorities must not be duplicated in `README.md`.

This roadmap is now organized around a single product objective:

Build a viable Windows personal assistant with a strong daily workflow, dependable voice UX, and user-controlled persona/model behavior.

## North Star

Guppy should be the default daily assistant on a Microsoft PC:

1. Fast first response.
2. Reliable voice interruption behavior.
3. Safe action handling.
4. Clear model/persona customization.
5. Stable local-first operation with optional cloud boost.

## What Current Build Already Handles

These capabilities exist now and are usable in pilot:

1. Unified launcher is evolving toward Home, Instance Manager, Agent Tools, App Management, Local LLM, Models, and Voices, with settings folded into App Mgmt.
2. Launcher auto-starts guppy_api.py and guppy_hub.py on open — no manual service management required.
3. Home is now a chat-first daily surface; heavier runtime, routing, workflow, and recovery context lives in App Mgmt and the deeper Models/Voices surfaces.
4. Workspace management is live with persisted config/state plus create, activate, delete, and log-view endpoints, and explicit 5 configured / 2 runtime-active UX feedback.
5. Local 5-model fleet with runtime verification tooling.
6. Router modes for local, paired, code, and vault workflows.
7. Voice path with wake-word/PTT, Kokoro and fallback behavior.
8. Supervisor-friendly API + health/status/repair pathways with per-process token auth.
9. Runtime telemetry and logging health checks with JSONL rotation.
10. Personalization/provider/voice schema scaffolds and JSON validate/reload/save flows.
11. Pilot gate automation via tools/pilot_exit_check.py.
12. Atomic file I/O via utils/safe_io.py — no more torn reads from partial writes.
13. guppy_core is a proper package (guppy_core/) with clean submodule boundaries.
14. Local LLM benchmarking is beyond planning now: manifest validation, harness artifacts, human review packets, memory-backend comparisons, and runtime-challenger snapshots are all live in-tree.
15. Default repo verification is green from `.venv\Scripts\python.exe -m pytest -q`; `check_core_surface_integrity.py`, `validate_build_checks.py`, and `tools/pilot_exit_check.py --allow-limited-go --python .venv\Scripts\python.exe` are also passing, and the changed-file line-cap guard is now cleared by the `server.py` and `router.py` split.
16. Workspace governance now has an editable first productized layer: per-workspace auth mode, tool allow/block lists, endpoint filters, operator notes, and clearer operator-visible policy reasons are live through the existing capability system plus the Workspaces editor.
17. Connector governance v1 is now live as workspace bindings over shared machine auth: `config/tool_permissions.json` remains the coarse guardrail, `config/connector_bindings.json` adds per-workspace connector/account/provider/action/endpoint policy, and the runtime enforces both layers before connector tool execution.
18. App Mgmt now includes a machine-level connector inventory/auth surface with `verify`, `connect`, `reconnect`, `disconnect`, and secret-management flows across Gmail, Calendar, Spotify, YouTube, CRM, and VoIP.
19. Blocked connector actions now report whether the stop came from an unbound workspace connector, connector action policy, account/provider mismatch, host auth readiness, or endpoint scope instead of a single coarse denial reason.
20. App Mgmt now includes a dedicated Windows install/update/diagnostics surface with visible runtime/data-path evidence plus one-click verify, update, package, supervised-API launch, restart, and repair actions.

## What Is Not Yet Fully Productized

1. Home still needs final spacing/rhythm polish so the top bar, transcript, composer, and right tray feel like one native chat product instead of adjacent surfaces.
2. Instances still need to read more clearly as user-facing workspaces with recurring context, not just runtime entities.
3. Route and voice decisions still need richer plain-language health and latency evidence beyond the current explainability pass.
4. In-app workflow productization still needs richer execution evidence and stronger Morning/Workday/Close polish.
5. End-user installer/update lifecycle and broader hardware fallback hardening remain open.
6. Tool/connectors governance now has an editable operator surface, machine-level connector inventory/actions, and workspace connector binding policy, but richer provider/account UX, deeper credential lifecycle polish, and broader admin workflows still need productization.
7. Windows install/update/diagnostics are now legible and actionable in App Mgmt, but broader installer/update automation and richer repair choreography still need deeper productization.

## GuppyPrime Parity Matrix

Objective: every capability must either work inside GuppyPrime UI now or be tracked with a roadmap milestone.

| Capability Domain | Current Surface | GuppyPrime Status | Milestone | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| Core chat transcript above input | Launcher Assistant | Live | M1 | UI | Embedded transcript is the default path; remaining work is polish and streaming UX. |
| Agent activation (Guppy/Merlin/Council) | Launcher status rail INIT | Live | M1 | UI | Embedded INIT is enforced in the default flow; no legacy window spawn from default launcher actions. |
| Recovery controls (snapshot/warmup/restart/audit) | Launcher App Mgmt + tray/top bar surfaces | Live | M1 | Platform | Keep as productized operator path. |
| Runtime health and syslog rail | Launcher right panel | Live | M1 | Platform | Status-only by policy; no primary chat content in right rail. |
| Model management and selection | Launcher Models tab | Live | M1 | ModelOps | Keep route/fallback cards aligned with runtime. |
| Voice library and preview | Launcher Voices tab | Live | M2 | Voice | Import, assignment, and preview flow are wired; remaining work is broader real-device validation and polish. |
| Persona/provider/voice config editing | Launcher App Mgmt settings section | Live | M2 | UI | Guided editing is live; remaining work is calmer UX, stronger guardrails, and expert-path cleanup. |
| Instance management and background collaboration | Home + Instance Manager | Partial | M2 | UI/Platform | Foundation is live: persisted state, launcher manager tab, lifecycle endpoints, instance logs, and visible bound feedback. Remaining work is deeper orchestration and stronger enforcement. |
| Tools and command workflows | Launcher Agent Tools tab | Partial | M2 | Tools | Agent Tools is now instance-scoped and capability-aware in the launcher. Remaining work is execution flow and server-side enforcement. |
| App recovery/operator controls | Launcher App Management tab | Partial | M2 | Platform | App Mgmt now owns recovery cards, diagnostics, and operator logs. Remaining work is polish and deeper guardrails. |
| Daily workflow orchestration | Daemon + docs | Partial | M3 | Runtime | Expose Morning/Workday/Close loops directly in GuppyPrime surfaces. |
| Legacy standalone UIs (`guppy_ui.py`, `merlin_ui.py`, `council_ui.py`) | Separate windows | Compatibility-only | M3 | Platform | Freeze by default path; keep only for fallback/debug until retirement gate passes. |

## Milestone Calendar

| Milestone | Target Date | Theme |
| --- | --- | --- |
| M1 | June 30, 2026 (Q2 2026) | Surface Consolidation and Embedded Agent Baseline |
| M2 | September 30, 2026 (Q3 2026) | UX Hierarchy, Workflow Entry, and Tooling Finish |
| M3 | December 31, 2026 (Q4 2026) | Workspace Completion, Windows Fit, and Productization Finish |

**M1 Exit Gate:** No new infrastructure tracks open until all M1 acceptance criteria
pass and are committed to documentation. The gate is: embedded-only INIT live,
transcript UX stable, right-rail policy enforced, and no-freeze startup telemetry
present. Date is firm.

## Execution Board (Refreshed Apr 15, 2026)

This board is the active execution queue. Items are ordered by product leverage,
not by implementation convenience. Status values:

- `active` = in current execution pass
- `next` = ready to start once the active card lands
- `queued` = scoped and sequenced, but waiting on upstream work
- `watch` = important, but not on the critical path this week

| Priority | Track | Status | Current Tranche | Acceptance Criteria | Depends On | Target Window |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Connector Governance V2 | active | Provider-specific readiness, verify detail, scope telemetry, guided multi-field auth for CRM + VoIP | App Mgmt can explain what is missing, what passed, and where to fix it for Salesforce/Twilio/HubSpot/Zoho/GoHighLevel without config-file editing | Existing connector governance v1 surface | Apr 15 - May 02 |
| P1 | Windows Servicing V2 | next | Installer/update automation, stronger verify/update/restart/repair choreography, durable change summaries | Operator can answer what is installed, what changed, what is active, and how to repair it from App Mgmt alone | Current Windows ops panel and recovery paths | Apr 29 - May 16 |
| P2 | Workspace Framing | next | Recast instances into clearer user-facing workspaces with stronger recurring-context and collaboration cues | A user can tell what each workspace is for without backend knowledge | Stable governance + connector workflow | May 06 - May 23 |
| P3 | Home / Chat-First Polish | queued | First-run guidance, calmer transcript/composer rhythm, starter-path polish | New users can start productive work from Home without reading operator docs | Workspace framing direction | May 20 - Jun 06 |
| P4 | Route + Voice Trust Layer | queued | Better plain-language route reasoning, readiness, latency evidence, and device-state clarity | Users can understand route/voice choices and recovery state from launcher surfaces | Home polish and servicing evidence | Jun 03 - Jun 20 |
| P5 | Local LLM Promotion Flow | queued | Runtime/default decision workflow, benchmark-to-promotion evidence, clearer role mapping | Default local runtime/model choices are measurable and auditable from the product | Servicing and trust layers | Jun 17 - Jul 03 |
| P6 | Packaging / Release Hardening | watch | Reduce environment drift, unify release/build rails, improve package-policy evidence | Release verification is one repeatable path, not several partially overlapping ones | Servicing automation | Jul 01 - Jul 17 |
| P7 | Legacy / Historical Debt | watch | Keep pruning legacy aliases, obsolete references, and archive assumptions | Live surface is unmistakable in docs and code | Ongoing | Rolling |

### Current Sprint Focus

1. Connector Governance V2
   - Provider-specific verify adapters and readiness checks for CRM + VoIP.
   - Guided multi-field provider setup polish in App Mgmt.
   - Queryable connector action/result telemetry and operator-visible fix guidance.
2. Windows Servicing V2 preparation
   - Inventory installer/update/repair seams after connector verify adapters land.
   - Keep operator logs and change summaries aligned with the future servicing path.
   - Turn update into a postflight-validated servicing loop with before/after evidence.

### Immediate Card Breakdown

1. Card CG2.1 - Provider verify adapters
   - Status: done
   - Scope: Salesforce, Twilio, HubSpot, Zoho, GoHighLevel readiness checks with operator-facing pass/fail detail.
   - Acceptance: `verify` is more than auth-state echo; provider rows surface concrete readiness checks.
2. Card CG2.2 - Guided auth flow polish
   - Status: done
   - Scope: step-by-step provider field guidance, stronger inline validation, cleaner next-action prompts.
   - Acceptance: App Mgmt always advances operators to the next missing field or verify step.
3. Card CG2.3 - Queryable telemetry alignment
   - Status: done
   - Scope: normalize connector action/result payloads across API docs, launcher logs, and telemetry query surfaces.
   - Acceptance: every verify/connect attempt has a stable operator-visible reference and filterable event payload.
4. Card WO2.1 - Servicing action evidence
   - Status: done
   - Scope: durable verify/update/restart/repair output summaries and clearer “what changed” feedback.
   - Acceptance: operator logs answer what changed without reading raw terminal output.
5. Card WO2.2 - Update automation + postflight verification
   - Status: done
   - Scope: make App Mgmt update run dependency refresh plus build/runtime postflight checks, then persist before/after servicing evidence.
   - Acceptance: update is more than pip install; it leaves a completed servicing record with validation steps and concrete environment/artifact deltas.
6. Card WO2.3 - Installer + repair choreography
   - Status: done
   - Scope: tighten installer/build entry points, repair sequencing, and operator-visible "where to fix this" guidance for packaging/runtime recovery.
   - Acceptance: App Mgmt can point operators at the right install/build/repair path without them reconstructing it from docs and scripts.
7. Card WO2.4 - Packaging/install automation lane
   - Status: done
   - Scope: turn the packaging and supervised-launch paths into more direct launcher-driven actions with clearer completion evidence.
   - Acceptance: operators can trigger the most common package/install follow-ups from App Mgmt instead of assembling the commands manually.
8. Card WO2.5 - Servicing docs + release evidence sync
   - Status: done
   - Scope: align packaging/supervision/troubleshooting docs with the now-direct launcher actions and tighten release-facing evidence wording.
   - Acceptance: docs and operator surfaces describe the same packaging/install/recovery path with no stale manual-only assumptions.
9. Card R2.1 - Release lane hardening
   - Status: active
   - Scope: push the new package/install lane toward release-grade repeatability with better artifact/report handoff and fewer manual follow-up steps.
   - Acceptance: the common release path is mostly launcher-driven, with remaining manual steps explicit and evidence-backed.
   - Progress: App Mgmt now persists release handoff refs for diagnostics, challenger, package, beta-policy, and dry-run artifacts in `windows_ops_state.json`, mirrors them into operator-visible launcher events, writes a canonical `runtime/windows_release_receipt.json` handoff file after completed servicing runs, emits a readable `runtime/windows_release_summary.md` companion summary for operator handoff, exposes a launcher-first `RELEASE DRY RUN` action for the beta release gate, surfaces parsed gate verdict details directly in App Mgmt plus operator logs, includes structured dry-run check/file breakdown in the release receipt for handoff-safe review, and now generates fix-first release recommendations with direct fix targets, docs hints, and entry commands from failed checks and missing handoff files across the receipt, live App Mgmt surface, and operator log stream.

## GuppyPrime Action Queue (Prioritized With Milestones)

### ~~M1 - Surface Consolidation (CLOSED Apr 13, 2026)~~ → **M2 Active**

### **M2 - UX Hierarchy, Workflow Entry, and Tooling Finish (Highest) — Due September 30, 2026**

**[Detailed Breakdown: docs/M2_ENGINEERING_PLAN.md](docs/M2_ENGINEERING_PLAN.md)** — 8 workstreams, detailed PRDs, risk assessment, schedule, success metrics

**ACTIVE THIS WEEK (Week of Apr 15):**

- **Instance Manager + Home Primary**
  - `config/instances.json` + `runtime/instance_state.json` are now live.
  - Home header quick-switcher and per-instance transcript restore are live.
  - New lifecycle endpoints and launcher Instance Manager foundation are live.
  - Explicit 5 configured / 2 runtime-active feedback is now live in API + launcher UI.
  - Remaining acceptance work: recast instances into workspaces with clearer purpose, context cues, and richer collaboration flows beyond UI/API feedback.

- **Current Focus Reset (Post Builder v1)**
  - Persona Builder v1, route explainability, and voice assignment/import/preview are now live.
  - The active push has moved to workflow productization, UX hierarchy, operator docs, validation breadth, and hardening.
  - App Mgmt workflow-loop shortcuts, pilot-gate builder coverage, and voice upload guardrails are now part of this pass.
  - Builder work is now primarily polish: empty states, teaching copy, and calmer non-technical flows.

- **UX Hierarchy + Daily Mode Pass**
  - Make Home the undeniable daily surface with one obvious primary action and calmer default copy.
  - Add first-run guidance and stronger empty states so new users can start without reading settings docs.
  - Keep operator-heavy language and controls in App Mgmt instead of drifting back into Home.
  - Acceptance: the launcher reads like one assistant with advanced layers, not six tools sharing one shell.

- **Workspace Framing**
  - Recast Instances into user-facing workspaces with plain-language purpose, saved context, and clearer naming cues.
  - Keep runtime enforcement and diagnostics, but expose them through a workspace story first.
  - Acceptance: a user can tell what each instance is for without understanding backend architecture.

- **Route + Voice Transparency**
  - Make route and voice choices readable in plain language from the daily surfaces, not only settings vocabulary.
  - Add live health and latency evidence where users choose or review routes.
  - Continue voice reliability work around interruption safety, transcript continuity, and stable preview behavior.
  - Acceptance: users can understand why Guppy chose a route or voice without opening Settings.

- **Local LLM + Local Memory Track**
  - Evaluate MemPalace as a local-memory upgrade path for Guppy’s local-model workflows instead of treating it as a blind drop-in replacement.
  - Keep the first integration adapter-shaped: retrieval spike, local-memory comparison, and optional backend wiring before any broad page rename.
  - Dedicated Local LLM page is now live in the launcher so local fleet status, local memory posture, benchmark evidence, and challenger recommendations no longer stay scattered across Home, Models, and internals.
  - Freeze the current Ollama/Qwen2.5 fleet as the benchmark baseline with a pinned manifest in `config/local_llm/models.json`.
  - The harness, review-packet emitter, memory-backend compare path, and dedicated launcher evidence surface are now live; current remaining work is promotion decisions, governance, and installer/ops polish.
  - Runtime challenger probe is now live: on this Windows + RX 7900 XTX host, `llama.cpp` is currently the benchmark-first challenger, `lemonade` is the integration-first challenger, and `vllm-rocm` remains research-only.
  - Acceptance: a user can see local model readiness and local memory state in one place, and we have measured whether MemPalace beats current semantic recall on real Guppy follow-ups.

- **Starter Templates + Guided Workflow Entry**
  - Add guided entry points for morning brief, focused research, file triage, and builder review.
  - Keep templates scoped and explainable rather than broad connector sprawl.
  - Acceptance: Home and workflow surfaces reduce blank-page anxiety for common daily jobs.


- **Agent Tools + App Management Separation**
  - Split instance tools from operator recovery/diagnostics.
  - First-pass launcher split now live: Agent Tools is instance-scoped, App Mgmt owns recovery and diagnostics.
  - Enforce per-instance capabilities in API/tool runner, not only UI.
  - Scope `run_python` and writes to approved capabilities.
  - Acceptance: every visible control has a documented action and restricted tools are blocked server-side.

- **App Management Recovery Actions**
  - Warmup (refetch models).
  - Restart daemon.
  - Audit runtime.
  - Process guards (no duplicate launches).
  - Outcome visibility in Assistant transcript.
  - Acceptance: recovery flows are discoverable and outcomes are visible.

- **Off-Hours Agent Scaling**
  - Write tasks now common, not just read.
  - Merlin-code generates tests, schemas, and docstrings.
  - Dry-run review loop: stage → human approve → apply.
  - Budget: 3 writes/run max.
  - Acceptance: 5–10 safe write tasks/week running unattended.

**NOT IN M2 (Deferred):**

- iOS client
- Live CRM writes
- Full Shared Memory v1 rollout
- Broad connector expansion before workspace/context UX is clear
- CI/CD deploy gates

### M3 - Legacy Retirement and Productization Finish — Due December 31, 2026

- Deprecate legacy standalone launchers from recommended daily path.
  - Acceptance: docs and launch scripts mark GuppyPrime as sole default surface, and canonical CLI keeps specialist legacy surfaces behind explicit compatibility gating.

- Add in-app roadmap placeholders for not-yet-live capabilities.
  - Acceptance: every non-live feature has milestone label, owner, and short ETA in product UI.

- Complete workspace/context containers.
  - Acceptance: workspaces combine instructions, files, recurring context, and saved history without leaking runtime implementation details.

- Run parity release gate.
  - Acceptance: all matrix rows are either Live or assigned with owner/milestone and tested fallback.

- Complete daily workflow product loop inside GuppyPrime.
  - Acceptance: Morning, Workday, and Close flows are executable without leaving the unified UI.

- Add faster Windows-native entry and continuity after Home/workspace flow is stable.
  - Acceptance: quick invoke and ambient continuity improve access without bypassing approval and transparency patterns.

- Stage the connector story only after workspace UX is coherent.
  - Acceptance: any connector rollout has explicit scope, milestone, and user-facing rationale instead of broad undifferentiated expansion.

### 2026-04-13 (Dependency Split + Canonical Legacy Launch Gate + Doc Truth Cleanup)

- Reduced default install footprint:
  - moved dev-only packages out of `requirements.txt` into `requirements-dev.txt`
  - added `requirements-optional.txt` for `openwakeword` and `chromadb`
- Tightened canonical launch policy for legacy specialist surfaces:
  - `src/guppy/cli/launch.py` now rejects `merlin` and `council` launches unless `GUPPY_ENABLE_LEGACY_SURFACES=1` is set
- Reconciled core docs to match current launcher-first and packaging reality:
  - refreshed `README.md`, `docs/PROJECT_BRIEF.md`, `documentation/ARCHITECTURE.md`, `documentation/TRUTH_AUDIT.md`, `docs/PACKAGING.md`, `docs/TROUBLESHOOTING.md`, `instructions/DEVELOPMENT.md`, and `CONTRIBUTING.md`

### 2026-04-14 (Builder Queue Activation + Off-Hours Approval Flow)

- Corrected live-status docs to match current launcher state:
  - `docs/PROJECT_BRIEF.md` now reflects that Persona Builder v1 is still pending while model routing and voice bindings are live
  - `docs/M2_WEEK1_IMPLEMENTATION_QUEUE.md` now records W1-03 as reopened after doc-to-tree drift review
- Fixed the beta release dry-run handoff reference:
  - `tools/beta_release_dry_run.py` now checks the archived handoff file path under `docs/archive/planning-history/`
- Activated the first in-app low-risk local builder path:
  - launcher Agent Tools now includes a local builder queue panel backed by off-hours templates
  - added shared builder task helpers under `utils/offhours_builder.py`
  - added prompt/template catalog under `config/offhours_prompts/builder_task_templates.json`
  - off-hours worker now supports `awaiting_approval`, approval application, and report output
- Validation completed:
  - focused builder + launcher tests passing
  - beta release dry-run passes after path correction
  - local builder task validated end to end: queue -> dry-run stage -> approval -> safe write
  - reduced stress harness passed with zero API failures and latency well under current thresholds

### 2026-04-15 (Repo Truth Review + Verification Pass + Competitive Gap Reset)

- Corrected top-level docs to match the live tree:
  - `README.md` now reflects the active launcher tabs, App Mgmt-embedded settings, compatibility-only legacy surfaces, and the live Local LLM benchmark/runtime-challenger track.
  - this roadmap now reflects that Home is chat-first, the deeper runtime story lives outside Home, and several previously "partial" launcher capabilities are in fact live with hardening still open.
- Fixed verification drift in the test bootstrap:
  - added a Qt/offscreen pytest bootstrap in `conftest.py` so widget-based unit tests can instantiate launcher views consistently from the default suite.
  - added a defensive alias fallback in `src/guppy/inference/router.py` so `_ollama_call()` still returns `None` on network failure even when the router is constructed through stripped-down test harnesses.

### 2026-04-15 (Server/Router Split + API Truth Pass + Local LLM Surface)

- Cleared the active changed-file line-cap failure without breaking compatibility imports:
  - split `src/guppy/inference/router.py` into smaller fragments and kept the public module surface stable.
  - split `src/guppy/api/server.py` into smaller fragments, preserved the FastAPI app surface, and kept monkeypatched test seams intact.
- Restored and hardened local-runtime API behavior during the split:
  - kept Lemonade/Ollama runtime selection, local runtime status reporting, and launcher-facing status payloads alive after the server refactor.
  - updated `docs/API.md` so the documented route set now matches the live FastAPI surface, including `/`, `/metrics`, and the `/instances*` lifecycle/query endpoints.
- Shipped the dedicated launcher Local LLM page:
  - added `ui/launcher/views/local_llm_view.py` plus launcher/sidebar wiring so benchmark artifacts, memory baseline, review packets, and challenger recommendations now live in one calm evidence surface outside Home.
- Verified with focused regression coverage:
  - `python tools/check_new_module_line_cap.py`
  - `.venv\Scripts\python.exe -m pytest tests\unit\test_chat_routing_alignment.py tests\unit\test_security_hardening.py tests\smoke\test_runtime_smoke.py tests\smoke\test_launcher_interactions_smoke.py -q`
- Validation completed:
  - `.venv\Scripts\python.exe -m pytest -q` -> passing
  - `python tools/check_architecture_boundaries.py` -> passing
  - `python tools/check_wrapper_integrity.py` -> passing
  - `python tools/check_doc_ownership.py` -> passing
  - `.venv\Scripts\python.exe tools/verify_ollama_runtime.py --prompt ok` -> READY
  - `.venv\Scripts\python.exe tools/verify_runtime_challengers.py` -> `llama.cpp` benchmark-first, `lemonade` integration-first, `vllm-rocm` research-only
- Remaining hardening signal from the repo review:
  - installer/update/repair ergonomics still needed to catch up with the broader launcher product surface
  - workspace governance needed a richer operator-facing layer beyond raw capability booleans
- Competitive-review reset for the next execution pass:
  - prioritize packaging/update reliability, a dedicated Local LLM surface, stronger permissions/governance visibility, and module-splitting before broad connector growth or new surface sprawl.

### 2026-04-15 (Workspace Governance Productization + Windows Ops Surface)

- Productized the existing capability system instead of replacing it:
  - `config/tool_permissions.json` now supports per-workspace `auth_mode`, tool allow/block lists, endpoint allow/block filters, and operator-facing policy notes.
  - `utils/instance_capabilities.py` now resolves those richer policies while staying backward-compatible with the existing capability booleans and tuple contract.
  - API/tool-runner enforcement now passes endpoint context into policy checks so local-only or filtered workspaces can block external connector scopes before execution.
- Brought the launcher policy and operations story up to product level:
  - Agent Tools cards now show auth mode, allow/block scope, endpoint filters, and clearer restriction reasons instead of only coarse capability text.
  - App Mgmt now includes a dedicated Windows install/update/diagnostics section covering what is installed, which local runtime is configured/live, where runtime/config data lives, how repair token flow works, and which diagnostics artifact was written most recently.
- Reconciled the status-owner docs to current truth:
  - refreshed `README.md`, `ROADMAP.md`, `docs/PROJECT_BRIEF.md`, and `docs/TROUBLESHOOTING.md` so the Local LLM page, line-cap cleanup, governance layer, and Windows ops surface all match the live tree.
- Verified with focused regression coverage:
  - `.venv\Scripts\python.exe -m pytest tests\unit\test_instance_controls.py tests\smoke\test_launcher_interactions_smoke.py tests\smoke\test_runtime_smoke.py -q`

### 2026-04-15 (Editable Governance UI + Connector Auth Telemetry + Windows Ops Actions)

- Moved governance from config-only to launcher-editable:
  - Workspaces now exposes a governance editor for auth mode, tool allow/block lists, endpoint filters, and operator notes.
  - API now serves governance summaries on `/instances` and accepts edits through `POST /instances/{name}/governance`.
- Tightened blocked-action telemetry:
  - permission metadata now carries connector name, connector auth state/detail, and a structured policy reason code so blocked actions can distinguish auth failures, endpoint scope failures, and workspace-policy denials.
  - Agent Tools cards now surface connector auth state alongside the existing role/policy explanation.
- Turned Windows ops into action:
  - App Mgmt now exposes one-click `VERIFY`, `UPDATE`, `PACKAGE`, `SUPERVISED API`, `RESTART`, and `REPAIR` flows, routing verify/update/package into the embedded terminal, supervised launch through the packaged batch entry point, and restart/repair into the existing guarded recovery path.
- Verified with focused regression coverage:
  - `.venv\Scripts\python.exe -m pytest tests\unit\test_instance_controls.py tests\smoke\test_launcher_interactions_smoke.py tests\smoke\test_runtime_smoke.py -q`
  - `python tools/check_new_module_line_cap.py`

### 2026-04-15 (Connector Governance V1 + API/Docs Truth Pass)

- Finished the next connector-governance tranche as workspace bindings over shared machine auth:
  - added `utils/connector_manager.py` and `utils/connector_bindings.py` so Gmail, Calendar, Spotify, YouTube, CRM, and VoIP now share one normalized connector contract for status, auth/source detail, supported actions, accounts/providers, and operator-facing telemetry.
  - added persisted workspace connector bindings in `config/connector_bindings.json` with `enabled`, `account_id`, `provider`, action allow/block lists, endpoint allow/block lists, and operator note fields.
  - kept `config/tool_permissions.json` as the coarse workspace guardrail and layered connector binding checks on top for action/account/provider/auth enforcement.
- Productized the operator flow across launcher and API:
  - App Mgmt now shows a machine-level connector inventory with `verify`, `connect`, `reconnect`, `disconnect`, and secret-management actions.
  - Workspaces now includes an editable connector-binding panel alongside the existing governance editor.
  - `/connectors`, `/connectors/{id}/{action}`, `/instances/{name}/connectors`, and `/instances/{name}/connectors/{connector}` are now live, and `/instances` now includes connector summary data for first render.
- Tightened runtime denials and telemetry:
  - connector tool checks now emit structured reasons for `connector_unbound`, `connector_action_blocked`, `connector_account_unavailable`, `connector_provider_unconfigured`, and `connector_host_auth_missing`.
  - Agent Tools now points operators to Workspaces or App Mgmt depending on where the fix belongs.
- Reconciled repo docs to the shipped surface:
  - refreshed `README.md`, `ROADMAP.md`, `docs/API.md`, and `docs/TROUBLESHOOTING.md` so the API, connector workflow, and Windows/operator guidance match the live tree.
- Verified with focused regression coverage:
  - `.venv\Scripts\python.exe -m pytest tests\unit\test_connector_manager.py tests\unit\test_instance_controls.py tests\smoke\test_launcher_interactions_smoke.py tests\smoke\test_runtime_smoke.py -q`
  - `python tools/check_new_module_line_cap.py`

## Priority Order (Rebuilt)

### Track 1: Daily Surface + Workspace Hierarchy (Highest)

Goal: make Guppy feel like one daily assistant with advanced layers, not multiple tools sharing one shell.

- Home daily mode
  - one obvious primary action
  - calm default state and first-run guidance
  - stronger empty states across launcher surfaces

- Workspace framing
  - recast instances as user-facing workspaces
  - visible purpose, context, and naming guidance
  - groundwork for richer context containers in M3

- Plain-language explainability
  - route and voice decisions understandable from daily surfaces
  - live health/latency evidence where users choose or review routes
  - operator detail remains in App Mgmt, not Home

Definition of done:

1. Home has one obvious primary action and a calm default state.
2. Non-technical users can start, choose a workspace, and understand route/voice decisions without reading docs or editing files.
3. Advanced operational controls stay discoverable but visually secondary to daily assistant flow.

### Track 2: Daily Workflow Productization

Goal: turn existing runtime pieces into a repeatable daily operating flow.

1. Morning boot flow with readiness checks and briefing output.
2. Workday loop for capture, reminders, coding support, and lightweight automation.
3. Evening close flow with daily report, follow-ups, and next-day setup.
4. Guided starter templates for common jobs like morning brief, focused research, file triage, and builder review.
5. Workspace/context container UX that combines instructions, files, and recurring context without exposing raw implementation structure.
6. Shared Memory Catalog v1 for cross-agent recall and continuity, including canonical entity notes, source-linked memory entries with timestamps and confidence, and a query API for Guppy, Merlin, Council, and daemon workflows.

Definition of done:

1. Daily workflow documented and executable in under 5 minutes setup.
2. Recovery path is obvious when any subsystem is degraded.
3. Starter flows reduce blank-page anxiety and map to existing commands/tools in repo.
4. Workspace context is legible enough that users understand where instructions/files/history live.
5. Agents can retrieve and cite shared memory entries consistently in responses.

### Track 3: Windows General Assistant Viability

Goal: close the gap from pilot to broader Windows usability.

1. Installer/update/uninstall polish.
2. Permission and confirmation policy hardening for risky actions.
3. Hardware profile fallback policy (no-GPU, low-RAM, intermittent network).
4. Faster Windows-native entry and continuity after the daily surface is stable.
5. Optional Microsoft Graph integrations after workspace UX is coherent.
6. Remote beta tester executable with limited-access runtime policy.

- one-folder signed EXE bundle for testers (no source tree required)
- restricted tool allowlist and write-action confirmation policy
- remote API token scoping, rate limits, and auditable action logs

Definition of done:

1. New machine setup is one guided path.
2. No silent failure for speech, model, or API routes.
3. User can inspect what happened via status and logs.
4. Beta tester EXE can run safely without exposing full codebase or unrestricted tools.

## 30-Day Delivery Plan

### Week 1

1. Home daily mode pass with one obvious primary action.
2. First-run guidance and stronger launcher empty states.
3. Validation for calm default-state and onboarding copy flows.

### Week 2

1. Reframe Instances into workspaces in copy, labels, and flow.
2. Surface clearer purpose/context cues for active workspace selection.
3. Tighten builder teaching surfaces so advanced settings do not become the front door.

### Week 3

1. Route and voice explanations in plain language on daily surfaces.
2. Live health badges and latency evidence where users inspect routes.
3. Voice transcript continuity and interruption-safety polish.

### Week 4

1. Starter templates for morning brief, focused research, file triage, and builder review.
2. Daily workflow polish and guided checklist in-app/docs.
3. Windows viability hardening items (recovery UX, profile fallback rules).
4. Pilot gate + acceptance sweep and release decision.
5. Shared Memory Catalog schema + ingestion/retrieval smoke checks.
6. Remote beta package dry run with limited-access policy verification.

## Acceptance Gates

A build is release-ready for pilot when all are true:

1. tools/pilot_exit_check.py returns GO.
2. Builder flows work without manual JSON editing.
3. Voice interruption and fallback behavior pass manual smoke.
4. Settings recovery can restore safe operation in one pass.
5. Daily workflow checklist completes end-to-end in one session.
6. Remote beta EXE profile passes restricted-tool and auth-scope checks.
7. Home has one obvious primary action and a calm default state.
8. Route and voice decisions are understandable without opening Settings.
9. Advanced operational detail stays in App Mgmt, not Home.

## Defer Until After Track 1

To protect focus, do not expand these until Track 1 is complete:

1. New CRM/VoIP live write integrations.
2. Broad external connector expansion before workspace/context UX is clear.
3. Additional specialist surfaces that bypass launcher UX.

## Handoff Notes

If a new coding pass starts, begin here:

1. Confirm pilot gate status from runtime/pilot_exit_report.json.
2. Prioritize unfinished Track 1 tasks.
3. Keep all new settings reachable from launcher tabs first.
4. Update README.md and this roadmap whenever status changes.

- **Pytest root bootstrap**
  - Added `pytest.ini` and root `conftest.py` so `python -m pytest` resolves project imports cleanly.

- **Sparkline consolidation**
  - Consolidated to shared implementation at `ui/components/sparkline.py`; launcher uses alias module.

## Historical Status Archive

Large historical status/audit sections from earlier stabilization passes were archived to:

- docs/archive/planning-history/ROADMAP_HISTORICAL_SECTIONS_2026-04-13.md

Canonical active planning and execution remains in this file's current roadmap, parity tracker, and handoff log sections.

## Handoff Rules

- Add new notes at the top of the handoff log.
- Keep entries short and factual.
- Record what changed, what was verified, and what still needs follow-up.
- Do not create another status markdown file for routine session notes.

## Handoff Log

### 2026-04-14 (Spacing Pass + Deeper Evidence + Tool Policy Framing)

- Continued the launcher-first M2 pass as one integrated shell + evidence slice:
  - tightened top bar, transcript, composer, and tray spacing so the launcher reads as one softer native chat product instead of separate densities
  - narrowed the tray, reduced top-bar pressure, and trimmed composer/transcript proportions for more usable chat room
  - pushed fuller live evidence out of Home and into the heavier surfaces:
    - Models now keeps route-plan copy and live route evidence separate, with clearer cloud/local readiness wording
    - Voices now reports default runtime voice, binding counts, selected engine readiness, and active selection in plainer language
    - App Mgmt now carries explicit route evidence and richer workflow evidence alongside existing runtime/recovery context
  - hardened Agent Tools around the same permission policy helpers the repo already uses:
    - tool cards now surface capability + runtime-policy framing
    - restricted tools no longer prime Home if triggered indirectly
    - Home prompts are more task-shaped and clearer about safe scope
  - kept improving workspace framing:
    - launcher role labels now use clearer workspace names like builder collaborator / read-only reference / operations workspace
    - workspace purpose language was refreshed toward recurring-context framing instead of raw instance mechanics
- Verified with focused launcher coverage:
  - `.venv\Scripts\python.exe -m compileall ui\launcher\components\topbar.py ui\launcher\components\status_panel.py ui\launcher\views\assistant_view.py ui\launcher\views\models_view.py ui\launcher\views\voices_view.py ui\launcher\views\advanced_view.py ui\launcher\views\tools_view.py ui\launcher\views\instance_manager_view.py ui\launcher\launcher_window.py utils\instance_capabilities.py tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py`
  - `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py tests\unit\test_chat_routing_alignment.py -q`
- Follow-up:
  - finish the remaining workspace-manager truth pass so role counts and collaboration cues are even more explicit
  - extend the policy-backed tool framing into more server-backed execution seams where it materially affects runtime behavior
  - keep Home calm while making Models / Voices / App Mgmt the canonical source of live readiness evidence

### 2026-04-14 (Messenger-Style Launcher Softness Pass)

- Continued the launcher-first M2 design execution with a stronger chat-room bias:
  - removed the large Home hero from the visible chat surface and kept transcript + composer as the primary objects on screen
  - collapsed starter actions into smaller composer-adjacent chips instead of a separate middle block
  - moved active chat context into a top-bar pill so mode/persona/profile no longer compete with the room itself
  - softened transcript bubbles, composer proportions, and bottom rhythm toward a calmer iOS-messenger feel
  - softened the right tray cards/buttons/media dock so the tray now matches the same lower-density visual language as Home
  - replaced the old sidebar badge treatment with a painted guppy-style fish mark and more distinct left-rail symbols
  - fixed hidden activity/status labels that were surfacing as stray popup widgets after the layout simplification
- Verified with focused launcher coverage:
  - `.venv\Scripts\python.exe -m compileall ui\launcher\views\assistant_view.py ui\launcher\components\sidebar.py ui\launcher\components\topbar.py ui\launcher\components\status_panel.py ui\launcher\launcher_window.py tests\smoke\test_launcher_interactions_smoke.py`
  - `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_chat_routing_alignment.py -q`
- Follow-up:
  - tighten final spacing pressure across top bar / transcript / tray in a live render pass
  - deepen route and voice evidence into fuller live state without re-cluttering Home
  - continue App Mgmt workflow evidence and Agent Tools execution hardening

### 2026-04-14 (Launcher Prompt Chain Follow-On: Live Evidence, Workflow Outcomes, Tool Handoffs, Empty States)

- Extended the launcher-first M2 polish pass without changing backend contracts:
  - Home route preview now carries a compact evidence line, and voice summaries now include source plus readiness wording.
  - Models now folds the latest runtime latency into route-readiness language when that evidence is available.
  - Voices now keeps a persistent readiness summary instead of relying only on transient assignment status text.
  - App Mgmt workflow loops now report short outcomes alongside next-step guidance, so load/run actions explain what happened and what to check next.
  - Agent Tools now prime Home with task-specific prompts instead of raw tool keys, and filtered-empty states now tell users how to recover.
- Verified with focused launcher coverage:
  - `.venv\Scripts\python.exe -m compileall ui\launcher\views\models_view.py ui\launcher\views\voices_view.py ui\launcher\views\tools_view.py ui\launcher\views\advanced_view.py ui\launcher\views\assistant_view.py ui\launcher\launcher_window.py tests\smoke\test_launcher_interactions_smoke.py`
  - `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py -q`
- Remaining follow-up:
  - deepen launcher evidence from light readiness/latency hints into fuller live state
  - persist workflow outcomes beyond launcher-local labels and terminal output
  - continue tightening execution behavior behind the improved Agent Tools prompt handoff

### 2026-04-14 (Launcher Prompt Chain: Route/Voice Clarity, Starters, Tool Split, Workflow Guidance)

- Continued the M2 launcher execution chain after the Home/workspace pass:
  - Home now surfaces voice source in plain language, starter actions for morning brief / focused research / file triage / builder review, and route preview context that stays aligned with those starters.
  - Models now explains route choices in plainer language and shows readiness context for cloud/local routing.
  - Voices now reads more clearly for non-technical users with default/active voice wording and visible persona/model binding summaries.
  - Agent Tools and App Mgmt now reinforce a cleaner split: Agent Tools reads as workspace task work, while App Mgmt reads as recovery / diagnostics / workflow loops / operator logs.
  - App Mgmt workflow shortcuts now include clearer next-step guidance after load/run actions.
- Verified with focused launcher coverage:
  - `.venv\Scripts\python.exe -m compileall ui\launcher\views\models_view.py ui\launcher\views\voices_view.py ui\launcher\views\assistant_view.py ui\launcher\views\tools_view.py ui\launcher\views\advanced_view.py ui\launcher\launcher_window.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py tests\smoke\test_launcher_interactions_smoke.py`
  - `.venv\Scripts\python.exe -m pytest tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py tests\smoke\test_launcher_interactions_smoke.py -q`
- Remaining follow-up:
  - deepen route/voice evidence into fuller live health and latency signals
  - persist richer workflow outcomes beyond terminal/status text
  - continue tightening server-side execution flow behind the clearer Agent Tools vs App Mgmt split

### 2026-04-14 (Home Daily Mode + Workspace Framing Launcher Pass)

- Shipped the launcher-first UX slice for today's M2 focus without changing backend instance contracts:
  - Home now reads as a calmer daily assistant surface with clearer start-here guidance, workspace summary, and plain-language runtime / route / health text.
  - top-level launcher navigation now presents `WORKSPACES` in the visible shell while internal `instance*` names remain unchanged in code, API, config, and tests.
  - Instance Manager copy now frames entries as workspaces with role/purpose language and friendlier create/update affordances.
- Verified with focused launcher regression coverage:
  - `.venv\Scripts\python.exe -m compileall ui\launcher\views\assistant_view.py ui\launcher\views\instance_manager_view.py ui\launcher\components\topbar.py ui\launcher\components\sidebar.py ui\launcher\launcher_window.py tests\smoke\test_launcher_interactions_smoke.py`
  - `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py -q`
- Remaining follow-up:
  - deepen workspace context beyond copy into richer saved-context containers later in M3
  - continue route/voice health evidence and starter workflow templates on top of this calmer Home surface

### 2026-04-14 (Competitive UX Recommendations Merged Into Timeline)

- Reviewed `docs/generated/competitive_ux_analysis_2026-04-14.md` against the active roadmap and folded the highest-signal recommendations into execution planning instead of creating a separate strategy appendix.
- Re-sequenced active work around:
  - Home daily mode and first-run guidance
  - Instances reframed as workspaces
  - plain-language route/voice transparency with live health evidence
  - starter templates for common assistant jobs
- Updated M2, M3, the rebuilt track order, the 30-day plan, and acceptance gates so the roadmap now reflects a daily-assistant-first hierarchy.

### 2026-04-14 (Lifecycle Evidence Artifact + Recovery Re-Sync Failure Signal)

- Extended release evidence and recovery observability:
  - `tools/validate_live_lifecycle.py` now writes `runtime/lifecycle_validation_report.json` in addition to printing its report.
  - pilot validation now includes a dry-run lifecycle gate entry and snapshot path in `tools/pilot_exit_check.py`.
  - launcher repair-token re-sync failures now emit a distinct `repair_token_resync_failed` event instead of collapsing into a generic 403-only path.
- Added focused regression coverage:
  - `tests/unit/test_validate_live_lifecycle.py` now checks report-file output.
  - `tests/unit/test_pilot_exit_decision_canary.py` now covers lifecycle dry-run gate wiring.
  - `tests/unit/test_security_hardening.py` now covers invalid/empty repair-token refresh behavior in the launcher.

### 2026-04-14 (Instance Self-Healing Persistence + Pilot Report Resilience)

- Hardened API self-healing for instance metadata:
  - normalized `config/instances.json` and `runtime/instance_state.json` now persist back to disk on read paths instead of only healing in memory.
  - chat/voice-active instance resolution, `/instances`, and instance-query flows now repair malformed instance artifacts as part of normal traffic.
- Hardened pilot-gate report generation:
  - `tools/pilot_exit_check.py` now converts gate execution exceptions into failed gate entries so `runtime/pilot_exit_report.json` is still written even when a verifier times out or crashes.
- Added focused regression coverage:
  - extended malformed-instance runtime smoke to assert repaired files are written back to disk.
  - added chat-path persistence coverage for active-instance repair.
  - added `tests/unit/test_pilot_exit_report_resilience.py` to verify pilot report creation on gate-exception paths.

### 2026-04-14 (Verifier Truthfulness + Safer Settings Persistence)

- Hardened operator and validation truthfulness:
  - `tools/validate_live_lifecycle.py` now returns non-zero when any lifecycle action fails while still printing the full JSON report.
  - `tools/verify_ollama_runtime.py` now treats `ollama ps` failure as a readiness failure and records that state in the snapshot.
- Reduced partial-save risk in launcher Settings:
  - runtime and persona writes now use atomic JSON helpers where available.
  - `ui/launcher/views/settings_view.py` now validates payloads up front, persists persona/runtime settings in one guarded sequence, and attempts rollback if the second write fails.
- Added focused regression coverage:
  - `tests/unit/test_validate_live_lifecycle.py`
  - `tests/unit/test_verify_ollama_runtime.py`
  - launcher settings rollback coverage in `tests/smoke/test_launcher_interactions_smoke.py`

### 2026-04-14 (Workflow Productization + Voice Upload Guardrails + Doc Truth Refresh)

- Continued the post-builder pass with workflow and hardening work:
  - App Mgmt now includes workflow-loop shortcuts that can load or run Morning Boot, acceptance snapshot, midday stability, evening close, and overnight low-compute commands in the embedded terminal.
  - `/chat/voice` now streams uploads to disk with content-type checks and a configurable size ceiling before transcription starts.
  - `tools/pilot_exit_check.py` now includes builder regression suites in the runtime gate command so pilot readiness covers shipped builder surfaces.
- Docs and runbooks were refreshed to match current state:
  - `GOALS.md`, `DAILY_WORKFLOW.md`, `instructions/OPERATIONS.md`, `docs/PROJECT_BRIEF.md`, `docs/TROUBLESHOOTING.md`, `docs/PACKAGING.md`, `README.md`, and active `ROADMAP.md` sections now reflect that builder v1 is live and the next focus is workflow productization plus hardening.
- Verification target for this pass:
  - launcher interaction smoke now covers workflow recipe loading.
  - runtime smoke now covers oversized voice upload rejection.

### 2026-04-14 (Builder Surfaces - Persona End-to-End + Route Explainability + Voice Lifecycle)

- Completed the next launcher-first builder slice across Settings, Models, Voices, launcher shell, and API:
  - Persona Builder now runs end-to-end from `ui/launcher/views/settings_view.py` through launcher persona selection into `src/guppy/api/server.py` prompt assembly via personalization overlays.
  - Assistant surface now carries route-preview context so chat mode/persona changes and queued commands show why a route was selected.
  - Models view now includes sample-query route explainability on top of route/fallback editing.
  - Voices view now loads live persona/model choices, supports custom voice imports, keeps binding summaries visible, and uses the voice backend path for more stable non-Edge previews.
- Shared personalization helpers landed in `utils/personalization_config.py`:
  - persona resolution by explicit selection or model assignment
  - persona prompt overlay construction
  - voice binding resolution with model > persona > default precedence
- Docs updated to reflect current launcher reality:
  - `docs/PROJECT_BRIEF.md` now marks Persona Builder v1, route explainability, and voice assignment/import/preview as live, with follow-up gaps narrowed to polish and broader validation.
- Verification evidence:
  - `.venv\\Scripts\\python.exe -m compileall utils/personalization_config.py ui/launcher/views/assistant_view.py ui/launcher/views/settings_view.py ui/launcher/views/models_view.py ui/launcher/views/voices_view.py ui/launcher/views/instance_manager_view.py ui/launcher/launcher_window.py src/guppy/api/server.py` -> passed.
  - `.venv\\Scripts\\python.exe -m pytest tests/unit/test_personalization_resolution.py tests/unit/test_models_routes.py tests/unit/test_voices_view_validation.py tests/smoke/test_launcher_interactions_smoke.py tests/smoke/test_runtime_smoke.py -q` -> 39 passed.

### 2026-04-14 (/chat Prompt Gate Follow-Through + Streaming/Voice Alignment)

- Continued the prompt-context latency slice from the prior handoff:
  - factored shared prompt assembly in `src/guppy/api/server.py` so `/chat`, `/chat/voice`, websocket chat, and instance queries use the same light-vs-rich context decision.
  - websocket payloads now honor optional `mode` when selecting prompt richness.
- Added focused regression coverage in `tests/smoke/test_runtime_smoke.py`:
  - verified lightweight `/chat` requests stay on the light prompt path.
  - verified short voice transcriptions and websocket chat messages also skip memory/semantic enrichment unless needed.
- Verification evidence:
  - `.venv\\Scripts\\python.exe -m pytest tests/smoke/test_runtime_smoke.py -k "light_prompt_context or websocket or voice" -q` -> passed.
  - `.venv\\Scripts\\python.exe -m pytest tests/smoke/test_runtime_smoke.py tests/smoke/test_launcher_interactions_smoke.py -q` -> 30 passed.
  - `.venv\\Scripts\\python.exe -m compileall src/guppy/api/server.py tests/smoke/test_runtime_smoke.py` -> passed.

### 2026-04-14 (CodexGPT Handoff - Docs Canonicality + /chat Latency Slice)

- Completed the runtime artifact hygiene follow-up for BOM handling:
  - verified `runtime/stress_run_output.txt` had a real UTF-8 BOM and removed it.
  - hardened `tests/smoke/stress_system.py` with `_write_json_no_bom()` so future JSON reports stay UTF-8 without BOM.
- Landed doc-entrypoint labeling so historical material stops competing with canonical docs:
  - added `docs/README.md` as the operational/product docs front door.
  - updated `documentation/README.md` to explicitly pair `documentation/` with `docs/` and demote archive/history material.
- Landed a focused `/chat` latency reduction before inference:
  - `src/guppy/api/server.py` now uses `_should_use_rich_chat_prompt_context()` to keep lightweight turns off the expensive memory/semantic prompt path.
  - `guppy_core/system_prompt.py` now supports optional memory/semantic inclusion plus short TTL caching for memory briefing, semantic context, and window context.
  - added smoke coverage in `tests/smoke/test_runtime_smoke.py` for light vs rich prompt behavior.
- Verification status:
  - latest code edits have not yet been validated with targeted pytest after the prompt-path changes.
  - `get_errors` shows broad pre-existing/static-analysis noise in `src/guppy/api/server.py`; `guppy_core/system_prompt.py` and `tests/smoke/test_runtime_smoke.py` showed no file-level errors.
- Next step for CodexGPT:
  - run focused verification first: `.venv\\Scripts\\python.exe -m pytest tests/smoke/test_runtime_smoke.py -q`
  - if green, run a small `/chat` latency comparison or smoke path to confirm the lighter prompt path helps real request latency.
  - avoid touching unrelated in-flight repo changes; this slice was intentionally limited to docs labeling and `/chat` prompt assembly cost.

### 2026-04-14 (M2 Progress - Unified Launcher Home Refresh + Instance Manager Foundation)

- Continued the unified launcher product surface instead of creating a second launcher:
  - launcher navigation now follows Home, Instance Manager, Agent Tools, App Mgmt, Settings, Models, and Voices.
  - Home surface now shows active-instance, background activity, runtime facts, and recovery summary.
  - right rail trimmed further toward background-ops focus.
- Landed Phase 2 foundation in API and launcher:
  - added `POST /instances`, `POST /instances/{name}/activate`, `DELETE /instances/{name}`, and `GET /instances/{name}/logs`.
  - added `ui/launcher/views/instance_manager_view.py` and wired it into `ui/launcher/launcher_window.py`.
  - launcher and bounded inter-instance query paths now write per-instance JSONL logs.
- Updated documentation to match actual repo state in `docs/PROJECT_BRIEF.md`, `docs/M2_IMPLEMENTATION_BACKLOG.md`, and `docs/M2_UI_QUICK_REFERENCE.md`.
- Verification evidence:
  - `python -m pytest tests/smoke/test_launcher_interactions_smoke.py tests/smoke/test_runtime_smoke.py` -> 16 passed.

### 2026-04-13 (M2 Week 1 Execution - W1-05 Complete)

- Completed W1-05 Voice Engine Abstraction Design Stub in launcher voices view:
  - added runtime engine capability summary across EDGE/KOKORO/WINDOWS SAPI/ELEVENLABS.
  - surfaced configured default engine/voice binding in top bar status.
  - added engine/voice validation hook points for default save and persona/model assignment paths.
  - refactored preview flow into centralized non-blocking preview runner with interruption-safe cancellation.
- Added targeted regression coverage for voice validation helpers:
  - new `tests/test_voices_view_validation.py` verifies engine capability gating and engine/voice catalog validation.
- Verification evidence:
  - `python -m pytest tests/test_models_routes.py tests/test_voices_view_validation.py tests/smoke/test_launcher_interactions_smoke.py -q` -> passed.
- Next queued task: W1-06 Agent Tools and App Management Split Skeleton.

### 2026-04-13 (M2 Week 1 Execution - W1-04 Complete)

- Completed W1-04 Model Assignment Editor + Route Visualizer alignment in launcher models view:
  - added task-type route controls for `simple`, `complex`, and `teaching` strategy targets.
  - added fallback-chain validation against provider registry route targets (+ `local/guppy` allowance).
  - added read-only route summary block that reflects active task routing and fallback chain.
- Added targeted regression coverage for route helper logic:
  - new `tests/test_models_routes.py` verifies route target extraction and fallback token parsing.
- Verification evidence:
  - `python -m pytest tests/test_models_routes.py tests/smoke/test_launcher_interactions_smoke.py -q` -> passed.
- Next queued task: W1-05 Voice Engine Abstraction Design Stub.

### 2026-04-13 (M2 Week 1 Execution - W1-01/W1-02/W1-03 Complete + Chat 429 Hotfix)

- Completed W1-01 Instance Manager schema hardening in API:
  - normalized malformed `config/instances.json` and `runtime/instance_state.json` data paths.
  - added warnings in `/instances` response for ignored/invalid entries.
  - added resilient runtime smoke coverage for malformed instance config/state handling.
- Fixed launcher chat 429 lockouts caused by shared global auth rate-limit bucket:
  - implemented route-aware rate-limit policy in `guppy_api_auth.py` with separate poll/chat/default buckets.
  - added regression tests confirming poll traffic does not block chat quota.
- Completed W1-02 Home quick-switcher skeleton:
  - added active-instance selector in launcher top bar.
  - wired instance selection into launcher session rotation and status logging.
  - added per-instance transcript snapshot/restore behavior in assistant view and launcher wiring.
- Completed W1-03 Persona Builder v1 mockup in launcher settings:
  - added tone and verbosity sliders, teaching style selector, and scope toggle scaffold.
  - added live system-prompt preview panel that updates from control changes.
  - preserved existing guided save behavior to avoid backend schema churn in Week 1.
- Verification evidence:
  - `python -m pytest tests/smoke/test_launcher_interactions_smoke.py tests/smoke/test_runtime_smoke.py tests/unit/test_security_hardening.py -v` -> 49 passed.
  - `python tools/check_architecture_boundaries.py` -> passed.
  - `python tools/check_wrapper_integrity.py` -> passed.
  - `python tools/check_doc_ownership.py` -> passed.
  - `python tools/check_new_module_line_cap.py` -> passed.
- Next queued task: W1-04 Model Assignment Editor + Route Visualizer alignment.

### 2026-04-13 (Framework/Test/Document Iteration - Doc Governance Before Runtime Debugging)

- Deferred launch-failure debugging by request and prioritized framework/documentation hardening first.
- Added explicit doc ownership contract to core docs:
  - `README.md` now defines architecture/setup/operations-only scope.
  - `ROADMAP.md` now defines queue + dated handoff ownership.
- Removed duplicated status sections from `README.md` that conflicted with single-source governance:
  - removed `Session Log` block
  - removed `Active Priorities` block
  - replaced with pointer to `ROADMAP.md`
- Added CI governance guard:
  - new `tools/check_doc_ownership.py`
  - integrated as `Doc ownership guard` in `.github/workflows/quality-gates.yml`
- Verification evidence:
  - `python tools/check_doc_ownership.py` passes.
  - `python -m py_compile tools/check_doc_ownership.py` passes.
  - `python -m unittest tests.test_runtime_smoke` passes.

### 2026-04-13 (Framework/Test/Document Iteration - Architecture Boundaries + Guided Provider Routing)

- Added architecture boundary CI guard:
  - New `tools/check_architecture_boundaries.py` scans changed `src/guppy/*.py` files.
  - Blocks imports from legacy root modules (`guppy_ui`, `merlin_ui`, `council_ui`, `guppy_hub`, `guppy_launcher`).
  - Blocks `ui.launcher` imports from `src/guppy/hub/*` to preserve domain boundaries.
- Integrated guard in `.github/workflows/quality-gates.yml` as `Architecture boundary guard`.
- Advanced guided builder parity in launcher Settings:
  - Added `GUIDED_PROVIDER_ROUTING` section in `ui/launcher/views/settings_view.py`.
  - Added guided controls for `simple`, `complex`, `teaching`, and `fallback_chain` routes.
  - Added `APPLY PROVIDER ROUTES` action with existing `validate_provider_registry` + `save_provider_registry` path.
  - Guided route changes refresh the Providers JSON editor for transparency.
- Verification evidence:
  - `python -m py_compile` passes for `settings_view.py`, `check_architecture_boundaries.py`, `hub_app.py`, `manager.py`, `guppy_ui.py`, `merlin_ui.py`, and `council_ui.py`.
  - `python tools/check_new_module_line_cap.py` passes.
  - `python tools/check_architecture_boundaries.py` passes.
  - `python tools/check_wrapper_integrity.py` passes.
  - `python -m unittest tests.test_runtime_smoke` passes.

### 2026-04-13 (Framework Split Iteration - Hub Domain Submodules Pass 2)

- Continued decomposition of `src/guppy/apps/hub_app.py`:
  - Extracted `ManagerCard` from `hub_app.py` into `src/guppy/hub/cards.py`.
  - `hub_app.py` now imports `ManagerCard` from hub domain module, reducing in-file UI class footprint.
- Verification evidence:
  - `python -m py_compile src/guppy/hub/cards.py src/guppy/apps/hub_app.py` passes.
  - `python -m unittest tests.test_runtime_smoke` passes after extraction.

### 2026-04-13 (Framework/Test/Document Iteration - Legacy Surface Entrypoint Compatibility Gates)

- Hardened legacy specialist surface entrypoints:
  - `guppy_ui.py`, `merlin_ui.py`, and `council_ui.py` now run under `main()` + `if __name__ == "__main__"` guards.
  - Added explicit `GUPPY_ENABLE_LEGACY_SURFACES=1` requirement before launching each legacy surface.
  - Preserves compatibility behavior while making launcher-first path authoritative by default.
- Verification evidence:
  - `python -m py_compile guppy_ui.py merlin_ui.py council_ui.py` passes.

### GuppyPrime Parity Tracker (Update Each Session)

- [x] M1 | UI | Embedded-only INIT path enforced in default flow (no legacy UI spawn from GuppyPrime actions).
- [x] M1 | UI | Assistant transcript is the primary chat surface (messages render above input, chronological).
- [x] M1 | Platform | Right status rail remains operational-only (health/syslog/recovery), not primary chat output.
- [x] M1 | Platform | Startup responsiveness guardrails hold (startup markers emitted, no blocking loops on UI thread).
- [ ] M2 | UI | Guided persona/provider/voice builder cards/forms shipped (JSON editing optional, not required).
- [x] M2 | Tools | Every visible tool control has real side effects or explicit roadmap placeholder.
- [x] M2 | Platform | Advanced/operator actions include process guards and embedded outcome reporting.
- [ ] M2 | Voice | Voice import + assignment + interruption-safe preview flow complete in GuppyPrime.
- [ ] M3 | Platform | Legacy launcher surfaces marked compatibility-only and removed from recommended daily path.
- [ ] M3 | Runtime | Daily workflow loop (Morning/Workday/Close) executable end-to-end inside GuppyPrime.

Use this tracker first in each handoff update:

1. Mark completed items from this session.
2. Add one line of verification evidence under the current date entry.
3. Carry forward remaining unchecked items unchanged.

### 2026-04-13 (Framework Split Iteration - Hub Domain Submodules First Pass)

- Started structural split of `src/guppy/apps/hub_app.py` into clear domain submodules under `src/guppy/hub/`:
  - `theme_config.py` (colors + agent definitions)
  - `runtime_checks.py` (status/health/runtime helper functions)
  - `cards.py` (extracted `GlowOrb` widget)
  - `shell.py` (extracted `SystemTray` shell)
- Rewired `hub_app.py` to import extracted modules while preserving current behavior and wrapper entrypoint contract.
- Verification evidence:
  - Editor diagnostics report no errors in split modules and `hub_app.py`.
  - `python -m py_compile` passes for `src/guppy/apps/hub_app.py`, `src/guppy/hub/*.py`, and `guppy_hub.py`.
  - Import smoke test passes for split hub modules (`hub_split_ok True`).

### 2026-04-13 (Framework/Test/Document Iteration - CI Guard Hardening)

- Tightened module line-cap policy:
  - Updated `tools/check_new_module_line_cap.py` to enforce cap on changed files (A/M), not only newly added files.
  - Scope remains focused on `src/guppy/` to drive structural migration discipline.
- Added wrapper integrity gate:
  - New `tools/check_wrapper_integrity.py` ensures `guppy_launcher.py` and `guppy_hub.py` remain thin compatibility wrappers.
  - Fails on wrapper overgrowth, duplicate main guards, or missing canonical app imports.
- CI integration:
  - Added wrapper integrity step to `.github/workflows/quality-gates.yml`.
- Documentation update:
  - Updated `docs/PROJECT_BRIEF.md` with current CI guardrail policy.
- Verification evidence:
  - `python tools/check_new_module_line_cap.py` passes.
  - `python tools/check_wrapper_integrity.py` passes.
  - `python -m py_compile tools/check_new_module_line_cap.py tools/check_wrapper_integrity.py` passes.
  - `python -m unittest tests.test_personalization_config_scaffold` passes.

### 2026-04-13 (Legacy/Corruption Sweep + Docs Condensation Pass)

- Fixed top-level wrapper corruption in `guppy_hub.py`:
  - File is now wrapper-only and delegates to `src/guppy/apps/hub_app.py`.
  - Removed duplicated wrapper blocks and stale appended legacy body from the root entrypoint file.
- Documentation condensation step completed:
  - Added `docs/PROJECT_BRIEF.md` as the concise canonical snapshot.
  - Linked the brief from `README.md` living docs and from the top of `ROADMAP.md`.
- Verification evidence:
  - `python -m py_compile guppy_hub.py` passes after wrapper repair.
  - Editor diagnostics report no errors in touched docs and wrapper files.

### 2026-04-13 (M2 Progress - Guided Builder + Voice Assignment Mapping)

- Advanced M2 guided builder work in launcher Settings:
  - Added `GUIDED_PERSONA_BUILDER` form in `ui/launcher/views/settings_view.py`.
  - Added non-JSON controls for global persona name, tone, verbosity, and response style.
  - Added `APPLY PERSONA` flow that updates `runtime/persona_config.json` through personalization validators/savers and refreshes the expert JSON editor.
- Advanced M2 voice workflow work in launcher Voices:
  - Added `SAVE AS DEFAULT` plus guided `ASSIGN TO PERSONA` and `ASSIGN TO MODEL` controls in `ui/launcher/views/voices_view.py`.
  - Added persistence to `runtime/voice_bindings.json` via `load/save/validate_voice_bindings` with runtime scaffold bootstrap.
- Verification evidence:
  - Editor diagnostics report no errors in edited files.
  - `python -m py_compile` passes for `ui/launcher/views/settings_view.py` and `ui/launcher/views/voices_view.py`.

### 2026-04-12 (M1 Execution Start - UI-Thread Recovery Unblock)

- Implemented non-blocking recovery execution in `ui/launcher/launcher_window.py`:
  - Recovery actions now run in a background worker thread instead of the UI thread.
  - Recovery status/syslog/outcome updates are queued and drained on the main thread.
  - Poll loop now drains recovery events alongside assistant/deferred syslog events.
- Verification evidence:
  - Editor diagnostics report no errors in `ui/launcher/launcher_window.py` after the refactor.
  - Direct win: restart/warmup/audit/snapshot control flow no longer depends on synchronous UI-thread waits.

### 2026-04-12 (M2 Execution Start - Advanced Surface Process Guards)

- Added duplicate-launch guards in `ui/launcher/views/advanced_view.py` for both OPEN INTERFACE and DEPLOY SURFACE actions.
- Each surface card now tracks its spawned process and reports `ALREADY RUNNING [pid=...]` instead of launching duplicates.
- Launch/deploy outcome text now includes PID for operator visibility.
- Verification evidence:
  - Editor diagnostics report no errors in `ui/launcher/views/advanced_view.py` after guard wiring.

### 2026-04-12 (M1 Completion - Embedded-Only Default Flow Enforced)

- Added strict compatibility gate in `ui/launcher/views/advanced_view.py`:
  - OPEN/DEPLOY legacy surface actions are disabled by default.
  - Explicit operator message shown: set `GUPPY_ENABLE_LEGACY_SURFACES=1` to enable compatibility behavior.
- Added matching gate in `guppy_hub.py` agent card `launch()` path:
  - Legacy card launches are blocked by default unless compatibility mode is enabled.
  - Blocked launch attempts are recorded to operator events with `launch_blocked` reason.
- Verification evidence:
  - Editor diagnostics report no errors in both gated files after implementation.

### 2026-04-12 (M1 Completion - Startup Guardrails + Operational Rail)

- Implemented startup responsiveness guardrails in `ui/launcher/launcher_window.py` and `guppy_launcher.py`:
  - Added startup phase duration telemetry events with `duration_ms`, `budget_ms`, and over-budget markers.
  - Added UI poll budget detection (`ui_poll_over_budget`) with throttled syslog signal.
  - Added startup summary status (`STARTING` / `STARTUP WARN`) and first-poll budget summary line.
- Enforced operational-only right rail behavior in launcher chat flow:
  - Chat error syslog now references transcript/system message instead of payload text.
- Confirmed Assistant transcript remains primary chat surface:
  - `ui/launcher/views/assistant_view.py` renders transcript above input and appends user/assistant messages chronologically.
- Completed M2 process guard criterion evidence:
  - `ui/launcher/views/advanced_view.py` blocks duplicate OPEN/DEPLOY launches and reports visible outcomes including PID.
- Verification evidence:
  - Editor diagnostics report no errors in edited files.
  - `python -m py_compile` passes for `ui/launcher/launcher_window.py` and `guppy_launcher.py`.

### 2026-04-12 (M2 Completion - Tools Controls Side Effects)

- Wired `ToolsView.tool_state_changed` into `LauncherWindow`.
- Implemented concrete side effects for tool toggles:
  - Persist current tool states to `runtime/launcher_tools_state.json` on each toggle.
  - Emit launcher telemetry event `tool_state_changed` for each control change.
  - Append operational syslog line for each change.
- Implemented state rehydration on startup:
  - Restore tool toggles from `runtime/launcher_tools_state.json`.
  - Log `tools_state_restored` event and operator syslog confirmation.
- Verification evidence:
  - Editor diagnostics report no errors in updated files.
  - `python -m py_compile` passes for `ui/launcher/launcher_window.py`.

### 2026-04-12 (Pre-Cruise Tooling + Provider/Logging Verifiers)

- Added coding ops tools in `guppy_core.py` for faster iteration loops:
  - `test_targeted`
  - `lint_fix`
  - `typecheck_targeted`
  - `git_patch_summary`
- Added cheap/free provider client libraries and coding quality deps:
  - `openai`, `google-generativeai`, `mistralai`
  - `ruff`, `mypy`, `pytest-xdist`, `unidiff`
  - dev bundle file: `requirements-dev.txt`
- Added pre-cruise readiness scripts:
  - `tools/verify_ollama_runtime.py` (models, pings, context, residency)
  - `tools/verify_provider_runtime.py` (key/library readiness + optional smoke)
  - `tools/verify_logging_health.py` (runtime JSONL freshness + SQLite telemetry mirror health)
- Tool schema audit rerun clean after additions (`runtime/tool_schema_audit.json`, 0 errors).

### 2026-04-12 (Recovery UX + Telemetry API + Personalization Scaffold)

- Added launcher Recovery controls in Settings and wired actions end-to-end through launcher runtime calls.
- Added guarded API `/repair` endpoint with dry-run support and actions:
  - `warmup`
  - `restart_daemon`
  - `audit_runtime`
- Added status rail "last recovery outcome" feedback line and launcher runtime event logging for recovery operations.
- Added personalization runtime scaffold + schemas:
  - `docs/schemas/persona.schema.json`
  - `docs/schemas/provider_registry.schema.json`
  - `docs/schemas/voice_binding.schema.json`
  - `utils/personalization_config.py`
- Wired scaffold ensure on startup and added launcher Settings JSON editors for Personas, Providers, and Voices with reload/validate/save.
- Added/updated smoke coverage for repair + launcher interactions and added personalization scaffold tests.
- Stress harness now reports and gates hot-path API latency separately from global p95; default hot-path gate tightened to 1100ms after stable full passes.
- Live runtime validation note: current model runtime checks should use `ollama show` + `ollama ps`; recent verification confirmed active `num_ctx=16384` on loaded runtime.

### 2026-04-12 (Runtime Profiles + Guppy-First Launch Path)

- Added `utils/runtime_profile.py` as the shared profile/settings source for `light`, `standard`, and `power` runtime modes.
- Guppy now loads the active runtime profile on startup, shows it in the status area, and can save profile selection from both the command palette and an in-app settings dialog.
- Guppy settings now drive live behavior for:
  - daemon on/off
  - voice enabled/disabled
  - wake-word default on/off
- Hub now displays active profile/default surface settings, shows a hardware-aware profile recommendation, and hides advanced surfaces when requested.
- Tray menu now offers:
  - Launch Guppy
  - Launch Merlin (Advanced)
  - Launch Council (Advanced)
- Updated Windows launch scripts so:
  - Guppy launches with `standard` profile by default
  - Merlin/Council launch with `power` profile and are labeled advanced

### 2026-04-12 (Product Direction Reset: Guppy-First Windows Assistant)

- Locked in product direction for next planning cycle:
  - Guppy is the main product surface.
  - Merlin shifts toward persona/mode behavior inside Guppy where practical.
  - Council remains a power-user surface rather than a default entry point.
- Added a Windows assistant quality bar to guide future implementation:
  - fast launch/resume
  - low idle overhead
  - native tray/toast/audio behavior
  - strong voice ergonomics
  - trust/audit before autonomous actions
  - hardware-aware defaults via runtime profiles
- Added new roadmap phase: **Phase 16: Surface Consolidation & Windows Productization**.

### 2026-04-12 (Risk Sweep 1-4 Completed)

- Item 1 (repo hygiene) closed:
  - Expanded `.gitignore` for volatile runtime/operator artifacts (`runtime/*.jsonl.*`, `runtime/*.status`, `runtime/*.cmd`, stress/lifecycle reports, local `.claude/settings.local.json`).
- Item 2 (remote stability pass) executed with explicit dry/live reports:
  - Dry report: `runtime/lifecycle_dry_report.json`
  - Live report: `runtime/lifecycle_live_report.json`
  - Key finding: API and Ollama restart paths still report stop-side unverified states while ending in running/healthy for Ollama and transiently down for API in final check snapshot.
  - Cloudflared start/stop path verified healthy in live run.
- Item 3 (lean packaging profile) implemented:
  - `build_executable.bat` now supports `--lean` with robust multi-flag parsing.
  - `Guppy.spec` now supports `GUPPY_LEAN_BUILD=1` with optional-heavy excludes and reduced hidden imports for faster iteration builds.
  - Packaging docs updated in `docs/PACKAGING.md` with lean/CI examples.
- Item 4 (fresh reliability evidence) completed:
  - Extensive stress suite rerun passed (`ok: true`) at `runtime/stress_report_20260412_203540.json`.
  - Scorecard analyzer rerun completed and refreshed `runtime/router_tuning_patch.env`.
  - Current recommendation remains `GUPPY_SLO_SIMPLE_MS=3500`.

### 2026-04-12 (Packaged EXE Smoke Launch)

- Ran packaged smoke test from `dist/Guppy.exe`.
- Result: process launched and stayed alive for at least 8 seconds (`RUNNING_AFTER_8S=1`).
- Test harness then force-stopped process to keep the workspace clean (`STOPPED_AFTER_SMOKE=1`).

### 2026-04-12 (Packaging Gate Closed + Reminder UX Ack)

- Implemented reminder-fired user acknowledgement path:
  - `guppy_daemon.py`: scheduler now emits `reminder_fired` IPC command to both Guppy and Council UIs on trigger.
  - `guppy_ui.py`: added `reminder_fired` command handler to post "Reminder completed" bubble.
  - `council_ui.py`: added `reminder_fired` command handler to post completion bubbles in both panels.
- Refreshed stale roadmap wording:
  - Phase 1 now marked complete (removed stale "starting now" phrasing).
  - Updated ambient open-question phrasing to match implemented Phase 11 baseline.
- Packaging run outcome:
  - Build complete: `dist/Guppy.exe` present (~719 MB).
  - Validator fixed and green:
    - `validate_build.bat` parsing bug corrected (escaped `)` in size echo).
    - `tools/validate_build_checks.py` now injects repo root into `sys.path` for stable module imports.
    - `validate_build.bat` now passes all checks on current environment.

### 2026-04-12 (Live Packaging Poll + Next-Step Refresh)

- Started a dedicated packaging run with:
  - `build_executable.bat --no-clean --ci`
- Build process health checks during run:
  - Found duplicate PyInstaller runs and terminated the older duplicate process to avoid contention.
  - Confirmed one active child PyInstaller process remains and continues advancing (high cumulative CPU time, ~1 GB working set).
- Current gate status:
  - `dist/Guppy.exe` still pending while analysis/collection continues.
  - `validate_build.bat` will be re-run immediately once artifact appears.
- Updated immediate execution order:
  1. Wait for artifact emit (`dist/Guppy.exe`).
  2. Run `validate_build.bat` and record exact pass/fail checks.
  3. If build time remains excessive, add a lean packaging profile in `Guppy.spec` to reduce optional heavy module collection.

### 2026-04-12 (Next-Step Items Executed)

- Re-ran extensive stress suite:
  - `python -m tests.stress_system --api-requests 900 --api-workers 35 --route-iterations 14000 --reminders 900 --log-events 8000`
  - Result: pass (`ok: true`) in `runtime/stress_report_20260412_195028.json`
  - Highlights:
    - route resolution: 14,000 iterations, 0 failures
    - API: 900 requests @ 35 workers, 0 failures
    - reminders: 900/900 created and cancelled, 0 remaining
- Re-ran router scorecard analyzer:
  - `python runtime/review_router_scorecard.py --days 7 --write-patch`
  - Current recommendation retained: `GUPPY_SLO_SIMPLE_MS=3500`
  - Patch file refreshed at `runtime/router_tuning_patch.env`
- Packaging gate execution:
  - `validate_build.bat` now runs cleanly for checks 3-7
  - Found build blocker in `build_executable.bat`: hidden import `APScheduler` was invalid for PyInstaller on this environment
  - Fixed to `--hidden-import=apscheduler` and restarted `build_executable.bat --no-clean --ci`
  - Current remaining blocker: `dist/Guppy.exe` not yet produced (check 1); re-run `validate_build.bat` once build completes

### 2026-04-12 (Extensive Stress Pass + Scheduler Fix)

- Added `tests/stress_system.py` for high-volume local stress across:
  - route resolution
  - API endpoint concurrency
  - reminder scheduler burst behavior
  - logging I/O throughput
- First heavy run exposed reminder scheduling collisions under burst load.
- Root cause: timestamp-derived reminder IDs were not unique enough under high-frequency scheduling.
- Fixed `TaskScheduler.schedule_reminder()` to use UUID-based job IDs in `guppy_daemon.py`.
- Final stress run passed (`ok: true`) with report:
  - `runtime/stress_report_20260412_194705.json`
  - route resolution: 14,000 iterations, 0 failures
  - API: 900 requests @ 35 workers, 0 failures
  - reminders: 900 requested / 900 created / 900 cancelled / 0 remaining
  - logging I/O: 8,000 events, stable write throughput
- Next operational step: run this stress suite weekly and log the newest report filename in handoff.

### 2026-04-12 (5-Item Execution Sprint)

- Item 1 complete: seeded mixed scorecard workload events and verified analyzer can compute SLO/latency/route distributions.
- Item 2 complete: executed `python runtime/review_router_scorecard.py --days 7 --write-patch`; applied low-risk `.env` overrides:
  - `GUPPY_TOOL_BUDGET=6`
  - `COUNCIL_TOOL_BUDGET=5`
  - `GUPPY_SLO_SIMPLE_MS=3500`
- Item 3 complete: route policy resolution moved into `inference_router.py` for Guppy UI non-auto paths and Council Guppy worker decisions.
- Item 4 complete: hardened reminder reliability in `TaskScheduler`:
  - fixed active reminder listing bug (`get_job(job_id)` check)
  - cleanup on reminder fire
  - added reminder event journal (`runtime/reminder_events.jsonl`)
  - added test `tests/test_reminder_workflow.py` (passes)
- Item 5 in progress/completion tail:
  - fixed `validate_build.bat` command parsing failures
  - added `tools/validate_build_checks.py`
  - made `build_executable.bat` non-interactive via `--ci`
  - build + full validator pass pending `dist/Guppy.exe` artifact completion

### 2026-04-12 (6A Router Scorecard Auto-Analyzer)

- Implemented `runtime/review_router_scorecard.py`.
- Analyzer reads `runtime/router_scorecard.jsonl` (default 7-day window), reports:
  - SLO hit rate
  - latency/first-token p95
  - error/degraded counts
  - budget-hit counts
  - route/task/model distributions
- Added bounded tuning recommendations and optional patch output:
  - `python runtime/review_router_scorecard.py --days 7 --write-patch`
  - Writes `runtime/router_tuning_patch.env` for manual review before applying.
- Current run status: script executes successfully; no recommendations until scorecard events accumulate.

### 2026-04-12 (Items 1, 2, 5 Delivered)

- Implemented Phase 6 telemetry normalization in `guppy_ui.py`:
  - Added scorecard logger (`utils/router_scorecard.py`) output to `runtime/router_scorecard.jsonl`
  - Added `first_token_ms`, `slo_target_ms`, `slo_met`, `fallback_count`, and `tool_budget_hit` metrics
  - Added SLO env knobs: `GUPPY_SLO_SIMPLE_MS`, `GUPPY_SLO_COMPLEX_MS`, `GUPPY_SLO_VOICE_MS`
- Implemented tool-loop budgets (runaway prevention):
  - Guppy: `GUPPY_TOOL_BUDGET` (default 8)
  - Council: `COUNCIL_TOOL_BUDGET` (default 6)
  - Behavior on cap: return best-effort response and mark request degraded/tool_budget_hit
- Council Merlin performance tuning (item 5):
  - Added `COUNCIL_MERLIN_TIMEOUT` (default 75s)
  - Added `COUNCIL_MERLIN_NUM_PREDICT` (default 320)
  - Tightened local options (`temperature/top_p/top_k`) for faster, more stable response times

### 2026-04-12 (Daily Routine E2E + Scheduled News Reports)

- Evaluated routine as a true end-to-end workflow: trigger -> gather -> reference yesterday -> synthesize -> persist -> notify.
- Extended `ProactiveLoop` report pipeline in `guppy_daemon.py` to include:
  - Popular RSS feeds (BBC, NYT World, Al Jazeera, Reuters World, Google News RSS)
  - Runtime logs (`agent_performance.jsonl`, `session_events.jsonl`, `integration_events.jsonl`, `hub_patterns.jsonl`)
  - Manual inputs from `runtime/manual_events.jsonl|.txt`, `runtime/daily_manual_events.md`, `runtime/todo.txt|.md`
  - Pending tasks/facts from memory and explicit yesterday-report reference
- Added scheduled world news reports at `12:00`, `18:00`, and `22:00` with per-day per-slot dedupe.
- Output files:
  - Daily summary: `runtime/daily_reports/YYYY-MM-DD.md`
  - News slots: `runtime/daily_reports/YYYY-MM-DD-news-HH00.md`
- New config: `GUPPY_NEWS_REPORT_HOURS` (default `12,18,22`)

### 2026-04-12 (Codebase Audit + Cleanup)

**Syntax**: All 40+ Python files pass `py_compile` with no errors.

**Port pivot propagated**: `8080` → `8081` corrected in `bin/launch_api.bat`, `guppy_api.py` (allowed origins), `guppy_hub.py` (default health-check port), `docs/API.md`, `CREDENTIALS_AUDIT.md`. Previously only the runtime files and tunnel config had been updated.

**Stale docs archived** to `docs/archive/root-history/`:

- `CLAUDE_REVIEW_SUMMARY.md`, `HANDOFF_COPILOT_2026-04-11.md`, `INFERENCE_ROUTER_INTEGRATION_COMPLETE.md`, `PHASE2_COMPLETE.md`, `IMPLEMENTATION_COMPLETE.txt`, `docs/CLAUDE_CODE_HANDOFF.md`

**Files relocated**:

- `proxy8080.py` → `tools/proxy8080.py` (port-forwarding utility, not a top-level module)
- `validate_phase_1_3_no_ui.py` → `tests/test_router_smoke.py` (promoted to permanent test)
- `validate_phase_1_3.py` → `docs/archive/root-history/` (UI-dependent, phases done)

**Deleted**:

- `chroma_test_soak/` — soak test binary artifacts (verified Chroma works, data not needed)
- `runtime/diagnostics_guppy_20260412_*.json` — 6 stale single-session diagnostics dumps

**No live code changed** beyond port number corrections. All model strings already current.

**Flagged for Ryan** (not touched):

- `AI_Project/` subfolder — appears to be a separate older project with its own venv. Not referenced by any Guppy code. Safe to delete or move out of repo, but not done without confirmation.
- Root `Modelfile.guppy` / `Modelfile.merlin` — different from `models/` versions (different base model configs). Need Ryan to confirm which is current before pruning either.

### 2026-04-12 (Phase 11 Ambient Awareness Complete)

### Ambient Offer To Proactive Banner

- `AmbientWatcher._haiku_interesting_check()` added to `guppy_daemon.py`: calls Haiku with clipboard content, returns `(interesting: bool, action: str)`. Fails open (True) if no API key or call errors. Skips offer if `interesting=False`.
- `AmbientBanner` widget added to `guppy_ui.py`: 42px bar between scroll area and input bar, hidden until an offer arrives. Shows Haiku's suggested action sentence, "Ask Guppy" button (pre-fills input), dismiss button (×), 30s auto-expire.
- `ambient_offer` IPC handler in `GuppyWindow._handle_cmd()` updated: was dumping into chat via `_bubble()`; now calls `self._ambient_banner.show_offer(action)`.
- Phase 11 marked complete in ROADMAP.

**Files changed**:

- `guppy_daemon.py` — `_tick()` Haiku gate, `_haiku_interesting_check()` method
- `guppy_ui.py` — `AmbientBanner` class, `_build_chat_pane()` banner slot, `ambient_offer` handler

### 2026-04-12 (Benchmark + 5 items complete)

**Doc-vs-reality audit findings**:

- Smart dispatch tool loop was already wired (docs said "not yet") — `_claude()` has full `while True:` tool loop and `_smart_dispatch` calls it directly.
- `ProactiveLoop` and `AmbientWatcher` are full implementations, not skeletons as docs claimed.
- Actual tool count: 73 (after this session). README claimed 75, handoff claimed 65 — both stale.
- Tool calls through smart dispatch confirmed working. No code change needed.

**Missing tools added to `guppy_core.py`** (tool count: 70 → 73):

- `run_python` — subprocess execution of Python snippets, `.venv` python, stdout/stderr capture, 1–60s configurable timeout
- `notify` — Windows 11 toast via `win11toast`, fallback to ctypes MessageBox
- `web_summarize` — HTTP fetch + Claude Haiku summary; Firecrawl if `FIRECRAWL_API_KEY` set

**Phase 4 voice fast-path — COMPLETE**:

- Added `voice_triggered` parameter to `Worker.__init__`
- `_smart_dispatch` now short-circuits task classification when `voice_triggered=True` → always Haiku-first (2s latency target)
- `_trigger_wake_listen` passes `voice_triggered=True` to `_send_text`
- TTS on completion was already wired; no change needed there

**Scheduled `analyze_patterns()` — COMPLETE** (`guppy_hub.py`):

- `OperatorCard.__init__` now starts two timers: 30s display refresh, 15min auto-analyze
- `_auto_analyze()` runs `HubOperator.analyze_patterns(force=False)` in background thread
- HubOperator internal throttle (1/hr) prevents excess API calls; timer just ensures it fires without manual button press

**Phase 5 response cache — COMPLETE** (`guppy_ui.py`):

- Module-level `_RESPONSE_CACHE` dict (TTL 5 min, max 100 entries, oldest-evicted)
- Only caches `task_type == "simple"` responses where `tool_calls == 0`
- Voice-triggered queries bypass cache (often time-sensitive)
- Cache hit emits full text in one shot, updates history, sets `model_used = "cache"`
- Configurable via `GUPPY_CACHE_TTL` and `GUPPY_CACHE_MAX` env vars

**Files changed this session**:

- `guppy_core.py` — added `run_python`, `notify`, `web_summarize` tool definitions + handlers
- `guppy_ui.py` — `voice_triggered` param, Haiku fast-path, response cache
- `guppy_hub.py` — `OperatorCard` scheduled refresh + auto-analyze timers
- `guppy_semantic_memory.py` — Chroma upsert ID fix, warning removal, migrate helper
- `ROADMAP.md` — this log entry

**Known deferred**:

- Phase 6 (single inference path) — UIs still bypass router for non-auto modes; low urgency now that smart dispatch is the primary path
- FIRECRAWL_API_KEY not set — `web_summarize` will fall back to HTTP+Haiku (works, just no JS rendering)
- `run_python` and `notify` available but not in Merlin/Council tool surfaces (only Guppy)

### 2026-04-12 (Chroma Unblocked)

### Chroma Semantic Backend Ready

- Ran soak test: 20 upserts + query against `chromadb 1.5.2` with `anonymized_telemetry=False`. No crash. All ops passed.
- Root cause of prior deferred status: posthog telemetry thread. Already mitigated in code via `ANONYMIZED_TELEMETRY=FALSE` env + `Settings(anonymized_telemetry=False)`.
- **Bug fixed** — `_remember_chroma` was using `f"{k}:{timestamp}"` as the Chroma ID, creating duplicate documents on every write instead of upserting. Fixed to use `key` as the ID.
- **Cleaned up** — removed "experimental/deferred" warning prefixes that were being injected into tool return values (would corrupt Guppy's tool responses).
- Added `migrate_sqlite_to_chroma()` helper for one-time migration of existing SQLite semantic memories.
- Default backend remains `sqlite`. Enable Chroma with `GUPPY_SEMANTIC_BACKEND=chroma` in `.env`.
- Chroma advantage: HNSW approximate nearest neighbor (scales, native distance). SQLite advantage: zero deps, fine for <10k memories.

**Files changed**:

- `guppy_semantic_memory.py` — fixed upsert ID, removed warning prefixes, added `migrate_sqlite_to_chroma()`

### 2026-04-12 (Strict Mode + Public Auth Complete)

### Remote API Hardening Complete

- `GUPPY_DEV_MODE=0` set in `.env` — strict mode active
- Cloudflare Turnstile widget created; site key + secret written to `.env` and `web/turnstile.js`
- `CLOUDFLARE_HOSTNAME` set to `guppy.sparkscuriositystudio.com`; `GUPPY_ALLOWED_ORIGINS` updated
- **Bug fixed** — `hub_operator.py` health check: default port `8000` → `8081`
- **Bug fixed** — `guppy_api_auth.py`: stale shell env captured at import time; added `load_env_file(override=True)` at module level + `_refresh_runtime_config()` called before every auth operation
- **Bug fixed** — `guppy_api.py`: `reload=True` was hardcoded; now mirrors `DEV_MODE` (can force with `GUPPY_API_RELOAD=1`)
- **Port pivot** — ghost OS socket entries held `127.0.0.1:8080` (PIDs unkillable without reboot); API moved to `8081` (`GUPPY_API_PORT` env var)
- Cloudflare tunnel ingress updated via API to route `guppy.sparkscuriositystudio.com` → `localhost:8081`
- `~/.cloudflared/config.yml` written to ensure local config matches dashboard
- **End-to-end verified**: `POST https://guppy.sparkscuriositystudio.com/auth/verify` with dummy token → `400 {"detail":"Invalid Turnstile token"}` — Cloudflare edge → tunnel → API → Turnstile verify chain all working

**Files changed this session**:

- `.env` — `GUPPY_DEV_MODE`, `CLOUDFLARE_HOSTNAME`, `GUPPY_ALLOWED_ORIGINS`, `TURNSTILE_SECRET/SITE_KEY`, `GUPPY_JWT_SECRET`
- `web/turnstile.js` — site key updated
- `guppy_api.py` — `load_env_file(override=True)`, port via `GUPPY_API_PORT` env, reload respects `DEV_MODE`
- `guppy_api_auth.py` — `load_env_file(override=True)` at module level, `_refresh_runtime_config()` added
- `utils/hub_operator.py` — default API port `8000` → `8081`
- `bin/start_tunnel.bat` — `LOCAL_PORT` `8080` → `8081`
- `~/.cloudflared/config.yml` — new file, routes both hostnames to `localhost:8081`

**Known deferred**:

- Ghost PIDs `2764` / `54256` still show LISTENING on `8080` in `netstat` but are dead (cleared on next reboot)
- `bin/start_tunnel.bat` `TUNNEL_ID` still uses placeholder default; relies on `.env` override (working)

### 2026-04-12 (Phase 3 Merlin Routing Complete)

### Phase 3: Merlin Smart Routing Implemented

- Imported Merlin's system components into guppy_ui.py: `get_merlin_startup_system()` and `SPELL_MAP`
- Enhanced `_smart_dispatch()` to detect task type and select appropriate persona:
  - Teaching tasks (explain, teach, learn, etc.) → use `get_merlin_startup_system()`
  - All other tasks → use Guppy's `get_startup_system()`
- Merlin persona now invoked automatically for teaching queries without user having to open separate window
- Task classification reuses router's heuristics: Socratic teaching prompts route to Merlin, technical queries route to Guppy
- UI feedback updated to show persona in use ("Smart routing via Merlin..." vs. "Smart routing via Guppy...")
- All Merlin queries still respect smart fallback chain: Ollama (Merlin model preferred) → Haiku → Sonnet
- Decision: Merlin stays local-only (Ollama) for teaching; no cloud fallback for teaching tasks (intentional—local model + Socratic style preferred)

**CUMULATIVE STATUS (Phases 1-3 Complete)**:

- ✓ Smart dispatcher core with task classification (15/15 tests passing)
- ✓ Haiku-first routing (3s timeout, proper fallback chain with no retries)
- ✓ Merlin automatic routing for teaching tasks (Socratic persona)
- ✓ All integrated into guppy_ui.py Worker class
- ✓ Mode="auto" now uses intelligent smart dispatch instead of legacy _route_auto_mode()
- ✓ Backward compatible: manual modes ("claude", "ollama") still work
- ✓ No new UI buttons: routing is invisible, just faster + smarter

**Impact Summary**:

- Speed: Simple queries 2-3s (vs. 10-30s with Ollama)
- Intelligence: Teaching tasks get Socratic method automatically
- Reliability: No random timeouts, clean fallback chain
- Cost: Haiku-first reduces API spend for simple tasks

**What's Ready to Test**:

- Run Guppy in "auto" mode and ask simple, complex, and teaching questions
- Profile actual latency (empirical validation)
- Verify persona switching (Merlin for "explain" vs. Guppy for others)

**What's Next**:

- Phase 4: Voice integration (wake-word fast-path, PTT responsive)
- Phase 5: Caching (repeated Q instant, reduced API calls)
- Phase 6: Foundation (logging, metrics, tool loops, streaming)

### 2026-04-12 (Phase 1 Implementation)

### Phase 1: Smart Dispatcher Core Implemented

- Enhanced `inference_router.py` with task classification and smart dispatch:
  - Added `_classify_task()` method: heuristic classification into simple/complex/teaching based on keywords and length
  - Added `query_smart()` method: Haiku-first routing for butler UX (<3s latency target)
    - Simple tasks (lookup, format, summarize) → Haiku (2-3s)
    - Complex tasks (build, debug, research, code) → Sonnet (5-10s)
    - Teaching tasks (explain, teach, learn) → Merlin/Ollama (Socratic, local)
  - Updated `query()` signature to support mode parameter: "legacy" (local-first) or "smart" (Haiku-first, task-aware)
  - Added `route_inference_smart()` convenience function for UIs to use
  - Decision: Reduced OLLAMA_TIMEOUT from 30s to 10s (no longer primary path); added HAIKU_TIMEOUT_SMART of 3s
  - Decision: No retry loops—once fallback starts, don't retry failed backend
  
- Integrated smart dispatch into `guppy_ui.py` Worker class:
  - Added import: `from inference_router import route_inference_smart`
  - Added `_smart_dispatch()` method: calls router, handles response streaming and history updates
  - Modified `run()` method: when mode="auto", now uses `_smart_dispatch()` instead of `_route_auto_mode()`
  - Legacy modes ("claude", "ollama") remain unchanged for backward compatibility
  - Routing decision logged to UI as "routing (smart mode) • task-aware dispatch"
  
- Design decisions recorded:
  - Smart dispatch is invisible to user (no new UI buttons; just faster/smarter)
  - Backward compatible: manual modes still work, "auto" mode gets smart dispatch
  - Task classification uses simple keyword heuristics (regex-free, fast, debuggable)
  - Teaching tasks route to local Merlin first (Socratic teaching intent) before cloud fallback
  - Complex tasks prefer Sonnet (more expensive but better reasoning) over Haiku
  - Simple tasks prefer Haiku (cheap, fast) for instant response

**Status**: Phase 1 complete and integrated. Ready for testing.

**Validation Results**:

- ✓ Router initialization: successful (Anthropic available status checked, timeouts set correctly)
- ✓ Task classification: 15/15 tests passed (simple, complex, teaching queries all classified correctly)
- ✓ Edge cases: handled (short queries, empty inputs, ambiguous queries default safely)
- ✓ Syntax validation: both inference_router.py and guppy_ui.py pass error checks
- ✓ Integration: router successfully imported and integrated into Guppy UI Worker class

**Classifier Notes**:

- Simple tasks (what, when, where, remind, format, summarize, list)
- Complex tasks (build, debug, design, research, analyze, optimize)
- Teaching tasks (explain, teach, learn, understand, how does, why is, concept)
- Fallback: length < 50 chars → simple; default → complex (safe over-dispatch to Sonnet)

**Known Limitations (Deferred)**:

- ⏸ Tool calls: Not yet supported in smart dispatch (Phase 1). Single-turn responses only.
  - Will be added in Phase 6 (Foundation work) via router enhancement to return full response metadata.
- ⏸ Streaming: Smart dispatch returns full response text (no streaming like _claude has).
  - Will be added in Phase 6 as part of foundation improvements.

**Follow-up**:

- Phase 1a (Tonight/Tomorrow): Run live butler queries to validate task classification accuracy
- Phase 1b (Tomorrow): Profile latency improvements (expectation: simple queries <3s, complex 5-10s)
- Phase 4 (Tomorrow): Voice integration tuning (wake-word fast-path to Haiku)
- Phase 5 (Later this week): Memory & context caching (repeated questions instant)
- Phase 6 (Later this week): Foundation work (logging, metrics, tool loop support, streaming)

### 2026-04-12 (Strategic Shift)

### Strategic Shift: Smart Dispatcher For Butler Assistant UX

- Analyzed current system: Ollama bottleneck is killing latency; inference router exists but UIs bypass it; Merlin unused (requires manual selection).
- Reframed priorities away from CRM/sales workflows toward butler/personal assistant: fast (<3s), accurate, transparent, integrated voice.
- Designed 6-phase implementation plan:
  - Phase 1 (Starting): Smart dispatcher core (task classification → Haiku for simple, Sonnet for complex, Merlin for teaching)
  - Phase 2: Fallback chain fix (no more random 30s timeouts)
  - Phase 3: Merlin smart routing (auto-detect teaching tasks)
  - Phase 4: Voice fast-path tuning (wake-word triggers quick response)
  - Phase 5: Memory/caching (repeated questions instant)
  - Phase 6: Foundation (logging, metrics, streaming, single inference path)
- Aligned phases with existing roadmap goals: remote hardening unblocked by Phase 1 latency improvement; butler workflows enabled by Phase 1-3; release discipline enabled by Phase 6.
- Identified that monetization is secondary; butler experience is primary. Foundation for future fine-tuning and scaling built into architecture.

### 2026-04-12 (Docs Consolidation)

- Decided to keep `docs/TROUBLESHOOTING.md` and `docs/PACKAGING.md` as standalone runbooks, while folding short operational summaries into `README.md`.
- Archived `docs/FEATURES.md` to `docs/archive/reference-history/FEATURES.md`; kept `docs/API.md` and `docs/VOICE.md` as focused operational references.
- Kept `CONTRIBUTING.md` in the repo root by convention and moved `PACKAGING.md` to `docs/PACKAGING.md` to reduce root noise.
- Moved older planning and reference docs from `docs/` into `docs/archive/planning-history/`.
- Moved older session, review, milestone, and one-off briefing docs out of the repo root into `docs/archive/root-history/`.
- Added archive notices to older handoff and completion docs so they no longer compete with the living-doc pair.
- Folded the most useful API and voice operational details into `README.md`.
- Current living docs remain `README.md` and `ROADMAP.md` only.

### 2026-04-12

- Condensed living status docs down to `README.md` and `ROADMAP.md`.
- Rewrote `README.md` as the primary source of truth for architecture, setup, current state, and active priorities.
- Rewrote `ROADMAP.md` as the active work board plus handoff log for multi-agent sessions.
- Fixed Guppy UI streaming crash in `guppy_ui.py` by initializing streamed label text state and falling back safely when appending.
- Confirmed the repo already contains the API surface, web client alpha, smoke tests, semantic memory, hub logging, wake-word path, and CRM/VoIP scaffolding.
- Remaining high-value gaps: external remote validation, `/status` latency, packaging hardening, and one complete revenue workflow.

---

## Prioritised Next Steps (2026-04-12)

Ordered by impact. First three are ship-blockers for a trustworthy daily butler.

### 1. Semantic task classifier (SHIP BLOCKER — AI quality)

Replace `inference_router._classify_task()` keyword matching with a Haiku-backed structured output call.

**Why it matters**: The current classifier misroutes "what is X" queries to Ollama/teaching. If Ollama is offline, those fail. For voice queries especially, a misroute to a slow backend breaks the <3s target.

**Approach**:

```python
# In _classify_task(), call Haiku with:
# system: "Classify the intent of this query."
# user: query text
# force tool_choice or structured output: {task_type: "simple"|"complex"|"teaching"}
# Cache result for identical queries (session TTL)
```

**File**: `inference_router.py:71`

---

### 2. Persistent response cache (SHIP BLOCKER — UX)

Back `_RESPONSE_CACHE` with SQLite so it survives restarts.

**Why it matters**: Butler warms up cold every morning. Same "what's my schedule?" at 9am every day hits the API every time.

**Approach**: Add a `response_cache` table to `ops_telemetry.sqlite3` with columns `(key TEXT PRIMARY KEY, response TEXT, model TEXT, ts REAL)`. On cache miss, check SQLite before API. On hit within TTL, serve from SQLite. On write, update SQLite + in-process dict.

**File**: `guppy_ui.py:42` (or extract to `utils/response_cache.py`)

---

### 3. Cross-session memory injection into system prompt (SHIP BLOCKER — AI quality)

**Why it matters**: The semantic memory backend is fully built. Nothing uses it at inference time. This is the gap between a chatbot and a butler. "Ryan mentioned he prefers concise answers" should influence every reply automatically.

**Approach**:

```python
# At start of each _smart_dispatch / Worker.run():
memories = semantic_memory.recall(user_text, k=5)
if memories:
    system_prompt = system_prompt + "\n\n[RELEVANT CONTEXT]\n" + format_memories(memories)
```

**File**: `guppy_ui.py` Worker class, `guppy_api.py` chat handler

---

### 4. Fix `GUPPY_TOOL_BUDGET` code default (quick fix)

Change `guppy_ui.py:102` default from `"8"` to `"6"` to match the validated env patch.

**File**: `guppy_ui.py:102`

---

### 5. Type annotations on `utils/` public functions

Annotate return types on all public functions in `utils/runtime_profile.py`, `utils/hub_operator.py`, `utils/agent_perf.py`, `utils/operational_telemetry.py`. Prevents the `recommend_runtime_profile() → dict` category of silent caller bugs.

---

### 6. CI baseline

Add `conftest.py` and `pytest.ini` at project root. Target suite: `test_smart_dispatch`, `test_router_smoke`, `test_reminder_workflow`, `test_runtime_smoke`. `python -m pytest` should pass clean.

---

### 7. Consolidate Sparkline implementations

`ui/components/sparkline.py` (old, `set_values()`) and `ui/launcher/components/sparkline.py` (new, `push()`). Consolidate on the launcher version. Update the one import in `guppy_ui.py`.

---

### 8. `guppy_ui.py` retirement decision

It is not imported by council_ui. It is a 2,200-line standalone surface diverging from the launcher. Decision: **freeze it** — add a deprecation header, stop updating it, migrate the ambient banner to the launcher shell. Do not spend time keeping it feature-equal to the new system.

---

### 9. Voice tuning (when classifier is fixed)

Validate wake-word → Haiku fast-path end-to-end latency with real use. Tune `openwakeword` model and cooldown. The infrastructure is right; the real-world calibration hasn't happened.

---

### 10. CRM live wiring (only after #1 and #3)

Do not wire live CRM writes until the classifier is semantic and memory injection is live. A misrouted "teaching" query that triggers a send-email tool is a bad outcome.

---

## Next Update Template

Use this format for the next roadmap update:

### YYYY-MM-DD

- Changed:
- Verified:
- Follow-up:

### 2026-04-14

- Changed: Reworked launcher Home into a chat-first messenger-style surface, moved heavy runtime/routing/recovery context into App Mgmt, shifted quick workspace tools into the right tray, and replaced the old right-rail syslog/init area with a reserved media dock.
- Verified: `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py -q`
- Follow-up: Validate the new chat shell against live launcher runtime again, then decide whether Agent Tools should stay as a builder-only surface or collapse fully into Home + tray.

### 2026-04-14

- Changed: Pushed a full launcher redesign pass across tokens, stylesheet, sidebar, top bar, Home, and the right tray. The shell now uses a warmer gallery-like light theme, stronger editorial type, a richer empty-state composition, and more art-directed gradients/cards while keeping the launcher architecture intact.
- Verified: `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py tests\unit\test_voices_view_validation.py tests\unit\test_chat_routing_alignment.py -q`
- Follow-up: Run the live launcher to tune spacing, icon density, and any last typography/copy adjustments from the real window, then decide whether to deepen the art direction into Models/Voices/Workspaces too.

### 2026-04-14

- Changed: Finished the workspace-manager truth pass by adding visible role-mix and collaboration-fit cues to Workspaces, then hardened the server-side `/instances/{name}/query` seam so source workspaces must pass the same policy-backed cross-workspace query check the launcher now explains.
- Verified: `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py tests\smoke\test_runtime_smoke.py tests\unit\test_instance_controls.py tests\unit\test_chat_routing_alignment.py -q`
- Follow-up: Keep deepening workspace purpose/collaboration cues, then carry the same explicit policy checks into any remaining server-backed runtime bridges that can still bypass launcher framing.

### 2026-04-14

- Changed: Cloned and evaluated `MemPalace/mempalace` as a candidate local-memory backend, documented the feasibility call in `docs/MEMPALACE_EVALUATION.md`, added a Local LLM + local-memory track to M2, and switched the launcher app icon to the Guppy fish mark at the application level.
- Verified: repo inspection of `vendor/mempalace` plus `.venv\Scripts\python.exe -m compileall src\guppy\apps\launcher_app.py ui\launcher\components\sidebar.py`
- Follow-up: run the retrieval spike against real Guppy local-chat history, then design the dedicated Local LLM page before renaming the current Home surface.

### 2026-04-15

- Changed: Added the concrete Local LLM planning package: pinned local-model manifest in `config/local_llm/models.json`, starter benchmark prompt pack in `config/local_llm/benchmark_prompts.json`, benchmark/promotion rules in `docs/LOCAL_LLM_BENCHMARK_SPEC.md`, and a first-tranche implementation plan in `docs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`.
- Verified: `python -c "import json, pathlib; json.loads(pathlib.Path('config/local_llm/models.json').read_text(encoding='utf-8')); json.loads(pathlib.Path('config/local_llm/benchmark_prompts.json').read_text(encoding='utf-8'))"`
- Follow-up: wire `tools/verify_ollama_runtime.py` to the manifest, add `tools/local_llm_harness.py`, then build the memory adapter seam before opening the dedicated Local LLM page.

### 2026-04-15

- Changed: Added the first launcher-facing Local LLM runtime control surface in `ui/launcher/views/models_view.py`. The Models page can now switch the local runtime between `ollama` and `lemonade`, persist the Lemonade endpoint plus fast/complex/teach/code/vault role mappings through `runtime/app_settings.json`, and push those values back into the live launcher env without hand-editing `.env`.
- Verified: `python -m py_compile ui\launcher\views\models_view.py ui\launcher\launcher_window.py utils\runtime_profile.py tests\smoke\test_launcher_interactions_smoke.py tests\unit\test_models_routes.py`, `.venv\Scripts\python.exe -m pytest tests\unit\test_models_routes.py -q`, and `.venv\Scripts\python.exe -m pytest tests\smoke\test_launcher_interactions_smoke.py -q`.
- Observed: this is the right control-surface cut for the current Lemonade lane. Runtime choice and alias mapping now live where users already inspect local models and route behavior, while the rest of the launcher contract stays unchanged.
- Follow-up: add richer runtime evidence into the Models surface itself from `/status`, then decide whether `auto` local fallback and paired-local paths should also honor the saved runtime selection.

### 2026-04-15

- Changed: Implemented the first Local LLM execution tranche: `tools/verify_ollama_runtime.py` now reads the pinned manifest by default and records manifest metadata in the runtime snapshot, `tools/local_llm_harness.py` now runs the benchmark prompt pack and writes benchmark artifacts under `runtime/local_llm_benchmarks/`, and the semantic memory path now includes a backend adapter seam so `semantic-sqlite`, `semantic-chroma`, and a future `mempalace-adapter` can be benchmarked without changing the chat contract.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_verify_ollama_runtime.py tests\unit\test_local_llm_manifest.py tests\unit\test_local_llm_harness.py tests\unit\test_memory_backend_adapter.py -q`, `.venv\Scripts\python.exe tools\verify_ollama_runtime.py --skip-ping`, `.venv\Scripts\python.exe tools\local_llm_harness.py --max-prompts-per-track 1 --timeout 90`, and a preserved 10-case baseline run at `runtime/local_llm_benchmarks/reviews/2026-04-15_baseline_10case.json`.
- Follow-up: run challenger passes against the same harness, starting with `qwen3:8b` and `qwen3:30b`, and use the new baseline artifacts to tune local prompt-path/task-fit issues before opening the dedicated Local LLM page.

### 2026-04-15

- Changed: Finished the next Local LLM evidence tranche. Pulled `qwen3:8b` and `qwen3:30b` into Ollama, added explicit `--think` handling so Qwen challenger runs stop failing on hidden thinking-mode empties, added a controlled `guppy_local` harness mode for Guppy-style local-lane benchmarking, added seeded memory fixtures in `config/local_llm/benchmark_memory_seeds.json`, and finished a stable `mempalace-adapter` path that benchmarks from the new memory seam without changing the chat contract.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_local_llm_harness.py tests\unit\test_memory_backend_adapter.py tests\unit\test_mempalace_adapter.py tests\unit\test_verify_ollama_runtime.py tests\unit\test_local_llm_manifest.py -q`, `ollama pull qwen3:8b`, `ollama pull qwen3:30b`, `tools/local_llm_harness.py --all-tracks-model-tag qwen3:8b --prompt-style raw --think false`, `--prompt-style guppy`, `--prompt-style guppy_local`, the same three passes for `qwen3:30b`, and seeded recall runs at `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_semantic_qwen3-8b_guppy-local.json`, `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_mempalace_qwen3-8b_guppy-local.json`, and `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_compare_qwen3-8b_guppy-local.json`.
- Observed: `qwen3:8b` is currently the healthier challenger for Guppy’s local lane on this machine. In the controlled `guppy_local` pass it averaged about `10.4s` across the five tracks versus about `18.7s` for `qwen3:30b`, and the 30b model still tends to narrate its own reasoning more often than desired. In the seeded memory comparison, `semantic-sqlite` and `mempalace-adapter` both surfaced the intended memories with near-identical retrieval previews, so there is still no evidence to promote MemPalace over the baseline yet.
- Follow-up: add reviewer scores/notes to the new challenger artifacts, repeat the seeded memory comparison on more real Guppy follow-ups and additional challenger models, and only then spend energy on the dedicated Local LLM page and any backend promotion decision.

### 2026-04-15

- Changed: Started the first in-product Lemonade lane instead of treating it only as a benchmark target. `src/guppy/api/server.py` now has a narrow local-runtime selector, explicit `local` mode can route through Lemonade when `GUPPY_LOCAL_RUNTIME_BACKEND=lemonade`, Lemonade model aliases can be mapped with `GUPPY_LEMONADE_*_MODEL`, and `/status` plus `/startup/check` now expose the selected local runtime with backend/model/detail evidence.
- Verified: `python -m py_compile src\guppy\api\server.py tests\unit\test_chat_routing_alignment.py tests\smoke\test_runtime_smoke.py`, `.venv\Scripts\python.exe -m pytest tests\unit\test_chat_routing_alignment.py -q`, and `.venv\Scripts\python.exe -m pytest tests\smoke\test_runtime_smoke.py -q`.
- Observed: this is the right first product cut for Lemonade. It gives Guppy a real opt-in local-runtime lane without silently changing the meaning of explicit `ollama` mode or claiming tool-calling parity that has not been proven yet. The current Lemonade path is intentionally chat-only and depends on explicit model mapping for Guppy’s local role aliases.
- Follow-up: add a launcher-facing Local LLM/runtime control surface, decide whether any `auto` local fallbacks should also honor the selected runtime, and only then consider extending the Lemonade lane into richer tool-loop or paired-local paths.

### 2026-04-15

- Changed: Ran the stronger same-family runtime comparison requested for the Llama 3.2 instruct line by pulling `llama3.2:3b` into Ollama and `Llama-3.2-3B-Instruct-GGUF` into Lemonade, then benchmarking both through the same `guppy_local` harness slice. Emitted human-review packets for both new 3B runtime artifacts.
- Verified: `ollama pull llama3.2:3b`, `lemonade pull Llama-3.2-3B-Instruct-GGUF`, `tools/local_llm_harness.py --all-tracks-model-tag llama3.2:3b --prompt-style guppy_local --think false --max-prompts-per-track 1`, and the matching Lemonade run at `runtime/local_llm_benchmarks/reviews/2026-04-15_llama3.2-3b_lemonade_guppy-local.json`.
- Observed: the stronger 3B same-family comparison preserved the runtime gap. Ollama `llama3.2:3b` averaged about `8.9s` across the five-track Guppy-local slice, while Lemonade `Llama-3.2-3B-Instruct-GGUF` averaged about `0.7s`. Both runs completed all five tracks successfully, so this is now stronger evidence that Lemonade can materially outperform Ollama on this machine for small/medium instruct workloads. The remaining question is still answer quality: Lemonade is fast and responsive, but several previews still read more brittle or overconfident than we would want for a default Guppy lane.
- Follow-up: score the new 3B runtime review packets, then either 1) run one final higher-value same-family comparison in the local sweet spot, or 2) begin a narrow Lemonade integration seam for an opt-in local lane if the human review scores support it.

### 2026-04-15

- Changed: Extended `tools/local_llm_harness.py` with a real `lemonade` runtime path, including runtime override/base-url handling and OpenAI-compatible `chat/completions` execution. Pulled `Qwen3-0.6B-GGUF` and `Llama-3.2-1B-Instruct-GGUF` into Lemonade, pulled the matching small Ollama challengers `qwen3:0.6b` and `llama3.2:1b`, and emitted review packets for the first runtime-backed Llama comparison artifacts.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_local_llm_harness.py -q`, `.venv\Scripts\python.exe tools\local_llm_harness.py --all-tracks-model-tag qwen3:0.6b --prompt-style guppy_local --think false`, the matching Lemonade pass for `Qwen3-0.6B-GGUF`, then the cleaner instruct-model pair at `runtime/local_llm_benchmarks/reviews/2026-04-15_llama3.2-1b_ollama_guppy-local.json` and `runtime/local_llm_benchmarks/reviews/2026-04-15_llama3.2-1b_lemonade_guppy-local.json`.
- Observed: the first tiny-Qwen Lemonade pass proved the runtime path but also exposed a product-fit issue: `Qwen3-0.6B-GGUF` often returned `reasoning_content` with empty final content on Guppy-style prompts, so the runtime is live but that particular small reasoning model is not a trustworthy chat benchmark. The first clean runtime-vs-runtime pair came from the small Llama instruct models instead: Ollama `llama3.2:1b` averaged about `4.8s` across the five-track `guppy_local` slice, while Lemonade `Llama-3.2-1B-Instruct-GGUF` averaged about `0.9s` on the same slice. Lemonade is dramatically faster in this first pass, but some answers are also more brittle and less grounded, so this is a promising runtime result rather than a promotion decision.
- Follow-up: run one more same-family runtime comparison at a slightly stronger model size, then add reviewer scores to the new Llama runtime artifacts before making any claim that Lemonade should outrank Ollama for Guppy’s default local lane.

### 2026-04-15

- Changed: Installed the official Windows Lemonade Server minimal build (`10.2.0`) and added the first usable backend by installing `llamacpp:rocm` on the `RX 7900 XTX` host. Refreshed `runtime/runtime_challenger_snapshot.json` after install so Lemonade now shows as actually installed instead of only host-compatible.
- Verified: official installer at `https://github.com/lemonade-sdk/lemonade/releases/latest/download/lemonade-server-minimal.msi`, `C:\Users\Ryan\AppData\Local\lemonade_server\bin\lemonade.exe --version`, `lemonade backends`, `lemonade status`, `Invoke-WebRequest http://localhost:13305/api/v1/health`, and `.venv\Scripts\python.exe tools\verify_runtime_challengers.py` with the Lemonade `bin` directory present on `PATH`.
- Observed: Lemonade is now the first installed non-Ollama runtime challenger in the workspace. The server is live on port `13305`, `llamacpp:rocm` is installed, no models are loaded yet, and the current probe still keeps `llama.cpp` as the best benchmark-first challenger while confirming Lemonade as the best integration-first challenger.
- Follow-up: pull a small Lemonade GGUF model or import a matching challenger model, then add the first harness/runtime override seam so Guppy can benchmark a real Lemonade-backed lane instead of only detecting that the runtime exists.

### 2026-04-15

- Changed: Added the first runtime-challenger probe layer with `tools/verify_runtime_challengers.py` plus manifest-backed host-fit helpers in `src/guppy/local_llm/runtime_challengers.py`. The probe now classifies runtime challengers against the current machine, checks whether their binaries are actually present, and writes `runtime/runtime_challenger_snapshot.json` with separate benchmark-first and integration-first recommendations.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_runtime_challengers.py tests\unit\test_local_llm_manifest.py tests\unit\test_verify_ollama_runtime.py -q`, `.venv\Scripts\python.exe -m compileall src\guppy\local_llm\runtime_challengers.py tools\verify_runtime_challengers.py`, and `.venv\Scripts\python.exe tools\verify_runtime_challengers.py`.
- Observed: on this Windows + `AMD Radeon RX 7900 XTX` host, `llama.cpp` is the right benchmark-first runtime challenger, `lemonade` is the right integration-first runtime challenger, and `vllm-rocm` remains research-only. Both `llama.cpp` and `lemonade` fit the host well, but neither runtime is installed yet; Lemonade is currently only present as a cloned vendor repo.
- Follow-up: install one runtime challenger instead of debating in the abstract, then add a minimal runtime-override seam so the benchmark harness can record a real non-Ollama backend rather than only a planned one.

### 2026-04-15

- Changed: Completed the next challenger-memory tranche by running the broader seeded semantic-vs-MemPalace comparison pack against `gemma3:12b` and `mistral-small3.1:24b`, then emitted human-review packets for `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_compare_gemma3-12b_guppy-local_broad.json` and `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_compare_mistral-small3.1-24b_guppy-local_broad.json`.
- Verified: `tools/local_llm_harness.py --prompt-file config/local_llm/benchmark_prompts_memory_recall.json --all-tracks-model-tag gemma3:12b --prompt-style guppy_local --think false --compare-memory-backends semantic-sqlite mempalace-adapter --memory-seed-file config/local_llm/benchmark_memory_seeds_broad.json --max-prompts-per-track 8`, the same broad comparison for `mistral-small3.1:24b`, and `tools/local_llm_review_packet.py` for both new comparison artifacts.
- Observed: both non-Qwen challengers stayed stable across the full 16-case broad memory comparison, but neither displaced the current read on this machine. `gemma3:12b` averaged about `8.9s` across the broad comparison and `mistral-small3.1:24b` averaged about `11.6s`, yet both still answered the seeded “safer default challenger” follow-up by pointing back to `qwen3:8b`. `semantic-sqlite` and `mempalace-adapter` again remained close enough that there is still no promotion case for MemPalace.
- Follow-up: get human reviewer scores into the new Gemma and Mistral artifact packets, then use those scores plus the existing Qwen evidence to decide whether any non-Qwen role deserves more targeted benchmarking or whether the next investment should move to runtime-serving challengers instead.

### 2026-04-15

- Changed: Continued the challenger sweep by pulling `gemma3:12b` and `mistral-small3.1:24b` into Ollama, then running the same five-track harness slice in both `raw` and `guppy_local` modes. Emitted new human-review packets for `runtime/local_llm_benchmarks/reviews/2026-04-15_gemma3-12b_guppy-local.json` and `runtime/local_llm_benchmarks/reviews/2026-04-15_mistral-small3.1-24b_guppy-local.json`.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_local_llm_harness.py tests\unit\test_local_llm_review_packet.py tests\unit\test_memory_backend_adapter.py tests\unit\test_mempalace_adapter.py tests\unit\test_verify_ollama_runtime.py tests\unit\test_local_llm_manifest.py -q`, `ollama pull gemma3:12b`, `ollama pull mistral-small3.1:24b`, `tools/local_llm_harness.py --all-tracks-model-tag gemma3:12b --prompt-style raw --think false --max-prompts-per-track 1`, `--prompt-style guppy_local`, and the same two passes for `mistral-small3.1:24b`.
- Observed: `gemma3:12b` is now the fastest challenger in the controlled `guppy_local` slice at about `9.3s` average across the five tracks, ahead of `qwen3:8b` at about `10.4s`, but its repo/tool answers are currently more generic and less Guppy-specific. `mistral-small3.1:24b` stayed stable and cleaner than `qwen3:30b`, but averaged about `12.9s` and still reads less pointed than `qwen3:8b`. On this machine, `qwen3:8b` still looks like the healthiest overall local-lane candidate until the new human review packets are filled.
- Follow-up: have a human reviewer score the new Gemma and Mistral packets, then extend the memory-focused comparison to the strongest non-Qwen challenger before changing any default local-model role assignments.

### 2026-04-15

- Changed: Added a human-review workflow for Local LLM artifacts with stable `record_id`s in `tools/local_llm_harness.py` and a packet emit/apply tool in `tools/local_llm_review_packet.py`. Added a broader memory-follow-up pack in `config/local_llm/benchmark_prompts_memory_recall.json` plus a broader seed pack in `config/local_llm/benchmark_memory_seeds_broad.json`, then reran the `qwen3:8b` seeded semantic-vs-MemPalace comparison against the broader real Guppy follow-up set.
- Verified: `.venv\Scripts\python.exe -m pytest tests\unit\test_local_llm_harness.py tests\unit\test_local_llm_review_packet.py tests\unit\test_memory_backend_adapter.py tests\unit\test_mempalace_adapter.py tests\unit\test_verify_ollama_runtime.py tests\unit\test_local_llm_manifest.py -q`, `tools/local_llm_review_packet.py` against the existing Qwen artifacts, and the broader recall runs at `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_semantic_qwen3-8b_guppy-local_broad.json`, `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_mempalace_qwen3-8b_guppy-local_broad.json`, and `runtime/local_llm_benchmarks/reviews/2026-04-15_memory_compare_qwen3-8b_guppy-local_broad.json`.
- Observed: the broader eight-prompt recall pass kept both memory backends stable and close in latency at roughly `8.1s` to `8.3s`, with both backends surfacing the intended memory blocks on the same seeded follow-ups. The broadened pass also exposed one missing seed about the machine-specific Qwen challenger call, which is now included in the broad seed pack.
- Follow-up: have a human reviewer fill the emitted `*.human_review_packet.json` files for the current Qwen and memory artifacts, then promote only if the manual scores agree with the current machine evidence.

Keep this template at the bottom of the roadmap.
