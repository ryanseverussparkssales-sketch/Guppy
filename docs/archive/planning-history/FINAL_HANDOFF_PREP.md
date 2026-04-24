# Final Handoff Prep

Date: April 12, 2026

This is the operational handoff checklist for the current build state, including remote beta EXE restricted-access readiness.

## 1) Current Readiness Snapshot

1. Pilot gate currently reports NO_GO in latest runtime snapshot due to local model fleet ping timeout path.
2. Core hardening and triage infrastructure are in place.
3. Remote beta restricted policy is now implemented in runtime tool execution.

## 2) Remote Beta Restricted Access (Implemented)

1. Enable restricted mode:
  - Set environment variable `GUPPY_BETA_RESTRICTED_MODE=1`
2. Policy source:
  - `config/beta_tool_allowlist.txt`
3. Runtime enforcement point:
  - `guppy_core/tool_runner.py` in `run_tool(...)`
4. Verification command:
  - `python tools/verify_beta_package_policy.py`
5. Verification artifact:
  - `runtime/beta_policy_report.json`

## 3) Packaging Checklist for Beta EXE

1. Build one-folder executable distribution.
2. Include required runtime policy/config files:
  - `config/beta_tool_allowlist.txt`
  - any beta profile env file used by launcher
3. Exclude source, tests, and internal-only tooling from tester bundle unless explicitly needed.
4. Validate restricted policy report before release.
5. Validate pilot gate status before release window.
6. Run one-command release dry-run and archive report.
  - `python tools/beta_release_dry_run.py`

## 4) Suggested Release Gates (Beta Drop)

1. `python tools/verify_beta_package_policy.py` returns PASS.
2. `python tools/pilot_exit_check.py --allow-limited-go` returns GO or LIMITED_GO.
3. Logging health check is READY.
4. Auth scope test for tester token passes in API path.
5. `python tools/beta_release_dry_run.py` returns PASS.

## 5) Open Risks

1. Local model ping timeout still blocks full GO status in current snapshot.
2. Legacy `guppy_ui.py` overlap remains a maintenance risk.
3. Shared memory catalog is planned and partially scaffolded, not fully productized in all surfaces.

## 6) Next Work Packet

1. Stabilize model ping timeout path in verifier and startup warm path.
2. Add restricted-profile API token scope checks into automated gate script.
3. Add beta packaging dry-run script that asserts required files and env settings.
