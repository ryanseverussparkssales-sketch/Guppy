# Daily Workflow

Last updated: April 12, 2026

This runbook is designed for the current Guppy build and can be executed today.

## Morning Boot (5 to 10 minutes)

1. Start environment and launcher.
  - Command: python guppy_launcher.py
2. Run pilot gate quick health.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
3. Run triage decision canary (fast confidence check).
  - Command: python -m pytest -q tests/test_pilot_exit_decision_canary.py
4. Run fault-injection triage canary (alerts + regression pipeline check).
  - Command: python tools/run_triage_fault_canary.py
3. If gate returns NO_GO, run targeted verifiers to isolate fault.
  - Command: python tools/verify_ollama_runtime.py --skip-ping
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - Command: python tools/verify_provider_runtime.py

Handled by current build:

1. Launcher startup and status rail.
2. Automated pilot gate output at runtime/pilot_exit_report.json.
3. Health snapshots for model, provider, and logging systems.

## Workday Loop

1. Use Assistant tab for default interaction and quick tasks.
2. Use Models tab to confirm active model choices.
3. Use Voices tab and existing voice bindings for current profile.
4. Use reminders and daemon-backed nudges for follow-through.
5. For coding sessions, use code mode and tool-assisted checks.

Handled by current build:

1. Mode routing (local, local_paired, code, vault).
2. Voice runtime with interruption behavior and fallback chain.
3. Runtime telemetry, scorecard, and logging events.
4. Tool schema enforcement and targeted test/lint/typecheck tooling.

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
4. Record blockers for next day in roadmap handoff section.

Handled by current build:

1. Daily report generation in daemon workflows.
2. Settings validate/reload/save flows.
3. Repeatable GO/NO_GO pilot reporting.

## Recovery Flow (When Something Breaks)

1. Run pilot gate report first.
2. If models fail, rebuild model/runtime state.
  - Command: python tools/verify_ollama_runtime.py
3. If logs fail freshness checks, run logging probe and inspect snapshots.
  - Command: python tools/verify_logging_health.py --emit-probe --require-fresh-core
4. If provider path fails, fall back to local mode and continue.

Handled by current build:

1. Repair-oriented diagnostics from verifier scripts.
2. Local-first operation even when optional provider keys are missing.

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
3. merlin-code (local 14B): batch code review notes and test suggestion drafts.
4. Haiku (cloud low-cost): final concise morning brief, route-quality spot checks, UX copy tightening.
5. guppy and merlin (local 32B): reserve for one scheduled deep synthesis run, not continuous loops.

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
  - Command: python tools/idle_agent_worker.py --add-title "Overnight code review" --add-target merlin-code --add-prompt "Review changed files and list likely risks." --add-priority 1
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

1. Guided builder UI for persona/model/voice instead of JSON-first management.
2. Visual precedence inspector and route simulation in launcher.
3. Voice import wizard with richer validation and preview controls.
4. Installer/update lifecycle for broader Windows rollout.

## Remote Beta EXE Safety Check

Run this before shipping any remote beta executable.

1. Enable restricted beta profile in the launch environment.
  - Env: GUPPY_BETA_RESTRICTED_MODE=1
2. Validate restricted tool allowlist policy.
  - Command: python tools/verify_beta_package_policy.py
3. Confirm pilot gate status for beta window.
  - Command: python tools/pilot_exit_check.py --allow-limited-go
4. Run one-command beta release dry-run.
  - Command: python tools/beta_release_dry_run.py

Artifacts:

1. Policy report: runtime/beta_policy_report.json
2. Pilot report: runtime/pilot_exit_report.json
3. Dry-run report: runtime/beta_release_dry_run_report.json
