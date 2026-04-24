# Daily Workflow

Last updated: April 16, 2026

This runbook is designed for the current Guppy build and can be executed today.

## Acceptance Monitoring Snapshot (Run After Major Changes)

Run this sequence after any base-functionality or auth/security change to produce a signed evidence snapshot before marking the work done.

### 1. Security and auth tests (must be zero warnings)
```
python -m pytest tests/unit/test_security_hardening.py tests/smoke/test_launcher_interactions_smoke.py -W error::DeprecationWarning
```
Expected: all tests pass, zero DeprecationWarnings.

### 2. Runtime smoke
```
python -m pytest tests/smoke/test_runtime_smoke.py -v
```
Expected: smoke suite passes.

### 3. Guard suite (all five checks)
```
python tools/check_architecture_boundaries.py
python tools/check_new_module_line_cap.py
python tools/check_wrapper_integrity.py
python tools/check_core_surface_integrity.py
python tools/check_doc_ownership.py
```
Expected: all five print "passed".

### 4. Telemetry freshness check
```
python tools/verify_logging_health.py --emit-probe --require-fresh-core
```
Watch for:
- `integration_events.jsonl` STALE — expected until API runs with heartbeat; not a blocker offline.
- All core logs (`session_events`, `router_scorecard`, `agent_performance`) must be FRESH.

### 5. Builder regression sweep
```bash
python -m pytest tests/unit/test_personalization_resolution.py tests/unit/test_models_routes.py tests/unit/test_voices_view_validation.py tests/unit/test_offhours_builder.py -q
```
Expected: builder round-trip, route explainability, voice bindings, and off-hours queue coverage all pass.

### SLO Pass Criteria
| Signal | Target |
|---|---|
| Security tests | 0 failures, 0 DeprecationWarnings |
| Runtime smoke | 4/4 OK |
| Guard suite | all 5 passed |
| Core log freshness | session_events, router_scorecard, agent_performance = FRESH |
| 401/403 rate (live) | No new auth rejections in launcher_events.jsonl after restart |
| Crash-loop indicator | No agent exits < 30s in hub.log for 10 min post-start |
| Startup budget | No startup_phase_over_budget events in launcher_events.jsonl |

### Last Evidence Snapshot (April 13, 2026)
- Security: 37 passed, 0 warnings (30 hardening + 7 launcher interactions)
- Runtime smoke: 4/4 OK
- Guard suite: all 5 passed
- Core telemetry: session_events FRESH 4524KB, hub_patterns FRESH 40KB, router_scorecard FRESH 3813KB, agent_performance FRESH 62KB
- integration_events: STALE 1KB (expected — offline; heartbeat fires on live API startup)
- SQLite operational_events: 113787 rows
- datetime.utcnow deprecation: resolved in API auth, hub operator, and smoke coverage.

## Morning Boot (5 to 10 minutes)

1. Start environment and launcher.
  - Command: python src/guppy/cli/launch.py launcher
  - Note: launcher bootstrap starts `guppy_api.py` (:8081) and `guppy_hub.py` asynchronously when they are not already running.
2. Run pilot gate quick health.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
3. Run triage decision canary (fast confidence check).
  - Command: python -m pytest -q tests/test_pilot_exit_decision_canary.py
4. Run fault-injection triage canary (alerts + regression pipeline check).
  - Command: python tools/run_triage_fault_canary.py
5. If gate returns NO_GO, run targeted verifiers to isolate fault.
  - Command: python tools/verify_ollama_runtime.py --skip-ping
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - Command: python tools/verify_provider_runtime.py

Handled by current build:

1. Launcher startup and status rail.
2. Automated pilot gate output at runtime/pilot_exit_report.json.
3. Health snapshots for model, provider, and logging systems.
4. App Mgmt `WORKFLOW LOOPS` can queue Morning Boot, acceptance, midday, evening, and overnight commands in the embedded terminal.

## Workday Loop

1. Use Home for default interaction and quick tasks.
2. Use App Mgmt settings when persona tone, scope, or prompt preview needs to change.
3. Use Models to confirm route strategy and sample-query explainability.
4. Use Voices to confirm current bindings, imports, and preview behavior.
5. Use Instances to switch between `guppy-primary` and any configured collaborator such as `builder-collab`.
6. Use Agent Tools for power-user tool work, and use App Mgmt for recovery, settings, workflow loops, automation testing, and operator workflows.
7. Use reminders and daemon-backed nudges for follow-through.
8. For coding sessions, use code mode and tool-assisted checks.

Handled by current build:

1. Mode routing (local, local_paired, code, vault).
2. Voice runtime with interruption behavior and fallback chain.
3. Runtime telemetry, scorecard, and logging events.
4. Tool schema enforcement and targeted test/lint/typecheck tooling.

## Builder Validation Check (3 minutes)

Run this after changing persona/model/voice behavior or before a pilot candidate handoff.

1. Save or reload the target persona in App Mgmt settings and confirm the prompt preview updates.
2. Use Models with a sample request to confirm the route explainer still matches the expected task type and fallback.
3. Use Voices to confirm the default or selected binding can preview successfully.
4. If the change touched automation, use App Mgmt `AUTOMATION TEST` to queue a dry-run builder task and confirm it lands in `runtime/offhours_results/` for approval.

## Automation Test Path (2 minutes)

Use this when the question is "how do I test automation?" on the current build.

1. Launch the guided tester entrypoint.
  - Command: `bin\launch_automation_test.bat`
  - Alternate: `python src/guppy/cli/launch.py launcher --start automation-test`
2. In the launcher, go to App Mgmt `AUTOMATION TEST`.
3. Follow the guided order:
  - `VERIFY NOW`
  - `SWITCH TO BUILDER WORKSPACE`
  - `QUEUE DRY RUN`
  - `OPEN LATEST REPORT`
  - `APPROVE LATEST STAGED TASK`
  - `RUN VALIDATION`
4. Use Agent Tools only when you already know you need the raw builder queue surface.

## Midday Stability Check (2 minutes)

1. Re-run logging health check if behavior degrades.
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
2. Re-run ollama verifier if model responses degrade.
  - Command: python tools/verify_ollama_runtime.py --prompt ok

Handled by current build:

1. Freshness and mirror checks for core logs.
2. Live model readiness checks including ping and residency output.

## Evening Close (5 minutes)

1. Trigger or confirm daily report output exists in runtime/daily_reports.
2. Save any key persona/provider/voice changes from launcher settings.
3. Run one final pilot gate before stopping active work.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
4. Record blockers for next day in the handoff section of `docs/PROJECT_BRIEF.md`.

Handled by current build:

1. Daily report generation in daemon workflows.
2. Settings validate/reload/save flows.
3. Repeatable GO/NO_GO pilot reporting.

## Recovery Flow (When Something Breaks)

1. Run pilot gate report first.
2. If API or hub are not responding, use App Mgmt `WINDOWS INSTALL / UPDATE / DIAGNOSTICS` recovery actions first.
  - The launcher will call /repair (with token auth) or fall back to direct file-level diagnostics.
  - Repair token is auto-generated at API startup and stored in OS keyring when available, with runtime/repair_token.txt as fallback.
  - Repair-token refresh is localhost-only and now also requires valid bearer auth; the launcher handles that re-sync automatically.
3. If models fail, rebuild model/runtime state.
  - Command: python tools/verify_ollama_runtime.py
4. If logs fail freshness checks, run logging probe and inspect snapshots.
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
5. If provider path fails, fall back to local mode and continue.

Handled by current build:

1. Launcher auto-restarts API and hub if they are not running on open.
2. Repair-oriented diagnostics from verifier scripts.
3. Local-first operation even when optional provider keys are missing.
4. Direct fallback recovery (warmup, audit, snapshot) when API is unreachable.

## Overnight Low-Compute Plan

Use this schedule when you want useful progress with lower cost and lower interactive load.

1. Start with a baseline gate and snapshots.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
2. Run lightweight recurring checks overnight (for example every 2-3 hours).
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - Command: python tools/verify_ollama_runtime.py --skip-ping
3. Run one full model ping once overnight or at morning handoff.
  - Command: python tools/verify_ollama_runtime.py --prompt ok
4. Optional single-command overnight orchestration.
  - Command: python tools/run_overnight_low_compute.py
  - Example: python tools/run_overnight_low_compute.py --cycles 3 --interval-minutes 180
5. Generate nightly triage/regression summary.
  - Command: python tools/generate_triage_summary.py

Recommended model/task mapping for cheap overnight work:

1. guppy-fast (local 7B): routine summaries, reminders triage, carry-forward task drafts.
2. vault-scraper (local 7B): structured extraction and metadata cleanup jobs.
3. guppy-code (local 14B): batch code review notes and test suggestion drafts.
4. Haiku (cloud low-cost): final concise morning brief, route-quality spot checks, UX copy tightening.
5. guppy and guppy-teach (local 32B): reserve for one scheduled deep synthesis run, not continuous loops.

Overnight completion criteria:

1. Last pilot gate is GO or LIMITED_GO.
2. Core logs are fresh at final check.
3. Model roster and num_ctx checks remain healthy.
4. Morning summary includes actionable carry-forward items.

## Idle Agent Work Queue (Off-Hours)

Use the idle worker when you want queued tasks to run only when agents are not actively in use.

1. Seed starter tasks (optional).
  - Command: python tools/idle_agent_worker.py --seed-defaults --list
2. Add a task to queue.
  - Command: python tools/idle_agent_worker.py --add-title "Overnight code review" --add-target guppy-code --add-prompt "Review changed files and list likely risks." --add-priority 1
3. Start continuous idle processing.
  - Command: python tools/idle_agent_worker.py --poll-seconds 60 --idle-seconds 180
  - Optional hardening: python tools/idle_agent_worker.py --poll-seconds 60 --idle-seconds 180 --stale-running-seconds 900
4. Run one cycle for quick validation.
  - Command: python tools/idle_agent_worker.py --once
5. Wire unattended autostart (Task Scheduler when allowed, Startup fallback otherwise).
  - Command: powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\setup_idle_worker_task.ps1 -RunNow

Outputs:

1. Queue file: runtime/offhours_task_queue.json
2. Result stream: runtime/offhours_task_results.jsonl
3. Per-task result files: runtime/offhours_results/
4. Worker state heartbeat: runtime/offhours_task_worker_state.json
5. Nightly triage summary: runtime/nightly_triage_summary.md
6. Triage regression state: runtime/triage_regression_state.json

## Seed Vault Backup (USB Now, NAS Later)

Use this to preserve both program state and knowledge memory for portability and disaster recovery.

1. Create USB snapshot backup (short-term path).
  - Command: python tools/backup_seed_vault.py --destination "E:\\GuppyBackups" --retain 10
2. Create NAS snapshot backup (future path, same command shape).
  - Command: python tools/backup_seed_vault.py --destination "\\\\NAS01\\assistant\\guppy" --retain 30
3. Optional batch wrapper.
  - Command: bin\\backup_seed_vault.bat --destination "E:\\GuppyBackups" --retain 10

Outputs:

1. Snapshot root: <destination>\\guppy_seed_vault\\snapshots\\<UTC timestamp>\\
2. Snapshot data: <destination>\\guppy_seed_vault\\snapshots\\<UTC timestamp>\\data\\
3. Integrity manifest: <destination>\\guppy_seed_vault\\snapshots\\<UTC timestamp>\\manifest.json
4. Latest pointer: <destination>\\guppy_seed_vault\\latest.json

## What Still Requires Build Work

1. Builder polish: stronger guardrails, empty states, and broader device validation.
2. Guided in-app evidence summaries on top of the new App Mgmt workflow shortcuts.
3. Voice import validation and preview behavior across more machines and engines.
4. Installer/update lifecycle for broader Windows rollout.

## Remote Beta EXE Safety Check

Run this before shipping any remote beta executable.

1. Enable restricted beta profile in the launch environment.
  - Env: GUPPY_BETA_RESTRICTED_MODE=1
2. Validate restricted tool allowlist policy.
  - Command: python tools/verify_beta_package_policy.py
3. Confirm pilot gate status for beta window.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
4. Run the canonical release preflight, then emit the beta reviewer bundle.
  - Commands: python tools/dev_workflow.py release-check
  - Then: python tools/beta_release_dry_run.py
  - Launcher path: App Mgmt `RELEASE DRY RUN` runs the same sequence.

Artifacts:

1. Policy report: runtime/beta_policy_report.json
2. Pilot report: runtime/pilot_exit_report.json
3. Dry-run report: runtime/beta_release_dry_run_report.json
